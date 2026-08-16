"""Tests for the REINVENT 4 helper scripts.

No network and no REINVENT install -- these scripts write the TOML REINVENT
reads and parse the CSV it writes. The parts worth testing are the
generator/input pairings that fail late and confusingly when wrong, the
transform bounding that prevents reward hacking, and the mode-collapse
detection that is the only way to see the default failure of an RL run.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "generative-design"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


reinvent_config = _load("reinvent_config_script", "reinvent_config.py")
scoring_profile = _load("scoring_profile_script", "scoring_profile.py")
parse_run = _load("parse_run_script", "parse_run.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


def staged_args(**overrides):
    argv = ["staged", "--generator", overrides.pop("generator", "reinvent")]
    for key, value in overrides.items():
        argv += [f"--{key.replace('_', '-')}", str(value)]
    return reinvent_config.build_parser().parse_args(argv)


class GeneratorInputTests(unittest.TestCase):
    """Pairing the wrong input with a generator fails late in REINVENT itself."""

    def test_reinvent_needs_no_input(self) -> None:
        self.assertIsNone(reinvent_config.validate_input("reinvent", staged_args()))

    def test_libinvent_requires_a_scaffold(self) -> None:
        with self.assertRaises(reinvent_config.ConfigError) as caught:
            reinvent_config.validate_input("libinvent", staged_args(generator="libinvent"))
        self.assertIn("--scaffold", str(caught.exception))

    def test_libinvent_scaffold_needs_an_attachment_point(self) -> None:
        args = staged_args(generator="libinvent", scaffold="c1ccccc1")
        with self.assertRaises(reinvent_config.ConfigError) as caught:
            reinvent_config.validate_input("libinvent", args)
        self.assertIn("[*]", str(caught.exception))

    def test_valid_libinvent_scaffold_passes(self) -> None:
        args = staged_args(generator="libinvent", scaffold="c1ccc([*])cc1")
        self.assertEqual(reinvent_config.validate_input("libinvent", args), "c1ccc([*])cc1")

    def test_linkinvent_needs_exactly_two_warheads(self) -> None:
        args = staged_args(generator="linkinvent", warheads="c1ccccc1[*]")
        with self.assertRaises(reinvent_config.ConfigError) as caught:
            reinvent_config.validate_input("linkinvent", args)
        self.assertIn("exactly two", str(caught.exception))

    def test_linkinvent_warheads_need_one_attachment_each(self) -> None:
        args = staged_args(generator="linkinvent", warheads="c1ccccc1[*]|CC")
        with self.assertRaises(reinvent_config.ConfigError) as caught:
            reinvent_config.validate_input("linkinvent", args)
        self.assertIn("exactly one", str(caught.exception))

    def test_valid_linkinvent_warheads_pass(self) -> None:
        args = staged_args(generator="linkinvent", warheads="c1ccccc1[*]|[*]CCN")
        self.assertTrue(reinvent_config.validate_input("linkinvent", args))

    def test_mol2mol_requires_smiles(self) -> None:
        with self.assertRaises(reinvent_config.ConfigError):
            reinvent_config.validate_input("mol2mol", staged_args(generator="mol2mol"))


class PriorTests(unittest.TestCase):
    def test_each_generator_has_a_default_prior(self) -> None:
        for name, spec in reinvent_config.GENERATORS.items():
            with self.subTest(generator=name):
                self.assertTrue(spec["prior"].endswith(".prior"))

    def test_mol2mol_prior_choice_sets_the_novelty_regime(self) -> None:
        args = staged_args(generator="mol2mol", smiles="CCO", mol2mol_prior="scaffold")
        self.assertIn("scaffold", reinvent_config.prior_for("mol2mol", args))

    def test_unknown_mol2mol_prior_is_rejected(self) -> None:
        args = staged_args(generator="mol2mol", smiles="CCO", mol2mol_prior="nonsense")
        with self.assertRaises(reinvent_config.ConfigError):
            reinvent_config.prior_for("mol2mol", args)

    def test_explicit_prior_overrides_the_default(self) -> None:
        args = staged_args(prior="my.prior")
        self.assertEqual(reinvent_config.prior_for("reinvent", args), "my.prior")

    def test_all_mol2mol_priors_are_distinct(self) -> None:
        paths = list(reinvent_config.MOL2MOL_PRIORS.values())
        self.assertEqual(len(paths), len(set(paths)))


class ScoringTransformTests(unittest.TestCase):
    """Every numeric component must be bounded, or the agent exploits it."""

    def test_molecular_weight_uses_a_two_sided_window(self) -> None:
        lines = "\n".join(scoring_profile.component_toml("MolecularWeight", 0.2, (250.0, 500.0)))
        self.assertIn('transform.type = "double_sigmoid"', lines)
        self.assertIn("transform.low = 250.0", lines)
        self.assertIn("transform.high = 500.0", lines)

    def test_qed_needs_no_transform(self) -> None:
        lines = "\n".join(scoring_profile.component_toml("QED", 0.3, None))
        self.assertNotIn("transform.type", lines)

    def test_custom_alerts_emits_smarts(self) -> None:
        lines = "\n".join(scoring_profile.component_toml("custom_alerts", 0.2, None))
        self.assertIn("params.smarts", lines)
        self.assertIn(scoring_profile.DEFAULT_ALERTS[0], lines)

    def test_unknown_component_is_rejected(self) -> None:
        with self.assertRaises(scoring_profile.ScoringError):
            scoring_profile.component_toml("NotAComponent", 1.0, None)

    def test_inverted_window_is_rejected(self) -> None:
        with self.assertRaises(scoring_profile.ScoringError):
            scoring_profile.component_toml("SlogP", 1.0, (5.0, 1.0))

    def test_every_numeric_component_declares_a_default_window(self) -> None:
        for name, spec in scoring_profile.COMPONENTS.items():
            with self.subTest(component=name):
                if spec["transform"] is not None:
                    self.assertIsNotNone(spec["window"], f"{name} is unbounded")

    def test_profiles_use_known_components(self) -> None:
        for objective, components in scoring_profile.PROFILES.items():
            for name in components:
                with self.subTest(objective=objective, component=name):
                    self.assertIn(name, scoring_profile.COMPONENTS)

    def test_every_profile_includes_a_structural_alert_veto(self) -> None:
        """Without it the agent rediscovers reactive chemistry."""
        for objective, components in scoring_profile.PROFILES.items():
            with self.subTest(objective=objective):
                self.assertIn("custom_alerts", components)

    def test_cns_profile_has_a_tight_tpsa_window(self) -> None:
        _, window = scoring_profile.PROFILES["cns"]["TPSA"]
        self.assertLessEqual(window[1], 90.0)

    def test_unknown_profile_is_rejected(self) -> None:
        args = scoring_profile.build_parser().parse_args(["profile"])
        args.objective = "nope"
        with self.assertRaises(scoring_profile.ScoringError):
            scoring_profile.command_profile(args)

    def test_weight_override_must_name_a_component_in_the_profile(self) -> None:
        args = scoring_profile.build_parser().parse_args(
            ["profile", "--objective", "fragment", "--weight", "QED=0.5"]
        )
        with self.assertRaises(scoring_profile.ScoringError):
            scoring_profile.command_profile(args)

    def test_step_transform_is_documented_as_gradient_free(self) -> None:
        self.assertIn("gradient", scoring_profile.TRANSFORMS["step"])


class RunParsingTests(unittest.TestCase):
    def test_ring_signature_groups_decorations_of_one_core(self) -> None:
        first = parse_run.ring_signature("c1ccccc1CC")
        second = parse_run.ring_signature("c1ccccc1CCC")
        self.assertEqual(first, second)

    def test_ring_signature_separates_different_cores(self) -> None:
        benzene = parse_run.ring_signature("c1ccccc1C")
        pyridine = parse_run.ring_signature("c1ccncc1C")
        self.assertNotEqual(benzene, pyridine)

    def test_collapse_threshold_is_documented(self) -> None:
        self.assertEqual(parse_run.COLLAPSE_SCAFFOLD_FRACTION, 0.05)

    def test_smiles_column_is_found_case_insensitively(self) -> None:
        self.assertEqual(parse_run.pick({"SMILES": 1}, parse_run.SMILES_COLUMNS), "SMILES")
        self.assertEqual(parse_run.pick({"smiles": 1}, parse_run.SMILES_COLUMNS), "smiles")

    def test_missing_column_returns_none(self) -> None:
        self.assertIsNone(parse_run.pick({"other": 1}, parse_run.SMILES_COLUMNS))

    def test_as_float_tolerates_junk(self) -> None:
        self.assertIsNone(parse_run.as_float("n/a"))
        self.assertEqual(parse_run.as_float("0.5"), 0.5)


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (reinvent_config, ["generators"]),
            (reinvent_config, ["sampling", "--generator", "reinvent"]),
            (reinvent_config, ["staged", "--generator", "reinvent"]),
            (scoring_profile, ["profile"]),
            (scoring_profile, ["component", "--name", "QED"]),
            (scoring_profile, ["transforms"]),
            (parse_run, ["summary", "--csv", "x.csv"]),
            (parse_run, ["top", "--csv", "x.csv"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_default_aggregation_is_geometric(self) -> None:
        args = scoring_profile.build_parser().parse_args(["profile"])
        self.assertEqual(args.aggregation, "geometric_mean")

    def test_default_learning_strategy_is_dap(self) -> None:
        args = staged_args()
        self.assertEqual(args.strategy, "dap")

    def test_diversity_filter_names_are_validated(self) -> None:
        args = staged_args(diversity_filter="NotAFilter")
        with self.assertRaises(reinvent_config.ConfigError):
            reinvent_config.command_staged(args)


if __name__ == "__main__":
    unittest.main()
