"""Tests for the oligonucleotide design scripts.

No network. Like pkpd-translation, this skill's core is arithmetic that can be
checked in closed form: the nearest-neighbour thermodynamics reproduce the
SantaLucia (1998) published worked example exactly, and the gapmer architecture
has a hard constraint (RNase H needs a DNA gap) whose violation is otherwise
silent.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "oligonucleotides"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


shared = _load("_shared", "_shared.py")
oligo_design = _load("oligo_design_script", "oligo_design.py")
offtarget_scan = _load("offtarget_scan_script", "offtarget_scan.py")
chemistry_plan = _load("chemistry_plan_script", "chemistry_plan.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


class SantaLuciaTests(unittest.TestCase):
    """The published worked example: CGTTGA gives dH -41.2, dS -115.4."""

    def test_published_enthalpy(self) -> None:
        delta_h, _ = oligo_design.thermodynamics("CGTTGA")
        self.assertAlmostEqual(delta_h, -41.2, places=6)

    def test_published_entropy(self) -> None:
        _, delta_s = oligo_design.thermodynamics("CGTTGA")
        self.assertAlmostEqual(delta_s, -115.4, places=6)

    def test_initiation_terms_are_applied_per_terminus(self) -> None:
        """CGTTGA has a G/C 5' end and an A/T 3' end, so one of each."""
        stack_h = sum(
            oligo_design.NEAREST_NEIGHBOUR[pair][0]
            for pair in ("CG", "GT", "TT", "TG", "GA")
        )
        total_h, _ = oligo_design.thermodynamics("CGTTGA")
        self.assertAlmostEqual(
            total_h - stack_h,
            oligo_design.INIT_GC[0] + oligo_design.INIT_AT[0],
            places=9,
        )

    def test_complementary_dinucleotides_share_parameters(self) -> None:
        for first, second in (("AA", "TT"), ("CA", "TG"), ("GT", "AC"), ("GG", "CC")):
            with self.subTest(pair=(first, second)):
                self.assertEqual(
                    oligo_design.NEAREST_NEIGHBOUR[first],
                    oligo_design.NEAREST_NEIGHBOUR[second],
                )

    def test_all_sixteen_dinucleotides_are_covered(self) -> None:
        for first in "ACGT":
            for second in "ACGT":
                with self.subTest(pair=first + second):
                    self.assertIn(first + second, oligo_design.NEAREST_NEIGHBOUR)

    def test_gc_rich_duplex_melts_higher(self) -> None:
        gc_rich = oligo_design.melting_temperature("GCGCGCGCGCGC")
        at_rich = oligo_design.melting_temperature("ATATATATATAT")
        self.assertGreater(gc_rich, at_rich)

    def test_longer_duplex_melts_higher(self) -> None:
        short = oligo_design.melting_temperature("ACGTACGTAC")
        long = oligo_design.melting_temperature("ACGTACGTACGTACGTACGT")
        self.assertGreater(long, short)

    def test_zero_concentration_is_rejected(self) -> None:
        with self.assertRaises(shared.OligoError):
            oligo_design.melting_temperature("ACGTACGT", 0.0)

    def test_a_single_base_has_no_duplex(self) -> None:
        with self.assertRaises(shared.OligoError):
            oligo_design.thermodynamics("A")


class SequenceHandlingTests(unittest.TestCase):
    def test_uracil_is_mapped_to_thymine(self) -> None:
        self.assertEqual(shared.clean_sequence("ACGU"), "ACGT")

    def test_fasta_headers_and_whitespace_are_stripped(self) -> None:
        self.assertEqual(shared.clean_sequence(">name desc\nACGT\nACGT\n"), "ACGTACGT")

    def test_lowercase_is_accepted(self) -> None:
        self.assertEqual(shared.clean_sequence("acgt"), "ACGT")

    def test_degenerate_codes_are_rejected(self) -> None:
        with self.assertRaises(shared.OligoError) as caught:
            shared.clean_sequence("ACGTN")
        self.assertIn("N", str(caught.exception))

    def test_empty_input_is_rejected(self) -> None:
        with self.assertRaises(shared.OligoError):
            shared.clean_sequence("")

    def test_reverse_complement(self) -> None:
        self.assertEqual(shared.reverse_complement("ACGT"), "ACGT")
        self.assertEqual(shared.reverse_complement("AAAA"), "TTTT")
        self.assertEqual(shared.reverse_complement("ATGGC"), "GCCAT")

    def test_seed_is_antisense_positions_two_to_eight(self) -> None:
        self.assertEqual(shared.SEED_START, 1)
        self.assertEqual(shared.SEED_END, 8)
        self.assertEqual(offtarget_scan.seed_of("ACGTACGTACGT"), "CGTACGT")

    def test_too_short_for_a_seed_is_an_error(self) -> None:
        with self.assertRaises(shared.OligoError):
            offtarget_scan.seed_of("ACGT")


class DesignRuleTests(unittest.TestCase):
    def test_gc_fraction(self) -> None:
        self.assertAlmostEqual(oligo_design.gc_fraction("GCAT"), 0.5)
        self.assertAlmostEqual(oligo_design.gc_fraction("GGGG"), 1.0)

    def test_longest_homopolymer(self) -> None:
        self.assertEqual(oligo_design.longest_homopolymer("AACCCGT"), 3)
        self.assertEqual(oligo_design.longest_homopolymer("ACGT"), 1)
        self.assertEqual(oligo_design.longest_homopolymer("GGGGG"), 5)

    def test_gc_window_is_two_sided(self) -> None:
        """Too stable is as bad as too weak; RISC must unwind the duplex."""
        low, high = oligo_design.GC_WINDOW
        self.assertLess(low, high)
        self.assertAlmostEqual(low, 0.30)
        self.assertAlmostEqual(high, 0.60)

    def test_a_gc_rich_candidate_is_flagged(self) -> None:
        sense = "GCGCGCGCGCGCGCGCGCGCG"
        row = oligo_design.evaluate(shared.reverse_complement(sense), sense, "sirna")
        self.assertFalse(row["passes"])
        self.assertTrue(any(flag.startswith("gc_") for flag in row["flags"]))

    def test_a_poly_g_candidate_is_flagged(self) -> None:
        sense = "ACGTGGGGACGTACGTACGTA"
        row = oligo_design.evaluate(shared.reverse_complement(sense), sense, "sirna")
        self.assertIn("poly_g_quadruplex", row["flags"])

    def test_asymmetry_is_reported_for_sirna_only(self) -> None:
        sense = "ACGTACGTACGTACGTACGTA"
        antisense = shared.reverse_complement(sense)
        self.assertIn("asymmetry", oligo_design.evaluate(antisense, sense, "sirna"))
        self.assertNotIn("asymmetry", oligo_design.evaluate(antisense, sense, "aso"))

    def test_wrong_strand_loading_is_flagged(self) -> None:
        """A stable antisense 5' end means RISC loads the sense strand."""
        sense = "ATTTTTTTTTTTTTTTTGCGC"
        antisense = shared.reverse_complement(sense)
        row = oligo_design.evaluate(antisense, sense, "sirna")
        self.assertLessEqual(row["asymmetry"], 0)
        self.assertIn("wrong_strand_loaded", row["flags"])

    def test_end_stability_uses_the_terminal_window(self) -> None:
        value = oligo_design.end_stability("GCGCGCGC", window=5)
        expected = sum(oligo_design.NEAREST_NEIGHBOUR["GCGCGCGC"[i : i + 2]][0] for i in range(4))
        self.assertAlmostEqual(value, expected)

    def test_a_sequence_shorter_than_the_window_is_rejected(self) -> None:
        args = oligo_design.build_parser().parse_args(
            ["tile", "--sequence", "ACGTACGT", "--modality", "sirna"]
        )
        with self.assertRaises(shared.OligoError):
            oligo_design.command_tile(args)


class FastaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_multi_record_fasta(self) -> None:
        path = self.dir / "tx.fa"
        path.write_text(">tx1 desc\nACGT\nACGT\n>tx2\nTTTT\n")
        records = shared.read_fasta(str(path))
        self.assertEqual(records, {"tx1": "ACGTACGT", "tx2": "TTTT"})

    def test_ambiguity_codes_are_dropped_not_fatal(self) -> None:
        """A real transcriptome has N runs; one bad record must not stop a scan."""
        path = self.dir / "tx.fa"
        path.write_text(">tx1\nACGTNNNNACGT\n")
        self.assertEqual(shared.read_fasta(str(path))["tx1"], "ACGTACGT")

    def test_an_empty_fasta_is_an_error(self) -> None:
        path = self.dir / "empty.fa"
        path.write_text("")
        with self.assertRaises(shared.OligoError):
            shared.read_fasta(str(path))


class ContiguousMatchTests(unittest.TestCase):
    def test_full_match_is_the_whole_length(self) -> None:
        self.assertEqual(offtarget_scan.longest_common_substring("ACGTACGT", "TTACGTACGTTT"), 8)

    def test_partial_match(self) -> None:
        self.assertEqual(offtarget_scan.longest_common_substring("ACGTACGT", "TTTACGTTTT"), 5)

    def test_no_match_is_zero(self) -> None:
        self.assertEqual(offtarget_scan.longest_common_substring("AAAA", "GGGG"), 0)

    def test_rnase_h_liability_threshold(self) -> None:
        self.assertEqual(offtarget_scan.DEFAULT_MIN_CONTIG, 12)


class GapmerTests(unittest.TestCase):
    """RNase H needs a DNA gap; without one the failure is completely silent."""

    def test_minimum_gap_is_documented(self) -> None:
        self.assertEqual(chemistry_plan.MIN_GAP, 8)

    def test_a_short_gap_is_refused(self) -> None:
        args = chemistry_plan.build_parser().parse_args(
            ["gapmer", "--sequence", "GCTAGCTACGTAGC", "--wing-length", "5"]
        )
        with self.assertRaises(shared.OligoError) as caught:
            chemistry_plan.command_gapmer(args)
        message = str(caught.exception)
        self.assertIn("RNase H", message)
        self.assertIn("does nothing", message)

    def test_a_valid_five_ten_five_gapmer_is_accepted(self) -> None:
        args = chemistry_plan.build_parser().parse_args(
            ["gapmer", "--sequence", "GCTAGCTACGTAGCTAGCTA", "--wing-length", "5"]
        )
        chemistry_plan.command_gapmer(args)  # must not raise

    def test_an_unknown_wing_chemistry_is_refused(self) -> None:
        args = chemistry_plan.build_parser().parse_args(
            ["gapmer", "--sequence", "GCTAGCTACGTAGCTAGCTA"]
        )
        args.wing = "nonsense"
        with self.assertRaises(shared.OligoError):
            chemistry_plan.command_gapmer(args)

    def test_every_wing_chemistry_blocks_rnase_h(self) -> None:
        for code in chemistry_plan.WING_CHEMISTRIES:
            with self.subTest(chemistry=code):
                self.assertIn("blocks RNase H", chemistry_plan.CHEMISTRY[code]["costs"])

    def test_phosphorothioate_records_both_sides_of_the_trade(self) -> None:
        spec = chemistry_plan.CHEMISTRY["ps"]
        self.assertIn("uptake", spec["buys"])
        self.assertIn("thrombocytopenia", spec["costs"])

    def test_galnac_is_recorded_as_liver_restricted(self) -> None:
        self.assertIn("liver", chemistry_plan.CHEMISTRY["galnac"]["costs"])


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (oligo_design, ["tile", "--sequence", "ACGT"]),
            (oligo_design, ["tm", "--sequence", "ACGT"]),
            (oligo_design, ["rules"]),
            (offtarget_scan, ["seeds", "--antisense", "ACGT", "--fasta", "x.fa"]),
            (offtarget_scan, ["contig", "--antisense", "ACGT", "--fasta", "x.fa"]),
            (chemistry_plan, ["gapmer", "--sequence", "ACGT"]),
            (chemistry_plan, ["sirna", "--sense", "ACGT", "--antisense", "ACGT"]),
            (chemistry_plan, ["chemistry"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_default_modality_is_sirna(self) -> None:
        args = oligo_design.build_parser().parse_args(["tile", "--sequence", "ACGT"])
        self.assertEqual(args.modality, "sirna")

    def test_default_wing_is_moe(self) -> None:
        args = chemistry_plan.build_parser().parse_args(["gapmer", "--sequence", "ACGT"])
        self.assertEqual(args.wing, "moe")

    def test_no_sequence_is_an_error(self) -> None:
        args = oligo_design.build_parser().parse_args(["tm"])
        with self.assertRaises(shared.OligoError):
            oligo_design.read_sequence(args)


if __name__ == "__main__":
    unittest.main()
