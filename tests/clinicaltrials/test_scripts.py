"""Tests for the ClinicalTrials.gov client scripts.

Nothing here touches the network. The parts worth testing are the ones where
the registry's shape is surprising and the scripts exist to absorb it: cursor
pagination, `countTotal` being opt-in, deeply optional modules, server-side
enum validation, and the criteria blob that has no structured form.
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

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "clinicaltrials"
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
# resolves to this same module object.
common = _load("_common", "_common.py")
ct_search = _load("ct_search_script", "ct_search.py")
ct_study = _load("ct_study_script", "ct_study.py")
ct_landscape = _load("ct_landscape_script", "ct_landscape.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def fake_urlopen(payload, *, urls=None):
    def _open(request, timeout=None):
        if urls is not None:
            urls.append(request.full_url)
        body = payload(request) if callable(payload) else payload
        return FakeResponse(json.dumps(body).encode("utf-8"))

    return _open


def http_error(status: int, detail: str):
    def _open(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url, status, "error", {}, io.BytesIO(detail.encode("utf-8"))
        )

    return _open


def study(nct="NCT00000001", **overrides):
    protocol = {
        "identificationModule": {"nctId": nct, "briefTitle": "A study"},
        "statusModule": {"overallStatus": "COMPLETED", "startDateStruct": {"date": "2020-01-01"}},
        "designModule": {
            "studyType": "INTERVENTIONAL",
            "phases": ["PHASE3"],
            "enrollmentInfo": {"count": 100, "type": "ACTUAL"},
        },
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Acme"}},
    }
    for path, value in overrides.items():
        module, _, key = path.partition(".")
        protocol.setdefault(module, {})[key] = value
    return {"protocolSection": protocol, "hasResults": False}


class DigTests(unittest.TestCase):
    """Every module is optional, so a missing path must not raise."""

    def test_reads_a_nested_path(self) -> None:
        self.assertEqual(
            common.dig(study(), "protocolSection.designModule.enrollmentInfo.count"), 100
        )

    def test_missing_module_returns_default(self) -> None:
        self.assertIsNone(common.dig(study(), "protocolSection.outcomesModule.primaryOutcomes"))

    def test_default_is_returned_not_raised(self) -> None:
        self.assertEqual(common.dig(study(), "a.b.c", "fallback"), "fallback")

    def test_walking_through_a_non_mapping_is_safe(self) -> None:
        self.assertIsNone(common.dig({"a": 5}, "a.b.c"))

    def test_none_record_is_safe(self) -> None:
        self.assertIsNone(common.dig(None, "a.b"))


class SummariseTests(unittest.TestCase):
    def test_phases_are_joined_not_indexed(self) -> None:
        record = study()
        record["protocolSection"]["designModule"]["phases"] = ["PHASE2", "PHASE3"]
        self.assertEqual(common.summarise(record)["phase"], "PHASE2|PHASE3")

    def test_has_results_is_read_from_the_top_level(self) -> None:
        record = study()
        record["hasResults"] = True
        self.assertTrue(common.summarise(record)["has_results"])

    def test_missing_optional_fields_become_none_not_errors(self) -> None:
        row = common.summarise({"protocolSection": {}})
        self.assertIsNone(row["nct_id"])
        self.assertEqual(row["phase"], "")
        self.assertFalse(row["has_results"])


class QueryBuildingTests(unittest.TestCase):
    def test_condition_maps_to_query_cond(self) -> None:
        args = ct_search.build_parser().parse_args(["search", "--condition", "asthma"])
        self.assertEqual(common.build_query(args)["query.cond"], "asthma")

    def test_phase_uses_the_essie_area_expression(self) -> None:
        args = ct_search.build_parser().parse_args(
            ["search", "--condition", "asthma", "--phase", "PHASE3"]
        )
        self.assertEqual(common.build_query(args)["filter.advanced"], "AREA[Phase]PHASE3")

    def test_multiple_statuses_are_comma_joined(self) -> None:
        args = ct_search.build_parser().parse_args(
            ["search", "--condition", "x", "--status", "COMPLETED", "--status", "TERMINATED"]
        )
        self.assertEqual(
            common.build_query(args)["filter.overallStatus"], "COMPLETED,TERMINATED"
        )

    def test_bad_status_is_rejected_before_the_request(self) -> None:
        """The API 400s on `Completed`; catch it locally with a usable message."""
        args = ct_search.build_parser().parse_args(
            ["search", "--condition", "x", "--status", "Completed"]
        )
        with self.assertRaises(common.ClinicalTrialsError) as caught:
            common.build_query(args)
        self.assertIn("not a valid status", str(caught.exception))

    def test_bad_phase_is_rejected_before_the_request(self) -> None:
        args = ct_search.build_parser().parse_args(
            ["search", "--condition", "x", "--phase", "phase3"]
        )
        with self.assertRaises(common.ClinicalTrialsError):
            common.build_query(args)

    def test_an_empty_query_is_refused(self) -> None:
        args = ct_search.build_parser().parse_args(["search"])
        with self.assertRaises(common.ClinicalTrialsError):
            common.build_query(args)


class PagingTests(unittest.TestCase):
    def test_cursor_is_followed_until_exhausted(self) -> None:
        pages = [
            {"studies": [study("NCT1")], "totalCount": 2, "nextPageToken": "tok"},
            {"studies": [study("NCT2")], "totalCount": 2},
        ]
        seen = {"n": 0}

        def payload(request):
            page = pages[min(seen["n"], len(pages) - 1)]
            seen["n"] += 1
            return page

        with mock.patch("urllib.request.urlopen", fake_urlopen(payload)):
            records = list(common.paged({"query.cond": "x"}))
        self.assertEqual(len(records), 2)

    def test_page_token_is_sent_on_the_second_request(self) -> None:
        urls: list[str] = []
        pages = [
            {"studies": [study("NCT1")], "nextPageToken": "TOKEN123"},
            {"studies": [study("NCT2")]},
        ]
        seen = {"n": 0}

        def payload(request):
            page = pages[min(seen["n"], len(pages) - 1)]
            seen["n"] += 1
            return page

        with mock.patch("urllib.request.urlopen", fake_urlopen(payload, urls=urls)):
            list(common.paged({"query.cond": "x"}))
        self.assertNotIn("pageToken", urls[0])
        self.assertIn("pageToken=TOKEN123", urls[1])

    def test_count_total_is_always_requested(self) -> None:
        """Without it the response carries no total and code silently sees zero."""
        urls: list[str] = []
        with mock.patch(
            "urllib.request.urlopen", fake_urlopen({"studies": [study()]}, urls=urls)
        ):
            list(common.paged({"query.cond": "x"}))
        self.assertIn("countTotal=true", urls[0])

    def test_paging_stops_with_no_token(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen({"studies": [study()]})):
            self.assertEqual(len(list(common.paged({"query.cond": "x"}))), 1)

    def test_limit_is_respected(self) -> None:
        page = {"studies": [study(f"NCT{n}") for n in range(50)], "nextPageToken": "t"}
        with mock.patch("urllib.request.urlopen", fake_urlopen(page)):
            self.assertEqual(len(list(common.paged({"query.cond": "x"}, limit=3))), 3)

    def test_page_size_is_clamped(self) -> None:
        urls: list[str] = []
        with mock.patch("urllib.request.urlopen", fake_urlopen({"studies": []}, urls=urls)):
            list(common.paged({"query.cond": "x"}, page_size=99999))
        self.assertIn(f"pageSize={common.MAX_PAGE_SIZE}", urls[0])

    def test_total_count_reads_the_field(self) -> None:
        with mock.patch(
            "urllib.request.urlopen", fake_urlopen({"studies": [], "totalCount": 42})
        ):
            self.assertEqual(common.total_count({"query.cond": "x"}), 42)

    def test_total_count_of_a_missing_field_is_zero(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen({"studies": []})):
            self.assertEqual(common.total_count({"query.cond": "x"}), 0)


class TransportTests(unittest.TestCase):
    def test_bad_status_error_lists_the_accepted_values(self) -> None:
        detail = "Invalid value in parameter `overallStatus`: `Completed`"
        with mock.patch("urllib.request.urlopen", http_error(400, detail)):
            with self.assertRaises(common.ClinicalTrialsError) as caught:
                common.get("studies", {"filter.overallStatus": "Completed"})
        self.assertIn("RECRUITING", str(caught.exception))

    def test_404_explains_the_id_format(self) -> None:
        with mock.patch("urllib.request.urlopen", http_error(404, "not found")):
            with self.assertRaises(common.ClinicalTrialsError) as caught:
                common.get("studies/NCT99999999")
        self.assertIn("NCT01234567", str(caught.exception))

    def test_retryable_status_is_retried(self) -> None:
        with mock.patch("urllib.request.urlopen", http_error(503, "down")):
            with mock.patch("time.sleep") as sleep:
                with self.assertRaises(common.ClinicalTrialsError):
                    common.get("studies", max_attempts=3)
        self.assertEqual(sleep.call_count, 2)

    def test_400_is_not_retried(self) -> None:
        with mock.patch("urllib.request.urlopen", http_error(400, "bad")):
            with mock.patch("time.sleep") as sleep:
                with self.assertRaises(common.ClinicalTrialsError):
                    common.get("studies", max_attempts=3)
        sleep.assert_not_called()


class NctValidationTests(unittest.TestCase):
    def test_a_bad_id_is_rejected_before_the_request(self) -> None:
        with self.assertRaises(common.ClinicalTrialsError) as caught:
            ct_study._fetch("NCT123", "https://example.invalid")
        self.assertIn("NCT01234567", str(caught.exception))

    def test_lowercase_is_accepted_and_upcased(self) -> None:
        urls: list[str] = []
        with mock.patch("urllib.request.urlopen", fake_urlopen(study(), urls=urls)):
            ct_study._fetch("nct02142738", common.BASE_URL)
        self.assertIn("NCT02142738", urls[0])


class CriteriaTests(unittest.TestCase):
    def test_headings_split_inclusion_from_exclusion(self) -> None:
        text = (
            "Inclusion Criteria:\n\n- Age 18 or older\n- ECOG 0-1\n\n"
            "Exclusion Criteria:\n\n- Prior chemotherapy\n"
        )
        inclusion, exclusion = ct_study._split_criteria(text)
        self.assertEqual(inclusion, ["Age 18 or older", "ECOG 0-1"])
        self.assertEqual(exclusion, ["Prior chemotherapy"])

    def test_bullet_characters_are_stripped(self) -> None:
        inclusion, _ = ct_study._split_criteria("Inclusion Criteria:\n* Adult\n")
        self.assertEqual(inclusion, ["Adult"])

    def test_unlabelled_text_is_not_guessed_into_a_bucket(self) -> None:
        """No headings means we do not know which half anything belongs to."""
        inclusion, exclusion = ct_study._split_criteria("Adults only")
        self.assertEqual(exclusion, [])
        self.assertIn("Adults only", inclusion)

    def test_empty_text_is_empty(self) -> None:
        self.assertEqual(ct_study._split_criteria(""), ([], []))


class LandscapeTests(unittest.TestCase):
    def test_highest_phase_ranks_correctly(self) -> None:
        self.assertEqual(ct_landscape._highest_phase(["PHASE1", "PHASE3", "PHASE2"]), "PHASE3")

    def test_na_ranks_below_every_real_phase(self) -> None:
        self.assertEqual(ct_landscape._highest_phase(["NA", "PHASE1"]), "PHASE1")

    def test_no_recognised_phase_is_blank(self) -> None:
        self.assertEqual(ct_landscape._highest_phase([]), "")
        self.assertEqual(ct_landscape._highest_phase(["NONSENSE"]), "")

    def test_stopped_covers_the_three_early_exits(self) -> None:
        self.assertEqual(common.STOPPED, {"TERMINATED", "WITHDRAWN", "SUSPENDED"})


class VocabularyTests(unittest.TestCase):
    """Enums verified against the live API; a rename should fail loudly."""

    def test_status_vocabulary(self) -> None:
        for status in ("RECRUITING", "COMPLETED", "TERMINATED", "WITHDRAWN", "UNKNOWN"):
            self.assertIn(status, common.STATUSES)

    def test_phase_vocabulary_includes_na(self) -> None:
        self.assertIn("NA", common.PHASES)
        self.assertIn("EARLY_PHASE1", common.PHASES)

    def test_page_size_cap(self) -> None:
        self.assertEqual(common.MAX_PAGE_SIZE, 1000)


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (ct_search, ["search", "--condition", "x"]),
            (ct_search, ["count", "--condition", "x"]),
            (ct_study, ["show", "NCT00000001"]),
            (ct_study, ["outcomes", "NCT00000001"]),
            (ct_study, ["eligibility", "NCT00000001"]),
            (ct_landscape, ["sponsors", "--condition", "x"]),
            (ct_landscape, ["interventions", "--condition", "x"]),
            (ct_landscape, ["attrition", "--condition", "x"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_default_output_format_is_tsv(self) -> None:
        args = ct_search.build_parser().parse_args(["search", "--condition", "x"])
        self.assertEqual(args.output_format, "tsv")

    def test_lists_are_pipe_joined_in_tables(self) -> None:
        self.assertEqual(common._cell(["a", "b"]), "a|b")


if __name__ == "__main__":
    unittest.main()
