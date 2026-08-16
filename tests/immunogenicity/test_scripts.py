"""Tests for the immunogenicity scripts.

No network and no NetMHCIIpan install -- these scripts prepare its input and
parse its output. The parts worth testing are the header-driven output parser
(the format has varied between versions), the collapse of overlapping 15-mers
to distinct 9-mer cores, and the %Rank thresholding that must not be confused
with affinity.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "immunogenicity"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


epitope_scan = _load("epitope_scan_script", "epitope_scan.py")
ada_risk = _load("ada_risk_script", "ada_risk.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

NETMHCIIPAN_OUTPUT = """\
# NetMHCIIpan version 4.3
 Pos          MHC        Peptide      Of        Core  Core_Rel   Identity  Score_EL %Rank_EL
   1    DRB1_0101  EVQLVESGGGLVQPG       3   LVESGGGLV     0.850   Seq       0.5120     0.85
   1    DRB1_0401  EVQLVESGGGLVQPG       3   LVESGGGLV     0.810   Seq       0.4310     1.60
   1    DRB1_0701  EVQLVESGGGLVQPG       3   LVESGGGLV     0.790   Seq       0.3900     1.90
   2    DRB1_0101  VQLVESGGGLVQPGG       2   LVESGGGLV     0.840   Seq       0.5000     0.95
   5    DRB1_1101  ESGGGLVQPGGSLRL       4   GLVQPGGSL     0.700   Seq       0.1200    12.00
   7    DRB1_0301  GGGLVQPGGSLRLSC       1   QPGGSLRLS     0.660   Seq       0.2100     1.20
"""


def write(tmp: Path, name: str, text: str) -> Path:
    path = tmp / name
    path.write_text(text, encoding="utf-8")
    return path


class ThresholdTests(unittest.TestCase):
    """%Rank, not affinity: IC50 is not comparable between alleles."""

    def test_strong_and_weak_binder_conventions(self) -> None:
        self.assertEqual(epitope_scan.STRONG_BINDER_RANK, 2.0)
        self.assertEqual(epitope_scan.WEAK_BINDER_RANK, 10.0)

    def test_peptide_and_core_lengths(self) -> None:
        self.assertEqual(epitope_scan.PEPTIDE_LENGTH, 15)
        self.assertEqual(epitope_scan.CORE_LENGTH, 9)

    def test_reference_panel_is_class_two_drb1(self) -> None:
        for allele in epitope_scan.REFERENCE_ALLELES:
            with self.subTest(allele=allele):
                self.assertTrue(allele.startswith("DRB1_"))

    def test_panel_covers_the_common_alleles(self) -> None:
        for allele in ("DRB1_0101", "DRB1_0401", "DRB1_1501"):
            self.assertIn(allele, epitope_scan.REFERENCE_ALLELES)


class SequenceTests(unittest.TestCase):
    def test_fasta_header_is_stripped(self) -> None:
        self.assertEqual(epitope_scan.clean_sequence(">x\nEVQL\nVESG\n"), "EVQLVESG")

    def test_lowercase_is_accepted(self) -> None:
        self.assertEqual(epitope_scan.clean_sequence("evql"), "EVQL")

    def test_non_standard_residues_are_rejected(self) -> None:
        with self.assertRaises(epitope_scan.EpitopeError) as caught:
            epitope_scan.clean_sequence("EVQLX")
        self.assertIn("X", str(caught.exception))

    def test_empty_sequence_is_rejected(self) -> None:
        with self.assertRaises(epitope_scan.EpitopeError):
            epitope_scan.clean_sequence("")

    def test_a_sequence_shorter_than_the_window_is_rejected(self) -> None:
        args = epitope_scan.build_parser().parse_args(["peptides", "--sequence", "EVQL"])
        with self.assertRaises(epitope_scan.EpitopeError):
            epitope_scan.command_peptides(args)


class OutputParsingTests(unittest.TestCase):
    """Columns are located by header name because the format varies by version."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.path = write(self.dir, "out.txt", NETMHCIIPAN_OUTPUT)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_all_data_rows_are_parsed(self) -> None:
        records = epitope_scan.parse_output(str(self.path))
        self.assertEqual(len(records), 6)

    def test_rank_is_read_from_the_percent_rank_column(self) -> None:
        records = epitope_scan.parse_output(str(self.path))
        self.assertAlmostEqual(records[0]["rank"], 0.85)

    def test_allele_and_core_are_captured(self) -> None:
        records = epitope_scan.parse_output(str(self.path))
        self.assertEqual(records[0]["allele"], "DRB1_0101")
        self.assertEqual(records[0]["core"], "LVESGGGLV")

    def test_comment_lines_are_skipped(self) -> None:
        records = epitope_scan.parse_output(str(self.path))
        self.assertTrue(all(record["peptide"] for record in records))

    def test_a_file_without_a_header_is_rejected(self) -> None:
        path = write(self.dir, "bad.txt", "nothing useful here\n")
        with self.assertRaises(epitope_scan.EpitopeError) as caught:
            epitope_scan.parse_output(str(path))
        self.assertIn("NetMHCIIpan", str(caught.exception))

    def test_a_header_with_no_data_rows_is_rejected(self) -> None:
        path = write(self.dir, "empty.txt", " Pos MHC Peptide Core %Rank_EL\n")
        with self.assertRaises(epitope_scan.EpitopeError):
            epitope_scan.parse_output(str(path))

    def test_alternative_rank_column_name_is_found(self) -> None:
        text = " Pos MHC Peptide Core Rank\n 1 DRB1_0101 EVQLVESGGGLVQPG LVESGGGLV 0.5\n"
        path = write(self.dir, "alt.txt", text)
        self.assertEqual(len(epitope_scan.parse_output(str(path))), 1)


class CoreCollapseTests(unittest.TestCase):
    """Overlapping 15-mers share a 9-mer core; counting peptides overcounts."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.path = write(self.dir, "out.txt", NETMHCIIPAN_OUTPUT)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_four_binding_predictions_collapse_to_two_cores(self) -> None:
        """LVESGGGLV appears four times; QPGGSLRLS once; the rank-12 row is excluded."""
        records = epitope_scan.parse_output(str(self.path))
        binders = [r for r in records if r["rank"] <= epitope_scan.STRONG_BINDER_RANK]
        self.assertEqual(len(binders), 5)
        self.assertEqual(len({r["core"] for r in binders}), 2)

    def test_the_weak_binder_is_excluded_at_the_default_threshold(self) -> None:
        records = epitope_scan.parse_output(str(self.path))
        excluded = [r for r in records if r["rank"] > epitope_scan.STRONG_BINDER_RANK]
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]["core"], "GLVQPGGSL")

    def test_promiscuity_counts_distinct_alleles_not_peptides(self) -> None:
        records = epitope_scan.parse_output(str(self.path))
        binders = [r for r in records if r["rank"] <= 2.0 and r["core"] == "LVESGGGLV"]
        self.assertEqual(len(binders), 4)
        self.assertEqual(len({r["allele"] for r in binders}), 3)


class RiskScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.cores = write(
            self.dir,
            "cores.tsv",
            "core\texample_peptide\talleles_bound\tbest_rank\tpromiscuous\n"
            "LVESGGGLV\tEVQLVESGGGLVQPG\t3\t0.85\ttrue\n"
            "QPGGSLRLS\tGGGLVQPGGSLRLSC\t1\t1.20\tfalse\n",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_cores_are_read(self) -> None:
        records = ada_risk.read_cores(str(self.cores))
        self.assertEqual(len(records), 2)
        self.assertTrue(records[0]["promiscuous"])
        self.assertFalse(records[1]["promiscuous"])

    def test_a_table_without_a_core_column_is_rejected(self) -> None:
        path = write(self.dir, "bad.tsv", "foo\tbar\n1\t2\n")
        with self.assertRaises(ada_risk.RiskError) as caught:
            ada_risk.read_cores(str(path))
        self.assertIn("epitope_scan.py parse", str(caught.exception))

    def test_density_bands(self) -> None:
        self.assertEqual(ada_risk.band_for(0.5)[0], "low")
        self.assertEqual(ada_risk.band_for(2.0)[0], "moderate")
        self.assertEqual(ada_risk.band_for(3.0)[0], "elevated")
        self.assertEqual(ada_risk.band_for(9.0)[0], "high")

    def test_zero_length_is_rejected(self) -> None:
        args = ada_risk.build_parser().parse_args(
            ["score", "--cores", str(self.cores), "--length", "0"]
        )
        with self.assertRaises(ada_risk.RiskError):
            ada_risk.command_score(args)

    def test_low_humanness_becomes_the_dominant_risk(self) -> None:
        args = ada_risk.build_parser().parse_args(
            ["score", "--cores", str(self.cores), "--length", "120",
             "--humanness", "0.6", "--format", "json"]
        )
        ada_risk.command_score(args)  # must not raise

    def test_humanness_threshold(self) -> None:
        self.assertEqual(ada_risk.HUMANNESS_CONCERN, 0.85)

    def test_aggregation_is_named_the_largest_non_sequence_factor(self) -> None:
        self.assertIn("largest", ada_risk.FACTORS["aggregation"])

    def test_reference_rates_show_a_fully_human_antibody_with_high_ada(self) -> None:
        """Humanisation helps and does not decide it."""
        self.assertIn("adalimumab (fully human)", ada_risk.REFERENCE_RATES)
        self.assertIn("26%", ada_risk.REFERENCE_RATES["adalimumab (fully human)"])

    def test_glycosylation_is_listed_as_an_epitope_source(self) -> None:
        self.assertIn("glyc", ada_risk.FACTORS["glycosylation"].lower())


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (epitope_scan, ["peptides", "--sequence", "EVQL"]),
            (epitope_scan, ["parse", "--output", "x.txt"]),
            (epitope_scan, ["alleles"]),
            (ada_risk, ["score", "--cores", "c.tsv", "--length", "100"]),
            (ada_risk, ["factors"]),
            (ada_risk, ["context"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_default_rank_threshold_is_the_strong_binder_cut(self) -> None:
        args = epitope_scan.build_parser().parse_args(["parse", "--output", "x.txt"])
        self.assertEqual(args.rank_threshold, epitope_scan.STRONG_BINDER_RANK)

    def test_default_peptide_length_is_fifteen(self) -> None:
        args = epitope_scan.build_parser().parse_args(["peptides", "--sequence", "E"])
        self.assertEqual(args.length, 15)


if __name__ == "__main__":
    unittest.main()
