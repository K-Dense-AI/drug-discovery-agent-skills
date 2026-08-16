"""Tests for the DeepChem training scripts.

All three scripts end in a `model.fit(...)` that needs a GPU-scale budget and a
deep-learning backend, so none of them can be run to completion here. What can
be checked is everything that decides *what* gets trained, and that is where
these scripts can go wrong in ways a user only discovers minutes into a run:

* the MoleculeNet table -- `train_on_molnet` resolves a dataset name to
  `dc.molnet.load_<name>` by attribute lookup, so a name with no matching
  loader raises `AttributeError` only after the CLI has accepted it. BACE is
  exactly that case: DeepChem ships `load_bace_classification` and
  `load_bace_regression` but no `load_bace`.
* the model factory -- every `--model` choice must reach a real branch of
  `create_model`, not the fall-through `ValueError`.
* featurizer selection in the transfer-learning script -- ChemBERTa and
  MolFormer consume raw SMILES while GROVER needs graph features, and handing a
  model the wrong representation fails deep inside the fit.
* the fingerprint width, which is declared twice in `predict_solubility.py`:
  once as the regressor's `n_features` and once as the featurizer's `size`. A
  mismatch is a shape error at prediction time, after training has finished.

MoleculeNet loaders are stubbed rather than called, so no test downloads a
benchmark. The custom-CSV path is driven for real on twenty molecules, where the
80/10/10 scaffold split has a known answer.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "deepchem"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

deepchem = pytest.importorskip("deepchem", reason="deepchem skill needs deepchem")
pytest.importorskip("numpy", reason="deepchem skill needs numpy")

import graph_neural_network  # noqa: E402
import predict_solubility  # noqa: E402
import transfer_learning  # noqa: E402

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)

#: Published MoleculeNet task types. Delaney (ESOL), FreeSolv and Lipophilicity
#: are regression benchmarks; Tox21, BBBP, BACE and HIV are classification.
PUBLISHED_TASK_TYPES = {
    "tox21": "classification",
    "bbbp": "classification",
    "bace": "classification",
    "hiv": "classification",
    "delaney": "regression",
    "freesolv": "regression",
    "lipo": "regression",
}

#: Tox21 comprises 12 toxicity assays; the other benchmarks here are single-task.
PUBLISHED_TASK_COUNTS = {
    "tox21": 12,
    "bbbp": 1,
    "bace": 1,
    "hiv": 1,
    "delaney": 1,
    "freesolv": 1,
    "lipo": 1,
}

#: Twenty distinct molecules -- enough scaffolds for an 80/10/10 split to give
#: whole numbers, and small enough to featurize in milliseconds.
SAMPLE_SMILES = [
    "CCO", "CCC", "CCCC", "c1ccccc1", "CC(=O)O",
    "CN1C=NC2=C1C(=O)N(C(=O)N2C)C", "CCN", "CCCN", "c1ccncc1", "CC(C)O",
    "CCOC", "CCCl", "CCBr", "c1ccc(O)cc1", "CC(N)=O",
    "CCS", "CC#N", "CCC=O", "c1ccc2ccccc2c1", "CC(C)(C)O",
]


def parser_choices(module, destination: str) -> list[str]:
    """The choices argparse offers for one option of a script's parser.

    The parsers are built inside `main`, so they cannot be obtained without
    running it; the choice lists are read off the module source instead.
    """
    tree = ast.parse((SCRIPTS / f"{module.__name__}.py").read_text(encoding="utf-8"))
    flag = "--" + destination.replace("_", "-")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (node.args and isinstance(node.args[0], ast.Constant)):
            continue
        if node.args[0].value != flag:
            continue
        for keyword in node.keywords:
            if keyword.arg != "choices":
                continue
            source = ast.unparse(keyword.value)
            if source.startswith("list("):
                # `choices=list(SOME_DICT)` or `choices=list(SOME_DICT.keys())`
                name = source[len("list(") : -1].removesuffix(".keys()")
                return list(getattr(module, name))
            return list(ast.literal_eval(keyword.value))
    raise AssertionError(f"{module.__name__} has no {flag} with choices")


def dotted_name(node: ast.AST) -> str:
    return ast.unparse(node)


def keyword_constants(source: str, callee: str, keyword: str) -> list[object]:
    """Every constant passed as `keyword` to calls of `callee` in `source`."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and dotted_name(node.func) == callee:
            for argument in node.keywords:
                if argument.arg == keyword and isinstance(argument.value, ast.Constant):
                    found.append(argument.value.value)
    return found


def run_script(name: str, *arguments: str, cwd: Path) -> subprocess.CompletedProcess:
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "MPLBACKEND": "Agg"}
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *arguments],
        capture_output=True,
        text=True,
        timeout=300,
        env=environment,
        cwd=str(cwd),
    )


class MolnetCatalogueTests(unittest.TestCase):
    """The dataset table in graph_neural_network.py."""

    def test_every_dataset_name_resolves_to_a_real_molnet_loader(self) -> None:
        # The regression this guards: `getattr(dc.molnet, f"load_{name}")` for a
        # dataset DeepChem exposes only under a suffixed loader name.
        for name in graph_neural_network.MOLNET_DATASETS:
            with self.subTest(dataset=name):
                loader = graph_neural_network.molnet_loader(name)
                self.assertTrue(callable(loader))

    def test_bace_resolves_to_the_classification_loader(self) -> None:
        # DeepChem has no `load_bace`; the table declares BACE a classification
        # benchmark, so the classification loader is the matching one.
        self.assertIs(
            graph_neural_network.molnet_loader("bace"),
            deepchem.molnet.load_bace_classification,
        )
        self.assertFalse(hasattr(deepchem.molnet, "load_bace"))

    def test_the_declared_task_types_match_the_published_benchmarks(self) -> None:
        # The task type selects the metric set (ROC-AUC vs R²) and the model
        # mode, so calling a regression benchmark "classification" produces
        # numbers that look plausible and mean nothing.
        self.assertEqual(
            {
                name: task_type
                for name, (task_type, _) in graph_neural_network.MOLNET_DATASETS.items()
            },
            PUBLISHED_TASK_TYPES,
        )

    def test_the_declared_task_counts_match_the_published_benchmarks(self) -> None:
        self.assertEqual(
            {
                name: count
                for name, (_, count) in graph_neural_network.MOLNET_DATASETS.items()
            },
            PUBLISHED_TASK_COUNTS,
        )

    def test_the_dataset_flag_offers_exactly_the_table(self) -> None:
        self.assertEqual(
            parser_choices(graph_neural_network, "dataset"),
            list(graph_neural_network.MOLNET_DATASETS),
        )

    def test_the_model_flag_offers_exactly_the_model_table(self) -> None:
        self.assertEqual(
            parser_choices(graph_neural_network, "model"),
            list(graph_neural_network.AVAILABLE_MODELS),
        )


class ModelFactoryTests(unittest.TestCase):
    """`create_model` must cover every `--model` choice."""

    def test_an_unknown_model_is_refused_by_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown model type: transformer"):
            graph_neural_network.create_model("transformer", 1)

    def test_every_advertised_model_reaches_a_branch(self) -> None:
        # Constructing these needs a torch backend, which the documented install
        # does not always provide, so the assertion is narrower than "it works":
        # whatever happens, it must not be the unknown-model fall-through.
        for name in graph_neural_network.AVAILABLE_MODELS:
            with self.subTest(model=name):
                try:
                    graph_neural_network.create_model(name, 1)
                except ValueError as error:  # pragma: no cover - backend dependent
                    self.fail(f"{name} is advertised but unreachable: {error}")
                except Exception:
                    # A missing deep-learning backend is an environment problem,
                    # not a wiring problem.
                    pass

    def test_every_advertised_model_has_a_human_readable_description(self) -> None:
        # The descriptions are printed as the run banner, so an empty one leaves
        # the log ambiguous about what was trained.
        for name, description in graph_neural_network.AVAILABLE_MODELS.items():
            with self.subTest(model=name):
                self.assertTrue(description.strip())
                self.assertNotEqual(description, name)


class PretrainedCatalogueTests(unittest.TestCase):
    """The pretrained-model table in transfer_learning.py."""

    def test_the_model_flag_offers_exactly_the_pretrained_table(self) -> None:
        self.assertEqual(
            parser_choices(transfer_learning, "model"),
            list(transfer_learning.PRETRAINED_MODELS),
        )

    def test_each_entry_carries_a_name_and_a_description(self) -> None:
        for key, entry in transfer_learning.PRETRAINED_MODELS.items():
            with self.subTest(model=key):
                self.assertEqual(set(entry), {"name", "description", "model_id"})
                self.assertTrue(entry["name"].strip())
                self.assertTrue(entry["description"].strip())

    def test_the_hub_backed_models_name_a_hugging_face_repository(self) -> None:
        # These strings are passed straight to HuggingFaceModel; a bare model
        # name without the owner prefix cannot be resolved.
        for key in ("chemberta", "molformer"):
            with self.subTest(model=key):
                model_id = transfer_learning.PRETRAINED_MODELS[key]["model_id"]
                self.assertRegex(model_id, r"^[\w.-]+/[\w.-]+$")

    def test_grover_declares_no_hub_id_because_it_loads_itself(self) -> None:
        # GroverModel takes a model_dir, not a hub id; a placeholder string here
        # would be passed to a loader that ignores it.
        self.assertIsNone(transfer_learning.PRETRAINED_MODELS["grover"]["model_id"])

    def test_every_pretrained_model_has_a_fine_tuning_entry_point(self) -> None:
        # main() dispatches on the key; an unhandled one falls through to a
        # "not yet implemented" message after the dataset has been loaded.
        for key in transfer_learning.PRETRAINED_MODELS:
            with self.subTest(model=key):
                self.assertTrue(callable(getattr(transfer_learning, f"train_{key}")))


class MolnetFeaturizerSelectionTests(unittest.TestCase):
    """`load_molnet_dataset` picks the representation each model can consume."""

    def load(self, dataset: str, model: str, loader: str | None = None) -> dict:
        """Call `load_molnet_dataset` with the real MoleculeNet loader stubbed."""
        captured: dict = {}

        def stub(**keywords):
            captured.update(keywords)
            return (["task"], ("train", "valid", "test"), [])

        with mock.patch.object(deepchem.molnet, loader or f"load_{dataset}", stub):
            transfer_learning.load_molnet_dataset(dataset, model)
        return captured

    def test_smiles_models_get_raw_strings_and_grover_gets_graphs(self) -> None:
        # ChemBERTa and MolFormer tokenise SMILES themselves; GROVER is a graph
        # transformer and cannot read a string.
        self.assertEqual(self.load("bbbp", "chemberta")["featurizer"], "Raw")
        self.assertEqual(self.load("bbbp", "molformer")["featurizer"], "Raw")
        self.assertEqual(self.load("bbbp", "grover")["featurizer"], "GraphConv")

    def test_an_unrecognised_model_falls_back_to_fingerprints(self) -> None:
        self.assertEqual(self.load("bbbp", "random-forest")["featurizer"], "ECFP")

    def test_every_dataset_is_loaded_with_a_scaffold_split(self) -> None:
        # A random split shares scaffolds between train and test and inflates
        # every reported score, so the split must not depend on the model.
        for model in ("chemberta", "grover", "molformer"):
            with self.subTest(model=model):
                self.assertEqual(self.load("delaney", model)["splitter"], "scaffold")

    def test_every_offered_dataset_is_in_the_loader_table(self) -> None:
        # `--dataset` and the dict inside load_molnet_dataset are written out
        # separately, so a name in one and not the other is a live failure --
        # the CLI accepts the run and it dies on "Unknown dataset".
        loaders = (
            "load_tox21",
            "load_bbbp",
            "load_bace_classification",
            "load_hiv",
            "load_delaney",
            "load_freesolv",
            "load_lipo",
        )

        def stub(**keywords):
            return (["task"], ("train", "valid", "test"), [])

        with mock.patch.multiple(
            deepchem.molnet, **{name: stub for name in loaders}
        ):
            for name in parser_choices(transfer_learning, "dataset"):
                with self.subTest(dataset=name):
                    tasks, datasets, _ = transfer_learning.load_molnet_dataset(
                        name, "chemberta"
                    )
                    self.assertEqual(len(datasets), 3)
                    self.assertEqual(tasks, ["task"])

    def test_an_unknown_dataset_is_refused_before_anything_downloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown dataset: not-a-benchmark"):
            transfer_learning.load_molnet_dataset("not-a-benchmark", "chemberta")


class CustomDatasetTests(unittest.TestCase):
    """`load_custom_dataset` on a real CSV, where the split sizes are known."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self.csv = self.root / "molecules.csv"
        rows = "\n".join(
            f"{smiles},{index % 2}" for index, smiles in enumerate(SAMPLE_SMILES)
        )
        self.csv.write_text(f"smiles,target\n{rows}\n", encoding="utf-8")

    def test_the_split_is_eighty_ten_ten(self) -> None:
        train, valid, test = transfer_learning.load_custom_dataset(
            str(self.csv), ["target"], "smiles", "chemberta"
        )
        self.assertEqual((len(train), len(valid), len(test)), (16, 2, 2))
        # Nothing is lost or duplicated by the split.
        self.assertEqual(len(train) + len(valid) + len(test), len(SAMPLE_SMILES))

    def test_a_smiles_model_keeps_the_strings_unfeaturized(self) -> None:
        # DummyFeaturizer is deliberate: the tokenizer inside the model does the
        # featurizing, so turning the SMILES into a fingerprint here would
        # destroy the input it needs.
        train, _, _ = transfer_learning.load_custom_dataset(
            str(self.csv), ["target"], "smiles", "chemberta"
        )
        self.assertEqual(train.X[0], "CCO")

    def test_a_fingerprint_model_gets_a_2048_bit_vector(self) -> None:
        train, _, _ = transfer_learning.load_custom_dataset(
            str(self.csv), ["target"], "smiles", "random-forest"
        )
        # CircularFingerprint's documented default width.
        self.assertEqual(train.X.shape, (16, 2048))

    def test_the_named_smiles_column_is_the_one_featurized(self) -> None:
        path = self.root / "renamed.csv"
        rows = "\n".join(
            f"{index % 2},{smiles}" for index, smiles in enumerate(SAMPLE_SMILES)
        )
        path.write_text(f"target,structure\n{rows}\n", encoding="utf-8")
        train, _, _ = transfer_learning.load_custom_dataset(
            str(path), ["target"], "structure", "chemberta"
        )
        self.assertEqual(train.X[0], "CCO")


class SolubilityScriptTests(unittest.TestCase):
    """Static consistency in predict_solubility.py."""

    def test_the_fingerprint_width_matches_the_regressor_input_size(self) -> None:
        # `n_features` is fixed when the model is built and `size` when new
        # molecules are featurized. A mismatch is a shape error at predict
        # time -- after the training run has already been paid for.
        source = (SCRIPTS / "predict_solubility.py").read_text(encoding="utf-8")
        declared = keyword_constants(source, "dc.models.MultitaskRegressor", "n_features")
        featurized = keyword_constants(source, "dc.feat.CircularFingerprint", "size")
        self.assertEqual(len(set(declared)), 1, declared)
        self.assertEqual(set(declared), set(featurized))

    def test_the_fingerprint_radius_is_the_same_everywhere(self) -> None:
        # Training on ECFP4 and predicting with ECFP6 silently produces garbage
        # rather than an error, because the vector width is unchanged.
        source = (SCRIPTS / "predict_solubility.py").read_text(encoding="utf-8")
        radii = keyword_constants(source, "dc.feat.CircularFingerprint", "radius")
        self.assertEqual(len(set(radii)), 1, radii)

    def test_the_default_target_column_is_the_delaney_column_name(self) -> None:
        # The function's default has to match the column in the published
        # Delaney (ESOL) CSV, or the benchmark path finds no target.
        import inspect

        default = inspect.signature(
            predict_solubility.train_solubility_model
        ).parameters["target_col"].default
        self.assertEqual(default, "measured log solubility in mols per litre")


class ArgumentValidationTests(unittest.TestCase):
    """Both scripts refuse an ambiguous invocation before loading anything."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)

    def test_a_gnn_run_needs_a_dataset_or_a_csv(self) -> None:
        result = run_script("graph_neural_network.py", cwd=self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Must specify either", result.stderr)

    def test_a_gnn_run_refuses_both_a_dataset_and_a_csv(self) -> None:
        # Silently preferring one would train on data the user did not ask for.
        result = run_script(
            "graph_neural_network.py", "--dataset", "bbbp", "--data", "custom.csv",
            cwd=self.root,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Cannot specify both", result.stderr)

    def test_transfer_learning_requires_a_pretrained_model(self) -> None:
        result = run_script("transfer_learning.py", "--dataset", "bbbp", cwd=self.root)
        # argparse's own exit code for a missing required option.
        self.assertEqual(result.returncode, 2)
        self.assertIn("--model", result.stderr)

    def test_transfer_learning_refuses_both_input_sources(self) -> None:
        result = run_script(
            "transfer_learning.py", "--model", "chemberta",
            "--dataset", "bbbp", "--data", "custom.csv",
            cwd=self.root,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Cannot specify both", result.stderr)


if __name__ == "__main__":
    unittest.main()
