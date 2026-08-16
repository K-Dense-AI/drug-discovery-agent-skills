# Available Featurizers in Molfeat

Catalog for **molfeat 0.11.0**. Every width below was measured by calling the featurizer with
default parameters on Python 3.10 (RDKit 2026.03.5) — not copied from documentation.

Two different name spaces exist and they do not match:

- **Calculator names** passed to `get_calculator()` / `MoleculeTransformer("...")` —
  `desc2D`, `cats2D`, `pharm2D`, `ecfp`, ...
- **Model-store card names** returned by `ModelStore().available_models` —
  `pharm2D-gobbi`, `gin_supervised_masking`, `ChemBERTa-77M-MLM`, ... (underscores and
  hyphens are literal; `gin-supervised-masking` is not a valid name).

## Model store contents (44 cards)

`ModelStore()` in 0.11.0 serves exactly 44 cards, grouped as follows.

| Group | Cards | Artifact |
|---|---|---|
| `huggingface` | `ChemBERTa-77M-MLM`, `ChemBERTa-77M-MTR`, `ChemGPT-1.2B`, `ChemGPT-19M`, `ChemGPT-4.7M`, `GPT2-Zinc480M-87M`, `MolT5`, `Roberta-Zinc480M-102M` | directory — **not downloadable from the store**, see below |
| `dgllife` | `gin_supervised_contextpred`, `gin_supervised_edgepred`, `gin_supervised_infomax`, `gin_supervised_masking`, `jtvae_zinc_no_kl` | file |
| `graphormer` | `pcqm4mv2_graphormer_base` | file |
| `rdkit` | `ecfp`, `ecfp-count`, `fcfp`, `fcfp-count`, `atompair-count`, `topological`, `topological-count`, `avalon`, `pattern`, `rdkit`, `maccs`, `estate`, `erg`, `desc2D`, `desc3D` | file |
| `fp` | `map4`, `secfp` | file |
| `pharmacophore` | `pharm2D-cats`, `pharm2D-default`, `pharm2D-gobbi`, `pharm2D-pmapper`, `pharm3D-cats`, `pharm3D-gobbi`, `pharm3D-pmapper` | file |
| `shape` | `usr`, `usrcat`, `electroshape` | file |
| `all` | `cats2d`, `cats3d`, `scaffoldkeys` | file |

The 8 HuggingFace cards fail to download in 0.11.0 (`IsADirectoryError` →
`ModelStoreError: Can't retrieve model ... from the store !`) because the store now serves
directory artifacts over plain HTTP. Load them from the HuggingFace Hub with
`HFModel.from_pretrained` instead — see the pretrained section of the main `SKILL.md`. The 36
single-file cards download normally.

Cards carry `inputs` (`smiles`, `selfies`, or `mol`), `require_3D`, `description`, `authors`,
`reference`, and `usage()`, which returns the canonical snippet as a string.

## Fingerprints

All 19 methods accepted by `FPCalculator`, with measured default widths.

| Name | Width | Notes |
|---|---|---|
| `ecfp` | 2048 | Circular; **default radius 2** (= ECFP4). `radius`, `fpSize`, `includeChirality` |
| `ecfp-count` | 2048 | Count version |
| `fcfp` / `fcfp-count` | 2048 | Feature-class circular (pharmacophoric atom invariants) |
| `maccs` | 167 | 166 MACCS keys plus an unused index-0 bit |
| `avalon` / `avalon-count` | 512 | Avalon toolkit |
| `rdkit` / `rdkit-count` | 2048 | Path-based topological |
| `pattern` | 2048 | Substructure-screening fingerprint |
| `layered` | 2048 | Layered substructure |
| `atompair` / `atompair-count` | 2048 | `minDistance=1`, `maxDistance=30`, `use2D=True` |
| `topological` / `topological-count` | 2048 | Topological torsions |
| `erg` | 315 | Extended reduced graph, pharmacophore nodes |
| `estate` | 79 | E-state indices |
| `secfp` | 2048 | SMILES extended connectivity, `radius=3`, `n_permutations=128` |
| `map4` | — | Requires the external [map4](https://github.com/reymond-group/map4) package; defaults `dimensions=2048`, `radius=2` |

Set a custom width with `FPCalculator(method, length=1024)`; the per-method key (`fpSize`,
`nBits`, `dimensions`) also works, but a wrong key is logged and ignored rather than raising.

## Descriptors

| Name | Class | Width | Notes |
|---|---|---|---|
| `desc2D` | `RDKitDescriptors2D` | 223 | Named RDKit 2D descriptors; `.columns` gives names. Args: `replace_nan`, `augment`, `descrs`, `ignore_descrs`, `avg_ipc` |
| `desc3D` | `RDKitDescriptors3D` | 639 | PMI ratios, asphericity, radius of gyration, autocorrelations — needs conformers |
| `mordred` | `MordredDescriptors` | 1613 | Broad descriptor sweep; implements `batch_compute`, so `n_jobs` adds little |
| `estate` | `FPCalculator("estate")` | 79 | E-state indices |

`desc2D` is the interpretability workhorse — every column has a name, which is what makes
coefficient inspection meaningful after a linear model.

## Pharmacophores

| Name | Class | Width | Notes |
|---|---|---|---|
| `cats2D` | `CATS(use_3d_distances=False)` | 189 | Topological-distance pharmacophore pair histogram |
| `cats3D` | `CATS(use_3d_distances=True)` | 126 | Euclidean distances; needs conformers |
| `pharm2D` | `Pharmacophore2D(factory=...)` | 2048 | `factory` ∈ `default`, `gobbi`, `pmapper`, `cats`; default `pmapper` |
| `pharm3D` | `Pharmacophore3D(factory=...)` | 2048 | Consensus over conformers |

There is no `gobbi2D`, `pmapper2D`, or `cats2D_pharm` calculator — those are `factory` values
of `Pharmacophore2D` (and `pharm2D-gobbi` / `pharm2D-pmapper` as store card names).

## Shape descriptors

| Name | Class | Width | Notes |
|---|---|---|---|
| `usr` | `USRDescriptors(method="usr")` | 12 | Ultrafast shape recognition |
| `usrcat` | `USRDescriptors(method="usrcat")` | 60 | USR + pharmacophoric channels |
| `electroshape` | `ElectroShapeDescriptors()` | 15 | Shape, chirality, and partial charges |

All three require conformers — pass `Mol` objects with 3D coordinates, not SMILES.

## Scaffold descriptors

| Name | Class | Width | Notes |
|---|---|---|---|
| `scaffoldkeys` | `ScaffoldKeyCalculator()` | 42 | Scaffold-level counts and ratios; aliases `skeys`, `scaffkeys` |

## Pretrained embeddings

| Card | Transformer class | Width | Notes |
|---|---|---|---|
| `ChemBERTa-77M-MLM` | `PretrainedHFTransformer` | 384 | RoBERTa MLM on 77M PubChem SMILES |
| `ChemBERTa-77M-MTR` | `PretrainedHFTransformer` | 384 | Multitask-regression pretraining |
| `Roberta-Zinc480M-102M` | `PretrainedHFTransformer` | — | RoBERTa on ~480M ZINC SMILES |
| `GPT2-Zinc480M-87M` | `PretrainedHFTransformer` | — | GPT-2 on ~480M ZINC SMILES |
| `ChemGPT-4.7M` / `-19M` / `-1.2B` | `PretrainedHFTransformer` | — | Autoregressive on PubChem10M; `notation="selfies"` |
| `MolT5` | `PretrainedHFTransformer` | — | Encoder-decoder, molecule↔text |
| `gin_supervised_masking` | `PretrainedDGLTransformer` | 300 | GIN pretrained on ChEMBL, masking objective |
| `gin_supervised_infomax` | `PretrainedDGLTransformer` | 300 | Mutual-information maximization |
| `gin_supervised_edgepred` | `PretrainedDGLTransformer` | 300 | Edge prediction |
| `gin_supervised_contextpred` | `PretrainedDGLTransformer` | 300 | Context prediction |
| `jtvae_zinc_no_kl` | `PretrainedDGLTransformer` | — | Junction-tree VAE latent space |
| `pcqm4mv2_graphormer_base` | `GraphormerTransformer` | — | Graph transformer, PCQM4Mv2 quantum properties |
| FCD | `FCDTransformer` | — | ChemNet activations for Fréchet ChemNet Distance |

Widths marked `—` were not executed here (they need the corresponding extra plus a model
download); read `X.shape` after a first call rather than assuming a hidden size. The commonly
quoted "768" applies to none of the ChemBERTa-77M checkpoints.

Pass `notation` matching the card's `inputs` field: `selfies` for ChemGPT, `smiles` elsewhere.
Pooling defaults to `mean`; `cls` and `max` are also available.

## Graph featurizers for GNN input

Atom- and bond-level calculators, for building your own graph pipelines:

```python
from molfeat.calc.atom import AtomCalculator, AtomMaterialCalculator, DGLCanonicalAtomCalculator, DGLWeaveAtomCalculator
from molfeat.calc.bond import BondCalculator, EdgeMatCalculator, DGLCanonicalBondCalculator, DGLWeaveEdgeCalculator
```

They are not exported from `molfeat.calc` itself — import from the submodules.

## Optional dependencies

| Featurizers | Install |
|---|---|
| ChemBERTa, ChemGPT, MolT5, Zinc models | `uv pip install "molfeat[transformer]==0.11.0"` |
| `gin_supervised_*`, `jtvae_zinc_no_kl` | `uv pip install "molfeat[dgl]==0.11.0"` (`dgl>=1.1.1,<=2.0`) |
| `pcqm4mv2_graphormer_base` | `uv pip install "molfeat[graphormer]==0.11.0"` |
| FCD | `uv pip install "molfeat[fcd]==0.11.0"` |
| PyTorch Geometric featurizers | `uv pip install "molfeat[pyg]==0.11.0"` |
| NGLView widgets | `uv pip install "molfeat[viz]==0.11.0"` |
| Everything pip-installable | `uv pip install "molfeat[all]==0.11.0"` |
| MAP4 | external: [reymond-group/map4](https://github.com/reymond-group/map4) |

## Choosing by task

**Traditional ML (RF, SVM, XGBoost)** — `ecfp` or `maccs` first; `desc2D` when you need to
explain the model; `FeatConcat(["maccs", "ecfp"])` (2167 dims) when you want both.

**Deep learning** — ChemBERTa embeddings for transfer learning, `gin_supervised_*` for graph
representations, Graphormer for quantum-property tasks.

**Similarity searching** — `ecfp` for general purpose, `maccs` for scaffold-level similarity,
`usr`/`usrcat` for 3D shape.

**Pharmacophore-driven work** — `fcfp`, `cats2D`, `pharm2D` with the `gobbi` or `pmapper`
factory.

**Interpretability** — `desc2D` and `mordred` (named columns), `maccs` (defined substructure
keys), `scaffoldkeys`.

## Speed and size at a glance

Measured wall-clock, single process, 12-core machine:

| Featurizer | 300 molecules | 10,272 molecules |
|---|---|---|
| `ecfp` | <0.05 s | 0.43 s |
| `desc2D` | 0.96 s | — |
| `mordred` | 4.83 s | — |

3D featurizers (`desc3D`, `usr`, `cats3D`, `pharm3D`, `electroshape`) are dominated by
conformer generation, not by the descriptor itself. Pretrained models are dominated by the
first-run download and then by batch inference.

Width bands: shape descriptors 12–60; `maccs` 167; `cats2D` 189; `desc2D` 223;
GIN 300; `erg` 315; ChemBERTa-77M 384; `avalon` 512; `desc3D` 639; `mordred` 1613;
most fingerprints 2048; concatenations whatever their parts add up to.

## Listing everything programmatically

```python
from molfeat.store.modelstore import ModelStore

store = ModelStore()
for card in store.available_models:
    print(f"{card.name:32s} {card.group:14s} {card.type:14s} inputs={card.inputs}")

pretrained = [c for c in store.available_models if c.type == "pretrained"]
needs_3d = [c for c in store.available_models if c.require_3D]
```
