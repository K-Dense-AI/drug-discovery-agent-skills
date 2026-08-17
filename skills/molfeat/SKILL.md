---
name: molfeat
description: Molecular featurization hub with one consistent interface over 100+ featurizers. Fingerprints (ECFP/Morgan, MACCS, atom pair, topological torsion, Avalon, RDKit, ERG), RDKit and Mordred descriptor sets, pharmacophore and 3D shape descriptors, scaffold keys, and pretrained embeddings (ChemBERTa, ChemGPT, MolT5, GIN, Graphormer) through a common transformer API with caching and parallelism. Use this skill to convert SMILES into model-ready feature matrices for QSAR, virtual screening, and molecular ML, and to choose between featurizer families. Also trigger on molfeat, MoleculeTransformer, FPVecTransformer, PretrainedHFTransformer, molfeat model store, or featurizer selection.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.9–3.10 (molfeat 0.11.0 declares `requires-python <3.11`). Requires datamol, RDKit, and PyTorch; GNN and transformer featurizers need optional extras. The 8 HuggingFace models in the model store cannot be downloaded from it — see "Pretrained models" below.
metadata:
  version: "1.4"
  skill-author: K-Dense Inc.
---

# Molfeat - Molecular Featurization Hub

## Overview

Molfeat turns molecules (SMILES strings or RDKit/datamol `Mol` objects) into numerical
representations for machine learning: fingerprints, descriptors, pharmacophores, shape
descriptors, and pretrained neural embeddings, all behind one scikit-learn-compatible
transformer interface with state serialization and caching.

**Current baseline (verified 2026-08-16):** **molfeat 0.11.0** (May 2025) is still the latest
PyPI and GitHub release; the repository has had no commits since. All examples in this skill
were executed against 0.11.0 on **Python 3.10** with datamol 0.12.5, RDKit 2026.03.5, numpy
2.2.6 and torch 2.13.0. Python 3.11+ is not installable (`requires-python = ">=3.9,<3.11"`).

**The Python cap isolates this skill from the rest of the bundle.** Nothing else here needs an
interpreter below 3.11, so molfeat requires its own environment and cannot share one with
`admet-prediction` (3.11+), `pytdc`, or `deepchem`. That is manageable for a featurisation step
that writes a matrix to disk, and painful for anything interactive. For new work where the
featuriser is not itself the point, RDKit or datamol fingerprints plus a Chemprop or scikit-learn
model reach the same place without the constraint; use molfeat when you specifically want its
breadth of featurisers behind one interface.
0.11.0 loads pretrained models in memory, sets base models to eval mode, and moved the model
store to a Cloudflare HTTP bucket (PR #115) — that last change broke store downloads for the
HuggingFace models (see [Pretrained models](#pretrained-models)).

## When to Use This Skill

- Converting SMILES into ML-ready feature matrices (QSAR/QSPR, ADMET, activity prediction)
- Virtual screening: featurize a library, score it with a trained model
- Similarity searching and chemical-space analysis (clustering, UMAP/t-SNE)
- Benchmarking several representations against each other on the same task
- Building reproducible featurization pipelines that can be serialized and reloaded

For raw cheminformatics control (custom sanitization, reactions, substructures) use `rdkit` or
`datamol` directly; molfeat is the layer above them that produces feature matrices.

## Installation

```bash
uv venv --python 3.10 && uv pip install "molfeat==0.11.0"
```

Optional extras (all pin-able the same way):

| Extra | Enables | Note |
|---|---|---|
| `molfeat[transformer]` | ChemBERTa, ChemGPT, MolT5, GPT2/Roberta-Zinc | Pins `tokenizers<0.13.2`, so it resolves to `transformers` 4.33.x |
| `molfeat[dgl]` | GIN variants, JTVAE | Needs `dgl>=1.1.1,<=2.0`; conda-forge is easier than PyPI |
| `molfeat[graphormer]` | `pcqm4mv2_graphormer_base` | `graphormer-pretrained` |
| `molfeat[fcd]` | FCD descriptors | |
| `molfeat[pyg]` | PyTorch Geometric featurizers | |
| `molfeat[viz]` | NGLView widgets | |

MAP4 is **not** a molfeat extra. `FPCalculator("map4")` raises `ImportError: Cannot import
map4` until you install it from [reymond-group/map4](https://github.com/reymond-group/map4).

## Three Things to Get Right First

These three calls are where most molfeat scripts go wrong; everything else follows the docs.

```python
import numpy as np
from molfeat.trans import MoleculeTransformer

# 1. Without `dtype`, the transformer returns a LIST of arrays, not a matrix.
#    `features.shape` raises AttributeError. Pass dtype to get an ndarray.
transformer = MoleculeTransformer("ecfp", dtype=np.float32)

# 2. `ignore_errors` is a CALL argument, not a constructor argument. Passing it to
#    the constructor is silently swallowed by **params and does nothing.
features, valid_ids = transformer(smiles, ignore_errors=True)

# 3. With ignore_errors=True, __call__ returns (features, ids) and DROPS failures.
#    Realign the labels with `ids` or the rows no longer match y.
y = np.asarray(y)[valid_ids]
```

`transformer.transform(smiles, ignore_errors=True)` is the other half of the pair: it returns a
plain list with `None` in the failed positions instead of dropping them.

## Core Concepts

### 1. Calculators (`molfeat.calc`)

Callable objects that featurize one molecule. Exported from `molfeat.calc`: `FPCalculator`,
`RDKitDescriptors2D`, `RDKitDescriptors3D`, `MordredDescriptors`, `CATS`, `Pharmacophore2D`,
`Pharmacophore3D`, `USRDescriptors`, `ElectroShapeDescriptors`, `ScaffoldKeyCalculator`,
plus the `SerializableCalculator` base class. Atom- and bond-level calculators for GNN input
live one level deeper, in `molfeat.calc.atom` and `molfeat.calc.bond`.

```python
from molfeat.calc import FPCalculator, get_calculator

calc = FPCalculator("ecfp", radius=2, fpSize=2048)   # radius 2 is the default (= ECFP4)
fp = calc("CCO")            # numpy uint8 array, shape (2048,)
len(calc)                   # 2048
calc.columns[:3]            # ['fp_0', 'fp_1', 'fp_2']

calc = get_calculator("desc2D")   # factory: any built-in by name
```

`get_calculator` accepts every name in `FP_FUNCS` plus `desc2D`, `desc3D`, `mordred`, `cats`,
`cats2D`, `cats3D`, `pharm2D`, `pharm3D`, `usr*`, `electroshape`, and `scaffoldkeys`.

### 2. Transformers (`molfeat.trans`)

`MoleculeTransformer` wraps a calculator (or a calculator *name*) for batch use and plugs into
scikit-learn pipelines. `FPVecTransformer` is the fingerprint-specific shortcut, and unlike
`MoleculeTransformer` it defaults to `dtype=np.float32`, so it returns an array out of the box.

```python
import numpy as np
from molfeat.trans import MoleculeTransformer, FPVecTransformer, FeatConcat

t = MoleculeTransformer("ecfp", n_jobs=1, dtype=np.float32)
X = t(smiles)                                   # (n, 2048) float32

fp = FPVecTransformer(kind="ecfp:4", length=1024)   # "name:diameter"; length defaults to 2000
X = fp(smiles)                                      # (n, 1024) float32

both = FeatConcat(["maccs", "ecfp"], dtype=np.float32)
X = both(smiles)                                # (n, 2167) — 167 + 2048
```

`FeatConcat` **is itself a transformer**. Do not wrap it in `MoleculeTransformer`.

### 3. Pretrained transformers (`molfeat.trans.pretrained`)

One class per backend — there is no generic "load by name" transformer:

| Class | For | Example |
|---|---|---|
| `PretrainedHFTransformer` | ChemBERTa, ChemGPT, MolT5, GPT2/Roberta-Zinc | `PretrainedHFTransformer(kind="ChemBERTa-77M-MLM", notation="smiles")` |
| `PretrainedDGLTransformer` | GIN variants, JTVAE | `PretrainedDGLTransformer(kind="gin_supervised_masking", dtype=float)` |
| `GraphormerTransformer` | Graphormer | `GraphormerTransformer(kind="pcqm4mv2_graphormer_base", dtype=float)` |
| `FCDTransformer` | FCD embeddings | `FCDTransformer()` |

`PretrainedMolTransformer` is the abstract base for these — instantiating it with a model name
does not work.

## Pretrained models

**The 8 HuggingFace models in the model store cannot be downloaded from it.** Since 0.11.0
serves artifacts over plain HTTP, `HTTPFileSystem.find()` reports the artifact directory itself
as a file, so datamol's `copy_dir` tries to write a file over the destination directory:

```text
IsADirectoryError: [Errno 21] Is a directory: '~/Library/Caches/molfeat/ChemBERTa-77M-MLM/model.save'
ModelStoreError: Can't retrieve model ChemBERTa-77M-MLM from the store !
```

This is not a version-pin problem — it reproduces on fsspec 2024.6.1, 2025.3.0 and 2026.7.0 —
and it is open upstream as
[#119](https://github.com/datamol-io/molfeat/issues/119) and
[#120](https://github.com/datamol-io/molfeat/issues/120). It affects only the 8 HuggingFace
cards (ChemBERTa x2, ChemGPT x3, MolT5, GPT2-Zinc480M-87M, Roberta-Zinc480M-102M); the 36
other cards are single-file artifacts and download normally.

Load those models from the HuggingFace Hub instead — verified working:

```python
import numpy as np
from molfeat.trans.pretrained.hf_transformers import HFModel, PretrainedHFTransformer

model = HFModel.from_pretrained("DeepChem/ChemBERTa-77M-MLM", "DeepChem/ChemBERTa-77M-MLM")
transformer = PretrainedHFTransformer(kind=model, notation="smiles", dtype=np.float32)
X = transformer(["CCO", "CC(=O)O", "c1ccccc1"])     # (3, 384) float32, mean pooling
```

Note the width: **ChemBERTa-77M is 384-dimensional**, not 768. Check `X.shape` rather than
assuming a hidden size.

Pooling defaults to `mean`; `avg`, `sum`, and `clf` (CLS token) also work. `pooling="max"`
raises `RuntimeError: masked_fill_ only supports boolean masks` on current PyTorch — molfeat
builds a long mask — so avoid it.

## Discovering featurizers

```python
from molfeat.store.modelstore import ModelStore

store = ModelStore()
len(store.available_models)        # 44 cards in 0.11.0

card = store.search(name="ChemBERTa-77M-MLM")[0]
print(card.name, card.group, card.inputs, card.description)
print(card.usage())                # returns the canonical snippet as a string
```

`store.load(name)` returns a `(model, ModelInfo)` **tuple**, not a transformer — use the
transformer classes above for featurization, and `store.load` only when you want the raw
artifact. A full name-by-name catalog is in
[references/available_featurizers.md](references/available_featurizers.md).

## Quick Start

```python
import numpy as np
import datamol as dm
from molfeat.trans import MoleculeTransformer

data = dm.data.freesolv()                       # 642 molecules: iupac, smiles, expt, calc
smiles = data.smiles.tolist()

transformer = MoleculeTransformer("ecfp", n_jobs=1, dtype=np.float32)
X, ids = transformer(smiles, ignore_errors=True)
y = data.expt.values[ids]
print(X.shape, y.shape)                         # (642, 2048) (642,)
```

### Save and reload a configuration

```python
transformer.to_state_yaml_file("featurizer.yml")     # also to_state_json_file
loaded = MoleculeTransformer.from_state_yaml_file("featurizer.yml")
```

The state file records the molfeat version alongside the featurizer arguments, which is what
makes it worth committing next to a trained model.

### Standardize before featurizing

`preprocess()` is a batch hook with the signature `preprocess(inputs, labels)`, and `transform`
**never calls it**. Overriding it per-molecule does nothing. Standardize explicitly instead:

```python
import datamol as dm

def clean(smi):
    mol = dm.to_mol(smi)
    if mol is None:
        return None
    # dont_remove_everything=True, or a molecule that IS a solvent comes back empty
    mol = dm.remove_salts_solvents(mol, dont_remove_everything=True)
    return dm.to_smiles(dm.standardize_mol(mol, disconnect_metals=True, uncharge=True))

clean_smiles = [s for s in dm.parallelized(clean, smiles, n_jobs=-1) if s]
X = transformer(clean_smiles)
```

(`dm.remove_salts` does not exist; the function is `dm.remove_salts_solvents`.)

## Caching expensive featurization

Use molfeat's own cache rather than a hand-rolled dictionary — it hashes molecules canonically,
so a re-run hits the cache even when the input SMILES are written differently:

```python
import numpy as np
from molfeat.trans import MoleculeTransformer
from molfeat.trans.base import PrecomputedMolTransformer
from molfeat.utils.cache import FileCache

base = MoleculeTransformer("desc2D", n_jobs=-1, dtype=np.float32)
cache = FileCache(cache_file="features.parquet", file_type="parquet", clear_on_exit=False)

featurizer = PrecomputedMolTransformer(cache=cache, featurizer=base, dtype=np.float32)
X = featurizer(smiles)
cache.save_to_file("features.parquet")

# next run
cache = FileCache.load_from_file("features.parquet", file_type="parquet")
featurizer = PrecomputedMolTransformer(cache=cache, featurizer=base, dtype=np.float32)
```

`molfeat.utils.cache` also offers in-memory `DataCache`, multiprocessing-safe `MPDataCache`,
and `CacheList` for chaining. Prefer these over pickling feature matrices yourself; if you do
persist arrays directly, use `np.savez`, not `pickle`, which executes code on load.

## Parallelism: measure before setting n_jobs=-1

`n_jobs=-1` is not free — molfeat parallelizes with joblib processes, and the pickling overhead
exceeds the work for cheap featurizers. Measured on 12 cores:

| Featurizer | Molecules | `n_jobs=1` | `n_jobs=-1` |
|---|---|---|---|
| `ecfp` | 642 | 0.03 s | 0.13 s |
| `ecfp` | 10,272 | 0.43 s | 0.56 s |
| `desc2D` | 300 | 0.96 s | 0.23 s |
| `mordred` | 300 | 4.83 s | 4.21 s |

Rule of thumb: keep `n_jobs=1` for fingerprints at any scale, use `n_jobs=-1` for descriptor
and conformer-dependent calculators (`desc2D`, `desc3D`, pharmacophores, shape), and don't
expect much from it for `mordred`, which does its own batching through `batch_compute`.

## Choosing a Featurizer and Common Workflows

Featurizer choice by task — traditional ML (RF, SVM, XGBoost), deep learning, similarity
searching, pharmacophore-based approaches — plus worked workflows for QSAR model building,
virtual screening, similarity search, scikit-learn pipeline integration, and comparing
featurizers, are in
[references/choosing_a_featurizer.md](references/choosing_a_featurizer.md).

The full featurizer catalog with measured output widths is in
[references/available_featurizers.md](references/available_featurizers.md); more worked code is
in [references/examples.md](references/examples.md); class-by-class signatures are in
[references/api_reference.md](references/api_reference.md).

## Common Featurizers Reference

Widths below are what molfeat 0.11.0 actually returns for default parameters.

| Featurizer | Type | Width | Speed | Use case |
|---|---|---|---|---|
| `ecfp` | Fingerprint | 2048 | Fast | General purpose (radius 2 default) |
| `fcfp` | Fingerprint | 2048 | Fast | Pharmacophore-flavored circular FP |
| `maccs` | Fingerprint | 167 | Very fast | Scaffold similarity |
| `avalon` | Fingerprint | 512 | Fast | Similarity searching |
| `erg` | Reduced graph | 315 | Fast | Scaffold hopping |
| `estate` | Descriptors | 79 | Fast | Electrotopological state |
| `desc2D` | Descriptors | 223 | Medium | Interpretable models |
| `desc3D` | Descriptors | 639 | Slow | Needs conformers |
| `mordred` | Descriptors | 1613 | Slow | Comprehensive descriptor sweep |
| `cats2D` | Pharmacophore | 189 | Medium | Pharmacophore pair distributions |
| `pharm2D` | Pharmacophore | 2048 | Medium | `factory="pmapper"` by default |
| `usr` / `usrcat` | Shape | 12 / 60 | Fast | 3D shape similarity (needs conformers) |
| `scaffoldkeys` | Scaffold | 42 | Fast | Scaffold-level properties |
| `ChemBERTa-77M-MLM` | Transformer | 384 | Slow | Transfer learning (load from HF Hub) |
| `gin_supervised_masking` | GNN | 300 | Slow | Graph embeddings (needs `molfeat[dgl]`) |

## Troubleshooting

**`AttributeError: 'list' object has no attribute 'shape'`** — the transformer has no `dtype`.
Construct it with `dtype=np.float32` (or use `FPVecTransformer`).

**`ValueError: Cannot transform molecule at index i`** — an input failed to parse. Pass
`ignore_errors=True` **to the call**, and use the returned `ids` to realign labels. Set
`verbose=True` on the constructor to log which molecules failed.

**`ModelStoreError: Can't retrieve model <name> from the store!`** — the HuggingFace-artifact
download bug above. Load from the HF Hub with `HFModel.from_pretrained`.

**A fingerprint parameter had no effect** — `FPCalculator` logs unknown parameters as an error
and then drops them; construction still succeeds. `FPCalculator("ecfp", n_bits=1024)` returns
2048 dimensions (the key is `fpSize`). Check `len(calc)` after passing parameters.

**`ImportError: Cannot import map4`** — MAP4 is external; install it from the reymond-group
repository.

**Package will not install** — check the interpreter first: molfeat 0.11.0 is capped below
Python 3.11 and pip/uv will refuse to resolve on 3.11+.

**3D featurizers return errors or zeros** — `desc3D`, `usr`, `usrcat`, `electroshape`,
`cats3D` and `pharm3D` need conformers. Generate them first with
`dm.conformers.generate(mol, n_confs=1)` and pass `Mol` objects, not SMILES.

**Reproducibility** — save `to_state_yaml_file` next to the model, and record
`molfeat.__version__`; state files carry the writing version in `_molfeat_version`.

## Composing with the rest of the bundle

- `rdkit` / `datamol` → before: **standardise and desalt first.** A featurizer embeds whatever
  string it is given, so a salt or mixture produces a vector for the wrong species — and no error.
- `chembl` → before: curated measured bioactivity is what you want to featurize, not raw rows.
- `pytdc` → alongside: the scaffold and cold-start splits. Featurization quality is invisible under
  a random split, which reports a fantasy R² regardless of the representation you chose.
- `deepchem` → after: model fitting, if you want the training loop rather than just the features.
- `admet-prediction` → instead: for standard ADMET endpoints, a ready-made model beats featurizing
  and training from scratch unless you have your own measured data.
- `chemical-space` / `generative-design` → after: features are what a similarity or diversity
  selection over an enumerated set is computed on.

**Try ECFP first.** Across most QSAR tasks a count-based Morgan fingerprint with a gradient-boosted
model is within noise of a pretrained transformer embedding, at a fraction of the cost. Reach for
pretrained embeddings when you have shown ECFP is the bottleneck, not before.

## Additional Resources

- Official documentation: https://molfeat-docs.datamol.io/
- GitHub repository: https://github.com/datamol-io/molfeat
- PyPI package: https://pypi.org/project/molfeat/
- Tutorial: https://portal.valencelabs.com/datamol/post/types-of-featurizers-b1e8HHrbFMkbun6
