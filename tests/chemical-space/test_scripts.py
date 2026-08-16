"""Tests for the chemical-space scripts.

Nothing here touches the network. The parts worth testing are CartBlanche's
habit of returning its HTML app shell with HTTP 200 and a JSON content type,
ZINC identifier padding, the tranche naming convention that addresses the bulk
tree, and the cascade arithmetic that decides whether a screen is affordable.
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

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "chemical-space"
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
cartblanche_lookup = _load("cartblanche_lookup_script", "cartblanche_lookup.py")
space_plan = _load("space_plan_script", "space_plan.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

APP_SHELL = '<!doctype html><html lang="en"><head><title>Cartblanche</title></head></html>'

SUBSTANCE = {
    "smiles": "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1",
    "tranche_details": {
        "heavy_atoms": 37,
        "logp": 4.59,
        "mwt": 493.615,
        "inchikey": "KTUFNOKKBVMGRW-UHFFFAOYSA-N",
    },
    "mol_formula": "C29H31N7O",
    "rings": 5,
    "hetero_atoms": 8,
    "db": "zinc20",
    "zinc_id": "ZINC000019632618",
    "catalogs": [
        {"catalog_name": "eMolecules", "price": 240, "purchase": 1, "quantity": 10,
         "shipping": "6 weeks", "supplier_code": "876446"},
        {"catalog_name": "Other", "price": 900, "purchase": 1, "quantity": 5,
         "shipping": "3 weeks", "supplier_code": "X1"},
    ],
}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def fake_urlopen(raw, *, urls=None):
    body = raw if isinstance(raw, str) else json.dumps(raw)

    def _open(request, timeout=None):
        if urls is not None:
            urls.append(request.full_url)
        return FakeResponse(body.encode("utf-8"))

    return _open


class AppShellTests(unittest.TestCase):
    """200 + application/json + HTML body. The header cannot be trusted."""

    def test_html_shell_raises_instead_of_looking_like_data(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen(APP_SHELL)):
            with self.assertRaises(common.ChemicalSpaceError) as caught:
                common.get_json("tranches.json")
        message = str(caught.exception)
        self.assertIn("HTML app shell", message)
        self.assertIn("/substance/<ZINC id>.json", message)

    def test_leading_whitespace_before_html_is_still_caught(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen("\n  " + APP_SHELL)):
            with self.assertRaises(common.ChemicalSpaceError):
                common.get_json("anything.json")

    def test_real_json_is_returned(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen(SUBSTANCE)):
            self.assertEqual(common.get_json("substance/x.json")["zinc_id"], "ZINC000019632618")

    def test_unparseable_body_is_named_as_such(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen("{not json")):
            with self.assertRaises(common.ChemicalSpaceError) as caught:
                common.get_json("substance/x.json")
        self.assertIn("unparseable", str(caught.exception))


class IdentifierTests(unittest.TestCase):
    def test_short_form_is_padded_to_twelve_digits(self) -> None:
        self.assertEqual(common.normalise_zinc_id("ZINC53"), "ZINC000000000053")

    def test_bare_digits_are_accepted(self) -> None:
        self.assertEqual(common.normalise_zinc_id("53"), "ZINC000000000053")

    def test_already_padded_is_unchanged(self) -> None:
        self.assertEqual(
            common.normalise_zinc_id("ZINC000019632618"), "ZINC000019632618"
        )

    def test_lowercase_prefix_is_accepted(self) -> None:
        self.assertEqual(common.normalise_zinc_id("zinc53"), "ZINC000000000053")

    def test_nonsense_is_rejected_with_the_expected_shape(self) -> None:
        with self.assertRaises(common.ChemicalSpaceError) as caught:
            common.normalise_zinc_id("CHEMBL25")
        self.assertIn("ZINC000019632618", str(caught.exception))


class SummariseTests(unittest.TestCase):
    def test_purchasability_and_cheapest_price(self) -> None:
        row = common.summarise(SUBSTANCE)
        self.assertTrue(row["purchasable"])
        self.assertEqual(row["catalogs"], 2)
        self.assertEqual(row["min_price"], 240)

    def test_no_catalogs_is_not_purchasable(self) -> None:
        record = dict(SUBSTANCE, catalogs=[])
        row = common.summarise(record)
        self.assertFalse(row["purchasable"])
        self.assertIsNone(row["min_price"])

    def test_properties_come_from_the_tranche_block(self) -> None:
        row = common.summarise(SUBSTANCE)
        self.assertEqual(row["heavy_atoms"], 37)
        self.assertEqual(row["mwt"], 493.615)

    def test_missing_tranche_block_is_survivable(self) -> None:
        row = common.summarise({"zinc_id": "ZINC1", "smiles": "C"})
        self.assertIsNone(row["mwt"])


class SubstanceLookupTests(unittest.TestCase):
    def test_lookup_pads_the_identifier_in_the_url(self) -> None:
        urls: list[str] = []
        with mock.patch("urllib.request.urlopen", fake_urlopen(SUBSTANCE, urls=urls)):
            common.substance("ZINC53")
        self.assertIn("substance/ZINC000000000053.json", urls[0])

    def test_a_record_without_smiles_is_treated_as_missing(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen({"zinc_id": "x"})):
            with self.assertRaises(common.ChemicalSpaceError):
                common.substance("ZINC53")


class TrancheNamingTests(unittest.TestCase):
    """The bulk tree is addressed by heavy atoms and logP, not molecular weight."""

    def test_positive_logp_uses_a_p_prefix(self) -> None:
        self.assertEqual(space_plan.logp_code(2.0), "P200")

    def test_negative_logp_uses_an_m_prefix(self) -> None:
        self.assertEqual(space_plan.logp_code(-1.0), "M100")

    def test_zero_is_p000(self) -> None:
        self.assertEqual(space_plan.logp_code(0.0), "P000")

    def test_half_steps_are_encoded(self) -> None:
        self.assertEqual(space_plan.logp_code(2.5), "P250")

    def test_codes_span_the_window(self) -> None:
        codes = space_plan.tranche_codes(25, 25, 1.0, 2.0)
        self.assertEqual([code for _, _, code in codes], ["H25P100", "H25P150", "H25P200"])

    def test_heavy_atom_count_is_two_digit_padded(self) -> None:
        codes = space_plan.tranche_codes(4, 4, 0.0, 0.0)
        self.assertEqual(codes[0][2], "H04P000")

    def test_inverted_windows_are_rejected(self) -> None:
        with self.assertRaises(common.ChemicalSpaceError):
            space_plan.tranche_codes(30, 20, 0.0, 1.0)
        with self.assertRaises(common.ChemicalSpaceError):
            space_plan.tranche_codes(20, 30, 4.0, 1.0)


class CascadeTests(unittest.TestCase):
    def test_stage_parsing(self) -> None:
        self.assertEqual(space_plan.parse_stage("dock:0.01:3"), ("dock", 0.01, 3.0))

    def test_malformed_stage_is_rejected(self) -> None:
        for text in ("dock:0.01", "dock:0.01:3:4", "dock:abc:3"):
            with self.subTest(text=text):
                with self.assertRaises(common.ChemicalSpaceError):
                    space_plan.parse_stage(text)

    def test_keep_fraction_must_be_a_fraction(self) -> None:
        for text in ("dock:0:3", "dock:1.5:3", "dock:-0.1:3"):
            with self.subTest(text=text):
                with self.assertRaises(common.ChemicalSpaceError):
                    space_plan.parse_stage(text)

    def test_negative_seconds_are_rejected(self) -> None:
        with self.assertRaises(common.ChemicalSpaceError):
            space_plan.parse_stage("dock:0.5:-1")

    def test_default_cascade_reduces_a_billion_to_thousands(self) -> None:
        remaining = 1e9
        for _, keep, _ in space_plan.DEFAULT_CASCADE:
            remaining *= keep
        self.assertEqual(int(remaining), 6000)

    def test_default_cascade_keep_fractions_are_all_valid(self) -> None:
        for name, keep, seconds in space_plan.DEFAULT_CASCADE:
            with self.subTest(stage=name):
                self.assertTrue(0 < keep <= 1)
                self.assertGreaterEqual(seconds, 0)


class ScaleTests(unittest.TestCase):
    def test_documented_space_sizes(self) -> None:
        self.assertEqual(common.ZINC22_2D_COMPOUNDS, 54_900_000_000)
        self.assertEqual(common.ZINC22_3D_COMPOUNDS, 5_900_000_000)
        self.assertEqual(common.ENAMINE_REAL_SPACE, 94_000_000_000)

    def test_subsets_are_the_three_zinc22_trees(self) -> None:
        self.assertEqual(space_plan.SUBSETS, ("zinc-22a", "zinc-22b", "zinc-22c"))


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (cartblanche_lookup, ["substance", "ZINC53"]),
            (cartblanche_lookup, ["catalogs", "ZINC53"]),
            (space_plan, ["tranches"]),
            (space_plan, ["cascade", "--library-size", "1e6"]),
            (space_plan, ["strategy", "--library-size", "1e6"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_no_ids_is_an_error_not_an_empty_run(self) -> None:
        with self.assertRaises(common.ChemicalSpaceError):
            common.read_ids([], None)

    def test_bad_subset_is_rejected(self) -> None:
        args = space_plan.build_parser().parse_args(["tranches", "--subset", "zinc-22z"])
        with self.assertRaises(common.ChemicalSpaceError):
            space_plan.command_tranches(args)

    def test_default_output_format_is_tsv(self) -> None:
        args = space_plan.build_parser().parse_args(["strategy", "--library-size", "1e6"])
        self.assertEqual(args.output_format, "tsv")


if __name__ == "__main__":
    unittest.main()
