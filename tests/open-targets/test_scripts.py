"""Tests for the Open Targets client scripts.

Nothing here touches the network. The parts worth testing are the ones where
the Platform API's behaviour is surprising and the script exists to absorb it:
GraphQL errors arriving with HTTP 200, two different pagination models, and
datasource restriction being a weighting operation rather than a filter.
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

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "open-targets"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# Registered under its own name so the scripts' `from _common import ...`
# resolves to this same module object -- loading it twice would give two
# distinct `OpenTargetsError` classes and make `assertRaises` silently miss.
common = _load("_common", "_common.py")
ot_query = _load("ot_query_script", "ot_query.py")
ot_associations = _load("ot_associations_script", "ot_associations.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


class FakeResponse(io.BytesIO):
    """Minimal stand-in for what `urlopen` returns as a context manager."""

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def fake_urlopen(payload, *, calls=None):
    def _open(request, timeout=None):
        if calls is not None:
            calls.append(json.loads(request.data.decode("utf-8")))
        body = payload(request) if callable(payload) else payload
        return FakeResponse(json.dumps(body).encode("utf-8"))

    return _open


class TransportTests(unittest.TestCase):
    def test_graphql_errors_arrive_with_http_200_and_still_raise(self) -> None:
        """The failure mode this client exists to prevent."""
        payload = {"errors": [{"message": "Cannot query field 'knownDrugs' on type 'Target'."}]}
        with mock.patch("urllib.request.urlopen", fake_urlopen(payload)):
            with self.assertRaises(common.OpenTargetsError) as caught:
                common.post("{ target { knownDrugs } }")
        self.assertIn("knownDrugs", str(caught.exception))

    def test_partial_data_alongside_errors_still_raises(self) -> None:
        payload = {"data": {"target": {"id": "ENSG1"}}, "errors": [{"message": "boom"}]}
        with mock.patch("urllib.request.urlopen", fake_urlopen(payload)):
            with self.assertRaises(common.OpenTargetsError):
                common.post("{ target { id } }")

    def test_data_is_returned_unwrapped(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen({"data": {"meta": {"name": "x"}}})):
            self.assertEqual(common.post("{ meta { name } }"), {"meta": {"name": "x"}})

    def test_variables_are_sent(self) -> None:
        calls: list[dict] = []
        with mock.patch("urllib.request.urlopen", fake_urlopen({"data": {}}, calls=calls)):
            common.post("query($id: String!) { target(ensemblId: $id) { id } }", {"id": "ENSG1"})
        self.assertEqual(calls[0]["variables"], {"id": "ENSG1"})

    def test_retryable_status_is_retried_then_succeeds(self) -> None:
        attempts = {"n": 0}

        def _open(request, timeout=None):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise urllib.error.HTTPError(
                    common.API_URL, 429, "Too Many Requests", {}, io.BytesIO(b"slow down")
                )
            return FakeResponse(json.dumps({"data": {"ok": True}}).encode())

        with mock.patch("urllib.request.urlopen", _open), mock.patch.object(common.time, "sleep"):
            self.assertEqual(common.post("{ ok }"), {"ok": True})
        self.assertEqual(attempts["n"], 2)

    def test_client_error_is_not_retried(self) -> None:
        attempts = {"n": 0}

        def _open(request, timeout=None):
            attempts["n"] += 1
            raise urllib.error.HTTPError(
                common.API_URL, 400, "Bad Request", {}, io.BytesIO(b"bad field")
            )

        with mock.patch("urllib.request.urlopen", _open), mock.patch.object(common.time, "sleep"):
            with self.assertRaises(common.OpenTargetsError):
                common.post("{ nope }")
        self.assertEqual(attempts["n"], 1, "a 400 is a client bug, not a transient failure")


class PaginationTests(unittest.TestCase):
    """Index pagination: `count` and an empty page are both stop conditions."""

    def _pages(self, total: int, size: int):
        def _payload(request):
            body = json.loads(request.data.decode("utf-8"))
            index = body["variables"]["index"]
            start = index * size
            rows = [{"n": i} for i in range(start, min(start + size, total))]
            return {"data": {"target": {"associatedDiseases": {"count": total, "rows": rows}}}}

        return _payload

    def test_walks_every_page_and_stops_on_count(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen(self._pages(25, 10))):
            rows = list(
                common.paged("q", {}, path=("target", "associatedDiseases"), size=10)
            )
        self.assertEqual([row["n"] for row in rows], list(range(25)))

    def test_limit_stops_early(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen(self._pages(1000, 10))):
            rows = list(
                common.paged("q", {}, path=("target", "associatedDiseases"), size=10, limit=12)
            )
        self.assertEqual(len(rows), 12)

    def test_empty_first_page_terminates(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen(self._pages(0, 10))):
            rows = list(common.paged("q", {}, path=("target", "associatedDiseases"), size=10))
        self.assertEqual(rows, [])

    def test_missing_entity_is_an_error_not_an_empty_result(self) -> None:
        """A null target means a bad id -- reporting it as "no diseases" would lie."""
        payload = {"data": {"target": None}}
        with mock.patch("urllib.request.urlopen", fake_urlopen(payload)):
            with self.assertRaises(common.OpenTargetsError):
                list(common.paged("q", {}, path=("target", "associatedDiseases")))

    def test_page_size_is_clamped_to_the_api_maximum(self) -> None:
        calls: list[dict] = []
        with mock.patch(
            "urllib.request.urlopen", fake_urlopen(self._pages(0, 500), calls=calls)
        ):
            list(common.paged("q", {}, path=("target", "associatedDiseases"), size=100_000))
        self.assertEqual(calls[0]["variables"]["size"], common.MAX_PAGE_SIZE)


class DatasourceSettingsTests(unittest.TestCase):
    """Restriction is a weighting operation; the zeroes are the whole point."""

    def test_none_means_platform_defaults(self) -> None:
        self.assertIsNone(ot_associations._datasource_settings(None))
        self.assertIsNone(ot_associations._datasource_settings([]))

    def test_kept_sources_get_weight_one_and_are_required(self) -> None:
        settings = ot_associations._datasource_settings(["gene_burden", "eva"])
        by_id = {entry["id"]: entry for entry in settings}
        for name in ("gene_burden", "eva"):
            self.assertEqual(by_id[name]["weight"], 1.0)
            self.assertTrue(by_id[name]["required"])

    def test_every_other_known_source_is_zeroed(self) -> None:
        settings = ot_associations._datasource_settings(["gene_burden"])
        by_id = {entry["id"]: entry for entry in settings}
        others = set(ot_associations.DATASOURCES) - {"gene_burden"}
        self.assertTrue(others)
        for name in others:
            self.assertEqual(
                by_id[name]["weight"],
                0.0,
                f"{name} left at a non-zero weight would keep contributing to the score",
            )
            self.assertFalse(by_id[name]["required"])

    def test_unknown_source_is_passed_through_with_a_warning(self) -> None:
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            settings = ot_associations._datasource_settings(["not_a_source"])
        self.assertIn("unrecognised datasource", stderr.getvalue())
        self.assertIn("not_a_source", {entry["id"] for entry in settings})


class VocabularyTests(unittest.TestCase):
    """The renames that make an otherwise-correct query return nothing."""

    def test_current_datatype_names_are_used(self) -> None:
        self.assertIn("clinical", ot_associations.DATATYPES)
        self.assertIn("genetic_literature", ot_associations.DATATYPES)
        self.assertNotIn(
            "known_drug",
            ot_associations.DATATYPES,
            "`known_drug` was renamed to `clinical`",
        )

    def test_both_spellings_of_the_renamed_sources_are_known(self) -> None:
        for name in ("chembl", "clinical_precedence", "ot_genetics_portal", "gwas_credible_sets"):
            self.assertIn(name, ot_associations.DATASOURCES)


class QueryDocumentTests(unittest.TestCase):
    """Guard the field names that were verified against the live schema."""

    def test_no_query_uses_the_removed_known_drugs_field(self) -> None:
        for name in dir(ot_query):
            value = getattr(ot_query, name)
            if isinstance(value, str) and name.endswith("_QUERY"):
                self.assertNotIn("knownDrugs", value, f"{name} uses a field removed from Target")

    def test_target_query_selects_the_verified_field_spellings(self) -> None:
        query = ot_query.TARGET_QUERY
        for fragment in ("labelSL", "probesDrugsScore", "depMapEssentiality", "prioritisation"):
            self.assertIn(fragment, query)

    def test_evidence_query_is_cursor_paginated(self) -> None:
        self.assertIn("cursor", ot_associations.EVIDENCE_QUERY)
        self.assertNotIn("page:", ot_associations.EVIDENCE_QUERY)

    def test_association_queries_are_index_paginated(self) -> None:
        for query in (
            ot_associations.TARGET_DISEASES_QUERY,
            ot_associations.DISEASE_TARGETS_QUERY,
        ):
            self.assertIn("page: {index: $index, size: $size}", query)
            self.assertIn("count", query)


class DiseaseIdGuardTests(unittest.TestCase):
    def test_a_null_disease_for_an_efo_id_explains_the_mondo_migration(self) -> None:
        stderr = io.StringIO()
        args = ot_query.build_parser().parse_args(["disease", "EFO_0000305"])
        with mock.patch("urllib.request.urlopen", fake_urlopen({"data": {"disease": None}})):
            with mock.patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit):
                    args.handler(args)
        message = stderr.getvalue()
        self.assertIn("MONDO", message)
        self.assertIn("resolve", message)

    def test_a_non_ensembl_target_id_is_rejected_before_the_request(self) -> None:
        args = ot_query.build_parser().parse_args(["target", "EGFR"])
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit):
                args.handler(args)
        self.assertIn("resolve", stderr.getvalue())


class TableTests(unittest.TestCase):
    def test_lists_are_pipe_joined_and_none_is_blank(self) -> None:
        stream = io.StringIO()
        common.write_table(
            [{"a": ["x", "y"], "b": None, "c": True, "d": 1 / 3}],
            ("a", "b", "c", "d"),
            stream=stream,
        )
        header, row = stream.getvalue().splitlines()
        self.assertEqual(header, "a\tb\tc\td")
        self.assertEqual(row.split("\t")[:3], ["x|y", "", "true"])

    def test_missing_columns_do_not_shift_the_row(self) -> None:
        stream = io.StringIO()
        common.write_table([{"b": 2}], ("a", "b", "c"), stream=stream)
        self.assertEqual(stream.getvalue().splitlines()[1], "\t2\t")


class ParserTests(unittest.TestCase):
    def test_evidence_takes_a_filter_flag_not_a_weighting_flag(self) -> None:
        """The two commands mean different things by "datasources"."""
        parser = ot_associations.build_parser()
        evidence = parser.parse_args(
            ["evidence", "ENSG1", "MONDO_1", "--datasources", "eva"]
        )
        self.assertEqual(evidence.datasources, ["eva"])
        associations = parser.parse_args(
            ["target-diseases", "ENSG1", "--only-datasources", "eva"]
        )
        self.assertEqual(associations.datasources, ["eva"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["target-diseases", "ENSG1", "--datasources", "eva"])

    def test_every_subcommand_binds_a_handler(self) -> None:
        for module, commands in (
            (ot_query, [["resolve", "EGFR"], ["search", "kinase"], ["target", "ENSG1"],
                        ["disease", "MONDO_1"], ["drug", "CHEMBL1"], ["raw", "q.graphql"]]),
            (ot_associations, [["target-diseases", "ENSG1"], ["disease-targets", "MONDO_1"],
                               ["evidence", "ENSG1", "MONDO_1"]]),
        ):
            for argv in commands:
                with self.subTest(command=argv[0]):
                    args = module.build_parser().parse_args(argv)
                    self.assertTrue(callable(getattr(args, "handler", None)))


if __name__ == "__main__":
    unittest.main()
