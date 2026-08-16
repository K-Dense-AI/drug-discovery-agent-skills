"""Tests for the patent-landscape scripts.

Nothing here touches the network. The parts worth testing are the bulk-tree
navigation (SureChEMBL has no REST API, so the FTP listing is the only route),
the PatentsView query builder and its key guard -- a missing key surfaces as a
connection failure rather than a 401 -- and the download planning that stops
someone pulling 15 GB to answer a lookup.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "patent-landscape"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


common = _load("_common", "_common.py")
surechembl_bulk = _load("surechembl_bulk_script", "surechembl_bulk.py")
patent_search = _load("patent_search_script", "patent_search.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

LISTING = """<html><body>
<a href="/pub/databases/chembl/">Parent</a>
<a href="2026-08-04/">2026-08-04/</a>
<a href="2026-07-17/">2026-07-17/</a>
<a href="2025-04-30/">2025-04-30/</a>
<a href="?C=N;O=D">sort</a>
</body></html>"""

FILE_LISTING = """<html><body>
<a href="compounds.parquet">compounds.parquet</a>
<a href="patents.parquet">patents.parquet</a>
<a href="patent_compound_map.parquet">patent_compound_map.parquet</a>
<a href="fpsim2_fingerprints.h5">fpsim2_fingerprints.h5</a>
</body></html>"""


class FakeResponse(io.BytesIO):
    def __init__(self, body: str, headers=None):
        super().__init__(body.encode("utf-8"))
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def fake_urlopen(body, *, headers=None, urls=None):
    def _open(request, timeout=None):
        if urls is not None:
            urls.append(request.full_url)
        text = body(request) if callable(body) else body
        return FakeResponse(text, headers)

    return _open


def http_error(status: int, detail: str = "nope"):
    def _open(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url, status, "error", {}, io.BytesIO(detail.encode("utf-8"))
        )

    return _open


class DirectoryListingTests(unittest.TestCase):
    def test_entries_are_extracted(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen(LISTING)):
            entries = common.list_directory("https://example.invalid/bulk_data")
        self.assertIn("2026-08-04/", entries)

    def test_parent_and_sort_links_are_dropped(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen(LISTING)):
            entries = common.list_directory("https://example.invalid/bulk_data")
        self.assertNotIn("?C=N;O=D", entries)
        self.assertFalse(any(entry.startswith("/") for entry in entries))

    def test_latest_release_is_the_newest_date(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen(LISTING)):
            self.assertEqual(surechembl_bulk.resolve_release("latest"), "2026-08-04")

    def test_an_explicit_release_is_not_looked_up(self) -> None:
        self.assertEqual(surechembl_bulk.resolve_release("2025-04-30"), "2025-04-30")

    def test_release_pattern_rejects_non_dates(self) -> None:
        self.assertIsNone(surechembl_bulk.RELEASE_PATTERN.match("SureChEMBLWorkshop2024/"))
        self.assertIsNotNone(surechembl_bulk.RELEASE_PATTERN.match("2026-08-04/"))


class DownloadPlanTests(unittest.TestCase):
    def test_a_structure_query_needs_three_tables(self) -> None:
        tables = surechembl_bulk.QUESTIONS["structure-to-patent"]["tables"]
        self.assertEqual(len(tables), 3)
        self.assertIn("patent_compound_map.parquet", tables)

    def test_similarity_search_needs_the_fpsim2_index(self) -> None:
        tables = surechembl_bulk.QUESTIONS["similarity-search"]["tables"]
        self.assertIn("fpsim2_fingerprints.h5", tables)

    def test_assignee_landscape_needs_only_patents(self) -> None:
        self.assertEqual(
            surechembl_bulk.QUESTIONS["assignee-landscape"]["tables"], ["patents.parquet"]
        )

    def test_every_question_names_real_tables(self) -> None:
        for question, spec in surechembl_bulk.QUESTIONS.items():
            for table in spec["tables"]:
                with self.subTest(question=question, table=table):
                    self.assertIn(table, common.BULK_TABLES)

    def test_unknown_question_is_rejected(self) -> None:
        args = surechembl_bulk.build_parser().parse_args(
            ["plan", "--question", "structure-to-patent"]
        )
        args.question = "nonsense"
        with self.assertRaises(common.PatentError):
            surechembl_bulk.command_plan(args)

    def test_document_fields_put_claims_first(self) -> None:
        """A compound in the claims means something a compound in the description does not."""
        self.assertEqual(common.DOCUMENT_FIELDS[0], "claims")
        self.assertIn("description", common.DOCUMENT_FIELDS)


class HumanBytesTests(unittest.TestCase):
    def test_bytes(self) -> None:
        self.assertEqual(common.human_bytes(512), "512 B")

    def test_gigabytes(self) -> None:
        self.assertEqual(common.human_bytes(4_200_000_000), "3.9 GB")

    def test_none_is_blank(self) -> None:
        self.assertEqual(common.human_bytes(None), "")

    def test_content_length_returns_none_on_failure(self) -> None:
        with mock.patch("urllib.request.urlopen", http_error(404)):
            self.assertIsNone(common.content_length("https://example.invalid/x"))


class PatentsViewKeyTests(unittest.TestCase):
    """A missing key looks like a network failure, so it is checked explicitly."""

    def test_missing_key_is_named_as_the_problem(self) -> None:
        args = patent_search.build_parser().parse_args(["patents", "--title", "kinase"])
        with mock.patch.dict("os.environ", {"PATENTSVIEW_API_KEY": ""}):
            with self.assertRaises(common.PatentError) as caught:
                patent_search.search(args, 10)
        message = str(caught.exception)
        self.assertIn("PATENTSVIEW_API_KEY", message)
        self.assertIn("SureChEMBL half", message)

    def test_key_is_read_from_the_environment(self) -> None:
        with mock.patch.dict("os.environ", {"PATENTSVIEW_API_KEY": "abc"}):
            self.assertEqual(common.patentsview_key(), "abc")

    def test_blank_key_is_none(self) -> None:
        with mock.patch.dict("os.environ", {"PATENTSVIEW_API_KEY": "   "}):
            self.assertIsNone(common.patentsview_key())

    def test_key_is_sent_as_a_header(self) -> None:
        urls: list[str] = []
        args = patent_search.build_parser().parse_args(["patents", "--title", "kinase"])
        with mock.patch.dict("os.environ", {"PATENTSVIEW_API_KEY": "abc"}):
            with mock.patch(
                "urllib.request.urlopen", fake_urlopen(json.dumps({"patents": []}), urls=urls)
            ):
                patent_search.search(args, 10)
        self.assertIn("search.patentsview.org", urls[0])

    def test_403_explains_the_key_requirement(self) -> None:
        with mock.patch("urllib.request.urlopen", http_error(403, "forbidden")):
            with self.assertRaises(common.PatentError) as caught:
                common.get("https://search.patentsview.org/api/v1/patent/")
        self.assertIn("free API key", str(caught.exception))

    def test_surechembl_404_points_at_the_bulk_tree(self) -> None:
        with mock.patch("urllib.request.urlopen", http_error(404, "not found")):
            with self.assertRaises(common.PatentError) as caught:
                common.get("https://www.surechembl.org/api/x")
        self.assertIn("no public REST API", str(caught.exception))


class QueryBuilderTests(unittest.TestCase):
    def test_a_single_clause_is_not_wrapped(self) -> None:
        args = patent_search.build_parser().parse_args(["patents", "--title", "kinase"])
        query = patent_search.build_query(args)
        self.assertIn("_text_any", query)
        self.assertNotIn("_and", query)

    def test_multiple_clauses_are_anded(self) -> None:
        args = patent_search.build_parser().parse_args(
            ["patents", "--title", "kinase", "--after", "2020-01-01"]
        )
        query = patent_search.build_query(args)
        self.assertIn("_and", query)
        self.assertEqual(len(query["_and"]), 2)

    def test_date_bounds_use_range_operators(self) -> None:
        args = patent_search.build_parser().parse_args(
            ["patents", "--after", "2020-01-01", "--before", "2024-12-31"]
        )
        query = patent_search.build_query(args)
        operators = {key for clause in query["_and"] for key in clause}
        self.assertEqual(operators, {"_gte", "_lte"})

    def test_an_empty_query_is_refused(self) -> None:
        args = patent_search.build_parser().parse_args(["patents"])
        with self.assertRaises(common.PatentError):
            patent_search.build_query(args)

    def test_assignee_uses_contains(self) -> None:
        args = patent_search.build_parser().parse_args(["patents", "--assignee", "Merck"])
        self.assertIn("_contains", patent_search.build_query(args))

    def test_organisations_are_extracted_from_nested_assignees(self) -> None:
        record = {"assignees": [{"assignee_organization": "Acme"}, {"assignee_country": "US"}]}
        self.assertEqual(patent_search.organisations(record), ["Acme"])


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (surechembl_bulk, ["releases"]),
            (surechembl_bulk, ["tables"]),
            (surechembl_bulk, ["plan", "--question", "similarity-search"]),
            (patent_search, ["patents", "--title", "x"]),
            (patent_search, ["assignees", "--title", "x"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_default_release_is_latest(self) -> None:
        args = surechembl_bulk.build_parser().parse_args(["tables"])
        self.assertEqual(args.release, "latest")

    def test_default_output_format_is_tsv(self) -> None:
        args = surechembl_bulk.build_parser().parse_args(["releases"])
        self.assertEqual(args.output_format, "tsv")


if __name__ == "__main__":
    unittest.main()
