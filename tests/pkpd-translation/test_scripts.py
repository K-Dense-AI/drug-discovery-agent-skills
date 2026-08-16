"""Tests for the PK/PD translation scripts.

No network anywhere -- this skill is pure arithmetic. That makes it the one
place in the bundle where results can be checked against closed-form answers
rather than against wiring, so most of these assert real numbers: an analytic
one-compartment profile, the FDA Km conversions, and the steady-state
identities AUC(tau) = Dose/CL and Cavg = Dose/(CL*tau).
"""

from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "pkpd-translation"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


nca = _load("nca_script", "nca.py")
allometry = _load("allometry_script", "allometry.py")
# exposure_margin imports pk_compartmental by module name.
pk_compartmental = _load("pk_compartmental", "pk_compartmental.py")
exposure_margin = _load("exposure_margin_script", "exposure_margin.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


def one_compartment_profile(dose=100.0, volume=10.0, k=0.1):
    times = [0.25, 0.5, 1, 2, 4, 6, 8, 12, 18, 24, 36, 48]
    concentrations = [(dose / volume) * math.exp(-k * t) for t in times]
    return times, concentrations


class AnalyticNcaTests(unittest.TestCase):
    """An exact one-compartment case: CL=1, V=10, t-half=6.931, AUC=100."""

    def setUp(self) -> None:
        times, concentrations = one_compartment_profile()
        self.result = nca.analyse(times, concentrations, dose=100.0, route="iv")

    def test_clearance_is_exact(self) -> None:
        self.assertAlmostEqual(self.result["clearance"], 1.0, places=6)

    def test_volume_is_exact(self) -> None:
        self.assertAlmostEqual(self.result["vz"], 10.0, places=5)

    def test_half_life_is_exact(self) -> None:
        self.assertAlmostEqual(self.result["half_life"], math.log(2) / 0.1, places=6)

    def test_auc_infinity_is_exact(self) -> None:
        self.assertAlmostEqual(self.result["auc_0_inf"], 100.0, places=4)

    def test_mrt_is_the_reciprocal_of_k(self) -> None:
        self.assertAlmostEqual(self.result["mrt"], 10.0, places=4)

    def test_vss_equals_vz_for_one_compartment(self) -> None:
        self.assertAlmostEqual(self.result["vss"], 10.0, places=4)

    def test_c0_is_back_extrapolated_to_the_true_value(self) -> None:
        self.assertAlmostEqual(self.result["c0_back_extrapolated"], 10.0, places=6)

    def test_terminal_fit_is_perfect_on_a_pure_exponential(self) -> None:
        self.assertAlmostEqual(self.result["terminal_r2"], 1.0, places=9)


class TrapezoidTests(unittest.TestCase):
    def test_log_down_is_lower_than_linear_on_a_decaying_curve(self) -> None:
        """The whole reason for the log rule: linear cuts the corner above."""
        times, concentrations = one_compartment_profile()
        log_auc, _ = nca.auc_linear_log(times, concentrations)
        linear_auc, _ = nca.auc_linear(times, concentrations)
        self.assertLess(log_auc, linear_auc)

    def test_log_rule_is_exact_for_an_exponential(self) -> None:
        times = [0.0, 1.0, 2.0, 3.0]
        k = 0.5
        concentrations = [10 * math.exp(-k * t) for t in times]
        auc, _ = nca.auc_linear_log(times, concentrations)
        exact = (10 / k) * (1 - math.exp(-k * 3.0))
        self.assertAlmostEqual(auc, exact, places=9)

    def test_ascending_segments_use_the_linear_rule(self) -> None:
        auc, _ = nca.auc_linear_log([0.0, 2.0], [0.0, 10.0])
        self.assertAlmostEqual(auc, 10.0, places=9)


class NcaValidationTests(unittest.TestCase):
    def test_mismatched_lengths_are_rejected(self) -> None:
        args = nca.build_parser().parse_args(
            ["--times", "1,2,3", "--conc", "1,2", "--dose", "10"]
        )
        with self.assertRaises(nca.NcaError):
            nca.read_profile(args)

    def test_non_increasing_times_are_rejected(self) -> None:
        args = nca.build_parser().parse_args(
            ["--times", "1,3,2", "--conc", "3,2,1", "--dose", "10"]
        )
        with self.assertRaises(nca.NcaError):
            nca.read_profile(args)

    def test_negative_concentration_is_rejected(self) -> None:
        args = nca.build_parser().parse_args(
            ["--times", "1,2,3", "--conc", "3,-1,1", "--dose", "10"]
        )
        with self.assertRaises(nca.NcaError):
            nca.read_profile(args)

    def test_too_few_terminal_points_is_an_error_not_a_guess(self) -> None:
        with self.assertRaises(nca.NcaError):
            nca.terminal_slope([0.0, 1.0, 2.0], [10.0, 12.0, 11.0])

    def test_a_never_descending_profile_has_no_terminal_slope(self) -> None:
        with self.assertRaises(nca.NcaError):
            nca.terminal_slope([0.0, 1, 2, 3, 4], [1.0, 2, 3, 4, 5])

    def test_oral_route_labels_clearance_as_cl_over_f(self) -> None:
        times = [0.5, 1, 2, 4, 8, 12, 24]
        concentrations = [2.0, 3.5, 4.0, 3.0, 1.5, 0.8, 0.15]
        result = nca.analyse(times, concentrations, dose=100.0, route="oral")
        self.assertEqual(result["clearance_label"], "CL/F")
        self.assertEqual(result["volume_label"], "Vz/F")

    def test_oral_route_reports_no_vss(self) -> None:
        times = [0.5, 1, 2, 4, 8, 12, 24]
        concentrations = [2.0, 3.5, 4.0, 3.0, 1.5, 0.8, 0.15]
        result = nca.analyse(times, concentrations, dose=100.0, route="oral")
        self.assertIsNone(result["vss"])

    def test_oral_route_does_not_back_extrapolate(self) -> None:
        """Concentration at t=0 after an oral dose is genuinely zero."""
        times = [0.5, 1, 2, 4, 8, 12, 24]
        concentrations = [2.0, 3.5, 4.0, 3.0, 1.5, 0.8, 0.15]
        result = nca.analyse(times, concentrations, dose=100.0, route="oral")
        self.assertIsNone(result["c0_back_extrapolated"])

    def test_back_extrapolation_declines_when_still_absorbing(self) -> None:
        self.assertIsNone(nca.back_extrapolate_c0([0.5, 1.0], [2.0, 4.0]))


class HedTests(unittest.TestCase):
    """FDA 2005 Table 1. The published divisors are 12.3, 6.2, 3.1, and 1.8."""

    def test_rat_divides_by_about_six_point_two(self) -> None:
        self.assertAlmostEqual(allometry.human_equivalent_dose("rat", 50.0), 50 / 6.1667, places=3)

    def test_mouse_divides_by_about_twelve_point_three(self) -> None:
        self.assertAlmostEqual(allometry.human_equivalent_dose("mouse", 50.0), 50 / 12.333, places=3)

    def test_dog_divides_by_about_one_point_eight(self) -> None:
        self.assertAlmostEqual(allometry.human_equivalent_dose("dog", 50.0), 50 / 1.85, places=3)

    def test_monkey_divides_by_about_three_point_one(self) -> None:
        self.assertAlmostEqual(allometry.human_equivalent_dose("monkey", 50.0), 50 / 3.0833, places=3)

    def test_human_to_human_is_identity(self) -> None:
        self.assertAlmostEqual(allometry.human_equivalent_dose("human", 7.5), 7.5, places=9)

    def test_unknown_species_lists_the_known_ones(self) -> None:
        with self.assertRaises(allometry.AllometryError) as caught:
            allometry.resolve("axolotl")
        self.assertIn("mouse", str(caught.exception))

    def test_species_names_are_case_insensitive(self) -> None:
        self.assertEqual(allometry.resolve("RAT")["km"], 6)


class AllometricFitTests(unittest.TestCase):
    def test_a_perfect_three_quarter_power_law_is_recovered(self) -> None:
        points = [(w, 2.0 * w ** 0.75) for w in (0.02, 0.15, 10.0, 3.0)]
        fit = allometry.fit_allometry(points)
        self.assertAlmostEqual(fit["exponent"], 0.75, places=6)
        self.assertAlmostEqual(fit["coefficient"], 2.0, places=6)
        self.assertAlmostEqual(fit["r2"], 1.0, places=9)

    def test_one_species_cannot_define_an_exponent(self) -> None:
        with self.assertRaises(allometry.AllometryError):
            allometry.fit_allometry([(10.0, 5.0)])

    def test_conventional_exponents(self) -> None:
        self.assertEqual(allometry.EXPONENTS["clearance"], 0.75)
        self.assertEqual(allometry.EXPONENTS["volume"], 1.0)
        self.assertEqual(allometry.EXPONENTS["half_life"], 0.25)

    def test_pair_parsing(self) -> None:
        self.assertEqual(
            allometry.parse_pairs(["rat:1.8,dog:12"], "x"), [("rat", 1.8), ("dog", 12.0)]
        )

    def test_malformed_pair_is_rejected(self) -> None:
        with self.assertRaises(allometry.AllometryError):
            allometry.parse_pairs(["rat"], "x")

    def test_default_safety_factor_is_ten(self) -> None:
        self.assertEqual(allometry.DEFAULT_SAFETY_FACTOR, 10.0)


class CompartmentalTests(unittest.TestCase):
    def test_iv_bolus_starts_at_dose_over_volume(self) -> None:
        c = pk_compartmental.concentration(
            0.0, dose=100, clearance=5, volume=50, route="iv", ka=None,
            bioavailability=1.0, infusion_hours=1.0,
        )
        self.assertAlmostEqual(c, 2.0, places=9)

    def test_iv_bolus_halves_after_one_half_life(self) -> None:
        k = 5 / 50
        half_life = math.log(2) / k
        c = pk_compartmental.concentration(
            half_life, dose=100, clearance=5, volume=50, route="iv", ka=None,
            bioavailability=1.0, infusion_hours=1.0,
        )
        self.assertAlmostEqual(c, 1.0, places=9)

    def test_oral_starts_at_zero(self) -> None:
        c = pk_compartmental.concentration(
            0.0, dose=100, clearance=5, volume=50, route="oral", ka=1.0,
            bioavailability=1.0, infusion_hours=1.0,
        )
        self.assertAlmostEqual(c, 0.0, places=9)

    def test_oral_handles_ka_equal_to_k_without_dividing_by_zero(self) -> None:
        """The standard solution has (ka - k) in the denominator."""
        k = 5 / 50
        c = pk_compartmental.concentration(
            2.0, dose=100, clearance=5, volume=50, route="oral", ka=k,
            bioavailability=1.0, infusion_hours=1.0,
        )
        expected = (100 * k * 2.0 / 50) * math.exp(-k * 2.0)
        self.assertAlmostEqual(c, expected, places=9)

    def test_oral_without_ka_is_an_error(self) -> None:
        with self.assertRaises(pk_compartmental.PkError):
            pk_compartmental.concentration(
                1.0, dose=100, clearance=5, volume=50, route="oral", ka=None,
                bioavailability=1.0, infusion_hours=1.0,
            )

    def test_zero_volume_is_rejected(self) -> None:
        with self.assertRaises(pk_compartmental.PkError):
            pk_compartmental.elimination_rate(5.0, 0.0)

    def test_negative_time_is_zero(self) -> None:
        c = pk_compartmental.concentration(
            -1.0, dose=100, clearance=5, volume=50, route="iv", ka=None,
            bioavailability=1.0, infusion_hours=1.0,
        )
        self.assertEqual(c, 0.0)


class SteadyStateIdentityTests(unittest.TestCase):
    """AUC(tau) = Dose/CL and Cavg = Dose/(CL*tau), exactly, at steady state."""

    def setUp(self) -> None:
        parser = pk_compartmental.build_parser()
        self.args = parser.parse_args(
            ["steady", "--dose", "100", "--cl", "5", "--v", "50", "--tau", "24"]
        )
        self.result = pk_compartmental.steady_state(self.args)

    def test_auc_over_the_interval_equals_dose_over_clearance(self) -> None:
        self.assertAlmostEqual(self.result["auc_tau"], 100 / 5, places=3)

    def test_average_concentration_identity(self) -> None:
        self.assertAlmostEqual(self.result["css_avg"], 100 / (5 * 24), places=5)

    def test_accumulation_matches_the_closed_form(self) -> None:
        k = 5 / 50
        expected = 1 / (1 - math.exp(-k * 24))
        self.assertAlmostEqual(self.result["accumulation_ratio"], expected, places=9)

    def test_time_to_steady_state_is_about_four_point_three_half_lives(self) -> None:
        self.assertAlmostEqual(self.result["half_lives_to_95pct_ss"], 4.3219, places=3)

    def test_accumulation_does_not_depend_on_dose(self) -> None:
        parser = pk_compartmental.build_parser()
        big = parser.parse_args(
            ["steady", "--dose", "1000", "--cl", "5", "--v", "50", "--tau", "24"]
        )
        self.assertAlmostEqual(
            pk_compartmental.steady_state(big)["accumulation_ratio"],
            self.result["accumulation_ratio"],
            places=9,
        )

    def test_trough_is_below_the_average(self) -> None:
        self.assertLess(self.result["css_min"], self.result["css_avg"])
        self.assertGreater(self.result["css_max"], self.result["css_avg"])


class MarginTests(unittest.TestCase):
    def test_comfortable_margin_threshold(self) -> None:
        self.assertEqual(exposure_margin.COMFORTABLE_MARGIN, 10.0)

    def test_margin_requires_a_matched_pair(self) -> None:
        args = exposure_margin.build_parser().parse_args(["margin", "--tox-cmax", "100"])
        with self.assertRaises(pk_compartmental.PkError):
            exposure_margin.command_margin(args)

    def test_zero_efficacious_exposure_is_rejected(self) -> None:
        args = exposure_margin.build_parser().parse_args(
            ["margin", "--tox-cmax", "100", "--eff-cmax", "0"]
        )
        with self.assertRaises(pk_compartmental.PkError):
            exposure_margin.command_margin(args)


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (allometry, ["hed", "--species", "rat", "--dose", "10"]),
            (allometry, ["scale", "--data", "rat:1"]),
            (allometry, ["fih", "--noael", "rat:10"]),
            (pk_compartmental, ["steady", "--dose", "1", "--cl", "1", "--v", "1", "--tau", "1"]),
            (pk_compartmental, ["simulate", "--dose", "1", "--cl", "1", "--v", "1", "--tau", "1"]),
            (exposure_margin, ["margin", "--tox-cmax", "1", "--eff-cmax", "1"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_nca_defaults_to_iv(self) -> None:
        args = nca.build_parser().parse_args(["--dose", "10"])
        self.assertEqual(args.route, "iv")

    def test_default_fu_is_one_and_is_flagged(self) -> None:
        args = exposure_margin.build_parser().parse_args(
            ["coverage", "--dose", "1", "--cl", "1", "--v", "1", "--tau", "1", "--target-conc", "1"]
        )
        self.assertEqual(args.fu, 1.0)


if __name__ == "__main__":
    unittest.main()
