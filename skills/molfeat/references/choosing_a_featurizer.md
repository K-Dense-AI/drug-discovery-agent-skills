# Choosing the Right Featurizer

Which representation suits which task, and the worked pipelines that follow from that choice.
All code targets **molfeat 0.11.0**; widths in comments are measured output.

Two rules apply to every snippet here:

- construct transformers with `dtype=np.float32` (otherwise you get a list, not a matrix);
- pass `ignore_errors=True` to the **call**, and realign labels with the returned `ids`.

## By task

### Traditional ML (RF, SVM, XGBoost)

Fingerprints first — they are cheap, strong baselines, and cost nothing to recompute.

```python
import numpy as np
from molfeat.calc import FPCalculator
from molfeat.trans import MoleculeTransformer, FeatConcat

MoleculeTransformer(FPCalculator("ecfp", radius=2, fpSize=2048), dtype=np.float32)  # 2048
MoleculeTransformer("maccs", dtype=np.float32)                                       # 167
MoleculeTransformer("fcfp", dtype=np.float32)                                        # 2048
```

Radius 2 (ECFP4) is molfeat's default and the usual starting point; radius 3 (ECFP6) captures
larger environments at the cost of sparser bits.

When you need to explain the model, switch to named descriptors:

```python
MoleculeTransformer("desc2D", n_jobs=-1, dtype=np.float32)    # 223 named RDKit descriptors
MoleculeTransformer("mordred", dtype=np.float32)              # 1613 descriptors
```

Both produce NaN on some molecules — impute before fitting. `mordred` batches internally, so
`n_jobs` buys little there; `desc2D` parallelizes well (~4x on 12 cores).

Combine representations when they encode different things:

```python
FeatConcat(["maccs", "ecfp"], dtype=np.float32)      # 167 + 2048 = 2167
```

`FeatConcat` is itself a transformer — do not wrap it in `MoleculeTransformer`.

### Deep learning

```python
import numpy as np
from molfeat.trans.pretrained.hf_transformers import HFModel, PretrainedHFTransformer
from molfeat.trans.pretrained import PretrainedDGLTransformer, GraphormerTransformer

# ChemBERTa: load from the HF Hub — the molfeat store cannot serve HF artifacts in 0.11.0
model = HFModel.from_pretrained("DeepChem/ChemBERTa-77M-MLM", "DeepChem/ChemBERTa-77M-MLM")
PretrainedHFTransformer(kind=model, notation="smiles", dtype=np.float32)     # 384-dim

# Graph neural networks (needs molfeat[dgl])
PretrainedDGLTransformer(kind="gin_supervised_masking", dtype=np.float32)    # 300-dim
PretrainedDGLTransformer(kind="gin_supervised_infomax", dtype=np.float32)

# Quantum-property pretraining (needs molfeat[graphormer])
GraphormerTransformer(kind="pcqm4mv2_graphormer_base", dtype=np.float32)
```

There is no generic `PretrainedMolTransformer("name")` — that class is the abstract base. Card
names use underscores (`gin_supervised_masking`), and ChemGPT needs `notation="selfies"`.

Pretrained embeddings are not automatically better: on small datasets a 2048-bit ECFP with a
random forest routinely beats a frozen transformer embedding. Benchmark before committing.

### Similarity searching

```python
MoleculeTransformer("ecfp", dtype=np.float32)      # general purpose
MoleculeTransformer("maccs", dtype=np.float32)     # coarse, scaffold-level
MoleculeTransformer("usr", dtype=np.float32)       # 3D shape; requires conformers
```

Tanimoto on binary fingerprints is the conventional metric (`dm.similarity`, or RDKit's
`BulkTanimotoSimilarity`); cosine on the float matrix is convenient when you already have `X`.

### Pharmacophore-based work

```python
from molfeat.calc import CATS, Pharmacophore2D

MoleculeTransformer("fcfp", dtype=np.float32)                        # 2048
MoleculeTransformer(CATS(use_3d_distances=False), dtype=np.float32)  # 189
MoleculeTransformer(Pharmacophore2D(factory="gobbi"), dtype=np.float32)   # 2048
```

`Pharmacophore2D(factory=...)` takes `default`, `gobbi`, `pmapper`, or `cats` — those are
factory names, not separate calculators, and `gobbi2D`/`pmapper2D` do not exist.

### 3D representations

`desc3D`, `usr`, `usrcat`, `electroshape`, `cats3D`, and `pharm3D` all need conformers:

```python
import datamol as dm

mols = [dm.conformers.generate(dm.to_mol(s), n_confs=1, ignore_failure=True) for s in smiles]
mols = [m for m in mols if m is not None]
X = MoleculeTransformer("desc3D", n_jobs=-1, dtype=np.float32)(mols)     # 639
```

Conformer generation dominates the runtime, so cache the featurized output
(`PrecomputedMolTransformer`) rather than regenerating conformers per experiment.

## Worked workflows

### QSAR model

```python
import numpy as np
import datamol as dm
from molfeat.trans import MoleculeTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score

data = dm.data.freesolv()
smiles, y = data.smiles.tolist(), data.expt.values

transformer = MoleculeTransformer("ecfp", dtype=np.float32)
X, ids = transformer(smiles, ignore_errors=True)

model = RandomForestRegressor(n_estimators=100, random_state=0)
scores = cross_val_score(model, X, y[ids], cv=5, scoring="r2")
print(f"R2 = {scores.mean():.3f}")

transformer.to_state_yaml_file("production_featurizer.yml")   # ship with the model
```

Random splits flatter chemistry models. For a realistic estimate, split by scaffold
(`dm.to_scaffold_murcko`, or the split utilities in `pytdc`).

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
top_hits = [library_smiles[screen_ids[i]] for i in order]
```

For libraries beyond a few hundred thousand molecules, featurize in chunks and keep the ids per
chunk; see `references/examples.md`.

### Similarity search

```python
from sklearn.metrics.pairwise import cosine_similarity
from molfeat.calc import FPCalculator

q = FPCalculator("ecfp")("CC(=O)Oc1ccccc1C(=O)O").reshape(1, -1)
db = MoleculeTransformer("ecfp", dtype=np.float32)(database_smiles)

sims = cosine_similarity(q, db)[0]
top = sims.argsort()[-10:][::-1]
```

### Scikit-learn pipeline

```python
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier

pipeline = Pipeline([
    ("featurizer", MoleculeTransformer("ecfp", dtype=np.float32)),
    ("classifier", RandomForestClassifier(n_estimators=100, random_state=0)),
])
pipeline.fit(smiles_train, y_train)
predictions = pipeline.predict(smiles_test)
```

Inside a pipeline there is no place to convert a list into an array, so `dtype` is required.
The pipeline also drops the `ignore_errors` escape hatch — clean the SMILES first.

### Comparing featurizers honestly

```python
from sklearn.impute import SimpleImputer
from sklearn.model_selection import cross_val_score
from sklearn.ensemble import RandomForestRegressor
from molfeat.trans import FeatConcat

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

Hold the model, the seed, and the split fixed across featurizers; otherwise the ranking
measures the split. On FreeSolv, `desc2D` with a plain Ridge reaches R2 0.90 — a reminder that
descriptors often beat fingerprints on physicochemical endpoints.

## Quick reference

| Task | First choice | Fallback | Width |
|---|---|---|---|
| Baseline QSAR | `ecfp` | `fcfp` | 2048 |
| Interpretable model | `desc2D` | `mordred` | 223 / 1613 |
| Physicochemical endpoints | `desc2D` | `desc2D` + `ecfp` | 223 / 2271 |
| Scaffold similarity | `maccs` | `scaffoldkeys` | 167 / 42 |
| Substructure similarity | `ecfp` | `atompair` | 2048 |
| 3D shape | `usrcat` | `usr`, `electroshape` | 60 / 12 / 15 |
| Pharmacophore | `cats2D` | `pharm2D` (gobbi) | 189 / 2048 |
| Transfer learning | ChemBERTa (HF Hub) | `gin_supervised_masking` | 384 / 300 |
