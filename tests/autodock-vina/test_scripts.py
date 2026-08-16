"""Tests for the AutoDock Vina helper scripts.

No network and no docking binary. What is tested is the arithmetic and the
parsing that decide whether a docking run is valid: box placement, box-edge
detection, heavy-atom counting, and the guards that stop a bad setup early.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "autodock-vina"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


make_box = _load("make_box_script", "make_box.py")
parse_vina = _load("parse_vina_script", "parse_vina_output.py")
dock_batch = _load("dock_batch_script", "dock_batch.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


# A ligand of four atoms spanning 10-14 in x, 20-24 in y, 30-34 in z, plus a
# sulfate and a water that must never be chosen as the reference ligand.
MINI_PDB = """\
ATOM      1  CA  ALA A  10      50.000  50.000  50.000  1.00 20.00           C
ATOM      2  CA  GLY A  11      52.000  51.000  50.000  1.00 20.00           C
HETATM    3  C1  LIG A 201      10.000  20.000  30.000  1.00 20.00           C
HETATM    4  C2  LIG A 201      14.000  20.000  30.000  1.00 20.00           C
HETATM    5  C3  LIG A 201      12.000  24.000  30.000  1.00 20.00           C
HETATM    6  C4  LIG A 201      12.000  22.000  34.000  1.00 20.00           C
HETATM    7  S   SO4 A 301      70.000  70.000  70.000  1.00 20.00           S
HETATM    8  O   HOH A 401      80.000  80.000  80.000  1.00 20.00           O
END
"""


class StructureParsingTests(unittest.TestCase):
    def test_pdb_coordinates_are_read(self) -> None:
        points = make_box.parse_structure(MINI_PDB)
        self.assertEqual(len(points), 8)
        self.assertEqual(points[0].resname, "ALA")

    def test_sdf_coordinate_lines_are_recognised(self) -> None:
        sdf = "\n".join(
            [
                "mol", "  test", "",
                "  3  2  0  0  0  0            999 V2000",
                "    1.0000    2.0000    3.0000 C   0  0",
                "    4.0000    5.0000    6.0000 N   0  0",
                "    7.0000    8.0000    9.0000 O   0  0",
                "  1  2  1  0",
                "M  END", "$$$$",
            ]
        )
        points = make_box.parse_structure(sdf)
        self.assertEqual(len(points), 3)
        self.assertEqual(points[1].element, "N")

    def test_mol2_atom_block_is_read(self) -> None:
        mol2 = "\n".join(
            [
                "@<TRIPOS>MOLECULE", "test", " 2 1", "SMALL", "USER_CHARGES", "",
                "@<TRIPOS>ATOM",
                "      1 C1    1.0000    2.0000    3.0000 C.3    1  LIG   0.0000",
                "      2 N1    4.0000    5.0000    6.0000 N.am   1  LIG   0.0000",
                "@<TRIPOS>BOND", "     1    1    2 1",
            ]
        )
        points = make_box.parse_structure(mol2)
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0].element, "C")


class LigandSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.points = make_box.parse_structure(MINI_PDB)

    def test_solvent_and_ions_are_not_ligands(self) -> None:
        ligands = make_box.list_ligands(self.points)
        self.assertEqual(list(ligands), [("LIG", "A", 201)])

    def test_auto_selection_takes_the_largest_component(self) -> None:
        with mock.patch("sys.stderr", io.StringIO()):
            selected = make_box.select_reference(self.points, None)
        self.assertEqual(len(selected), 4)
        self.assertTrue(all(point.resname == "LIG" for point in selected))

    def test_an_unknown_component_lists_what_is_present(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            make_box.select_reference(self.points, "STI")
        self.assertIn("LIG", str(caught.exception))

    def test_residue_selection_accepts_chain_prefixed_numbers(self) -> None:
        with mock.patch("sys.stderr", io.StringIO()):
            selected = make_box.select_residues(self.points, "A:10,A:11")
        self.assertEqual(len(selected), 2)

    def test_a_missing_residue_warns_rather_than_silently_shrinking_the_box(self) -> None:
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            make_box.select_residues(self.points, "A:10,A:999")
        self.assertIn("A:999", stderr.getvalue())

    def test_no_matching_residues_is_an_error(self) -> None:
        with mock.patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit):
                make_box.select_residues(self.points, "A:998,A:999")


class BoundingBoxTests(unittest.TestCase):
    def setUp(self) -> None:
        points = make_box.parse_structure(MINI_PDB)
        with mock.patch("sys.stderr", io.StringIO()):
            self.ligand = make_box.select_reference(points, "LIG")

    def test_centre_is_the_midpoint_of_the_extents(self) -> None:
        center, _ = make_box.bounding_box(self.ligand, padding=0.0, cubic=False)
        self.assertEqual(center, (12.0, 22.0, 32.0))

    def test_padding_is_applied_on_both_sides(self) -> None:
        _, size = make_box.bounding_box(self.ligand, padding=10.0, cubic=False)
        # x extent is 4 A, plus 10 A each side.
        self.assertEqual(size[0], 24.0)

    def test_edges_are_floored_so_a_ligand_can_rotate(self) -> None:
        _, size = make_box.bounding_box(self.ligand, padding=0.0, cubic=False)
        self.assertEqual(min(size), make_box.MIN_BOX_EDGE)

    def test_cubic_uses_the_longest_edge(self) -> None:
        _, size = make_box.bounding_box(self.ligand, padding=10.0, cubic=True)
        self.assertEqual(len(set(size)), 1)
        self.assertEqual(size[0], 24.0)


class BoxFileTests(unittest.TestCase):
    def test_the_box_pdb_has_eight_corners(self) -> None:
        text = make_box.box_pdb((0.0, 0.0, 0.0), (10.0, 10.0, 10.0))
        corners = [line for line in text.splitlines() if line.startswith("HETATM")]
        self.assertEqual(len(corners), 8)
        self.assertIn("END", text)


class ConfigReadingTests(unittest.TestCase):
    def test_center_and_size_keys_are_read(self) -> None:
        path = Path(self.enterContext(_temporary("box.txt", (
            "# a comment\n"
            "center_x = 1.0\ncenter_y = 2.0\ncenter_z = 3.0\n"
            "size_x = 10.0\nsize_y = 20.0\nsize_z = 30.0\n"
        ))))
        config = parse_vina.read_config(path)
        bounds = parse_vina.box_bounds(config)
        self.assertEqual(bounds[0], (-4.0, 6.0))
        self.assertEqual(bounds[2], (-12.0, 18.0))

    def test_a_config_without_box_keys_yields_no_bounds(self) -> None:
        path = Path(self.enterContext(_temporary("other.txt", "exhaustiveness = 32\n")))
        self.assertIsNone(parse_vina.box_bounds(parse_vina.read_config(path)))


@contextlib.contextmanager
def _temporary(name: str, content: str):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / name
        path.write_text(content, encoding="utf-8")
        yield str(path)


OUT_PDBQT = """\
MODEL 1
REMARK VINA RESULT:     -12.5      0.000      0.000
REMARK SMILES Cc1ccccc1
ROOT
ATOM      1  C   UNL     1       0.000   0.000   0.000  1.00  0.00     0.000 C
ATOM      2  C   UNL     1       1.000   1.000   1.000  1.00  0.00     0.000 C
ATOM      3  H   UNL     1       1.500   1.500   1.500  1.00  0.00     0.000 HD
ENDROOT
ENDMDL
MODEL 2
REMARK VINA RESULT:     -12.2      1.234      2.345
ROOT
ATOM      1  C   UNL     1       5.600   0.000   0.000  1.00  0.00     0.000 C
ENDROOT
ENDMDL
MODEL 3
REMARK VINA RESULT:      -9.1      3.456      5.678
ROOT
ATOM      1  C   UNL     1       0.000   0.000   0.000  1.00  0.00     0.000 C
ENDROOT
ENDMDL
"""


class PoseParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "lig.pdbqt"
        self.path.write_text(OUT_PDBQT, encoding="utf-8")

    def test_every_pose_is_found_with_its_rmsds(self) -> None:
        poses, smiles = parse_vina.parse_pdbqt(self.path)
        self.assertEqual([pose.affinity for pose in poses], [-12.5, -12.2, -9.1])
        self.assertEqual(poses[1].rmsd_lb, 1.234)
        self.assertEqual(smiles, "Cc1ccccc1")

    def test_polar_hydrogens_are_not_counted_as_heavy_atoms(self) -> None:
        poses, _ = parse_vina.parse_pdbqt(self.path)
        self.assertEqual(poses[0].heavy_atoms, 2, "the HD atom must not count")

    def test_ligand_efficiency_is_affinity_per_heavy_atom(self) -> None:
        poses, smiles = parse_vina.parse_pdbqt(self.path)
        row = parse_vina.pose_row(self.path, poses[0], 1, None, smiles)
        self.assertAlmostEqual(row["ligandEfficiency"], -6.25)

    def test_a_pose_touching_the_wall_is_flagged(self) -> None:
        """The check that invalidates a score."""
        bounds = ((-6.0, 6.0), (-6.0, 6.0), (-6.0, 6.0))
        poses, smiles = parse_vina.parse_pdbqt(self.path)
        edge_row = parse_vina.pose_row(self.path, poses[1], 2, bounds, smiles)
        inner_row = parse_vina.pose_row(self.path, poses[0], 1, bounds, smiles)
        self.assertEqual(edge_row["atEdge"], "+x")
        self.assertEqual(inner_row["atEdge"], "")

    def test_a_file_with_no_vina_results_yields_no_poses(self) -> None:
        path = Path(self.directory.name) / "empty.pdbqt"
        path.write_text("ATOM      1  C   UNL     1       0.0   0.0   0.0\n", encoding="utf-8")
        poses, _ = parse_vina.parse_pdbqt(path)
        self.assertEqual(poses, [])


class ParseCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "lig.pdbqt"
        self.path.write_text(OUT_PDBQT, encoding="utf-8")
        self.config = Path(self.directory.name) / "box.txt"
        self.config.write_text(
            "center_x = 0\ncenter_y = 0\ncenter_z = 0\n"
            "size_x = 12\nsize_y = 12\nsize_z = 12\n",
            encoding="utf-8",
        )

    def _run(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            code = parse_vina.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_summary_reports_one_row_per_ligand(self) -> None:
        code, stdout, _ = self._run([str(self.path), "--summary"])
        self.assertEqual(code, 0)
        rows = [line for line in stdout.splitlines() if line and not line.startswith("#")]
        self.assertEqual(len(rows), 2, "header plus one ligand")
        self.assertIn("-12.5", rows[1])

    def test_box_edge_and_close_pose_warnings_are_emitted(self) -> None:
        _, _, stderr = self._run([str(self.path), "--config", str(self.config)])
        self.assertIn("box wall", stderr)
        self.assertIn("0.30 kcal/mol", stderr)

    def test_the_scoring_caveat_is_always_printed(self) -> None:
        _, _, stderr = self._run([str(self.path)])
        self.assertIn("not a measured binding free energy", stderr)

    def test_top_limits_the_poses_reported(self) -> None:
        _, stdout, _ = self._run([str(self.path), "--top", "1"])
        rows = [line for line in stdout.splitlines() if line and not line.startswith("#")]
        self.assertEqual(len(rows), 2)


class DockBatchTests(unittest.TestCase):
    def test_ad4_is_refused_with_the_maps_recipe(self) -> None:
        args = dock_batch.build_parser().parse_args(
            ["run", "--receptor", "r.pdbqt", "--config", "b.txt", "--scoring", "ad4"]
        )
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            self.assertEqual(args.handler(args), 1)
        self.assertIn("autogrid4", stderr.getvalue())
        self.assertIn("not comparable", stderr.getvalue())

    def test_a_non_pdbqt_receptor_is_refused_with_the_meeko_command(self) -> None:
        args = dock_batch.build_parser().parse_args(
            ["run", "--receptor", "receptor.pdb", "--config", "b.txt", "--dry-run"]
        )
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            self.assertEqual(args.handler(args), 1)
        self.assertIn("mk_prepare_receptor.py", stderr.getvalue())

    def test_dry_run_prints_commands_without_executing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ligand = Path(directory) / "lig.sdf"
            ligand.write_text("", encoding="utf-8")
            args = dock_batch.build_parser().parse_args(
                [
                    "run", "--receptor", "rec.pdbqt", "--config", "box.txt",
                    "--ligands", str(ligand), "--out-dir", directory,
                    "--dry-run", "--seed", "7",
                ]
            )
            stdout, stderr = io.StringIO(), io.StringIO()
            with mock.patch("subprocess.run", side_effect=AssertionError("must not run")):
                with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
                    args.handler(args)
        printed = stdout.getvalue()
        self.assertIn("mk_prepare_ligand.py", printed)
        self.assertIn("--exhaustiveness 32", printed)
        self.assertIn("--seed 7", printed)

    def test_a_missing_seed_warns_about_reproducibility(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ligand = Path(directory) / "lig.sdf"
            ligand.write_text("", encoding="utf-8")
            args = dock_batch.build_parser().parse_args(
                ["run", "--receptor", "r.pdbqt", "--config", "b.txt",
                 "--ligands", str(ligand), "--out-dir", directory, "--dry-run"]
            )
            stderr = io.StringIO()
            with mock.patch("sys.stdout", io.StringIO()), mock.patch("sys.stderr", stderr):
                args.handler(args)
        self.assertIn("not reproducible", stderr.getvalue())

    def test_exhaustiveness_defaults_above_the_vina_default(self) -> None:
        """Vina's own default of 8 is too low; the docs recommend 32."""
        args = dock_batch.build_parser().parse_args(
            ["run", "--receptor", "r.pdbqt", "--config", "b.txt"]
        )
        self.assertEqual(args.exhaustiveness, 32)

    def test_check_reports_missing_required_tools(self) -> None:
        args = dock_batch.build_parser().parse_args(["check"])
        with mock.patch.object(dock_batch, "which", return_value=None):
            with mock.patch("sys.stdout", io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
                self.assertEqual(args.handler(args), 1)


class MakeBoxCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.structure = Path(self.directory.name) / "mini.pdb"
        self.structure.write_text(MINI_PDB, encoding="utf-8")

    def _run(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            code = make_box.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_config_is_written_in_vina_format(self) -> None:
        code, stdout, _ = self._run([str(self.structure), "--reference-ligand", "LIG"])
        self.assertEqual(code, 0)
        self.assertIn("center_x = 12.000", stdout)
        self.assertIn("size_x =", stdout)

    def test_the_meeko_command_is_suggested_with_matching_numbers(self) -> None:
        _, _, stderr = self._run([str(self.structure), "--reference-ligand", "LIG"])
        self.assertIn("mk_prepare_receptor.py", stderr)
        self.assertIn("--box_center 12.000 22.000 32.000", stderr)

    def test_blind_docking_warns(self) -> None:
        _, _, stderr = self._run([str(self.structure), "--chain", "A"])
        self.assertIn("blind", stderr.lower())

    def test_a_large_box_warns_about_search_dilution(self) -> None:
        _, _, stderr = self._run(
            [str(self.structure), "--center", "0", "0", "0", "--size", "40", "40", "40"]
        )
        self.assertIn("exhaustiveness", stderr)

    def test_center_without_size_is_rejected(self) -> None:
        with mock.patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit):
                make_box.main([str(self.structure), "--center", "0", "0", "0"])

    def test_list_ligands_excludes_solvent(self) -> None:
        _, stdout, _ = self._run([str(self.structure), "--list-ligands"])
        self.assertIn("LIG", stdout)
        self.assertNotIn("HOH", stdout)
        self.assertNotIn("SO4", stdout)


if __name__ == "__main__":
    unittest.main()
