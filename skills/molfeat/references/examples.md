# Molfeat Usage Examples

Every snippet below was executed against **molfeat 0.11.0** on Python 3.10 (datamol 0.12.5,
RDKit 2026.03.5, numpy 2.2.6, torch 2.13.0). Printed shapes and scores are real output from
those runs, using the built-in FreeSolv dataset (642 molecules) so you can reproduce them.

## Installation

```bash
uv venv --python 3.10
uv pip install "molfeat==0.11.0"

# extras, as needed
uv pip install "molfeat[transformer]==0.11.0"  # ChemBERTa, ChemGPT, MolT5
uv pip install "molfeat[dgl]==0.11.0"          # GIN, JTVAE
uv pip install "molfeat[graphormer]==0.11.0"   # Graphormer
uv pip install "molfeat[pyg]==0.11.0"          # PyTorch Geometric
uv pip install "molfeat[viz]==0.11.0"          # NGLView widgets
```

Python 3.11+ will not resolve: molfeat 0.11.0 declares `requires-python = ">=3.9,<3.11"`.

---

## Quick Start

```python
import numpy as np
import datamol as dm
from molfeat.calc import FPCalculator
from molfeat.trans import MoleculeTransformer

data = dm.data.freesolv()          # columns: iupac, smiles, expt, calc
smiles = data.smiles.tolist()
y = data.expt.values

# one molecule
calc = FPCalculator("ecfp")
calc(smiles[0])                    # (2048,) uint8

# a batch — dtype is what turns the list of arrays into a matrix
transformer = MoleculeTransformer(calc, n_jobs=1, dtype=np.float32)
X = transformer(smiles)            # (642, 2048) float32
```

Leave `dtype` off and `X` is a **list** of 642 arrays; `X.shape` raises `AttributeError`.

---

## Calculators

### Fingerprints

```python
from molfeat.calc import FPCalculator

ecfp = FPCalculator("ecfp", radius=2, fpSize=2048)   # radius 2 is the default (ECFP4)
ecfp("CCO").shape                                     # (2048,)

maccs = FPCalculator("maccs")
maccs("c1ccccc1").shape                               # (167,)

counts = FPCalculator("ecfp-count", radius=2)         # non-binary counts
short = FPCalculator("ecfp", length=1024)             # 1024-bit fold
```

Passing a parameter the method does not know (`n_bits`, `nBits` for ECFP, `mode`, ...) is
logged and then ignored — the calculator is built with defaults. Check `len(calc)` to confirm.

### Descriptors

```python
from molfeat.calc import RDKitDescriptors2D, MordredDescriptors

desc2d = RDKitDescriptors2D()
len(desc2d("CCO"))          # 223
desc2d.columns[:5]          # ['MaxAbsEStateIndex', 'MaxEStateIndex', ...]

mordred = MordredDescriptors()
len(mordred("c1ccccc1O"))   # 1613
```

### Pharmacophores

```python
from molfeat.calc import CATS, Pharmacophore2D

cats2d = CATS(use_3d_distances=False, scale="raw")
cats2d("CC(C)Cc1ccc(C)cc1C").shape      # (189,)

cats3d = CATS(use_3d_distances=True)    # (126,), needs conformers
pharm = Pharmacophore2D(factory="gobbi")   # (2048,)
```

The class is `CATS`, not `CATSCalculator`, and 2D/3D is `use_3d_distances`, not `mode`.

### 3D descriptors need conformers

```python
import datamol as dm
from molfeat.calc import RDKitDescriptors3D
from molfeat.trans import MoleculeTransformer

mols = [dm.conformers.generate(dm.to_mol(s), n_confs=1, ignore_failure=True) for s in smiles[:5]]
mols = [m for m in mols if m is not None]

X3 = MoleculeTransformer(RDKitDescriptors3D(), dtype=np.float32)(mols)   # (5, 639)
```

---

## Transformers

### Error handling, both flavors

```python
messy = ["CCO", "invalid", "CC(=O)O", "xyz123"]
t = MoleculeTransformer("ecfp", verbose=True, dtype=np.float32)

feats, ids = t(messy, ignore_errors=True)
# feats.shape -> (2, 2048); ids -> [0, 2]   failures are DROPPED
kept = [messy[i] for i in ids]              # ['CCO', 'CC(=O)O']
labels = np.asarray(y_all)[ids]             # realign labels or rows no longer match

rows = t.transform(messy, ignore_errors=True)
# ['arr', None, 'arr', None]  — positions preserved, failures are None
```

`ignore_errors` belongs on the **call**, not the constructor. `verbose=True` (constructor) logs
the underlying exception for each failure.

### Concatenating featurizers

```python
from molfeat.trans import FeatConcat

concat = FeatConcat(["maccs", "ecfp"], dtype=np.float32)
concat(smiles).shape          # (642, 2167) = 167 + 2048

triple = FeatConcat(["maccs", "ecfp", "estate"], dtype=np.float32)
triple(smiles).shape          # (642, 2246)
```

`FeatConcat` is a transformer already — wrapping it in `MoleculeTransformer` is wrong.

### The fingerprint shortcut

```python
from molfeat.trans import FPVecTransformer

fp = FPVecTransformer(kind="ecfp:4", length=1024)   # "name:diameter"; dtype float32 by default
fp(smiles).shape                                     # (642, 1024) float32
```

### Save and reload

```python
transformer.to_state_yaml_file("featurizer.yml")     # or to_state_json_file
reloaded = MoleculeTransformer.from_state_yaml_file("featurizer.yml")
reloaded(smiles[:3]).shape                           # (3, 2048)
```

The YAML records `_molfeat_version` next to the featurizer arguments — commit it with the
trained model.

---

## Pretrained models

### Discovering what exists

```python
from molfeat.store.modelstore import ModelStore

store = ModelStore()
len(store.available_models)                  # 44

card = store.search(name="ChemBERTa-77M-MLM")[0]
card.name, card.group, card.inputs, card.require_3D
# ('ChemBERTa-77M-MLM', 'huggingface', 'smiles', False)
print(card.usage())                          # returns the canonical snippet as a string
```

`store.load(name)` returns a `(model, ModelInfo)` tuple — not a ready-to-use transformer.

### ChemBERTa embeddings

The store cannot serve the HuggingFace artifacts in 0.11.0 (`IsADirectoryError` →
`ModelStoreError`), so go to the Hub:

```python
import numpy as np
from molfeat.trans.pretrained.hf_transformers import HFModel, PretrainedHFTransformer

model = HFModel.from_pretrained("DeepChem/ChemBERTa-77M-MLM", "DeepChem/ChemBERTa-77M-MLM")
transformer = PretrainedHFTransformer(kind=model, notation="smiles", dtype=np.float32)

emb = transformer(smiles[:32])     # (32, 384) float32, mean pooling
```

384, not 768 — read `emb.shape` instead of assuming. For ChemGPT pass `notation="selfies"`.
Pooling options are `mean` (default), `avg`, `sum`, and `clf`; `pooling="max"` raises
`RuntimeError: masked_fill_ only supports boolean masks` on current PyTorch.

### GIN graph embeddings

```python
import numpy as np
from molfeat.trans.pretrained import PretrainedDGLTransformer   # needs molfeat[dgl]

gin = PretrainedDGLTransformer(kind="gin_supervised_masking", dtype=np.float32)
gin(smiles[:8]).shape          # (8, 300)
```

Card names use underscores: `gin_supervised_masking`, `gin_supervised_infomax`,
`gin_supervised_edgepred`, `gin_supervised_contextpred`. Graphormer is
`GraphormerTransformer(kind="pcqm4mv2_graphormer_base")`.

---

## Machine learning

### Scikit-learn pipeline

```python
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score

pipe = Pipeline([
    ("featurizer", MoleculeTransformer("ecfp", dtype=np.float32)),
    ("model", RandomForestRegressor(n_estimators=50, random_state=0)),
])

scores = cross_val_score(pipe, smiles, y, cv=3, scoring="r2")
scores.mean()      # 0.652 on FreeSolv
```

The pipeline feeds SMILES straight in, so the featurizer must produce an array — `dtype` is
not optional here.

### QSAR with interpretable descriptors

```python
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.model_selection import cross_val_score

desc = MoleculeTransformer("desc2D", n_jobs=-1, dtype=np.float32)
X, ids = desc(smiles, ignore_errors=True)
y_ = y[ids]

X = SimpleImputer(strategy="median").fit_transform(X)   # some descriptors are NaN
X = StandardScaler().fit_transform(X)

model = Ridge(alpha=1.0)
cross_val_score(model, X, y_, cv=5, scoring="r2").mean()      # 0.901 on FreeSolv

model.fit(X, y_)
names = desc.featurizer.columns
top = np.abs(model.coef_).argsort()[-5:][::-1]
[(names[i], round(float(model.coef_[i]), 2)) for i in top]
# [('SlogP_VSA10', 1.46), ('TPSA', -1.45), ('VSA_EState1', -1.15), ...]
```

Impute before scaling — RDKit descriptors produce NaN for some molecules, and scikit-learn
estimators reject them.

### Comparing featurizers

```python
from sklearn.model_selection import cross_val_score
from sklearn.ensemble import RandomForestRegressor

candidates = {
    "ecfp": MoleculeTransformer("ecfp", dtype=np.float32),
    "maccs": MoleculeTransformer("maccs", dtype=np.float32),
    "desc2D": MoleculeTransformer("desc2D", n_jobs=-1, dtype=np.float32),
    "maccs+ecfp": FeatConcat(["maccs", "ecfp"], dtype=np.float32),
}

for name, featurizer in candidates.items():
    X, ids = featurizer(smiles, ignore_errors=True)
    X = SimpleImputer(strategy="median").fit_transform(X)
    score = cross_val_score(RandomForestRegressor(n_estimators=100, random_state=0),
                            X, y[ids], cv=5, scoring="r2").mean()
    print(f"{name:12s} R2 = {score:.3f}")
```

Use the same split and the same seed across featurizers, or the comparison measures the split.

### PyTorch

```python
import torch
from torch.utils.data import Dataset, DataLoader

class MoleculeDataset(Dataset):
    def __init__(self, smiles, labels, transformer):
        self.features = transformer(smiles)          # featurize once, up front
        self.labels = torch.tensor(labels, dtype=torch.float32)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.features[idx], self.labels[idx]

transformer = MoleculeTransformer("ecfp", n_jobs=1, dtype=torch.float32)
loader = DataLoader(MoleculeDataset(smiles, y, transformer), batch_size=32, shuffle=True)

model = torch.nn.Sequential(
    torch.nn.Linear(2048, 256), torch.nn.ReLU(), torch.nn.Dropout(0.3),
    torch.nn.Linear(256, 1),
)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

for epoch in range(10):
    for xb, yb in loader:
        optimizer.zero_grad()
        loss = torch.nn.functional.mse_loss(model(xb).squeeze(-1), yb)
        loss.backward()
        optimizer.step()
```

Featurizing inside `__getitem__` re-runs the calculator every epoch — do it in `__init__`, or
cache it (below).

---

## Workflows

### Virtual screening

```python
from sklearn.ensemble import RandomForestClassifier

transformer = MoleculeTransformer("ecfp", dtype=np.float32)

X_train, train_ids = transformer(train_smiles, ignore_errors=True)
clf = RandomForestClassifier(n_estimators=500, n_jobs=-1, random_state=0)
clf.fit(X_train, np.asarray(train_labels)[train_ids])

X_screen, screen_ids = transformer(library_smiles, ignore_errors=True)
scores = clf.predict_proba(X_screen)[:, 1]

order = scores.argsort()[::-1][:1000]
top_hits = [library_smiles[screen_ids[i]] for i in order]     # index through screen_ids
```

Indexing back through `screen_ids` is what keeps hit SMILES aligned after failures are dropped.

### Similarity search

```python
from sklearn.metrics.pairwise import cosine_similarity

query = "CC(=O)Oc1ccccc1C(=O)O"                     # aspirin
q = FPCalculator("ecfp")(query).reshape(1, -1)
db = MoleculeTransformer("ecfp", dtype=np.float32)(smiles)

sims = cosine_similarity(q, db)[0]
for i in sims.argsort()[-3:][::-1]:
    print(f"{sims[i]:.3f}  {smiles[i]}")
# 1.000  CC(=O)Oc1ccccc1C(=O)O
# 0.561  CC(=O)c1ccccc1
# 0.531  Cc1cccc(c1C)Nc2ccccc2C(=O)O
```

For binary fingerprints, Tanimoto (`dm.similarity` or RDKit's `BulkTanimotoSimilarity`) is the
conventional metric; cosine is used above because it works on the float matrix directly.

### Caching expensive featurization

```python
import numpy as np
from molfeat.trans import MoleculeTransformer
from molfeat.trans.base import PrecomputedMolTransformer
from molfeat.utils.cache import FileCache

base = MoleculeTransformer("desc2D", n_jobs=-1, dtype=np.float32)
cache = FileCache(cache_file="features.parquet", file_type="parquet", clear_on_exit=False)

featurizer = PrecomputedMolTransformer(cache=cache, featurizer=base, dtype=np.float32)
X = featurizer(smiles[:50])            # (50, 223)
cache.save_to_file("features.parquet")

# later run — no recomputation
cache = FileCache.load_from_file("features.parquet", file_type="parquet")
featurizer = PrecomputedMolTransformer(cache=cache, featurizer=base, dtype=np.float32)
X = featurizer(smiles[:50])            # (50, 223) from cache
```

`clear_on_exit` defaults to `True`, which deletes the file at exit — set it to `False` for a
cache you want to keep. Molecules are keyed by `dm.unique_id`, so equivalent SMILES written
differently still hit.

### Chunked featurization for large libraries

```python
def featurize_in_chunks(smiles_list, transformer, chunk_size=10000):
    blocks = []
    for i in range(0, len(smiles_list), chunk_size):
        feats, _ = transformer(smiles_list[i:i + chunk_size], ignore_errors=True)
        blocks.append(np.asarray(feats))
    return np.vstack(blocks)

X = featurize_in_chunks(smiles, MoleculeTransformer("ecfp", dtype=np.float32))   # (642, 2048)
```

Keep the returned ids per chunk if you need to map rows back to inputs.

---

## Troubleshooting

### Standardize before featurizing

`preprocess()` is a batch hook (`preprocess(inputs, labels)`) that `transform` never calls —
overriding it does nothing. Clean the input list yourself:

```python
import datamol as dm

def clean(smi):
    mol = dm.to_mol(smi)
    if mol is None:
        return None
    mol = dm.remove_salts_solvents(mol, dont_remove_everything=True)
    return dm.to_smiles(dm.standardize_mol(mol, disconnect_metals=True, uncharge=True))

clean_smiles = [s for s in dm.parallelized(clean, smiles, n_jobs=-1) if s]
```

Without `dont_remove_everything=True`, a molecule that *is* a solvent (ethanol, acetic acid)
comes back as an empty string. The function is `dm.remove_salts_solvents` — `dm.remove_salts`
does not exist.

### Parallelism

```python
MoleculeTransformer("ecfp", n_jobs=1)       # fingerprints: parallelism costs more than it saves
MoleculeTransformer("desc2D", n_jobs=-1)    # descriptors: ~4x on 12 cores
```

Measured: `ecfp` over 10,272 molecules takes 0.43 s at `n_jobs=1` and 0.56 s at `n_jobs=-1`;
`desc2D` over 300 molecules takes 0.96 s at `n_jobs=1` and 0.23 s at `n_jobs=-1`.

### Reproducibility

```python
import random, numpy as np, torch, molfeat

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

set_seed(42)
transformer.to_state_yaml_file("config.yml")
print(molfeat.__version__)      # '0.11.0'
```

Seeds do not affect fingerprints or descriptors — they are deterministic. They matter for the
model, for conformer generation (`dm.conformers.generate`), and for data splits.
