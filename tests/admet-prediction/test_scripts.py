"""Tests for the ADMET-AI helper scripts.

No network and no admet-ai install -- the scripts read what ADMET-AI wrote, so
the fixtures here are synthetic prediction CSVs. The parts worth testing are
the per-endpoint direction (high solubility is good, high clearance is bad),
the applicability-domain guardrails ADMET-AI does not provide, and the input
preparation that keeps a large run from wasting itself.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "admet-prediction"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


admet_report = _load("admet_report_script", "admet_report.py")
admet_batch = _load("admet_batch_script", "admet_batch.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

PREDICTIONS = """\
smiles,hERG,DILI,AMES,Solubility_AqSolDB,Lipophilicity_AstraZeneca,Half_Life_Obach,\
Clearance_Hepatocyte_AZ,BBB_Martins,molecular_weight,logP,hERG_drugbank_approved_percentile
CCO,0.05,0.10,0.08,-0.3,0.1,4.5,5.0,0.9,46.07,-0.1,3.2
CCCCc1ccc(Cl)cc1NC(=O)N,0.82,0.61,0.12,-5.4,4.6,1.9,35.0,0.8,273.7,3.9,91.4
"""


def write(tmp: Path, name: str, text: str) -> Path:
    path = tmp / name
    path.write_text(text, encoding="utf-8")
    return path


class DirectionTests(unittest.TestCase):
    """Each endpoint is flagged against its own direction; a summed score is meaningless."""

    def test_high_herg_is_a_liability(self) -> None:
        flagged, rule = admet_report.flag("hERG", 0.82)
        self.assertTrue(flagged)
        self.assertIn(">=", rule)

    def test_low_herg_is_not(self) -> None:
        self.assertFalse(admet_report.flag("hERG", 0.05)[0])

    def test_low_solubility_is_a_liability(self) -> None:
        """Solubility runs the other way: low is bad."""
        flagged, rule = admet_report.flag("Solubility_AqSolDB", -5.4)
        self.assertTrue(flagged)
        self.assertIn("<=", rule)

    def test_high_solubility_is_fine(self) -> None:
        self.assertFalse(admet_report.flag("Solubility_AqSolDB", -0.3)[0])

    def test_high_clearance_is_a_liability(self) -> None:
        self.assertTrue(admet_report.flag("Clearance_Hepatocyte_AZ", 35.0)[0])

    def test_short_half_life_is_a_liability(self) -> None:
        self.assertTrue(admet_report.flag("Half_Life_Obach", 1.9)[0])

    def test_long_half_life_is_fine(self) -> None:
        self.assertFalse(admet_report.flag("Half_Life_Obach", 12.0)[0])

    def test_bbb_has_no_direction_because_it_depends_on_the_target(self) -> None:
        self.assertIsNone(admet_report.ENDPOINTS["BBB_Martins"]["bad_high"])
        self.assertFalse(admet_report.flag("BBB_Martins", 0.99)[0])

    def test_missing_value_is_never_flagged(self) -> None:
        self.assertFalse(admet_report.flag("hERG", None)[0])

    def test_every_endpoint_declares_a_kind_and_a_label(self) -> None:
        for name, spec in admet_report.ENDPOINTS.items():
            with self.subTest(endpoint=name):
                self.assertIn(spec["kind"], ("classification", "regression"))
                self.assertTrue(spec["label"])
                self.assertTrue(spec["why"])

    def test_hard_stop_endpoints_are_present(self) -> None:
        for name in ("hERG", "AMES", "DILI", "Carcinogens_Lagunin"):
            self.assertIn(name, admet_report.ENDPOINTS)


class DomainTests(unittest.TestCase):
    """ADMET-AI reports no applicability domain, so the scripts add a proxy."""

    def test_small_molecule_is_out_of_domain(self) -> None:
        warnings = admet_report.domain_warnings({"molecular_weight": "46.07", "logP": "-0.1"})
        self.assertTrue(any("molecular_weight" in item for item in warnings))

    def test_drug_like_molecule_is_in_domain(self) -> None:
        self.assertEqual(
            admet_report.domain_warnings(
                {"molecular_weight": "350", "logP": "2.5", "tpsa": "70"}
            ),
            [],
        )

    def test_high_logp_is_flagged(self) -> None:
        warnings = admet_report.domain_warnings({"logP": "9.5"})
        self.assertTrue(any("logP" in item for item in warnings))

    def test_missing_physchem_columns_are_not_an_error(self) -> None:
        self.assertEqual(admet_report.domain_warnings({}), [])

    def test_documented_bounds(self) -> None:
        self.assertEqual(admet_report.PHYSCHEM_BOUNDS["molecular_weight"], (150.0, 700.0))
        self.assertEqual(admet_report.PHYSCHEM_BOUNDS["logP"], (-2.0, 6.0))


class ReadPredictionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_predictions_are_read(self) -> None:
        path = write(self.dir, "p.csv", PREDICTIONS)
        rows = admet_report.read_predictions(str(path))
        self.assertEqual(len(rows), 2)

    def test_a_csv_without_admet_columns_is_rejected_with_a_hint(self) -> None:
        path = write(self.dir, "wrong.csv", "a,b\n1,2\n")
        with self.assertRaises(admet_report.AdmetError) as caught:
            admet_report.read_predictions(str(path))
        self.assertIn("admet_predict", str(caught.exception))

    def test_an_empty_file_is_rejected(self) -> None:
        path = write(self.dir, "empty.csv", "smiles,hERG\n")
        with self.assertRaises(admet_report.AdmetError):
            admet_report.read_predictions(str(path))

    def test_unknown_endpoint_in_only_is_rejected(self) -> None:
        path = write(self.dir, "p.csv", PREDICTIONS)
        args = admet_report.build_parser().parse_args(
            ["report", "--csv", str(path), "--only", "NotAnEndpoint"]
        )
        with self.assertRaises(admet_report.AdmetError):
            admet_report.command_report(args)

    def test_percentile_column_naming(self) -> None:
        self.assertEqual(admet_report.PERCENTILE_SUFFIX, "_drugbank_approved_percentile")


class BatchPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_smi_file_is_read_with_identifiers(self) -> None:
        path = write(self.dir, "lib.smi", "CCO ethanol\nc1ccccc1 benzene\n")
        rows = admet_batch.read_smiles(str(path), None)
        self.assertEqual(rows, [("ethanol", "CCO"), ("benzene", "c1ccccc1")])

    def test_comments_and_blank_lines_are_skipped(self) -> None:
        path = write(self.dir, "lib.smi", "# header\n\nCCO x\n")
        self.assertEqual(len(admet_batch.read_smiles(str(path), None)), 1)

    def test_csv_smiles_column_is_found(self) -> None:
        path = write(self.dir, "lib.csv", "id,smiles\na,CCO\nb,CCC\n")
        rows = admet_batch.read_smiles(str(path), None)
        self.assertEqual([smiles for _, smiles in rows], ["CCO", "CCC"])

    def test_csv_without_a_smiles_column_is_rejected(self) -> None:
        path = write(self.dir, "bad.csv", "id,structure\na,CCO\n")
        with self.assertRaises(admet_batch.BatchError) as caught:
            admet_batch.read_smiles(str(path), None)
        self.assertIn("--smiles-column", str(caught.exception))

    def test_missing_file_is_rejected(self) -> None:
        with self.assertRaises(admet_batch.BatchError):
            admet_batch.read_smiles(str(self.dir / "nope.smi"), None)

    def test_duplicates_are_collapsed_and_salts_flagged(self) -> None:
        path = write(self.dir, "lib.smi", "CCO a\nCC(=O)O.[Na+] b\nCCO c\n")
        args = admet_batch.build_parser().parse_args(
            ["prepare", "--smiles", str(path), "--out-dir", str(self.dir / "in")]
        )
        admet_batch.command_prepare(args)
        manifest = json.loads((self.dir / "in" / "manifest.json").read_text())
        self.assertEqual(manifest["total_input"], 3)
        self.assertEqual(manifest["unique"], 2)
        self.assertEqual(manifest["duplicates_collapsed"], 1)
        self.assertEqual(manifest["mixtures"], ["b"])

    def test_chunking_splits_at_the_requested_size(self) -> None:
        path = write(self.dir, "big.smi", "\n".join(f"C{'C' * n} m{n}" for n in range(25)))
        args = admet_batch.build_parser().parse_args(
            [
                "prepare", "--smiles", str(path),
                "--out-dir", str(self.dir / "chunks"), "--chunk-size", "10",
            ]
        )
        admet_batch.command_prepare(args)
        manifest = json.loads((self.dir / "chunks" / "manifest.json").read_text())
        self.assertEqual(len(manifest["chunks"]), 3)
        self.assertEqual([c["molecules"] for c in manifest["chunks"]], [10, 10, 5])

    def test_written_chunks_have_a_header_row(self) -> None:
        """A headerless file silently loses its first molecule."""
        path = write(self.dir, "lib.smi", "CCO a\n")
        args = admet_batch.build_parser().parse_args(
            ["prepare", "--smiles", str(path), "--out-dir", str(self.dir / "h")]
        )
        admet_batch.command_prepare(args)
        first = (self.dir / "h" / "chunk_0000.csv").read_text().splitlines()
        self.assertEqual(first[0], "smiles")
        self.assertEqual(first[1], "CCO")

    def test_mixture_marker(self) -> None:
        self.assertEqual(admet_batch.MIXTURE_MARKER, ".")


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (admet_report, ["report", "--csv", "x.csv"]),
            (admet_report, ["summary", "--csv", "x.csv"]),
            (admet_report, ["endpoints"]),
            (admet_batch, ["prepare", "--smiles", "x.smi"]),
            (admet_batch, ["expand", "--input", "m.json", "--predictions", "p.csv"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_default_output_format_is_tsv(self) -> None:
        args = admet_report.build_parser().parse_args(["endpoints"])
        self.assertEqual(args.output_format, "tsv")

    def test_default_chunk_size(self) -> None:
        self.assertEqual(admet_batch.DEFAULT_CHUNK, 10_000)


if __name__ == "__main__":
    unittest.main()
