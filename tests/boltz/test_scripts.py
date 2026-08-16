"""Tests for the Boltz input and output helpers.

No GPU, no network, no boltz install. Two things are worth testing here: that
the generated YAML is valid and says what it should, and that the affinity
conversion is right -- `affinity_pred_value` runs the opposite way to every
other number in the field, so a sign error would be invisible and wrong.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "boltz"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# `screen_library` imports `make_boltz_yaml` by that name, so it must be
# registered under it rather than a test-local alias.
make_yaml = _load("make_boltz_yaml", "make_boltz_yaml.py")
collect = _load("collect_results_script", "collect_results.py")
screen = _load("screen_library_script", "screen_library.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

SEQUENCE = "MVTPEGNVSLVDESLLVGVTDEDRAVRSAHQFYERLIG"
IMATINIB = "Cc1ccc(cc1Nc1nccc(n1)c1cccnc1)NC(=O)c1ccc(CN2CCN(C)CC2)cc1"


def make(argv: list[str]) -> str:
    args = make_yaml.build_parser().parse_args(argv)
    return make_yaml.build_yaml(args)


class YamlStructureTests(unittest.TestCase):
    def test_protein_and_ligand_get_distinct_chain_ids(self) -> None:
        document = make(["--protein-sequence", SEQUENCE, "--ligand-smiles", "CCO"])
        self.assertIn("id: A", document)
        self.assertIn("id: B", document)
        self.assertIn("version: 1", document)

    def test_copies_become_a_chain_id_list(self) -> None:
        document = make(["--protein-sequence", SEQUENCE, "--copies", "3"])
        self.assertIn("id: [A, B, C]", document)

    def test_a_ligand_after_copies_takes_the_next_free_id(self) -> None:
        document = make(
            ["--protein-sequence", SEQUENCE, "--copies", "2", "--ligand-ccd", "SAH"]
        )
        self.assertIn("id: [A, B]", document)
        self.assertIn("id: C", document)

    def test_ccd_codes_are_upper_cased(self) -> None:
        self.assertIn("ccd: SAH", make(["--protein-sequence", SEQUENCE, "--ligand-ccd", "sah"]))

    def test_no_msa_writes_the_explicit_empty_marker(self) -> None:
        """Omitting `msa` entirely is a different, more confusing failure."""
        self.assertIn("msa: empty", make(["--protein-sequence", SEQUENCE, "--no-msa"]))

    def test_an_msa_path_is_written_verbatim(self) -> None:
        document = make(["--protein-sequence", SEQUENCE, "--msa-path", "aln.a3m"])
        self.assertIn("msa: aln.a3m", document)
        self.assertNotIn("msa: empty", document)


class SmilesQuotingTests(unittest.TestCase):
    def test_smiles_are_quoted(self) -> None:
        """An unquoted `#` starts a YAML comment and truncates the molecule."""
        document = make(["--protein-sequence", SEQUENCE, "--ligand-smiles", "C#CCO"])
        self.assertIn("smiles: 'C#CCO'", document)

    def test_an_embedded_apostrophe_is_escaped(self) -> None:
        document = make(["--protein-sequence", SEQUENCE, "--ligand-smiles", "CC'O"])
        self.assertIn("''", document)


class ValidationTests(unittest.TestCase):
    def test_a_non_amino_acid_sequence_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            make(["--protein-sequence", "MVTP123"])
        self.assertIn("non-amino-acid", str(caught.exception))

    def test_an_affinity_binder_that_is_not_a_ligand_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            make(
                ["--protein-sequence", SEQUENCE, "--ligand-smiles", "CCO",
                 "--affinity", "--affinity-binder", "A"]
            )
        self.assertIn("not a ligand chain", str(caught.exception))

    def test_affinity_without_a_ligand_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            make(["--protein-sequence", SEQUENCE, "--affinity"])

    def test_a_pocket_without_a_ligand_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            make(["--protein-sequence", SEQUENCE, "--pocket", "A:10"])

    def test_an_empty_input_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            make([])

    def test_out_of_range_pocket_distance_is_refused(self) -> None:
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            code = make_yaml.main(
                ["--protein-sequence", SEQUENCE, "--ligand-smiles", "CCO",
                 "--pocket", "A:10", "--pocket-distance", "40"]
            )
        self.assertEqual(code, 1)
        self.assertIn("between 4 and 20", stderr.getvalue())

    def test_a_malformed_contact_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            make_yaml.parse_contacts("A790")
        self.assertIn("CHAIN:RESIDUE", str(caught.exception))


class PocketTests(unittest.TestCase):
    def test_contacts_render_as_nested_lists(self) -> None:
        document = make(
            ["--protein-sequence", SEQUENCE, "--ligand-smiles", "CCO",
             "--pocket", "A:790,A:797,B:855"]
        )
        self.assertIn("contacts: [[A, 790], [A, 797], [B, 855]]", document)
        self.assertIn("binder: B", document)

    def test_force_is_only_written_when_asked(self) -> None:
        base = ["--protein-sequence", SEQUENCE, "--ligand-smiles", "CCO", "--pocket", "A:1"]
        self.assertNotIn("force: true", make(base))
        self.assertIn("force: true", make(base + ["--pocket-force"]))


class HeavyAtomEstimateTests(unittest.TestCase):
    def test_simple_molecules(self) -> None:
        self.assertEqual(make_yaml.estimate_heavy_atoms("CCO"), 3)
        self.assertEqual(make_yaml.estimate_heavy_atoms("c1ccccc1"), 6)

    def test_two_letter_elements_count_once(self) -> None:
        self.assertEqual(make_yaml.estimate_heavy_atoms("ClCCBr"), 4)

    def test_bracket_atoms_count_once_and_hydrogens_are_ignored(self) -> None:
        self.assertEqual(make_yaml.estimate_heavy_atoms("C[C@H](N)C(=O)O"), 6)

    def test_a_drug_sized_molecule_is_in_the_right_range(self) -> None:
        self.assertEqual(make_yaml.estimate_heavy_atoms(IMATINIB), 37)

    def test_an_oversized_ligand_warns_when_affinity_is_requested(self) -> None:
        big = "C" * 200
        args = make_yaml.build_parser().parse_args(
            ["--protein-sequence", SEQUENCE, "--ligand-smiles", big, "--affinity"]
        )
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            make_yaml.warn(args)
        self.assertIn(str(make_yaml.AFFINITY_ATOM_LIMIT), stderr.getvalue())


class AffinityConversionTests(unittest.TestCase):
    """The sign convention that makes this field easy to misreport."""

    def test_a_nanomolar_binder_converts_to_pic50_nine(self) -> None:
        row = collect.affinity_row(-3.0)
        self.assertAlmostEqual(row["pIC50"], 9.0)
        self.assertAlmostEqual(row["IC50_uM"], 0.001)

    def test_one_micromolar_is_pic50_six(self) -> None:
        row = collect.affinity_row(0.0)
        self.assertAlmostEqual(row["pIC50"], 6.0)
        self.assertAlmostEqual(row["IC50_uM"], 1.0)

    def test_a_positive_value_is_a_weak_binder(self) -> None:
        row = collect.affinity_row(2.0)
        self.assertAlmostEqual(row["pIC50"], 4.0)
        self.assertAlmostEqual(row["IC50_uM"], 100.0)

    def test_free_energy_is_negative_for_a_binder(self) -> None:
        row = collect.affinity_row(-3.0)
        self.assertAlmostEqual(row["dG_kcal_mol"], -12.28, places=2)

    def test_a_missing_value_yields_empty_columns(self) -> None:
        self.assertEqual(
            collect.affinity_row(None),
            {"pIC50": None, "IC50_uM": None, "dG_kcal_mol": None},
        )


def write_prediction(root: Path, name: str, confidence: dict, affinity: dict | None,
                     samples: int = 2) -> None:
    directory = root / "predictions" / name
    directory.mkdir(parents=True, exist_ok=True)
    for sample in range(samples):
        payload = dict(confidence)
        payload["confidence_score"] = confidence["confidence_score"] - 0.05 * sample
        (directory / f"confidence_{name}_model_{sample}.json").write_text(json.dumps(payload))
        (directory / f"{name}_model_{sample}.cif").write_text("data_x\n")
    if affinity is not None:
        (directory / f"affinity_{name}.json").write_text(json.dumps(affinity))


GOOD_CONFIDENCE = {
    "confidence_score": 0.84, "ptm": 0.85, "iptm": 0.82, "ligand_iptm": 0.79,
    "protein_iptm": 0.86, "complex_plddt": 0.88, "complex_iplddt": 0.83,
    "complex_pde": 0.9, "complex_ipde": 5.1,
}
POOR_CONFIDENCE = dict(GOOD_CONFIDENCE, confidence_score=0.51, iptm=0.42, ligand_iptm=0.31)
GOOD_AFFINITY = {
    "affinity_pred_value": -2.1, "affinity_probability_binary": 0.93,
    "affinity_pred_value1": -2.4, "affinity_pred_value2": -1.8,
}
SPLIT_AFFINITY = {
    "affinity_pred_value": 1.4, "affinity_probability_binary": 0.21,
    "affinity_pred_value1": 0.1, "affinity_pred_value2": 2.7,
}


class CollectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        write_prediction(self.root, "hit", GOOD_CONFIDENCE, GOOD_AFFINITY)
        write_prediction(self.root, "miss", POOR_CONFIDENCE, SPLIT_AFFINITY)

    def _run(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            code = collect.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_only_the_top_sample_is_reported_by_default(self) -> None:
        code, stdout, _ = self._run([str(self.root)])
        self.assertEqual(code, 0)
        rows = [line for line in stdout.splitlines() if line and not line.startswith("#")]
        self.assertEqual(len(rows), 3, "header plus one row per prediction")

    def test_all_samples_reports_every_diffusion_sample(self) -> None:
        _, stdout, _ = self._run([str(self.root), "--all-samples"])
        rows = [line for line in stdout.splitlines() if line and not line.startswith("#")]
        self.assertEqual(len(rows), 5, "header plus two samples per prediction")

    def test_rows_sort_by_potency(self) -> None:
        _, stdout, _ = self._run([str(self.root)])
        rows = [line for line in stdout.splitlines() if line and not line.startswith("#")]
        self.assertTrue(rows[1].startswith("hit"))

    def test_low_iptm_predictions_are_flagged(self) -> None:
        _, _, stderr = self._run([str(self.root)])
        self.assertIn("ipTM <", stderr)

    def test_ensemble_disagreement_is_flagged(self) -> None:
        _, _, stderr = self._run([str(self.root)])
        self.assertIn("ensemble members disagreeing", stderr)

    def test_min_iptm_filters(self) -> None:
        _, stdout, _ = self._run([str(self.root), "--min-iptm", "0.6"])
        rows = [line for line in stdout.splitlines() if line and not line.startswith("#")]
        self.assertEqual(len(rows), 2)
        self.assertIn("hit", rows[1])

    def test_the_predictions_child_is_found_from_the_run_directory(self) -> None:
        found = collect.find_prediction_dirs(self.root)
        self.assertEqual(sorted(path.name for path in found), ["hit", "miss"])

    def test_a_single_prediction_directory_also_works(self) -> None:
        found = collect.find_prediction_dirs(self.root / "predictions" / "hit")
        self.assertEqual([path.name for path in found], ["hit"])

    def test_a_directory_with_no_predictions_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            code, _, stderr = self._run([empty])
        self.assertEqual(code, 1)
        self.assertIn("prediction", stderr)

    def test_a_prediction_without_affinity_still_reports_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_prediction(root, "structure_only", GOOD_CONFIDENCE, None)
            _, stdout, _ = self._run([str(root)])
        rows = [line for line in stdout.splitlines() if line and not line.startswith("#")]
        self.assertEqual(len(rows), 2)
        self.assertIn("0.82", rows[1])


class ScreenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "target.fasta").write_text(f">t\n{SEQUENCE}\n", encoding="utf-8")
        (self.root / "lib.smi").write_text(
            "CCO ethanol\n# comment\n\nc1ccccc1 benzene\nCCN\n", encoding="utf-8"
        )

    def _run(self, extra=()):
        argv = [
            "--protein-fasta", str(self.root / "target.fasta"),
            "--smiles", str(self.root / "lib.smi"),
            "--out-dir", str(self.root / "screen"),
            *extra,
        ]
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            code = screen.main(argv)
        return code, stderr.getvalue()

    def test_one_yaml_per_molecule_plus_a_manifest(self) -> None:
        code, _ = self._run()
        self.assertEqual(code, 0)
        out_dir = self.root / "screen"
        self.assertTrue((out_dir / "ethanol.yaml").is_file())
        self.assertTrue((out_dir / "benzene.yaml").is_file())
        self.assertTrue((out_dir / "manifest.tsv").is_file())

    def test_comments_and_blank_lines_are_skipped(self) -> None:
        self._run()
        manifest = (self.root / "screen" / "manifest.tsv").read_text().splitlines()
        self.assertEqual(len(manifest), 4, "header plus three molecules")

    def test_unnamed_molecules_get_a_generated_name(self) -> None:
        self._run()
        names = [
            line.split("\t")[0]
            for line in (self.root / "screen" / "manifest.tsv").read_text().splitlines()[1:]
        ]
        self.assertIn("ethanol", names)
        self.assertTrue(any(name.startswith("mol") for name in names))

    def test_duplicate_names_are_disambiguated(self) -> None:
        (self.root / "dup.smi").write_text("CCO same\nCCN same\n", encoding="utf-8")
        entries = screen.read_smiles(self.root / "dup.smi")
        self.assertEqual([name for name, _ in entries], ["same", "same_2"])

    def test_unsafe_characters_in_names_are_replaced(self) -> None:
        (self.root / "odd.smi").write_text("CCO my/weird name\n", encoding="utf-8")
        entries = screen.read_smiles(self.root / "odd.smi")
        self.assertNotIn("/", entries[0][0])

    def test_missing_msa_path_warns_about_the_wasted_work(self) -> None:
        _, stderr = self._run()
        self.assertIn("build its own MSA", stderr)

    def test_an_msa_path_is_written_into_every_input(self) -> None:
        self._run(["--msa-path", "target.a3m"])
        for name in ("ethanol", "benzene"):
            document = (self.root / "screen" / f"{name}.yaml").read_text()
            self.assertIn("msa: target.a3m", document)

    def test_affinity_blocks_are_added_when_requested(self) -> None:
        self._run(["--affinity"])
        document = (self.root / "screen" / "ethanol.yaml").read_text()
        self.assertIn("properties:", document)
        self.assertIn("binder: B", document)

    def test_limit_truncates_the_library(self) -> None:
        self._run(["--limit", "1"])
        manifest = (self.root / "screen" / "manifest.tsv").read_text().splitlines()
        self.assertEqual(len(manifest), 2)

    def test_a_missing_library_file_is_an_error(self) -> None:
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            code = screen.main(
                ["--protein-fasta", str(self.root / "target.fasta"),
                 "--smiles", str(self.root / "nope.smi"),
                 "--out-dir", str(self.root / "screen")]
            )
        self.assertEqual(code, 1)

    def test_a_target_is_required(self) -> None:
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            code = screen.main(
                ["--smiles", str(self.root / "lib.smi"), "--out-dir", str(self.root / "s")]
            )
        self.assertEqual(code, 1)


class FastaTests(unittest.TestCase):
    def test_multi_record_fasta_is_split(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "two.fasta"
            path.write_text(">a\nMVTP\nEGNV\n>b\nAAAA\n", encoding="utf-8")
            records = make_yaml.read_fasta(path)
        self.assertEqual(records, [("a", "MVTPEGNV"), ("b", "AAAA")])

    def test_each_fasta_record_becomes_its_own_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "two.fasta"
            path.write_text(f">a\n{SEQUENCE}\n>b\n{SEQUENCE}\n", encoding="utf-8")
            document = make(["--protein-fasta", str(path)])
        self.assertIn("id: A", document)
        self.assertIn("id: B", document)


if __name__ == "__main__":
    unittest.main()
