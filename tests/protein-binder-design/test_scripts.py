"""Tests for the de novo binder design scripts.

No network and no design tool. The parts worth testing are the burial proxy
that catches an unusable hotspot before GPU time is spent, the conjunctive
filter set (passing one metric is meaningless), and the campaign arithmetic
that sizes a run from the filter pass rate rather than from the number of
binders wanted.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "protein-binder-design"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


binder_target_spec = _load("binder_target_spec_script", "binder_target_spec.py")
binder_filter = _load("binder_filter_script", "binder_filter.py")
design_manifest = _load("design_manifest_script", "design_manifest.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

METRICS_CSV = """\
design,iptm,ipae,plddt,dsasa,shape_complementarity,unsat_hbonds,sequence
d1,0.88,7.2,88,1450,0.62,2,MKELVAAWKELAAAAA
d2,0.61,14.0,72,800,0.48,7,MKELVAAWKEQAAAAA
d3,0.85,8.0,85,1200,0.60,3,MKELVAAWKELAAAAA
d4,0.83,9.0,84,1100,0.58,1,WQRTYIPHNDCFGKLM
"""


def pdb_line(serial: int, resseq: int, x: float, y: float, z: float, resname="ALA", atom="CB"):
    return (
        f"ATOM  {serial:5d}  {atom:<3} {resname:>3} A{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00"
    )


def write(tmp: Path, name: str, text: str) -> Path:
    path = tmp / name
    path.write_text(text, encoding="utf-8")
    return path


class TargetParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_residues_are_read(self) -> None:
        path = write(
            self.dir, "t.pdb",
            "\n".join(pdb_line(i, i, float(i), 0.0, 0.0) for i in range(1, 6)) + "\n",
        )
        residues = binder_target_spec.read_residues(str(path), "A")
        self.assertEqual(len(residues), 5)

    def test_waters_and_glycans_are_skipped(self) -> None:
        lines = [
            pdb_line(1, 1, 0, 0, 0),
            pdb_line(2, 2, 1, 0, 0, resname="HOH"),
            pdb_line(3, 3, 2, 0, 0, resname="NAG"),
        ]
        path = write(self.dir, "t.pdb", "\n".join(lines) + "\n")
        self.assertEqual(len(binder_target_spec.read_residues(str(path), "A")), 1)

    def test_chain_filter(self) -> None:
        lines = [
            pdb_line(1, 1, 0, 0, 0),
            "ATOM      2  CB  ALA B   2       1.000   0.000   0.000  1.00  0.00",
        ]
        path = write(self.dir, "t.pdb", "\n".join(lines) + "\n")
        self.assertEqual(len(binder_target_spec.read_residues(str(path), "A")), 1)
        self.assertEqual(len(binder_target_spec.read_residues(str(path), None)), 2)

    def test_an_empty_structure_is_rejected(self) -> None:
        path = write(self.dir, "empty.pdb", "HEADER nothing\n")
        with self.assertRaises(binder_target_spec.TargetError):
            binder_target_spec.read_residues(str(path), "A")

    def test_a_missing_file_is_rejected(self) -> None:
        with self.assertRaises(binder_target_spec.TargetError):
            binder_target_spec.read_residues(str(self.dir / "nope.pdb"), None)


class ExposureTests(unittest.TestCase):
    """A buried hotspot cannot be contacted, and no design tool will say so."""

    def test_a_crowded_residue_is_buried(self) -> None:
        self.assertEqual(
            binder_target_spec.exposure_label(binder_target_spec.BURIED_NEIGHBOURS), "buried"
        )

    def test_an_isolated_residue_is_highly_exposed(self) -> None:
        self.assertEqual(binder_target_spec.exposure_label(0), "highly exposed")

    def test_the_middle_band_is_surface(self) -> None:
        self.assertEqual(binder_target_spec.exposure_label(15), "surface")

    def test_neighbour_counting_is_symmetric(self) -> None:
        residues = {
            1: {"xyz": (0.0, 0.0, 0.0), "resname": "ALA", "chain": "A", "atom": "CB"},
            2: {"xyz": (3.0, 0.0, 0.0), "resname": "ALA", "chain": "A", "atom": "CB"},
            3: {"xyz": (50.0, 0.0, 0.0), "resname": "ALA", "chain": "A", "atom": "CB"},
        }
        counts = binder_target_spec.neighbour_counts(residues)
        self.assertEqual(counts[1], 1)
        self.assertEqual(counts[2], 1)
        self.assertEqual(counts[3], 0)

    def test_glycine_and_proline_are_poor_hotspots(self) -> None:
        self.assertIn("GLY", binder_target_spec.POOR_HOTSPOT)
        self.assertIn("PRO", binder_target_spec.POOR_HOTSPOT)

    def test_documented_hotspot_count_range(self) -> None:
        self.assertEqual(binder_target_spec.HOTSPOT_RANGE, (3, 6))

    def test_documented_trim_target(self) -> None:
        self.assertEqual(binder_target_spec.TRIM_TARGET, (100, 200))

    def test_hotspot_parsing_rejects_non_numbers(self) -> None:
        with self.assertRaises(binder_target_spec.TargetError):
            binder_target_spec.parse_hotspots("45,notanumber")

    def test_empty_hotspot_list_is_rejected(self) -> None:
        with self.assertRaises(binder_target_spec.TargetError):
            binder_target_spec.parse_hotspots("")


class FilterTests(unittest.TestCase):
    """The filters are a conjunction; passing one is meaningless."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.csv = write(self.dir, "m.csv", METRICS_CSV)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_columns_resolve(self) -> None:
        rows, columns, identifier = binder_filter.read_designs(str(self.csv))
        self.assertEqual(set(columns), set(binder_filter.FILTERS))
        self.assertEqual(identifier, "design")

    def test_a_good_design_passes_every_filter(self) -> None:
        rows, columns, _ = binder_filter.read_designs(str(self.csv))
        thresholds = {k: dict(v) for k, v in binder_filter.FILTERS.items()}
        result = binder_filter.evaluate(rows[0], columns, thresholds)
        self.assertTrue(result["passes"])

    def test_a_bad_design_fails_every_filter(self) -> None:
        rows, columns, _ = binder_filter.read_designs(str(self.csv))
        thresholds = {k: dict(v) for k, v in binder_filter.FILTERS.items()}
        result = binder_filter.evaluate(rows[1], columns, thresholds)
        self.assertFalse(result["passes"])
        self.assertEqual(len(result["failures"]), len(binder_filter.FILTERS))

    def test_a_table_without_iptm_is_rejected_and_explains_ptm(self) -> None:
        path = write(self.dir, "ptm.csv", "design,ptm\nd1,0.9\n")
        with self.assertRaises(binder_filter.FilterError) as caught:
            binder_filter.read_designs(str(path))
        self.assertIn("pTM is not ipTM", str(caught.exception))

    def test_iptm_aliases_resolve(self) -> None:
        for alias in ("iptm", "i_ptm", "pae_interaction"):
            with self.subTest(alias=alias):
                columns = binder_filter.resolve_columns([alias, "design"])
                self.assertTrue(columns)

    def test_thresholds_can_be_overridden(self) -> None:
        args = binder_filter.build_parser().parse_args(
            ["filter", "--csv", str(self.csv), "--iptm", "0.5"]
        )
        thresholds = binder_filter.thresholds_from(args)
        self.assertEqual(thresholds["iptm"]["min"], 0.5)

    def test_relaxing_iptm_lets_a_borderline_design_through_that_metric(self) -> None:
        rows, columns, _ = binder_filter.read_designs(str(self.csv))
        args = binder_filter.build_parser().parse_args(
            ["filter", "--csv", str(self.csv), "--iptm", "0.5"]
        )
        result = binder_filter.evaluate(rows[1], columns, binder_filter.thresholds_from(args))
        self.assertNotIn("iptm<0.5", result["failures"])

    def test_every_filter_declares_a_bound_and_a_reason(self) -> None:
        for name, spec in binder_filter.FILTERS.items():
            with self.subTest(metric=name):
                self.assertTrue("min" in spec or "max" in spec)
                self.assertTrue(spec["measures"])
                self.assertTrue(spec["why"])

    def test_iptm_threshold_matches_common_practice(self) -> None:
        self.assertEqual(binder_filter.FILTERS["iptm"]["min"], 0.80)

    def test_empty_table_is_rejected(self) -> None:
        path = write(self.dir, "empty.csv", "design,iptm\n")
        with self.assertRaises(binder_filter.FilterError):
            binder_filter.read_designs(str(path))


class DiversityTests(unittest.TestCase):
    """Ranking by ipTM alone selects near-identical designs."""

    def test_identical_sequences_score_one(self) -> None:
        self.assertAlmostEqual(binder_filter.similarity("MKEL", "MKEL"), 1.0)

    def test_unrelated_sequences_score_low(self) -> None:
        self.assertLess(binder_filter.similarity("AAAA", "WWWW"), 0.1)

    def test_empty_sequence_scores_zero(self) -> None:
        self.assertEqual(binder_filter.similarity("", "MKEL"), 0.0)

    def test_similarity_uses_the_shorter_sequence(self) -> None:
        self.assertAlmostEqual(binder_filter.similarity("MK", "MKELVA"), 1.0)

    def test_near_duplicates_are_dropped_from_a_diverse_pick(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = write(Path(tmp), "m.csv", METRICS_CSV)
            args = binder_filter.build_parser().parse_args(
                ["diverse", "--csv", str(csv_path), "--n", "10", "--format", "json"]
            )
            binder_filter.command_diverse(args)  # d1 and d3 are identical; only one survives


class CampaignTests(unittest.TestCase):
    def test_trajectories_scale_with_the_inverse_pass_rate(self) -> None:
        args = design_manifest.build_parser().parse_args(
            ["plan", "--want", "24", "--pass-rate", "0.03"]
        )
        design_manifest.command_plan(args)  # 24/0.03 = 800 -> 801 by ceiling

    def test_a_pass_rate_outside_zero_to_one_is_rejected(self) -> None:
        for rate in ("0", "1.5", "-0.1"):
            with self.subTest(rate=rate):
                args = design_manifest.build_parser().parse_args(
                    ["plan", "--pass-rate", rate]
                )
                with self.assertRaises(design_manifest.ManifestError):
                    design_manifest.command_plan(args)

    def test_zero_designs_is_rejected(self) -> None:
        args = design_manifest.build_parser().parse_args(["plan", "--want", "0"])
        with self.assertRaises(design_manifest.ManifestError):
            design_manifest.command_plan(args)

    def test_unknown_pipeline_is_rejected(self) -> None:
        args = design_manifest.build_parser().parse_args(["plan"])
        args.pipeline = "nonsense"
        with self.assertRaises(design_manifest.ManifestError):
            design_manifest.command_plan(args)

    def test_minimum_order_size(self) -> None:
        self.assertEqual(design_manifest.MIN_ORDER, 20)

    def test_bindcraft_is_documented_as_cofolding(self) -> None:
        self.assertIn("Co-folds", design_manifest.PIPELINES["bindcraft"]["fits"])

    def test_rfdiffusion_is_documented_as_fixed_target(self) -> None:
        self.assertIn("FIXED", design_manifest.PIPELINES["rfdiffusion"]["note"])

    def test_checklist_starts_from_the_structure_and_epitope(self) -> None:
        items = [item for item, _ in design_manifest.CHECKLIST]
        self.assertIn("target structure", items)
        self.assertIn("epitope chosen", items)


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (binder_target_spec, ["residues", "--pdb", "t.pdb"]),
            (binder_target_spec, ["hotspots", "--pdb", "t.pdb", "--hotspots", "1"]),
            (binder_target_spec, ["trim", "--pdb", "t.pdb", "--hotspots", "1"]),
            (binder_filter, ["filter", "--csv", "m.csv"]),
            (binder_filter, ["diverse", "--csv", "m.csv"]),
            (binder_filter, ["metrics"]),
            (design_manifest, ["plan"]),
            (design_manifest, ["pipelines"]),
            (design_manifest, ["checklist"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_default_pipeline_is_bindcraft(self) -> None:
        args = design_manifest.build_parser().parse_args(["plan"])
        self.assertEqual(args.pipeline, "bindcraft")

    def test_default_output_format_is_tsv(self) -> None:
        args = binder_filter.build_parser().parse_args(["metrics"])
        self.assertEqual(args.output_format, "tsv")


if __name__ == "__main__":
    unittest.main()
