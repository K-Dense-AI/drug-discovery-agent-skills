"""Tests for the openFDA client scripts.

Nothing here touches the network. The parts worth testing are the ones where
openFDA's behaviour is surprising and the scripts exist to absorb it: an empty
result set arriving as HTTP 404, a `limit` overflow arriving as a credential
error, the hard `skip` ceiling, and the disproportionality arithmetic -- which
is the only place in this skill where a wrong number looks entirely plausible.
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

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "openfda"
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
# distinct `OpenFdaError` classes and make `assertRaises` silently miss.
common = _load("_common", "_common.py")
fda_adverse = _load("fda_adverse_script", "fda_adverse.py")
fda_approvals = _load("fda_approvals_script", "fda_approvals.py")
fda_labels = _load("fda_labels_script", "fda_labels.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


class FakeResponse(io.BytesIO):
    """Minimal stand-in for what `urlopen` returns as a context manager."""

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


def http_error(status: int, body: dict, headers=None):
    def _open(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url,
            status,
            "error",
            headers or {},
            io.BytesIO(json.dumps(body).encode("utf-8")),
        )

    return _open


def results(records, total=None):
    return {
        "meta": {"results": {"skip": 0, "limit": len(records), "total": total or len(records)}},
        "results": records,
    }


class NotFoundTests(unittest.TestCase):
    """HTTP 404 means zero matches, not failure. The flagship behaviour."""

    def test_not_found_becomes_an_empty_payload(self) -> None:
        body = {"error": {"code": "NOT_FOUND", "message": "No matches found!"}}
        with mock.patch("urllib.request.urlopen", http_error(404, body)):
            document = common.get("drug/event", {"search": "x"})
        self.assertEqual(document["results"], [])
        self.assertEqual(document["meta"]["results"]["total"], 0)

    def test_a_404_that_is_not_not_found_still_raises(self) -> None:
        body = {"error": {"code": "BAD_REQUEST", "message": "something else"}}
        with mock.patch("urllib.request.urlopen", http_error(404, body)):
            with self.assertRaises(common.OpenFdaError):
                common.get("drug/event", {"search": "x"})

    def test_total_matching_reports_zero_rather_than_raising(self) -> None:
        body = {"error": {"code": "NOT_FOUND", "message": "No matches found!"}}
        with mock.patch("urllib.request.urlopen", http_error(404, body)):
            self.assertEqual(common.total_matching("drug/event", "nope"), 0)


class ErrorExplanationTests(unittest.TestCase):
    def test_api_key_missing_is_explained_as_a_limit_problem(self) -> None:
        """403 API_KEY_MISSING really means `limit` was above 1000."""
        body = {"error": {"code": "API_KEY_MISSING", "message": "No api_key was supplied."}}
        with mock.patch("urllib.request.urlopen", http_error(403, body)):
            with self.assertRaises(common.OpenFdaError) as caught:
                common.get("drug/event", {"limit": 1001})
        message = str(caught.exception)
        self.assertIn("limit", message)
        self.assertIn("not a credential problem", message)

    def test_skip_ceiling_error_names_the_fix(self) -> None:
        body = {"error": {"code": "BAD_REQUEST", "message": "Skip value must 25000 or less."}}
        with mock.patch("urllib.request.urlopen", http_error(400, body)):
            with self.assertRaises(common.OpenFdaError) as caught:
                common.get("drug/event", {"skip": 26000})
        self.assertIn("Narrow the search", str(caught.exception))

    def test_retryable_status_is_retried_then_raises(self) -> None:
        body = {"error": {"code": "SERVER_ERROR", "message": "boom"}}
        with mock.patch("urllib.request.urlopen", http_error(503, body)):
            with mock.patch("time.sleep") as sleep:
                with self.assertRaises(common.OpenFdaError):
                    common.get("drug/event", max_attempts=3)
        self.assertEqual(sleep.call_count, 2)

    def test_non_retryable_status_is_not_retried(self) -> None:
        body = {"error": {"code": "BAD_REQUEST", "message": "nope"}}
        with mock.patch("urllib.request.urlopen", http_error(400, body)):
            with mock.patch("time.sleep") as sleep:
                with self.assertRaises(common.OpenFdaError):
                    common.get("drug/event", max_attempts=3)
        sleep.assert_not_called()


class LimitTests(unittest.TestCase):
    def test_clamp_limit_holds_the_server_cap(self) -> None:
        self.assertEqual(common.clamp_limit(5000), common.MAX_LIMIT)
        self.assertEqual(common.clamp_limit(0), 1)
        self.assertEqual(common.clamp_limit(250), 250)

    def test_max_skip_matches_the_documented_ceiling(self) -> None:
        self.assertEqual(common.MAX_SKIP, 25000)


class UrlTests(unittest.TestCase):
    def test_json_suffix_is_added(self) -> None:
        url = common._build_url("drug/event", None, "https://api.fda.gov")
        self.assertEqual(url, "https://api.fda.gov/drug/event.json")

    def test_boolean_operators_survive_encoding(self) -> None:
        url = common._build_url(
            "drug/event", {"search": "a:1+AND+b:2"}, "https://api.fda.gov"
        )
        self.assertIn("+AND+", url)

    def test_api_key_is_added_when_set(self) -> None:
        with mock.patch.dict("os.environ", {"OPENFDA_API_KEY": "secret123"}):
            url = common._build_url("drug/event", None, "https://api.fda.gov")
        self.assertIn("api_key=secret123", url)

    def test_no_api_key_parameter_when_unset(self) -> None:
        with mock.patch.dict("os.environ", {"OPENFDA_API_KEY": ""}):
            url = common._build_url("drug/event", None, "https://api.fda.gov")
        self.assertNotIn("api_key", url)

    def test_quote_wraps_multiword_values_only(self) -> None:
        self.assertEqual(common.quote("aspirin"), "aspirin")
        self.assertEqual(common.quote("ATORVASTATIN CALCIUM"), '"ATORVASTATIN CALCIUM"')


class PagingTests(unittest.TestCase):
    def test_paging_stops_when_total_is_reached(self) -> None:
        pages = [results([{"i": 1}, {"i": 2}], total=3), results([{"i": 3}], total=3)]
        calls = {"n": 0}

        def payload(request):
            page = pages[min(calls["n"], len(pages) - 1)]
            calls["n"] += 1
            return page

        with mock.patch("urllib.request.urlopen", fake_urlopen(payload)):
            records = list(common.paged("drug/event", "x", page_size=2))
        self.assertEqual(len(records), 3)

    def test_paging_respects_an_explicit_limit(self) -> None:
        with mock.patch(
            "urllib.request.urlopen",
            fake_urlopen(results([{"i": n} for n in range(100)], total=10_000)),
        ):
            records = list(common.paged("drug/event", "x", limit=5, page_size=100))
        self.assertEqual(len(records), 5)

    def test_paging_terminates_on_an_empty_page(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen(results([]))):
            self.assertEqual(list(common.paged("drug/event", "x")), [])


class ContingencyTests(unittest.TestCase):
    """The disproportionality arithmetic. A wrong number here looks plausible."""

    def test_known_true_positive_is_flagged(self) -> None:
        """atorvastatin x rhabdomyolysis, from the live API in August 2026."""
        stats = fda_adverse.contingency(5713, 518912, 41110, 20692690)
        self.assertEqual(stats["a"], 5713)
        self.assertEqual(stats["b"], 513199)
        self.assertEqual(stats["c"], 35397)
        self.assertAlmostEqual(stats["prr"], 6.275, places=2)
        self.assertAlmostEqual(stats["ror"], 6.333, places=2)
        self.assertTrue(stats["signal"])

    def test_background_event_is_not_flagged_despite_a_huge_chi2(self) -> None:
        """The reason the rule is a conjunction: chi2 alone would flag this."""
        stats = fda_adverse.contingency(5344, 518912, 198392, 20692690)
        self.assertLess(stats["prr"], 2.0)
        self.assertGreater(stats["chi2"], fda_adverse.SIGNAL_MIN_CHI2)
        self.assertFalse(stats["signal"])

    def test_ror_confidence_interval_brackets_the_estimate(self) -> None:
        stats = fda_adverse.contingency(100, 1000, 500, 1_000_000)
        self.assertLess(stats["ror_ci_low"], stats["ror"])
        self.assertGreater(stats["ror_ci_high"], stats["ror"])

    def test_ror_equals_the_cross_product_ratio(self) -> None:
        stats = fda_adverse.contingency(10, 110, 110, 10_000)
        a, b, c, d = stats["a"], stats["b"], stats["c"], stats["d"]
        self.assertAlmostEqual(stats["ror"], (a * d) / (b * c), places=3)

    def test_too_few_reports_is_not_a_signal(self) -> None:
        stats = fda_adverse.contingency(2, 1000, 5, 1_000_000)
        self.assertLess(stats["a"], fda_adverse.SIGNAL_MIN_REPORTS)
        self.assertFalse(stats["signal"])

    def test_zero_joint_count_has_no_table(self) -> None:
        self.assertIsNone(fda_adverse.contingency(0, 1000, 500, 1_000_000))

    def test_inconsistent_totals_are_rejected(self) -> None:
        """a larger than the drug total cannot happen; do not return nonsense."""
        self.assertIsNone(fda_adverse.contingency(500, 100, 500, 1_000_000))

    def test_empty_comparator_arm_is_rejected(self) -> None:
        self.assertIsNone(fda_adverse.contingency(10, 10, 500, 1_000_000))


class SearchClauseTests(unittest.TestCase):
    def test_drug_clause_covers_raw_and_normalised_names(self) -> None:
        clause = fda_adverse.drug_clause("atorvastatin")
        self.assertIn("patient.drug.medicinalproduct:atorvastatin", clause)
        self.assertIn("patient.drug.openfda.generic_name:atorvastatin", clause)
        self.assertIn("+OR+", clause)

    def test_multiword_drug_is_quoted(self) -> None:
        self.assertIn('"ATORVASTATIN CALCIUM"', fda_adverse.drug_clause("ATORVASTATIN CALCIUM"))

    def test_label_clause_covers_three_name_fields(self) -> None:
        clause = fda_labels.drug_clause("metformin")
        for field in ("brand_name", "generic_name", "substance_name"):
            self.assertIn(f"openfda.{field}:metformin", clause)


class ApprovalsTests(unittest.TestCase):
    def test_original_approval_picks_the_earliest_approved_orig(self) -> None:
        record = {
            "submissions": [
                {"submission_type": "SUPPL", "submission_status": "AP", "submission_status_date": "20100101"},
                {"submission_type": "ORIG", "submission_status": "AP", "submission_status_date": "20140904"},
                {"submission_type": "ORIG", "submission_status": "CR", "submission_status_date": "20130101"},
            ]
        }
        self.assertEqual(fda_approvals._original_approval(record), "20140904")

    def test_complete_response_is_not_an_approval(self) -> None:
        record = {
            "submissions": [
                {"submission_type": "ORIG", "submission_status": "CR", "submission_status_date": "20130101"}
            ]
        }
        self.assertEqual(fda_approvals._original_approval(record), "")

    def test_missing_submissions_is_not_an_error(self) -> None:
        self.assertEqual(fda_approvals._original_approval({}), "")

    def test_selector_is_required(self) -> None:
        args = fda_approvals.build_parser().parse_args(["application"])
        with self.assertRaises(common.OpenFdaError):
            fda_approvals._search_clause(args)

    def test_appno_selector_wins(self) -> None:
        args = fda_approvals.build_parser().parse_args(["application", "--appno", "BLA125514"])
        self.assertIn("application_number:BLA125514", fda_approvals._search_clause(args))


class TableTests(unittest.TestCase):
    def test_lists_are_pipe_joined(self) -> None:
        self.assertEqual(common._cell(["a", "b"]), "a|b")

    def test_booleans_are_lowercase_words(self) -> None:
        self.assertEqual(common._cell(True), "true")
        self.assertEqual(common._cell(False), "false")

    def test_none_is_empty(self) -> None:
        self.assertEqual(common._cell(None), "")


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (fda_adverse, ["reports", "--drug", "x"]),
            (fda_adverse, ["reactions", "--drug", "x"]),
            (fda_adverse, ["signal", "--drug", "x", "--reaction", "y"]),
            (fda_approvals, ["application", "--drug", "x"]),
            (fda_approvals, ["products", "--appno", "NDA1"]),
            (fda_approvals, ["timeline", "--appno", "NDA1"]),
            (fda_labels, ["section", "--drug", "x"]),
            (fda_labels, ["boxed", "--drug", "x"]),
            (fda_labels, ["classes", "--drug", "x"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_default_output_format_is_tsv(self) -> None:
        args = fda_adverse.build_parser().parse_args(["reactions", "--drug", "x"])
        self.assertEqual(args.output_format, "tsv")

    def test_unknown_label_section_exits_one(self) -> None:
        args = fda_labels.build_parser().parse_args(
            ["section", "--drug", "x", "--section", "not_a_section"]
        )
        with self.assertRaises(SystemExit) as caught:
            fda_labels.command_section(args)
        self.assertEqual(caught.exception.code, 1)


class VocabularyTests(unittest.TestCase):
    """Field names verified against the live API; a rename should fail loudly."""

    def test_known_label_sections(self) -> None:
        for section in ("boxed_warning", "indications_and_usage", "mechanism_of_action"):
            self.assertIn(section, fda_labels.SECTIONS)

    def test_pharm_class_fields(self) -> None:
        self.assertIn("pharm_class_epc", fda_labels.PHARM_CLASSES)
        self.assertIn("pharm_class_moa", fda_labels.PHARM_CLASSES)

    def test_drug_endpoints_are_documented(self) -> None:
        for endpoint in ("event", "label", "drugsfda", "ndc", "enforcement", "shortages"):
            self.assertIn(endpoint, common.DRUG_ENDPOINTS)


if __name__ == "__main__":
    unittest.main()
