"""Tests for the antibody sequence-analysis scripts.

Two of the three scripts are standard-library only and are tested for real.
`number_antibody.py` needs ANARCI and HMMER, so its numbering path degrades to
a skip in the bare project environment and runs under
`tests/run_all.py --isolated`; the scheme tables and region logic around it are
pure data and are tested either way.

Trastuzumab is the fixture throughout because its liabilities are documented:
the CDR-H2 Asn55 deamidation site and the CDR-H3 Asp102-Gly isomerisation site.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "antibody-engineering"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


liabilities = _load("scan_liabilities_script", "scan_liabilities.py")
physchem = _load("physchem_profile_script", "physchem_profile.py")
numbering = _load("number_antibody_script", "number_antibody.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

TRASTUZUMAB_VH = (
    "EVQLVESGGGLVQPGGSLRLSCAASGFNIKDTYIHWVRQAPGKGLEWVARIYPTNGYTRYADSVKGRFTISADT"
    "SKNTAYLQMNSLRAEDTAVYYCSRWGGDGFYAMDYWGQGTLVTVSS"
)
TRASTUZUMAB_VL = (
    "DIQMTQSPSSLSASVGDRVTITCRASQDVNTAVAWYQQKPGKAPKLLIYSASFLYSGVPSRFSGSRSGTDFTLT"
    "ISSLQPEDFATYYCQQHYTTPPTFGQGTKVEIK"
)

# IMGT regions for the heavy chain above, as produced by number_antibody.py.
VH_REGIONS = [
    (1, 25, "FR1"),
    (26, 33, "CDRH1"),
    (34, 50, "FR2"),
    (51, 58, "CDRH2"),
    (59, 96, "FR3"),
    (97, 109, "CDRH3"),
    (110, 120, "FR4"),
]


class MotifDetectionTests(unittest.TestCase):
    def _findings(self, sequence: str, regions=()) -> list[dict]:
        return liabilities.scan("test", sequence, list(regions))

    def test_the_documented_trastuzumab_hotspots_are_found(self) -> None:
        findings = self._findings(TRASTUZUMAB_VH)
        motifs = {(item["liability"], item["position"]) for item in findings}
        self.assertIn(("deamidation (NG)", 55), motifs)
        self.assertIn(("isomerisation (DG)", 102), motifs)

    def test_an_n_glycosylation_sequon_is_found(self) -> None:
        findings = self._findings("AAANGTAAA")
        self.assertTrue(
            any(item["liability"] == "N-glycosylation sequon" for item in findings)
        )

    def test_proline_blocks_the_sequon(self) -> None:
        """N-X-S/T is only a sequon when X is not proline."""
        findings = self._findings("AAANPTAAA")
        self.assertFalse(
            any(item["liability"] == "N-glycosylation sequon" for item in findings)
        )

    def test_an_odd_cysteine_count_is_critical(self) -> None:
        findings = self._findings("ACACAC")
        unpaired = [item for item in findings if item["liability"] == "unpaired cysteine"]
        self.assertEqual(len(unpaired), 1)
        self.assertEqual(unpaired[0]["severity"], "critical")

    def test_an_even_cysteine_count_is_not_flagged_as_unpaired(self) -> None:
        findings = self._findings("ACACAA")
        self.assertFalse(
            any(item["liability"] == "unpaired cysteine" for item in findings)
        )

    def test_more_than_two_cysteine_pairs_is_noted(self) -> None:
        findings = self._findings("CACACACA")
        self.assertTrue(
            any(item["liability"] == "extra cysteine pair" for item in findings)
        )

    def test_n_terminal_pyroglutamate_only_matches_at_the_start(self) -> None:
        self.assertTrue(
            any(item["liability"] == "N-terminal pyroglutamate" for item in self._findings("QVQL"))
        )
        self.assertFalse(
            any(item["liability"] == "N-terminal pyroglutamate" for item in self._findings("AQVQL"))
        )

    def test_integrin_motifs_are_found(self) -> None:
        findings = self._findings("AAARGDAAA")
        self.assertTrue(any("RGD" in item["liability"] for item in findings))

    def test_findings_sort_by_severity_then_position(self) -> None:
        findings = self._findings(TRASTUZUMAB_VH)
        severities = [liabilities.SEVERITY_ORDER[item["severity"]] for item in findings]
        self.assertEqual(severities, sorted(severities, reverse=True))


class RegionWeightingTests(unittest.TestCase):
    """A liability in a CDR is materially worse than the same one in framework."""

    def test_a_cdr_hit_is_promoted(self) -> None:
        findings = liabilities.scan("vh", TRASTUZUMAB_VH, VH_REGIONS)
        by_position = {item["position"]: item for item in findings}
        self.assertEqual(by_position[55]["region"], "CDRH2")
        self.assertEqual(by_position[55]["severity"], "critical")

    def test_the_same_motif_outside_a_cdr_keeps_its_baseline(self) -> None:
        findings = liabilities.scan("vh", TRASTUZUMAB_VH, VH_REGIONS)
        framework = [
            item
            for item in findings
            if item["liability"] == "deamidation (NS/NT/NN/NA/ND/NH)"
            and item["region"].startswith("FR")
        ]
        self.assertTrue(framework)
        self.assertTrue(all(item["severity"] == "medium" for item in framework))

    def test_position_independent_motifs_are_not_promoted(self) -> None:
        regions = [(1, 10, "CDRH1")]
        findings = liabilities.scan("x", "QAAAAAAAAA", regions)
        pyro = next(
            item for item in findings if item["liability"] == "N-terminal pyroglutamate"
        )
        self.assertEqual(pyro["severity"], "low")

    def test_region_lookup_returns_empty_outside_every_range(self) -> None:
        self.assertEqual(liabilities.region_at(VH_REGIONS, 500), "")
        self.assertEqual(liabilities.region_at(VH_REGIONS, 55), "CDRH2")


class InputParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_multi_record_fasta(self) -> None:
        path = self.root / "ab.fasta"
        path.write_text(
            f">VH\n{TRASTUZUMAB_VH}\n>VL\n{TRASTUZUMAB_VL}\n", encoding="utf-8"
        )
        args = mock.Mock(paths=[str(path)], sequence=None)
        records = liabilities.read_sequences(args)
        self.assertEqual([name for name, _ in records], ["VH", "VL"])

    def test_a_csv_with_a_sequence_column(self) -> None:
        path = self.root / "ab.csv"
        path.write_text(f"name,sequence\nVH,{TRASTUZUMAB_VH}\n", encoding="utf-8")
        args = mock.Mock(paths=[str(path)], sequence=None)
        records = liabilities.read_sequences(args)
        self.assertEqual(records[0][0], "VH")

    def test_a_table_without_a_sequence_column_warns(self) -> None:
        path = self.root / "bad.csv"
        path.write_text("name,notes\nVH,hello\n", encoding="utf-8")
        args = mock.Mock(paths=[str(path)], sequence=None)
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            records = liabilities.read_sequences(args)
        self.assertEqual(records, [])
        self.assertIn("no sequence column", stderr.getvalue())

    def test_regions_round_trip_through_the_table_format(self) -> None:
        path = self.root / "regions.tsv"
        path.write_text(
            "name\tchain_type\tscheme\tregion\tstart\tend\tsequence\n"
            "VH\tH\timgt\tCDRH2\t51\t58\tIYPTNGYT\n",
            encoding="utf-8",
        )
        regions = liabilities.load_regions(path)
        self.assertEqual(regions["VH"], [(51, 58, "CDRH2")])


class LiabilityCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "ab.fasta"
        self.path.write_text(f">VH\n{TRASTUZUMAB_VH}\n", encoding="utf-8")

    def _run(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            code = liabilities.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_missing_regions_prompts_for_them(self) -> None:
        _, _, stderr = self._run([str(self.path)])
        self.assertIn("number_antibody.py", stderr)

    def test_min_severity_filters(self) -> None:
        _, all_output, _ = self._run([str(self.path), "--format", "tsv"])
        _, high_output, _ = self._run(
            [str(self.path), "--format", "tsv", "--min-severity", "high"]
        )
        self.assertLess(len(high_output.splitlines()), len(all_output.splitlines()))

    def test_the_scope_caveat_is_always_printed(self) -> None:
        _, _, stderr = self._run([str(self.path)])
        self.assertIn("Aggregation, viscosity", stderr)

    def test_a_nucleotide_sequence_is_flagged_as_suspicious(self) -> None:
        path = Path(self.directory.name) / "dna.fasta"
        path.write_text(">x\nATGCATGCATGCJJJ\n", encoding="utf-8")
        _, _, stderr = self._run([str(path)])
        self.assertIn("non-amino-acid", stderr)

    def test_no_input_is_an_error(self) -> None:
        code, _, _ = self._run([])
        self.assertEqual(code, 1)


class PhyschemTests(unittest.TestCase):
    def test_molecular_weight_is_in_the_right_range(self) -> None:
        weight = physchem.molecular_weight(TRASTUZUMAB_VH)
        self.assertTrue(12_500 < weight < 13_500, weight)

    def test_glycine_dipeptide_matches_the_hand_calculation(self) -> None:
        # 2 x 57.0519 + 18.0153
        self.assertAlmostEqual(physchem.molecular_weight("GG"), 132.1191, places=3)

    def test_net_charge_falls_as_ph_rises(self) -> None:
        charges = [physchem.net_charge(TRASTUZUMAB_VH, ph) for ph in (4, 7, 10)]
        self.assertTrue(charges[0] > charges[1] > charges[2])

    def test_net_charge_is_zero_at_the_isoelectric_point(self) -> None:
        pi = physchem.isoelectric_point(TRASTUZUMAB_VH)
        self.assertAlmostEqual(physchem.net_charge(TRASTUZUMAB_VH, pi), 0.0, places=2)

    def test_a_polylysine_is_basic_and_a_polyglutamate_acidic(self) -> None:
        self.assertGreater(physchem.isoelectric_point("K" * 20), 10.0)
        self.assertLess(physchem.isoelectric_point("E" * 20), 4.5)

    def test_extinction_uses_the_pace_coefficients(self) -> None:
        reduced, oxidised = physchem.extinction_coefficient("WWYYCC")
        self.assertEqual(reduced, 2 * 5500 + 2 * 1490)
        self.assertEqual(oxidised, reduced + 125)

    def test_gravy_is_positive_for_an_aliphatic_run(self) -> None:
        self.assertGreater(physchem.gravy("IIIVVV"), 0)
        self.assertLess(physchem.gravy("RRRKKK"), 0)

    def test_aliphatic_index_of_pure_alanine_is_one_hundred(self) -> None:
        self.assertAlmostEqual(physchem.aliphatic_index("A" * 10), 100.0)

    def test_profile_reports_the_charge_column_for_the_requested_ph(self) -> None:
        row = physchem.profile("x", TRASTUZUMAB_VH, 6.0)
        self.assertIn("netCharge_pH6", row)


class PhyschemCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "ab.fasta"
        self.path.write_text(
            f">VH\n{TRASTUZUMAB_VH}\n>VL\n{TRASTUZUMAB_VL}\n", encoding="utf-8"
        )

    def _run(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            code = physchem.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_combine_adds_a_row(self) -> None:
        _, without, _ = self._run([str(self.path), "--format", "tsv"])
        _, with_combined, _ = self._run([str(self.path), "--format", "tsv", "--combine"])
        self.assertEqual(
            len(with_combined.splitlines()), len(without.splitlines()) + 1
        )

    def test_a_pi_near_the_formulation_ph_warns(self) -> None:
        _, _, stderr = self._run([str(self.path)])
        self.assertIn("colloidal stability", stderr)

    def test_an_odd_cysteine_count_warns(self) -> None:
        path = Path(self.directory.name) / "odd.fasta"
        path.write_text(">x\nACDEFGHIKC C\n".replace(" ", "") + "\n", encoding="utf-8")
        _, _, stderr = self._run([str(path)])
        self.assertIn("odd number of cysteines", stderr)

    def test_the_pka_set_is_stated(self) -> None:
        _, _, stderr = self._run([str(self.path)])
        self.assertIn("EMBOSS", stderr)

    def test_charge_curve_prints_a_range_of_ph_values(self) -> None:
        _, stdout, _ = self._run([str(self.path), "--charge-curve"])
        self.assertIn("pH3:", stdout)
        self.assertIn("pH11:", stdout)


class NumberingTableTests(unittest.TestCase):
    """The scheme tables are pure data and testable without ANARCI."""

    def test_imgt_uses_the_same_cdrs_for_both_chains(self) -> None:
        imgt = numbering.CDR_DEFINITIONS["imgt"]
        self.assertEqual(imgt["H"], imgt["L"])

    def test_kabat_and_chothia_differ_on_cdr_h1(self) -> None:
        self.assertNotEqual(
            numbering.CDR_DEFINITIONS["kabat"]["H"][0],
            numbering.CDR_DEFINITIONS["chothia"]["H"][0],
        )

    def test_region_lookup_places_positions_correctly(self) -> None:
        self.assertEqual(numbering.region_of(1, "H", "imgt"), "FR1")
        self.assertEqual(numbering.region_of(30, "H", "imgt"), "CDRH1")
        self.assertEqual(numbering.region_of(45, "H", "imgt"), "FR2")
        self.assertEqual(numbering.region_of(60, "H", "imgt"), "CDRH2")
        self.assertEqual(numbering.region_of(80, "H", "imgt"), "FR3")
        self.assertEqual(numbering.region_of(110, "H", "imgt"), "CDRH3")
        self.assertEqual(numbering.region_of(125, "H", "imgt"), "FR4")

    def test_light_chains_use_the_l_labels(self) -> None:
        self.assertEqual(numbering.region_of(30, "L", "imgt"), "CDRL1")

    def test_kabat_boundaries_are_applied(self) -> None:
        self.assertEqual(numbering.region_of(33, "H", "kabat"), "CDRH1")
        self.assertEqual(numbering.region_of(33, "H", "chothia"), "FR2")

    def test_every_scheme_defines_three_cdrs_per_chain_type(self) -> None:
        for scheme, definitions in numbering.CDR_DEFINITIONS.items():
            for chain_type, ranges in definitions.items():
                with self.subTest(scheme=scheme, chain=chain_type):
                    self.assertEqual(len(ranges), 3)
                    self.assertTrue(all(start < end for start, end in ranges))


class NumberingRunTests(unittest.TestCase):
    """The ANARCI path, when ANARCI and HMMER are actually present."""

    @classmethod
    def setUpClass(cls) -> None:
        import shutil

        try:
            import anarci  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("anarci is not installed")
        if not shutil.which("hmmscan"):
            raise unittest.SkipTest("HMMER (hmmscan) is not on PATH")

    def _run(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            code = numbering.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_imgt_cdrs_of_a_known_antibody(self) -> None:
        code, stdout, _ = self._run(["--sequence", TRASTUZUMAB_VH])
        self.assertEqual(code, 0)
        self.assertIn("GFNIKDTY", stdout)
        self.assertIn("SRWGGDGFYAMDY", stdout)

    def test_kabat_gives_the_other_documented_cdrs(self) -> None:
        _, stdout, _ = self._run(["--sequence", TRASTUZUMAB_VH, "--scheme", "kabat"])
        self.assertIn("DTYIH", stdout)
        self.assertIn("WGGDGFYAMDY", stdout)

    def test_a_light_chain_is_identified_as_kappa(self) -> None:
        _, stdout, _ = self._run(["--sequence", TRASTUZUMAB_VL])
        self.assertIn("chain K", stdout)

    def test_regions_output_covers_the_whole_domain_without_overlap(self) -> None:
        _, stdout, _ = self._run(["--sequence", TRASTUZUMAB_VH, "--format", "regions"])
        rows = [line.split("\t") for line in stdout.strip().splitlines()[1:]]
        spans = sorted((int(row[4]), int(row[5])) for row in rows)
        self.assertEqual(spans[0][0], 1)
        for (_, previous_end), (next_start, _) in zip(spans, spans[1:]):
            self.assertEqual(next_start, previous_end + 1)

    def test_a_non_antibody_sequence_is_reported_not_crashed(self) -> None:
        code, stdout, stderr = self._run(["--sequence", "M" * 60])
        self.assertEqual(code, 1)
        self.assertIn("did not align", stdout + stderr)

    def test_the_scheme_is_stated_in_the_output(self) -> None:
        _, _, stderr = self._run(["--sequence", TRASTUZUMAB_VH])
        self.assertIn("IMGT", stderr)


if __name__ == "__main__":
    unittest.main()
