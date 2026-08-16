# Molfeat API Reference

Signatures and return types below were read from and executed against **molfeat 0.11.0**
(Python 3.10, datamol 0.12.5, RDKit 2026.03.5).

## Core Modules

- **`molfeat.calc`** — calculators for single-molecule featurization
- **`molfeat.trans`** — scikit-learn compatible transformers for batch processing
- **`molfeat.trans.pretrained`** — one transformer class per pretrained-model backend
- **`molfeat.store`** — model card discovery, download, and registration
- **`molfeat.utils.cache`** — molecule-keyed feature caches
- **`molfeat.plugins`** — plugin system for third-party featurizers
- **`molfeat.viz`** — visualization helpers (requires `molfeat[viz]`)

---

## molfeat.calc — Calculators

Exported from `molfeat.calc`: `FPCalculator`, `RDKitDescriptors2D`, `RDKitDescriptors3D`,
`MordredDescriptors`, `CATS`, `Pharmacophore2D`, `Pharmacophore3D`, `USRDescriptors`,
`ElectroShapeDescriptors`, `ScaffoldKeyCalculator`, `SerializableCalculator`, `get_calculator`,
`FP_FUNCS`. Atom/bond calculators are **not** exported at package level — import them from
`molfeat.calc.atom` and `molfeat.calc.bond`.

### SerializableCalculator (base class)

Subclasses implement `__call__()`; optionally `__len__()`, a `columns` property, and
`batch_compute()` for calculators that are faster in bulk (Mordred uses this).

State management: `to_state_dict()`, `to_state_json()`, `to_state_yaml()`,
`from_state_dict()`, and the `*_file` variants. Every state dict records `_molfeat_version`.

### FPCalculator

```python
FPCalculator(method: str, length: Optional[int] = None, counting: bool = False, **method_params)
```

`length` overrides the method's native width. `counting=True` appends `-count` to the method
name.

`method_params` are checked against the method's own defaults, but an unknown key is only
**logged** (`Params: {'n_bits'} are not valid for ecfp`) and then dropped — construction
succeeds and you get default behavior. `FPCalculator("ecfp", n_bits=1024)` silently returns
2048 dimensions. Verify with `len(calc)` whenever you pass fingerprint parameters, and check
the defaults table below for the correct key names.

**All 19 supported methods** (`FPCalculator.available_fingerprints()` / `FP_FUNCS`):

`atompair`, `atompair-count`, `avalon`, `avalon-count`, `ecfp`, `ecfp-count`, `erg`, `estate`,
`fcfp`, `fcfp-count`, `layered`, `maccs`, `map4`, `pattern`, `rdkit`, `rdkit-count`, `secfp`,
`topological`, `topological-count`

**Default parameters that differ from common assumptions:**

| Method | Defaults | Width |
|---|---|---|
| `ecfp` / `fcfp` | `radius=2`, `fpSize=2048`, `includeChirality=False`, `useBondTypes=True` | 2048 |
| `atompair` | `minDistance=1`, `maxDistance=30`, `use2D=True`, `fpSize=2048` | 2048 |
| `secfp` | `n_permutations=128`, `nBits=2048`, `radius=3`, `rings=True` | 2048 |
| `map4` | `dimensions=2048`, `radius=2` | needs external `map4` package |
| `maccs` | none | 167 |
| `avalon` | | 512 |
| `erg` | | 315 |
| `estate` | | 79 |
| `rdkit`, `pattern`, `layered`, `topological` | | 2048 |

ECFP's radius default is **2** (ECFP4), not 3.

```python
from molfeat.calc import FPCalculator

calc = FPCalculator("ecfp", radius=2, fpSize=2048)
fp = calc("CCO")          # numpy uint8 array (2048,)
len(calc)                 # 2048
calc.columns[:3]          # ['fp_0', 'fp_1', 'fp_2']
```

### Descriptor calculators

```python
from molfeat.calc import RDKitDescriptors2D, RDKitDescriptors3D, MordredDescriptors

RDKitDescriptors2D()      # 223 descriptors; .columns gives the names
RDKitDescriptors3D()      # 639 descriptors; requires a conformer
MordredDescriptors()      # 1613 descriptors; implements batch_compute
```

`RDKitDescriptors2D` takes `replace_nan`, `augment`, and an explicit `descrs` list to restrict
the set. 3D descriptors raise or return garbage on molecules without conformers.

### Pharmacophore calculators

```python
from molfeat.calc import CATS, Pharmacophore2D, Pharmacophore3D

CATS(max_dist=None, bins=None, scale="raw", use_3d_distances=False, **kwargs)
```

The class is `CATS` — there is no `CATSCalculator`, and there is no `mode=` argument; 2D vs 3D
is `use_3d_distances`. Widths: 2D → **189**, 3D → **126**. `scale` is `"raw"`, `"num"`, or
`"count"`. `get_calculator("cats2D")` and `get_calculator("cats3D")` set the flag for you.

```python
Pharmacophore2D(factory="pmapper", length=2048, useCounts=None, minPointCount=None, ...)
```

`factory` is one of `"default"`, `"gobbi"`, `"pmapper"`, `"cats"` — not separate calculator
names. Width is 2048 for every factory by default. `Pharmacophore3D` mirrors it and consumes
conformers.

### Shape and scaffold calculators

```python
from molfeat.calc import USRDescriptors, ElectroShapeDescriptors, ScaffoldKeyCalculator

USRDescriptors(method="usr")        # 12; method="usrcat" -> 60
ElectroShapeDescriptors()           # 15
ScaffoldKeyCalculator()             # 42
```

All three need 3D conformers except `ScaffoldKeyCalculator`.

### Graph calculators

```python
from molfeat.calc.atom import AtomCalculator, AtomMaterialCalculator, DGLCanonicalAtomCalculator, DGLWeaveAtomCalculator
from molfeat.calc.bond import BondCalculator, EdgeMatCalculator, DGLCanonicalBondCalculator, DGLWeaveEdgeCalculator
```

### get_calculator()

```python
get_calculator(name: str, **params)
```

Accepts every `FP_FUNCS` name plus `desc2D`, `desc3D`, `mordred`, `cats`, `cats2D`, `cats3D`,
`pharm2D`, `pharm3D`, `usr`/`usrcat`/`usr*`, `electroshape`, `scaffoldkeys` (aliases `skeys`,
`scaffkeys`), and `none`. Raises `ValueError` for anything else. Names are lowercased, so
`"desc2D"` and `"desc2d"` both work.

---

## molfeat.trans — Transformers

`from molfeat.trans import` gives `BaseFeaturizer`, `MoleculeTransformer`, `FPVecTransformer`,
`FeatConcat`. `PrecomputedMolTransformer` and `FPVecFilteredTransformer` live in
`molfeat.trans.base` and `molfeat.trans.fp`.

### MoleculeTransformer

```python
MoleculeTransformer(
    featurizer: Union[str, Callable],
    n_jobs: int = 1,
    verbose: bool = False,
    dtype: Union[Callable, str, None] = None,
    parallel_kwargs: Optional[Dict] = None,
    **params,
)
```

`featurizer` may be a calculator instance or a calculator **name**. Note what is *not* here:
`ignore_errors` is not a constructor argument — passing it lands in `**params` and is ignored.

```python
transform(mols, ignore_errors: bool = False, **kwargs)  -> list (None for failures)
__call__(mols, enforce_dtype: bool = True, ignore_errors: bool = False, **kwargs)
```

- `dtype=None` (the default) → `__call__` returns a **list of arrays**, so `.shape` fails.
  Pass `dtype=np.float32` (or `torch.float32` for a tensor) to get a matrix.
- `ignore_errors=True` on `__call__` → returns `(features, ids)`, with failures **dropped**;
  `ids` are the surviving input positions. Use them to realign labels.
- `ignore_errors=True` on `transform` → returns a list with `None` in the failed positions.
- `ignore_errors=False` → raises `ValueError: Cannot transform molecule at index i`.
- `verbose=True` (constructor) logs the underlying exception per failed molecule.

Other members: `to_state_dict/json/yaml` and `to_state_*_file`, the matching
`from_state_*` classmethods, `__len__` (output width), `columns`, `copy()`, and
`preprocess(inputs, labels)` — a **batch** hook that returns `(inputs, labels)` and that
`transform` never calls. Standardize before featurizing instead of overriding it.

```python
import numpy as np
import datamol as dm
from molfeat.trans import MoleculeTransformer

smiles = dm.data.freesolv().smiles.tolist()
transformer = MoleculeTransformer("ecfp", n_jobs=1, dtype=np.float32)
X, ids = transformer(smiles, ignore_errors=True)   # (642, 2048) float32
transformer.to_state_yaml_file("ecfp_config.yml")
transformer = MoleculeTransformer.from_state_yaml_file("ecfp_config.yml")
```

### FPVecTransformer

```python
FPVecTransformer(
    kind: str = "ecfp:4",
    length: int = 2000,
    n_jobs: int = 1,
    verbose: bool = False,
    dtype: Callable = np.float32,
    parallel_kwargs: Optional[dict] = None,
    **params,
)
```

The fingerprint shortcut: `kind` uses `"name:diameter"` notation (`"ecfp:4"` is radius 2), and
`dtype` already defaults to `np.float32`, so it returns an array without extra arguments. Note
`length=2000` — not the fingerprint's native 2048 — unless you override it.

`FPVecFilteredTransformer` (in `molfeat.trans.fp`) adds bit filtering on top:
`occ_threshold` drops bits set in fewer than that fraction of training molecules, and
`del_invariant` drops bits that never vary.

### FeatConcat

```python
FeatConcat(iterable=None, dtype=None, params=None, collate_fn=None)
```

A transformer in its own right (a `list` subclass) — **do not** wrap it in
`MoleculeTransformer`. Accepts calculator instances or names:

```python
from molfeat.trans import FeatConcat

concat = FeatConcat(["maccs", "ecfp"], dtype=np.float32)
X = concat(smiles)     # (n, 2167) = 167 + 2048
len(concat)            # 2 (number of featurizers, not the output width)
```

### PrecomputedMolTransformer

```python
from molfeat.trans.base import PrecomputedMolTransformer

PrecomputedMolTransformer(cache=None, cache_dict=None, cache_key=None, *args,
                          featurizer=None, state_path=None, **kwargs)
```

Wraps a transformer with a molecule-keyed cache so repeated featurization is free. See the
cache section below.

---

## molfeat.trans.pretrained — Pretrained transformers

Exports `PretrainedMolTransformer` (abstract base), `PretrainedHFTransformer`,
`PretrainedDGLTransformer`, `GraphormerTransformer`, `FCDTransformer`. Instantiating the base
class with a model name does not work — pick the class matching the backend.

```python
import numpy as np
from molfeat.trans.pretrained import PretrainedHFTransformer, PretrainedDGLTransformer, GraphormerTransformer

PretrainedHFTransformer(kind="ChemBERTa-77M-MLM", notation="smiles", pooling="mean", dtype=np.float32)
PretrainedDGLTransformer(kind="gin_supervised_masking", dtype=np.float32)   # 300-dim
GraphormerTransformer(kind="pcqm4mv2_graphormer_base", dtype=np.float32)
```

`notation` must match the card's `inputs` field (`selfies` for ChemGPT, `smiles` for the
rest). `pooling` accepts `mean` (default), `avg`, `sum`, `clf` (CLS token) and `None`;
`pooling="max"` raises `RuntimeError: masked_fill_ only supports boolean masks` on current
PyTorch. Measured width for ChemBERTa-77M is **384**.

### Loading HuggingFace models without the store

The store cannot serve the 8 HuggingFace artifacts in 0.11.0 (directory artifacts over HTTP;
upstream issues #119/#120). Go to the Hub directly:

```python
from molfeat.trans.pretrained.hf_transformers import HFModel, PretrainedHFTransformer

model = HFModel.from_pretrained("DeepChem/ChemBERTa-77M-MLM", "DeepChem/ChemBERTa-77M-MLM")
transformer = PretrainedHFTransformer(kind=model, notation="smiles", dtype=np.float32)
```

`HFModel.from_pretrained(model, tokenizer, model_class=None, model_name=None)` also accepts
already-instantiated `PreTrainedModel`/`PreTrainedTokenizer` objects or local paths.
`HFModel.register_pretrained(...)` pushes a model into a writable store of your own.

---

## molfeat.store — Model store

```python
ModelStore(model_store_root: Optional[str] = None)
```

Defaults to `https://fs.molfeat.datamol.io/artifacts/`, overridable with
`MOLFEAT_MODEL_STORE_ROOT` / `MOLFEAT_MODEL_STORE_BUCKET` or the constructor argument (any
fsspec-addressable path, which is how you host a private store).

| Member | Signature | Returns |
|---|---|---|
| `available_models` | property | list of 44 `ModelInfo` cards |
| `search` | `search(modelcard=None, **search_kwargs)` | list of matching cards |
| `load` | `load(model_name, load_fn=None, load_fn_kwargs=None, download_output_dir=None, chunk_size=2048, force=False)` | **tuple** `(model, ModelInfo)` |
| `download` | `download(modelcard, output_dir=None, chunk_size=2048, force=False)` | local path |
| `register` | `register(modelcard, model=None, chunk_size=2048, save_fn=None, save_fn_kwargs=None, force=True)` | — |
| `exists` | `exists(card=None, check_remote=False, **kwargs)` | bool |

`ModelInfo` fields: `name`, `inputs`, `type`, `version`, `group`, `submitter`, `description`,
`representation`, `require_3D`, `tags`, `authors`, `reference`, `created_at`, `sha256sum`,
`model_usage`. `card.usage()` returns the canonical usage snippet **as a string**.

```python
from molfeat.store.modelstore import ModelStore

store = ModelStore()
card = store.search(name="ChemBERTa-77M-MLM")[0]
print(card.group, card.inputs, card.usage())
```

Downloads land in `platformdirs.user_cache_dir("molfeat")` and are checksum-verified against
the card's `sha256sum`; a mismatch deletes the cached copy and raises `ModelStoreError`.

---

## molfeat.utils.cache — Feature caches

`DataCache` (in-memory, optionally file-backed), `FileCache` (parquet/csv/pickle on disk),
`MPDataCache` (multiprocessing-safe), `CacheList` (chain several), `MolToKey` (the hashing
policy — `dm.unique_id` by default, a structural hash, so differently written SMILES for the
same molecule share a cache entry).

```python
FileCache(cache_file, name=None, mol_hasher=None, n_jobs=None, verbose=False,
          file_type="parquet", clear_on_exit=True, parquet_kwargs=None)
```

`clear_on_exit=True` (the default) discards the cache file at interpreter exit — set it to
`False` for a cache you intend to reuse.

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

cache = FileCache.load_from_file("features.parquet", file_type="parquet")
featurizer = PrecomputedMolTransformer(cache=cache, featurizer=base, dtype=np.float32)
```

---

## Common Patterns

### Data type control

```python
import numpy as np, torch

MoleculeTransformer("ecfp", dtype=np.float32)     # ndarray
MoleculeTransformer("ecfp", dtype=torch.float32)  # torch.Tensor
MoleculeTransformer("ecfp")                       # list of arrays — usually not what you want
```

`enforce_dtype=False` on a call skips the cast for that call.

### Error handling with label realignment

```python
X, ids = transformer(smiles, ignore_errors=True)
y = np.asarray(labels)[ids]          # required: failures were dropped from X
```

### Scikit-learn pipeline

```python
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier

pipeline = Pipeline([
    ("featurizer", MoleculeTransformer("ecfp", dtype=np.float32)),
    ("classifier", RandomForestClassifier(n_estimators=100)),
])
pipeline.fit(smiles_train, y_train)
predictions = pipeline.predict(smiles_test)
```

The `dtype` matters here too: scikit-learn needs an array, and the pipeline gives you no place
to convert one.

### PyTorch dataset

```python
import torch
from torch.utils.data import Dataset, DataLoader

class MoleculeDataset(Dataset):
    def __init__(self, smiles, labels, transformer):
        self.features = transformer(smiles)                       # featurize once, not per item
        self.labels = torch.tensor(labels, dtype=torch.float32)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return torch.tensor(self.features[idx]), self.labels[idx]

transformer = MoleculeTransformer("ecfp", n_jobs=1, dtype=torch.float32)
loader = DataLoader(MoleculeDataset(smiles, labels, transformer), batch_size=32)
```

---

## Performance Notes

Measured on 12 cores with molfeat 0.11.0:

| Featurizer | Molecules | `n_jobs=1` | `n_jobs=-1` |
|---|---|---|---|
| `ecfp` | 642 | 0.03 s | 0.13 s |
| `ecfp` | 10,272 | 0.43 s | 0.56 s |
| `desc2D` | 300 | 0.96 s | 0.23 s |
| `mordred` | 300 | 4.83 s | 4.21 s |

- Parallelism costs more than it saves for fingerprints — joblib has to ship molecules to
  worker processes. Keep `n_jobs=1` there.
- It pays roughly linearly for descriptor and conformer-dependent calculators.
- Calculators implementing `batch_compute` (Mordred) already batch internally.
- Use `float32` over `float64` unless a model needs the precision.
- Cache pretrained embeddings with `PrecomputedMolTransformer` rather than recomputing.
