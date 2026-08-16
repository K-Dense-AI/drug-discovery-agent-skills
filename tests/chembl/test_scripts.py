"""Tests for the ChEMBL web-service scripts.

No network. The behaviours under test are the ones that make a ChEMBL-derived
dataset wrong without failing: a silently capped `limit`, a lookup suffix
written with one underscore, numbers arriving as strings, and censored `>`
rows being treated as measurements.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "chembl"
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
# distinct `ChemblError` classes and make `assertRaises` silently miss.
common = _load("_common", "_common.py")
target_activities = _load("chembl_target_activities", "target_activities.py")
compound_lookup = _load("chembl_compound_lookup", "compound_lookup.py")
chembl_query = _load("chembl_query_script", "chembl_query.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def fake_urlopen(payload, *, urls=None):
    def _open(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        if urls is not None:
            urls.append(url)
        body = payload(url) if callable(payload) else payload
        return FakeResponse(json.dumps(body).encode("utf-8"))

    return _open


class UrlBuildingTests(unittest.TestCase):
    def test_endpoint_names_gain_a_json_suffix(self) -> None:
        url = common._build_url("activity", {"limit": 5}, common.BASE_URL)
        self.assertTrue(url.startswith(f"{common.BASE_URL}/activity.json?"))
        self.assertIn("limit=5", url)

    def test_none_valued_parameters_are_dropped(self) -> None:
        url = common._build_url("molecule", {"limit": 5, "only": None}, common.BASE_URL)
        self.assertNotIn("only", url)

    def test_next_links_are_used_verbatim(self) -> None:
        """`page_meta.next` is already encoded; re-encoding it corrupts filters."""
        nxt = "/chembl/api/data/activity.json?limit=20&offset=20&standard_relation=%3D"
        url = common._build_url(nxt, None, common.BASE_URL)
        self.assertEqual(url, f"https://www.ebi.ac.uk{nxt}")
        self.assertIn("%3D", url)
        self.assertNotIn("%253D", url)

    def test_commas_survive_encoding_for_in_filters(self) -> None:
        url = common._build_url(
            "molecule", {"molecule_chembl_id__in": "CHEMBL25,CHEMBL941"}, common.BASE_URL
        )
        self.assertIn("CHEMBL25,CHEMBL941", url)


class FilterParsingTests(unittest.TestCase):
    def test_double_underscore_lookups_pass(self) -> None:
        self.assertEqual(
            common.parse_filters(["pchembl_value__gte=8", "assay_type=B"]),
            {"pchembl_value__gte": "8", "assay_type": "B"},
        )

    def test_single_underscore_lookup_is_rejected(self) -> None:
        """The failure that returns the whole table instead of nothing."""
        with self.assertRaises(common.ChemblError) as caught:
            common.parse_filters(["pchembl_value_gte=8"])
        self.assertIn("two", str(caught.exception))
        self.assertIn("pchembl_value__gte", str(caught.exception))

    def test_a_field_ending_in_a_lookup_word_is_not_confused(self) -> None:
        """`__in` is a lookup; a field genuinely ending in `_in` is not."""
        self.assertIn("direct_interaction", common.parse_filters(["direct_interaction=1"]))

    def test_missing_equals_is_an_error(self) -> None:
        with self.assertRaises(common.ChemblError):
            common.parse_filters(["assay_type"])


class PayloadKeyTests(unittest.TestCase):
    def test_irregular_plurals_are_mapped(self) -> None:
        self.assertEqual(common.payload_key("activity"), "activities")
        self.assertEqual(common.payload_key("mechanism"), "mechanisms")
        self.assertEqual(common.payload_key("atc_class"), "atc")

    def test_structure_searches_return_molecules(self) -> None:
        self.assertEqual(common.payload_key("similarity/CCO/70"), "molecules")
        self.assertEqual(common.payload_key("substructure/CCO"), "molecules")

    def test_unknown_endpoints_fall_back_to_simple_plural(self) -> None:
        self.assertEqual(common.payload_key("widget"), "widgets")


class PagingTests(unittest.TestCase):
    def _server(self, total: int, page_size: int):
        def _payload(url: str):
            offset = 0
            if "offset=" in url:
                offset = int(url.split("offset=")[1].split("&")[0])
            rows = [{"activity_id": i} for i in range(offset, min(offset + page_size, total))]
            nxt = None
            if offset + page_size < total:
                nxt = f"/chembl/api/data/activity.json?limit={page_size}&offset={offset + page_size}"
            return {
                "page_meta": {"limit": page_size, "offset": offset, "total_count": total, "next": nxt},
                "activities": rows,
            }

        return _payload

    def test_follows_next_until_exhausted(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen(self._server(250, 100))):
            rows = list(common.paged("activity", page_size=100))
        self.assertEqual(len(rows), 250)

    def test_limit_stops_early(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen(self._server(10_000, 100))):
            rows = list(common.paged("activity", limit=150, page_size=100))
        self.assertEqual(len(rows), 150)

    def test_page_size_is_clamped_to_the_server_cap(self) -> None:
        """Above 1000 the server truncates without saying so."""
        urls: list[str] = []
        with mock.patch(
            "urllib.request.urlopen", fake_urlopen(self._server(0, 1000), urls=urls)
        ):
            list(common.paged("activity", page_size=5000))
        self.assertIn(f"limit={common.MAX_LIMIT}", urls[0])

    def test_a_missing_payload_key_is_an_error_not_an_empty_result(self) -> None:
        payload = {"page_meta": {"next": None}, "error_message": "bad filter"}
        with mock.patch("urllib.request.urlopen", fake_urlopen(payload)):
            with self.assertRaises(common.ChemblError):
                list(common.paged("activity"))


class RetryTests(unittest.TestCase):
    def test_transient_status_is_retried(self) -> None:
        attempts = {"n": 0}

        def _open(request, timeout=None):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise urllib.error.HTTPError(
                    "u", 503, "Service Unavailable", {}, io.BytesIO(b"busy")
                )
            return FakeResponse(b'{"ok": true}')

        with mock.patch("urllib.request.urlopen", _open), mock.patch.object(common.time, "sleep"):
            self.assertEqual(common.get("status"), {"ok": True})
        self.assertEqual(attempts["n"], 3)

    def test_bad_filter_400_is_not_retried(self) -> None:
        attempts = {"n": 0}

        def _open(request, timeout=None):
            attempts["n"] += 1
            raise urllib.error.HTTPError(
                "u", 400, "Bad Request", {}, io.BytesIO(b'{"error_message": "not valid"}')
            )

        with mock.patch("urllib.request.urlopen", _open), mock.patch.object(common.time, "sleep"):
            with self.assertRaises(common.ChemblError) as caught:
                common.get("molecule", {"molecule_properties__cx_logp__lte": 3})
        self.assertEqual(attempts["n"], 1)
        self.assertIn("not valid", str(caught.exception))


class StringNumberTests(unittest.TestCase):
    """ChEMBL returns numbers as strings; comparing them as text misorders."""

    def test_as_float_handles_the_real_shapes(self) -> None:
        self.assertEqual(common.as_float("41.0"), 41.0)
        self.assertEqual(common.as_float(7), 7.0)
        self.assertIsNone(common.as_float(None))
        self.assertIsNone(common.as_float(""))
        self.assertIsNone(common.as_float("not a number"))

    def test_median_of_an_even_count_averages_the_middle_pair(self) -> None:
        self.assertEqual(common.median([1.0, 2.0, 3.0, 4.0]), 2.5)
        self.assertEqual(common.median([5.0]), 5.0)
        self.assertIsNone(common.median([]))


def _args(**overrides) -> argparse.Namespace:
    defaults = dict(
        units=None,
        exclude_duplicates=True,
        require_pchembl=True,
        min_pchembl=None,
        min_confidence=None,
        organism=None,
        spread_warning=1.0,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class CurationTests(unittest.TestCase):
    """Each filter exists because a published dataset was wrong without it."""

    ROWS = [
        {"molecule_chembl_id": "A", "standard_value": "10", "standard_relation": "=",
         "pchembl_value": "8.0", "standard_units": "nM", "potential_duplicate": 0,
         "assay_chembl_id": "AS1", "data_validity_comment": None},
        {"molecule_chembl_id": "B", "standard_value": "10000", "standard_relation": ">",
         "pchembl_value": "5.0", "standard_units": "nM", "potential_duplicate": 0,
         "assay_chembl_id": "AS1", "data_validity_comment": None},
        {"molecule_chembl_id": "C", "standard_value": "1", "standard_relation": "=",
         "pchembl_value": "9.0", "standard_units": "nM", "potential_duplicate": 0,
         "assay_chembl_id": "AS1", "data_validity_comment": "Outside typical range"},
        {"molecule_chembl_id": "D", "standard_value": "50", "standard_relation": "=",
         "pchembl_value": None, "standard_units": "nM", "potential_duplicate": 0,
         "assay_chembl_id": "AS1", "data_validity_comment": None},
        {"molecule_chembl_id": "E", "standard_value": "20", "standard_relation": "=",
         "pchembl_value": "7.7", "standard_units": "nM", "potential_duplicate": 1,
         "assay_chembl_id": "AS1", "data_validity_comment": None},
        {"molecule_chembl_id": "F", "standard_value": "30", "standard_relation": "=",
         "pchembl_value": "7.5", "standard_units": "nM", "potential_duplicate": 0,
         "assay_chembl_id": "LOWCONF", "data_validity_comment": None},
    ]

    def _kept(self, **overrides) -> set[str]:
        confidence = {"AS1": 9, "LOWCONF": 4}
        rows, _ = target_activities.curate(_args(**overrides), list(self.ROWS), confidence)
        return {row["molecule_chembl_id"] for row in rows}

    def test_censored_relations_are_dropped(self) -> None:
        self.assertNotIn("B", self._kept())

    def test_chembl_flagged_values_are_dropped(self) -> None:
        self.assertNotIn("C", self._kept())

    def test_rows_without_pchembl_are_dropped_by_default(self) -> None:
        self.assertNotIn("D", self._kept())
        self.assertIn("D", self._kept(require_pchembl=False))

    def test_potential_duplicates_are_dropped_by_default(self) -> None:
        self.assertNotIn("E", self._kept())
        self.assertIn("E", self._kept(exclude_duplicates=False))

    def test_low_confidence_assays_are_dropped_only_when_asked(self) -> None:
        self.assertIn("F", self._kept())
        self.assertNotIn("F", self._kept(min_confidence=8))

    def test_the_audit_trail_accounts_for_every_dropped_row(self) -> None:
        rows, audit = target_activities.curate(
            _args(), list(self.ROWS), {"AS1": 9, "LOWCONF": 4}
        )
        self.assertEqual(audit[0], f"input rows: {len(self.ROWS)}")
        self.assertEqual(audit[-1], f"kept rows: {len(rows)}")
        self.assertTrue(any("censored" in line for line in audit))


class AggregationTests(unittest.TestCase):
    def test_replicates_collapse_to_a_median_with_the_spread_reported(self) -> None:
        rows = [
            {"molecule_chembl_id": "X", "pchembl_value": "5.1", "standard_value": "7943",
             "standard_units": "nM", "standard_type": "IC50", "canonical_smiles": "CCO",
             "document_chembl_id": "D1", "assay_chembl_id": "A1"},
            {"molecule_chembl_id": "X", "pchembl_value": "8.9", "standard_value": "1.3",
             "standard_units": "nM", "standard_type": "IC50", "canonical_smiles": "CCO",
             "document_chembl_id": "D2", "assay_chembl_id": "A1"},
        ]
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            aggregated = target_activities.aggregate(_args(), rows, {"A1": 9})
        self.assertEqual(len(aggregated), 1)
        record = aggregated[0]
        self.assertAlmostEqual(record["pchembl_median"], 7.0)
        self.assertAlmostEqual(record["pchembl_spread"], 3.8)
        self.assertEqual(record["n_measurements"], 2)
        self.assertEqual(record["n_documents"], 2)
        self.assertTrue(record["inconsistent"], "a 3.8-log spread must be flagged")
        self.assertIn("review before modelling", stderr.getvalue())

    def test_rows_sort_most_potent_first(self) -> None:
        rows = [
            {"molecule_chembl_id": m, "pchembl_value": p, "standard_value": "1",
             "standard_units": "nM", "standard_type": "IC50", "canonical_smiles": "C",
             "document_chembl_id": "D", "assay_chembl_id": "A1"}
            for m, p in (("weak", "5.0"), ("strong", "9.5"), ("mid", "7.0"))
        ]
        aggregated = target_activities.aggregate(_args(), rows, {})
        self.assertEqual(
            [row["molecule_chembl_id"] for row in aggregated], ["strong", "mid", "weak"]
        )


class FlattenTests(unittest.TestCase):
    def test_biologics_with_null_structures_do_not_crash(self) -> None:
        """`structure_type: SEQ` records have null structures and properties."""
        record = {
            "molecule_chembl_id": "CHEMBL1201439",
            "structure_type": "SEQ",
            "molecule_structures": None,
            "molecule_properties": None,
            "max_phase": "4.0",
        }
        flat = compound_lookup.flatten(record)
        self.assertIsNone(flat["canonical_smiles"])
        self.assertIsNone(flat["full_mwt"])
        self.assertEqual(flat["max_phase"], 4.0)

    def test_string_properties_become_numbers(self) -> None:
        record = {
            "molecule_chembl_id": "CHEMBL25",
            "molecule_properties": {"full_mwt": "180.16", "alogp": "1.31", "hba": 3},
            "molecule_structures": {"canonical_smiles": "CC(=O)Oc1ccccc1C(=O)O"},
        }
        flat = compound_lookup.flatten(record)
        self.assertEqual(flat["full_mwt"], 180.16)
        self.assertEqual(flat["alogp"], 1.31)
        self.assertEqual(flat["hba"], 3)


class StructureSearchEncodingTests(unittest.TestCase):
    def test_a_smiles_with_a_hash_is_percent_encoded_into_the_path(self) -> None:
        """An unencoded `#` truncates the URL at the fragment marker."""
        urls: list[str] = []
        payload = {"page_meta": {"next": None}, "molecules": []}
        args = compound_lookup.build_parser().parse_args(["similar", "C#CCO", "--limit", "5"])
        with mock.patch("urllib.request.urlopen", fake_urlopen(payload, urls=urls)):
            args.handler(args)
        self.assertTrue(urls)
        self.assertIn("C%23CCO", urls[0])
        self.assertNotIn("#", urls[0])

    def test_similarity_threshold_below_the_api_floor_is_refused(self) -> None:
        args = compound_lookup.build_parser().parse_args(
            ["similar", "CCO", "--threshold", "10"]
        )
        with self.assertRaises(common.ChemblError):
            args.handler(args)

    def test_short_inchikeys_match_the_skeleton(self) -> None:
        urls: list[str] = []
        payload = {"page_meta": {"next": None}, "molecules": []}
        args = compound_lookup.build_parser().parse_args(["inchikey", "BSYNRYMUTXBXSQ"])
        with mock.patch("urllib.request.urlopen", fake_urlopen(payload, urls=urls)):
            args.handler(args)
        self.assertIn("startswith", urls[0])


class ParserTests(unittest.TestCase):
    def test_target_activities_requires_one_identity_flag(self) -> None:
        parser = target_activities.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--standard-type", "IC50"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["--uniprot", "P00533", "--target", "CHEMBL203"])
        args = parser.parse_args(["--uniprot", "P00533"])
        self.assertEqual(args.standard_type, "IC50")
        self.assertEqual(args.assay_types, ["B"])

    def test_every_subcommand_binds_a_handler(self) -> None:
        cases = [
            (compound_lookup, ["id", "CHEMBL25"]),
            (compound_lookup, ["name", "aspirin"]),
            (compound_lookup, ["smiles", "CCO"]),
            (compound_lookup, ["inchikey", "AAA"]),
            (compound_lookup, ["similar", "CCO"]),
            (compound_lookup, ["substructure", "CCO"]),
            (compound_lookup, ["mechanism", "--target", "CHEMBL203"]),
            (chembl_query, ["endpoints"]),
            (chembl_query, ["fetch", "activity"]),
            (chembl_query, ["count", "activity"]),
            (chembl_query, ["record", "target", "CHEMBL203"]),
            (chembl_query, ["status"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(getattr(args, "handler", None)))

    def test_documented_endpoints_all_have_a_description_and_filters(self) -> None:
        for name, (description, filters) in chembl_query.ENDPOINTS.items():
            with self.subTest(endpoint=name):
                self.assertTrue(description.strip())
                self.assertTrue(filters.strip())


if __name__ == "__main__":
    unittest.main()
