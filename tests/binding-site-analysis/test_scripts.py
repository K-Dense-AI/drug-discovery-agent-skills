"""Tests for the binding-site-analysis scripts.

No network and no fpocket binary -- the scripts parse what fpocket wrote, so
the fixtures here are synthetic fpocket output. The parts worth testing are
the Score/Druggability distinction that decides which cavity you dock into,
the box arithmetic that feeds AutoDock Vina, and the apo/holo matching that
identifies a cryptic site.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "binding-site-analysis"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# site_compare imports pocket_report by module name.
pocket_report = _load("pocket_report", "pocket_report.py")
pocket_box = _load("pocket_box_script", "pocket_box.py")
site_compare = _load("site_compare_script", "site_compare.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

INFO_TEXT = """\
Pocket 1 :
\tScore : \t0.412
\tDruggability Score : \t0.183
\tNumber of Alpha Spheres : \t120
\tTotal SASA : \t410.2
\tPolar SASA : \t280.1
\tApolar SASA : \t130.1
\tVolume : \t980.4

Pocket 2 :
\tScore : \t0.310
\tDruggability Score : \t0.871
\tNumber of Alpha Spheres : \t95
\tTotal SASA : \t350.0
\tPolar SASA : \t100.0
\tApolar SASA : \t250.0
\tVolume : \t720.5
"""


def pdb_atom(serial, x, y, z, *, resname="STP", chain="A", resseq=1, record="ATOM"):
    return (
        f"{record:<6}{serial:>5}  C   {resname:>3} {chain}{resseq:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}  1.00  0.00"
    )


def make_out_dir(root: Path, name: str, info: str, pockets: dict) -> Path:
    out = root / f"{name}_out"
    (out / "pockets").mkdir(parents=True)
    (out / f"{name}_info.txt").write_text(info)
    for filename, lines in pockets.items():
        (out / "pockets" / filename).write_text("\n".join(lines) + "\n")
    return out


class InfoParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.out = make_out_dir(Path(self.tmp.name), "x", INFO_TEXT, {})

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_both_pockets_are_parsed(self) -> None:
        pockets = pocket_report.parse_info(self.out / "x_info.txt")
        self.assertEqual([p["pocket"] for p in pockets], [1, 2])

    def test_druggability_and_score_are_kept_separate(self) -> None:
        pockets = pocket_report.parse_info(self.out / "x_info.txt")
        first = pockets[0]
        self.assertAlmostEqual(first["score"], 0.412)
        self.assertAlmostEqual(first["druggability"], 0.183)

    def test_out_dir_finds_the_info_file(self) -> None:
        args = pocket_report.build_parser().parse_args(
            ["rank", "--out-dir", str(self.out)]
        )
        self.assertEqual(pocket_report.resolve_info(args).name, "x_info.txt")

    def test_missing_info_file_names_the_expected_layout(self) -> None:
        args = pocket_report.build_parser().parse_args(
            ["rank", "--out-dir", self.tmp.name]
        )
        with self.assertRaises(pocket_report.PocketError) as caught:
            pocket_report.resolve_info(args)
        self.assertIn("_info.txt", str(caught.exception))

    def test_a_file_with_no_pockets_is_an_error(self) -> None:
        path = Path(self.tmp.name) / "empty.txt"
        path.write_text("nothing here\n")
        with self.assertRaises(pocket_report.PocketError):
            pocket_report.parse_info(path)

    def test_no_selector_is_an_error(self) -> None:
        args = pocket_report.build_parser().parse_args(["rank"])
        with self.assertRaises(pocket_report.PocketError):
            pocket_report.resolve_info(args)


class ClassificationTests(unittest.TestCase):
    """Volume alone is misleading; the apolar fraction is the discriminator."""

    def test_high_druggability_and_apolar_is_druggable(self) -> None:
        verdict, _ = pocket_report.classify(0.871, 720.5, 0.714)
        self.assertEqual(verdict, "druggable")

    def test_low_druggability_is_poor(self) -> None:
        verdict, _ = pocket_report.classify(0.183, 980.4, 0.317)
        self.assertEqual(verdict, "poor")

    def test_a_large_but_polar_cavity_is_flagged(self) -> None:
        verdict, reason = pocket_report.classify(0.7, 900.0, 0.20)
        self.assertEqual(verdict, "druggable but polar")
        self.assertIn("groove", reason)

    def test_small_volume_overrides_a_good_score(self) -> None:
        verdict, reason = pocket_report.classify(0.9, 120.0, 0.8)
        self.assertEqual(verdict, "too small")
        self.assertIn("120", reason)

    def test_marginal_band(self) -> None:
        self.assertEqual(pocket_report.classify(0.35, 500.0, 0.5)[0], "marginal")

    def test_absent_druggability_is_unknown(self) -> None:
        self.assertEqual(pocket_report.classify(None, 500.0, 0.5)[0], "unknown")

    def test_documented_thresholds(self) -> None:
        self.assertEqual(pocket_report.DRUGGABLE, 0.5)
        self.assertEqual(pocket_report.MIN_USEFUL_VOLUME, 200.0)
        self.assertEqual(pocket_report.MIN_APOLAR_FRACTION, 0.35)

    def test_apolar_fraction_is_derived(self) -> None:
        enriched = pocket_report.enrich(
            {"pocket": 1, "total_sasa": 400.0, "apolar_sasa": 100.0, "druggability": 0.6,
             "volume": 500.0}
        )
        self.assertAlmostEqual(enriched["apolar_fraction"], 0.25)


class BoxTests(unittest.TestCase):
    def test_centre_and_size_with_padding(self) -> None:
        points = [(10.0, 20.0, 30.0), (14.0, 24.0, 36.0)]
        box = pocket_box.box_from_points(points, 4.0)
        self.assertAlmostEqual(box["center_x"], 12.0)
        self.assertAlmostEqual(box["center_y"], 22.0)
        self.assertAlmostEqual(box["center_z"], 33.0)
        self.assertAlmostEqual(box["size_x"], 12.0)
        self.assertAlmostEqual(box["size_y"], 12.0)
        self.assertAlmostEqual(box["size_z"], 14.0)

    def test_zero_padding_gives_the_bare_extent(self) -> None:
        box = pocket_box.box_from_points([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)], 0.0)
        self.assertAlmostEqual(box["size_x"], 10.0)
        self.assertAlmostEqual(box["size_y"], 0.0)

    def test_a_single_point_is_a_cube_of_padding(self) -> None:
        box = pocket_box.box_from_points([(1.0, 2.0, 3.0)], 5.0)
        self.assertAlmostEqual(box["size_x"], 10.0)
        self.assertAlmostEqual(box["center_x"], 1.0)

    def test_volume_is_the_product(self) -> None:
        box = pocket_box.box_from_points([(0.0, 0.0, 0.0), (2.0, 2.0, 2.0)], 4.0)
        self.assertAlmostEqual(box["volume_A3"], 10.0 ** 3)

    def test_no_atoms_is_an_error(self) -> None:
        with self.assertRaises(pocket_box.BoxError):
            pocket_box.box_from_points([], 4.0)

    def test_default_padding_is_four(self) -> None:
        self.assertEqual(pocket_box.DEFAULT_PADDING, 4.0)

    def test_large_box_threshold(self) -> None:
        self.assertEqual(pocket_box.LARGE_BOX_VOLUME, 27000.0)

    def test_solvent_is_excluded_from_ligand_candidates(self) -> None:
        for residue in ("HOH", "SO4", "GOL", "EDO", "DMS"):
            with self.subTest(residue=residue):
                self.assertIn(residue, pocket_box.NON_LIGAND)


class BoxFromFilesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.out = make_out_dir(
            self.root,
            "x",
            INFO_TEXT,
            {
                "pocket2_vert.pqr": [
                    pdb_atom(1, 10.0, 20.0, 30.0),
                    pdb_atom(2, 14.0, 24.0, 36.0),
                ]
            },
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_vertices_are_preferred_over_lining_atoms(self) -> None:
        points = pocket_box.read_coordinates(
            self.out / "pockets" / "pocket2_vert.pqr", lambda line: True
        )
        self.assertEqual(len(points), 2)

    def test_missing_pocket_files_are_an_error(self) -> None:
        args = pocket_box.build_parser().parse_args(
            ["from-pocket", "--out-dir", str(self.out), "--pocket", "9"]
        )
        with self.assertRaises(pocket_box.BoxError):
            pocket_box.command_from_pocket(args)

    def test_ligand_not_present_lists_the_candidates(self) -> None:
        pdb = self.root / "holo.pdb"
        pdb.write_text(
            "\n".join(
                [
                    pdb_atom(1, 0, 0, 0, resname="E20", record="HETATM"),
                    pdb_atom(2, 1, 1, 1, resname="HOH", record="HETATM"),
                ]
            )
            + "\n"
        )
        args = pocket_box.build_parser().parse_args(
            ["from-ligand", "--pdb", str(pdb), "--resname", "XXX"]
        )
        with self.assertRaises(pocket_box.BoxError) as caught:
            pocket_box.command_from_ligand(args)
        message = str(caught.exception)
        self.assertIn("E20", message)
        self.assertNotIn("HOH", message)

    def test_residue_selection_parses_chain_and_number(self) -> None:
        pdb = self.root / "rec.pdb"
        pdb.write_text(
            "\n".join(
                [
                    pdb_atom(1, 0, 0, 0, chain="A", resseq=279),
                    pdb_atom(2, 6, 6, 6, chain="A", resseq=286),
                    pdb_atom(3, 99, 99, 99, chain="B", resseq=1),
                ]
            )
            + "\n"
        )
        args = pocket_box.build_parser().parse_args(
            ["from-residues", "--pdb", str(pdb), "--residues", "A:279,A:286", "--padding", "0"]
        )
        pocket_box.command_from_residues(args)  # must not raise

    def test_malformed_residue_selector_is_rejected(self) -> None:
        pdb = self.root / "rec2.pdb"
        pdb.write_text(pdb_atom(1, 0, 0, 0) + "\n")
        args = pocket_box.build_parser().parse_args(
            ["from-residues", "--pdb", str(pdb), "--residues", "A:notanumber"]
        )
        with self.assertRaises(pocket_box.BoxError):
            pocket_box.command_from_residues(args)


class SiteCompareTests(unittest.TestCase):
    def test_distance_is_euclidean(self) -> None:
        self.assertAlmostEqual(site_compare.distance((0, 0, 0), (3, 4, 0)), 5.0)

    def test_documented_defaults(self) -> None:
        self.assertEqual(site_compare.DEFAULT_MATCH_DISTANCE, 5.0)
        self.assertEqual(site_compare.MEANINGFUL_DELTA, 0.1)

    def test_centroid_is_averaged_over_atoms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = make_out_dir(
                Path(tmp),
                "y",
                INFO_TEXT,
                {"pocket1_vert.pqr": [pdb_atom(1, 0, 0, 0), pdb_atom(2, 4, 8, 12)]},
            )
            centre = site_compare.pocket_centre(out, 1)
        self.assertEqual(centre, (2.0, 4.0, 6.0))

    def test_missing_pocket_files_give_no_centre(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = make_out_dir(Path(tmp), "z", INFO_TEXT, {})
            self.assertIsNone(site_compare.pocket_centre(out, 1))


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (pocket_report, ["rank", "--out-dir", "x"]),
            (pocket_report, ["residues", "--out-dir", "x", "--pocket", "1"]),
            (pocket_box, ["from-pocket", "--out-dir", "x", "--pocket", "1"]),
            (pocket_box, ["from-ligand", "--pdb", "x.pdb", "--resname", "E20"]),
            (pocket_box, ["from-residues", "--pdb", "x.pdb", "--residues", "A:1"]),
            (site_compare, ["match", "--apo", "a", "--holo", "b"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_box_supports_a_vina_config_format(self) -> None:
        args = pocket_box.build_parser().parse_args(
            ["from-pocket", "--out-dir", "x", "--pocket", "1", "--format", "vina"]
        )
        self.assertEqual(args.output_format, "vina")


if __name__ == "__main__":
    unittest.main()
