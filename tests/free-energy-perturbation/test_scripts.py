"""Tests for the OpenFE planning and analysis helpers.

No network and no OpenFE install. This skill's arithmetic is checkable in
closed form, so most of these assert real numbers: the circuit rank that
counts how many independent validation checks a network supports, and cycle
closure -- the state-function identity that is FEP's only assumption-free
error estimate.
"""

from __future__ import annotations

import importlib.util
import math
import sys
import tempfile
import unittest
from pathlib import Path

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "free-energy-perturbation"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


fep_network = _load("fep_network_script", "fep_network.py")
fep_report = _load("fep_report_script", "fep_report.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

LIGANDS = ["a", "b", "c", "d", "e"]


def write_edges(directory: Path, rows: list[tuple], header="ligand_a\tligand_b\tddg\tuncertainty"):
    path = directory / "ddg.tsv"
    lines = [header] + ["\t".join(str(item) for item in row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class NetworkShapeTests(unittest.TestCase):
    def test_star_has_n_minus_one_edges(self) -> None:
        edges = fep_network.star_edges(LIGANDS, "a")
        self.assertEqual(len(edges), len(LIGANDS) - 1)

    def test_star_has_no_cycles(self) -> None:
        """A star forfeits the only internal error check FEP has."""
        edges = fep_network.star_edges(LIGANDS, "a")
        self.assertEqual(fep_network.count_independent_cycles(LIGANDS, edges), 0)

    def test_cyclic_network_gives_independent_checks(self) -> None:
        edges = fep_network.cyclic_edges(LIGANDS, "a")
        cycles = fep_network.count_independent_cycles(LIGANDS, edges)
        self.assertEqual(len(edges), 8)
        self.assertEqual(cycles, 8 - len(LIGANDS) + 1)
        self.assertEqual(cycles, 4)

    def test_complete_network_edge_count(self) -> None:
        n = len(LIGANDS)
        edges = fep_network.complete_edges(LIGANDS, "a")
        self.assertEqual(len(edges), n * (n - 1) // 2)

    def test_circuit_rank_matches_the_formula(self) -> None:
        for shape, builder in fep_network.BUILDERS.items():
            with self.subTest(shape=shape):
                edges = builder(LIGANDS, "a")
                expected = len(edges) - len(LIGANDS) + 1
                self.assertEqual(
                    fep_network.count_independent_cycles(LIGANDS, edges), expected
                )

    def test_disconnected_nodes_count_as_components(self) -> None:
        names = ["a", "b", "c", "d"]
        edges = [("a", "b"), ("c", "d")]
        self.assertEqual(fep_network.count_independent_cycles(names, edges), 0)

    def test_two_ligand_cyclic_network_stays_a_single_edge(self) -> None:
        edges = fep_network.cyclic_edges(["a", "b"], "a")
        self.assertEqual(len(edges), 1)

    def test_reference_must_be_in_the_set(self) -> None:
        with self.assertRaises(fep_network.NetworkError):
            fep_network.star_edges(LIGANDS, "zzz")


class LigandInputTests(unittest.TestCase):
    def test_one_ligand_is_refused(self) -> None:
        args = fep_network.build_parser().parse_args(["plan", "--ligands", "a"])
        with self.assertRaises(fep_network.NetworkError):
            fep_network.read_ligands(args)

    def test_duplicate_names_are_refused(self) -> None:
        args = fep_network.build_parser().parse_args(["plan", "--ligands", "a,b,a"])
        with self.assertRaises(fep_network.NetworkError):
            fep_network.read_ligands(args)

    def test_names_are_parsed_from_a_comma_list(self) -> None:
        args = fep_network.build_parser().parse_args(["plan", "--ligands", "a, b ,c"])
        self.assertEqual(fep_network.read_ligands(args), ["a", "b", "c"])

    def test_documented_cost_defaults(self) -> None:
        self.assertEqual(fep_network.DEFAULT_HOURS_PER_EDGE, 24.0)
        self.assertEqual(fep_network.DEFAULT_REPEATS, 3)


class CycleClosureTests(unittest.TestCase):
    """The state-function identity: a loop must sum to zero."""

    def test_a_perfect_cycle_closes_at_zero(self) -> None:
        edges = [
            {"ligand_a": "a", "ligand_b": "b", "ddg": 1.0, "uncertainty": 0.1},
            {"ligand_a": "b", "ligand_b": "c", "ddg": 1.0, "uncertainty": 0.1},
            {"ligand_a": "c", "ligand_b": "a", "ddg": -2.0, "uncertainty": 0.1},
        ]
        table = fep_report.edge_lookup(edges)
        self.assertAlmostEqual(fep_report.cycle_closure(["a", "b", "c"], table), 0.0, places=9)

    def test_hysteresis_is_reported_exactly(self) -> None:
        edges = [
            {"ligand_a": "a", "ligand_b": "b", "ddg": 1.0, "uncertainty": 0.2},
            {"ligand_a": "b", "ligand_b": "c", "ddg": 1.0, "uncertainty": 0.3},
            {"ligand_a": "c", "ligand_b": "a", "ddg": -1.5, "uncertainty": 0.2},
        ]
        table = fep_report.edge_lookup(edges)
        self.assertAlmostEqual(fep_report.cycle_closure(["a", "b", "c"], table), 0.5, places=9)

    def test_reverse_direction_is_negated(self) -> None:
        edges = [{"ligand_a": "a", "ligand_b": "b", "ddg": 1.5, "uncertainty": None}]
        table = fep_report.edge_lookup(edges)
        self.assertEqual(table[("a", "b")], 1.5)
        self.assertEqual(table[("b", "a")], -1.5)

    def test_a_missing_edge_makes_the_cycle_uncomputable(self) -> None:
        table = fep_report.edge_lookup(
            [{"ligand_a": "a", "ligand_b": "b", "ddg": 1.0, "uncertainty": None}]
        )
        self.assertIsNone(fep_report.cycle_closure(["a", "b", "c"], table))

    def test_cycles_are_found_in_a_triangle(self) -> None:
        edges = [
            {"ligand_a": "a", "ligand_b": "b", "ddg": 1.0, "uncertainty": None},
            {"ligand_a": "b", "ligand_b": "c", "ddg": 1.0, "uncertainty": None},
            {"ligand_a": "c", "ligand_b": "a", "ddg": -2.0, "uncertainty": None},
        ]
        self.assertEqual(len(fep_report.find_cycles(edges)), 1)

    def test_a_star_yields_no_cycles(self) -> None:
        edges = [
            {"ligand_a": "a", "ligand_b": name, "ddg": 1.0, "uncertainty": None}
            for name in ("b", "c", "d")
        ]
        self.assertEqual(fep_report.find_cycles(edges), [])

    def test_documented_thresholds(self) -> None:
        self.assertEqual(fep_report.POOR_CYCLE_CLOSURE, 1.0)
        self.assertEqual(fep_report.HIGH_UNCERTAINTY, 1.0)


class ResultsParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_tsv_is_read(self) -> None:
        path = write_edges(self.dir, [("a", "b", 1.0, 0.2)])
        edges = fep_report.read_edges(str(path))
        self.assertEqual(edges[0]["ddg"], 1.0)
        self.assertEqual(edges[0]["uncertainty"], 0.2)

    def test_alternative_column_names_are_accepted(self) -> None:
        path = write_edges(
            self.dir, [("a", "b", 1.0, 0.2)], header="from\tto\testimate\terror"
        )
        self.assertEqual(len(fep_report.read_edges(str(path))), 1)

    def test_a_table_without_a_ddg_column_is_rejected(self) -> None:
        path = write_edges(self.dir, [("a", "b")], header="ligand_a\tligand_b")
        with self.assertRaises(fep_report.ReportError) as caught:
            fep_report.read_edges(str(path))
        self.assertIn("openfe gather", str(caught.exception))

    def test_missing_uncertainty_column_is_tolerated(self) -> None:
        path = write_edges(self.dir, [("a", "b", 1.0)], header="ligand_a\tligand_b\tddg")
        self.assertIsNone(fep_report.read_edges(str(path))[0]["uncertainty"])

    def test_unparseable_rows_are_skipped_not_fatal(self) -> None:
        path = write_edges(self.dir, [("a", "b", "n/a", 0.1), ("b", "c", 1.0, 0.1)])
        self.assertEqual(len(fep_report.read_edges(str(path))), 1)


class ExperimentalConversionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_rt_constant(self) -> None:
        self.assertAlmostEqual(fep_report.RT_KCAL, 0.5924, places=4)

    def test_ic50_converts_by_rt_ln(self) -> None:
        path = self.dir / "exp.tsv"
        path.write_text("ligand\tic50\na\t1e-9\n", encoding="utf-8")
        values = fep_report.read_experimental(str(path))
        self.assertAlmostEqual(values["a"], fep_report.RT_KCAL * math.log(1e-9), places=6)

    def test_explicit_dg_is_used_directly(self) -> None:
        path = self.dir / "exp.tsv"
        path.write_text("ligand\tdg\na\t-12.3\n", encoding="utf-8")
        self.assertAlmostEqual(fep_report.read_experimental(str(path))["a"], -12.3)

    def test_a_table_with_no_usable_values_is_rejected(self) -> None:
        path = self.dir / "exp.tsv"
        path.write_text("ligand\tnotes\na\thello\n", encoding="utf-8")
        with self.assertRaises(fep_report.ReportError):
            fep_report.read_experimental(str(path))

    def test_a_table_without_a_ligand_column_is_rejected(self) -> None:
        path = self.dir / "exp.tsv"
        path.write_text("thing\tdg\na\t-1\n", encoding="utf-8")
        with self.assertRaises(fep_report.ReportError):
            fep_report.read_experimental(str(path))


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (fep_network, ["plan", "--ligands", "a,b"]),
            (fep_network, ["cost", "--edges", "10"]),
            (fep_network, ["shapes"]),
            (fep_report, ["edges", "--results", "x.tsv"]),
            (fep_report, ["cycles", "--results", "x.tsv"]),
            (fep_report, ["rank", "--results", "x.tsv"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_default_shape_is_cyclic_so_validation_is_available(self) -> None:
        args = fep_network.build_parser().parse_args(["plan", "--ligands", "a,b"])
        self.assertEqual(args.shape, "cyclic")

    def test_default_repeats_is_three(self) -> None:
        args = fep_network.build_parser().parse_args(["cost", "--edges", "1"])
        self.assertEqual(args.repeats, 3)


if __name__ == "__main__":
    unittest.main()
