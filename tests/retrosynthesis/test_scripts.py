"""Tests for the AiZynthFinder helper scripts.

No network and no aizynthfinder install -- these scripts write the YAML it
reads and parse the JSON it writes. The parts worth testing are the version-4
config schema (version 3 configs fail unhelpfully), the file-existence check
that saves a wasted run, and the route-tree walk that turns a nested JSON
structure into step counts and starting materials.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "retrosynthesis"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


aizynth_config = _load("aizynth_config_script", "aizynth_config.py")
route_report = _load("route_report_script", "route_report.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


def two_step_tree():
    """TARGET <- A + B, and B <- C + D. Three distinct leaves, all in stock."""
    return {
        "type": "mol", "smiles": "TARGET", "in_stock": False,
        "children": [{"type": "reaction", "children": [
            {"type": "mol", "smiles": "A", "in_stock": True},
            {"type": "mol", "smiles": "B", "in_stock": False, "children": [
                {"type": "reaction", "children": [
                    {"type": "mol", "smiles": "C", "in_stock": True},
                    {"type": "mol", "smiles": "D", "in_stock": True},
                ]},
            ]},
        ]}],
    }


def one_step_tree():
    return {
        "type": "mol", "smiles": "T2", "in_stock": False,
        "children": [{"type": "reaction", "children": [
            {"type": "mol", "smiles": "E", "in_stock": True},
        ]}],
    }


def write_output(directory: Path, records: list[dict], *, gzipped=True) -> Path:
    columns: dict[str, dict] = {}
    for index, record in enumerate(records):
        for key, value in record.items():
            columns.setdefault(key, {})[str(index)] = value
    document = {"data": columns}
    path = directory / ("out.json.gz" if gzipped else "out.json")
    opener = gzip.open if gzipped else open
    with opener(path, "wt", encoding="utf-8") as handle:
        json.dump(document, handle)
    return path


class ConfigTests(unittest.TestCase):
    def test_stock_parsing(self) -> None:
        self.assertEqual(aizynth_config.parse_stock("zinc:z.hdf5"), ("zinc", "z.hdf5"))

    def test_stock_without_a_colon_is_rejected(self) -> None:
        with self.assertRaises(aizynth_config.ConfigError) as caught:
            aizynth_config.parse_stock("zinc")
        self.assertIn("name:path", str(caught.exception))

    def test_empty_stock_half_is_rejected(self) -> None:
        with self.assertRaises(aizynth_config.ConfigError):
            aizynth_config.parse_stock("zinc:")

    def test_documented_algorithms(self) -> None:
        self.assertEqual(aizynth_config.ALGORITHMS, ("mcts", "retrostar", "dfpn"))

    def test_stock_backends_are_documented(self) -> None:
        for backend in ("inchiset", "mongodb", "molbloom"):
            self.assertIn(backend, aizynth_config.STOCK_TYPES)

    def test_defaults_match_the_documentation(self) -> None:
        self.assertEqual(aizynth_config.DEFAULT_TIME_LIMIT, 120)
        self.assertEqual(aizynth_config.DEFAULT_MAX_TRANSFORMS, 6)


class ConfigCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_missing_config_is_an_error(self) -> None:
        args = aizynth_config.build_parser().parse_args(
            ["check", "--config", str(self.dir / "nope.yml")]
        )
        with self.assertRaises(aizynth_config.ConfigError):
            aizynth_config.command_check(args)

    def test_a_file_without_expansion_is_rejected(self) -> None:
        path = self.dir / "bad.yml"
        path.write_text("something: else\n")
        args = aizynth_config.build_parser().parse_args(["check", "--config", str(path)])
        with self.assertRaises(aizynth_config.ConfigError) as caught:
            aizynth_config.command_check(args)
        self.assertIn("expansion", str(caught.exception))

    def test_missing_referenced_files_are_reported(self) -> None:
        path = self.dir / "config.yml"
        path.write_text(
            "expansion:\n  uspto:\n    type: template-based\n"
            "    model: absent_model.onnx\n    template: absent_templates.csv.gz\n"
        )
        args = aizynth_config.build_parser().parse_args(["check", "--config", str(path)])
        with self.assertRaises(aizynth_config.ConfigError) as caught:
            aizynth_config.command_check(args)
        self.assertIn("absent_model.onnx", str(caught.exception))

    def test_present_files_pass(self) -> None:
        (self.dir / "m.onnx").write_text("x")
        (self.dir / "t.csv.gz").write_text("x")
        path = self.dir / "config.yml"
        path.write_text(
            "expansion:\n  uspto:\n    type: template-based\n"
            "    model: m.onnx\n    template: t.csv.gz\n"
        )
        args = aizynth_config.build_parser().parse_args(["check", "--config", str(path)])
        aizynth_config.command_check(args)  # must not raise


class RouteWalkTests(unittest.TestCase):
    def test_step_count(self) -> None:
        self.assertEqual(route_report.route_stats(two_step_tree())["steps"], 2)

    def test_distinct_starting_materials(self) -> None:
        stats = route_report.route_stats(two_step_tree())
        self.assertEqual(stats["distinct_starting_materials"], 3)
        self.assertEqual(stats["leaves"], ["A", "C", "D"])

    def test_leaves_in_stock_counted(self) -> None:
        self.assertEqual(route_report.route_stats(two_step_tree())["leaves_in_stock"], 3)

    def test_a_one_step_route(self) -> None:
        stats = route_report.route_stats(one_step_tree())
        self.assertEqual(stats["steps"], 1)
        self.assertEqual(stats["distinct_starting_materials"], 1)

    def test_a_bare_molecule_has_no_steps(self) -> None:
        stats = route_report.route_stats({"type": "mol", "smiles": "X", "in_stock": True})
        self.assertEqual(stats["steps"], 0)
        self.assertEqual(stats["leaves"], ["X"])

    def test_out_of_stock_leaf_is_not_counted(self) -> None:
        tree = {
            "type": "mol", "smiles": "T", "in_stock": False,
            "children": [{"type": "reaction", "children": [
                {"type": "mol", "smiles": "A", "in_stock": True},
                {"type": "mol", "smiles": "B", "in_stock": False},
            ]}],
        }
        self.assertEqual(route_report.route_stats(tree)["leaves_in_stock"], 1)

    def test_deep_route_threshold(self) -> None:
        self.assertEqual(route_report.DEEP_ROUTE, 6)


class OutputLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_gzipped_column_major_output_is_read(self) -> None:
        path = write_output(
            self.dir,
            [{"target": "TARGET", "is_solved": True, "trees": [two_step_tree()]}],
        )
        records = route_report.load(str(path))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["target"], "TARGET")

    def test_plain_json_is_read_too(self) -> None:
        path = write_output(
            self.dir, [{"target": "T", "is_solved": True, "trees": []}], gzipped=False
        )
        self.assertEqual(len(route_report.load(str(path))), 1)

    def test_a_plain_list_is_accepted(self) -> None:
        path = self.dir / "list.json"
        path.write_text(json.dumps([{"target": "T", "is_solved": False}]))
        self.assertEqual(len(route_report.load(str(path))), 1)

    def test_unrecognised_json_is_rejected_with_a_hint(self) -> None:
        path = self.dir / "wrong.json"
        path.write_text(json.dumps({"something": "else"}))
        with self.assertRaises(route_report.RouteError) as caught:
            route_report.load(str(path))
        self.assertIn("aizynthcli", str(caught.exception))

    def test_missing_file_is_an_error(self) -> None:
        with self.assertRaises(route_report.RouteError):
            route_report.load(str(self.dir / "nope.json.gz"))

    def test_solved_fraction_across_two_targets(self) -> None:
        path = write_output(
            self.dir,
            [
                {"target": "A", "is_solved": True, "trees": [two_step_tree()], "search_time": 3.0},
                {"target": "B", "is_solved": False, "trees": [], "search_time": 120.0},
            ],
        )
        records = route_report.load(str(path))
        solved = [r for r in records if route_report.as_bool(r.get("is_solved"))]
        self.assertEqual(len(solved), 1)

    def test_as_bool_handles_strings_and_booleans(self) -> None:
        for value in (True, "True", "true", "1", "yes"):
            self.assertTrue(route_report.as_bool(value))
        for value in (False, "False", "0", "", None):
            self.assertFalse(route_report.as_bool(value))

    def test_trees_falls_back_to_top_score_routes(self) -> None:
        record = {"top_score_routes": [one_step_tree()]}
        self.assertEqual(len(route_report.trees_of(record)), 1)

    def test_missing_trees_is_empty_not_an_error(self) -> None:
        self.assertEqual(route_report.trees_of({}), [])


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (aizynth_config, ["config", "--model", "m", "--templates", "t", "--stock", "z:p"]),
            (aizynth_config, ["check", "--config", "c.yml"]),
            (aizynth_config, ["stocks"]),
            (route_report, ["summary", "--output", "o.json.gz"]),
            (route_report, ["routes", "--output", "o.json.gz"]),
            (route_report, ["blocks", "--output", "o.json.gz"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_config_requires_a_stock(self) -> None:
        parser = aizynth_config.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["config", "--model", "m", "--templates", "t"])

    def test_default_output_format_is_tsv(self) -> None:
        args = route_report.build_parser().parse_args(["summary", "--output", "o.json"])
        self.assertEqual(args.output_format, "tsv")


if __name__ == "__main__":
    unittest.main()
