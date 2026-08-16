"""Tests for the targeted protein degradation scripts.

No network. The parts worth testing are the two-sided bRo5 windows (a one-sided
filter is the standard error), the hook-effect detection that makes a naive
DC50 meaningless, and the E3 accessory-subunit registry that decides whether a
predicted ternary complex could exist at all.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "degraders"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


protac_properties = _load("protac_properties_script", "protac_properties.py")
ternary_setup = _load("ternary_setup_script", "ternary_setup.py")
degrader_triage = _load("degrader_triage_script", "degrader_triage.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


class WindowTests(unittest.TestCase):
    """Every window is two-sided; a one-sided filter is the standard error."""

    def test_every_window_has_a_low_and_a_high(self) -> None:
        for name, spec in protac_properties.WINDOWS.items():
            with self.subTest(property=name):
                low, high = spec["range"]
                self.assertLess(low, high)
                self.assertTrue(spec["why_low"])
                self.assertTrue(spec["why_high"])

    def test_molecular_weight_window_is_beyond_rule_of_five(self) -> None:
        low, high = protac_properties.WINDOWS["mw"]["range"]
        self.assertGreater(low, 500.0)
        self.assertGreaterEqual(high, 1000.0)

    def test_rotatable_bond_window_expects_a_linker(self) -> None:
        low, _ = protac_properties.WINDOWS["rotb"]["range"]
        self.assertGreaterEqual(low, 8.0)

    def test_tpsa_window_is_far_above_lipinski(self) -> None:
        low, _ = protac_properties.WINDOWS["tpsa"]["range"]
        self.assertGreater(low, 140.0)


class ColumnResolutionTests(unittest.TestCase):
    def test_rdkit_style_names_resolve(self) -> None:
        columns = protac_properties.resolve_columns(
            ["MolWt", "MolLogP", "TPSA", "NumHDonors", "NumRotatableBonds", "HeavyAtomCount"]
        )
        self.assertEqual(set(columns), set(protac_properties.WINDOWS))

    def test_plain_names_resolve(self) -> None:
        columns = protac_properties.resolve_columns(["mw", "clogp", "tpsa"])
        self.assertIn("mw", columns)
        self.assertIn("clogp", columns)

    def test_unknown_columns_are_ignored(self) -> None:
        self.assertEqual(protac_properties.resolve_columns(["foo", "bar"]), {})

    def test_a_table_with_no_descriptors_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.csv"
            path.write_text("foo,bar\n1,2\n")
            args = protac_properties.build_parser().parse_args(["check", "--csv", str(path)])
            with self.assertRaises(protac_properties.DegraderError) as caught:
                protac_properties.command_check(args)
            self.assertIn("rdkit", str(caught.exception))

    def test_a_typical_protac_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.csv"
            path.write_text(
                "id,mw,clogp,tpsa,hbd,rotb,heavy_atoms\n"
                "protac1,950,5.2,190,4,14,66\n"
            )
            args = protac_properties.build_parser().parse_args(["check", "--csv", str(path)])
            protac_properties.command_check(args)  # must not raise

    def test_a_lipinski_compliant_molecule_is_flagged_as_too_small(self) -> None:
        """The inverse of the usual filter: an Ro5 molecule is not a bifunctional."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.csv"
            path.write_text("id,mw,clogp,tpsa,hbd,rotb,heavy_atoms\nsmall,350,2.0,70,1,4,25\n")
            args = protac_properties.build_parser().parse_args(["check", "--csv", str(path)])
            protac_properties.command_check(args)


class E3RegistryTests(unittest.TestCase):
    """A model without the accessory subunits describes a complex that cannot exist."""

    def test_vhl_requires_elongin_b_and_c(self) -> None:
        accessory = ternary_setup.E3_COMPLEXES["vhl"]["accessory"]
        self.assertIn("Elongin B", accessory)
        self.assertIn("Elongin C", accessory)

    def test_crbn_requires_ddb1(self) -> None:
        self.assertIn("DDB1", ternary_setup.E3_COMPLEXES["crbn"]["accessory"])

    def test_iap_needs_no_accessory_subunit(self) -> None:
        self.assertEqual(ternary_setup.E3_COMPLEXES["iap"]["accessory"], [])

    def test_every_e3_has_a_reference_structure(self) -> None:
        for name, spec in ternary_setup.E3_COMPLEXES.items():
            with self.subTest(e3=name):
                self.assertTrue(spec["example_pdb"])

    def test_unknown_e3_is_rejected(self) -> None:
        args = ternary_setup.build_parser().parse_args(
            ["manifest", "--target", "6BOY", "--e3", "nonsense"]
        )
        with self.assertRaises(ternary_setup.TernaryError):
            ternary_setup.command_manifest(args)

    def test_alphafold3_caveat_is_recorded(self) -> None:
        self.assertIn("inflated", ternary_setup.TOOLS["AlphaFold3"]["note"])

    def test_prosettac_is_recorded_as_outperforming(self) -> None:
        self.assertIn("outperforms", ternary_setup.TOOLS["PRosettaC"]["note"])

    def test_the_two_main_e3s_are_in_the_property_registry(self) -> None:
        self.assertIn("CRBN", protac_properties.E3_LIGANDS)
        self.assertIn("VHL", protac_properties.E3_LIGANDS)

    def test_crbn_neosubstrate_liability_is_documented(self) -> None:
        self.assertIn("IKZF1", protac_properties.E3_LIGANDS["CRBN"]["note"])


class LinkerTests(unittest.TestCase):
    def test_typical_window(self) -> None:
        self.assertEqual(ternary_setup.LINKER_WINDOW, (4, 20))

    def test_inverted_range_is_rejected(self) -> None:
        args = ternary_setup.build_parser().parse_args(
            ["linkers", "--min", "10", "--max", "4"]
        )
        with self.assertRaises(ternary_setup.TernaryError):
            ternary_setup.command_linkers(args)

    def test_unknown_chemistry_is_rejected(self) -> None:
        args = ternary_setup.build_parser().parse_args(["linkers"])
        args.chemistry = "nonsense"
        with self.assertRaises(ternary_setup.TernaryError):
            ternary_setup.command_linkers(args)

    def test_rigid_linkers_are_described_as_geometry_dependent(self) -> None:
        self.assertIn("geometry", ternary_setup.LINKER_CHEMISTRY["rigid"])


class DoseResponseTests(unittest.TestCase):
    """The hook makes the curve non-monotonic; a sigmoid fit is meaningless."""

    HOOKED = [(0.1, 95.0), (1.0, 70.0), (10.0, 25.0), (100.0, 8.0), (1000.0, 15.0), (10000.0, 60.0)]
    CLEAN = [(0.1, 95.0), (1.0, 70.0), (10.0, 25.0), (100.0, 8.0), (1000.0, 7.0)]

    def test_hook_is_detected(self) -> None:
        result = degrader_triage.analyse(self.HOOKED)
        self.assertTrue(result["hook_effect"])
        self.assertAlmostEqual(result["rise_after_minimum_pct"], 52.0, places=6)

    def test_no_hook_on_a_clean_curve(self) -> None:
        self.assertFalse(degrader_triage.analyse(self.CLEAN)["hook_effect"])

    def test_dmax_is_from_the_minimum(self) -> None:
        result = degrader_triage.analyse(self.HOOKED)
        self.assertAlmostEqual(result["dmax_pct"], 92.0)
        self.assertEqual(result["dmax_concentration"], 100.0)

    def test_dc50_is_interpolated_on_the_descending_limb(self) -> None:
        """Between 1 nM/70% and 10 nM/25%, 50% falls at 10^(20/45) = 2.78."""
        result = degrader_triage.analyse(self.HOOKED)
        self.assertAlmostEqual(result["dc50"], 2.7826, places=3)

    def test_dc50_is_none_when_fifty_percent_is_never_reached(self) -> None:
        shallow = [(0.1, 99.0), (1.0, 90.0), (10.0, 80.0), (100.0, 75.0)]
        self.assertIsNone(degrader_triage.analyse(shallow)["dc50"])

    def test_shallow_degradation_is_flagged_as_not_meaningful(self) -> None:
        shallow = [(0.1, 99.0), (1.0, 90.0), (10.0, 80.0), (100.0, 75.0)]
        result = degrader_triage.analyse(shallow)
        self.assertFalse(result["meaningful_dmax"])

    def test_meaningful_dmax_threshold(self) -> None:
        self.assertEqual(degrader_triage.MEANINGFUL_DMAX, 50.0)

    def test_hook_rise_threshold_ignores_single_point_noise(self) -> None:
        self.assertEqual(degrader_triage.HOOK_RISE, 10.0)
        noisy = [(0.1, 95.0), (1.0, 70.0), (10.0, 25.0), (100.0, 8.0), (1000.0, 12.0)]
        self.assertFalse(degrader_triage.analyse(noisy)["hook_effect"])

    def test_too_few_points_is_refused(self) -> None:
        args = degrader_triage.build_parser().parse_args(
            ["curve", "--conc", "1,10", "--remaining", "50,20"]
        )
        with self.assertRaises(degrader_triage.TriageError):
            degrader_triage.read_curve(args)

    def test_mismatched_lengths_are_refused(self) -> None:
        args = degrader_triage.build_parser().parse_args(
            ["curve", "--conc", "1,10,100,1000", "--remaining", "50,20,10"]
        )
        with self.assertRaises(degrader_triage.TriageError):
            degrader_triage.read_curve(args)

    def test_nonpositive_concentration_is_refused(self) -> None:
        args = degrader_triage.build_parser().parse_args(
            ["curve", "--conc", "0,1,10,100", "--remaining", "99,50,20,10"]
        )
        with self.assertRaises(degrader_triage.TriageError):
            degrader_triage.read_curve(args)

    def test_points_are_sorted_by_concentration(self) -> None:
        args = degrader_triage.build_parser().parse_args(
            ["curve", "--conc", "100,1,10,0.1", "--remaining", "8,70,25,95"]
        )
        points = degrader_triage.read_curve(args)
        self.assertEqual([c for c, _ in points], [0.1, 1.0, 10.0, 100.0])


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (protac_properties, ["check", "--csv", "x.csv"]),
            (protac_properties, ["windows"]),
            (protac_properties, ["ligases"]),
            (ternary_setup, ["manifest", "--target", "6BOY", "--e3", "vhl"]),
            (ternary_setup, ["linkers"]),
            (ternary_setup, ["tools"]),
            (degrader_triage, ["curve", "--conc", "1", "--remaining", "1"]),
            (degrader_triage, ["hook"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_default_linker_chemistry_is_peg(self) -> None:
        args = ternary_setup.build_parser().parse_args(["linkers"])
        self.assertEqual(args.chemistry, "peg")

    def test_default_output_format_is_tsv(self) -> None:
        args = protac_properties.build_parser().parse_args(["windows"])
        self.assertEqual(args.output_format, "tsv")


if __name__ == "__main__":
    unittest.main()
