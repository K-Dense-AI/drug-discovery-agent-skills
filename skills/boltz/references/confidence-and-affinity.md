# Reading Boltz output

## Directory layout

```
out_dir/
└── predictions/
    └── <input_name>/
        ├── <input_name>_model_0.cif              # best-ranked pose, per-token pLDDT in B-factors
        ├── <input_name>_model_1.cif              # further diffusion samples
        ├── confidence_<input_name>_model_0.json  # one per sample
        ├── affinity_<input_name>.json            # one per input, not per sample
        ├── pae_<input_name>_model_0.npz          # with --write_full_pae
        ├── pde_<input_name>_model_0.npz          # with --write_full_pde
        └── plddt_<input_name>_model_0.npz
└── processed/                                    # cached inputs and MSAs
```

Samples are **ordered by confidence**, so `model_0` is the top-ranked pose.
`collect_results.py` walks this and returns one row per input (or per sample with
`--all-samples`).

## Confidence JSON

```json
{
  "confidence_score": 0.8367,
  "ptm": 0.8425,
  "iptm": 0.8225,
  "ligand_iptm": 0.0,
  "protein_iptm": 0.8225,
  "complex_plddt": 0.8402,
  "complex_iplddt": 0.8241,
  "complex_pde": 0.8912,
  "complex_ipde": 5.1650,
  "chains_ptm": {"0": 0.8533, "1": 0.8330},
  "pair_chains_iptm": {"0": {"0": 0.8533, "1": 0.8090}, "1": {"0": 0.8225, "1": 0.8330}}
}
```

| Field | Meaning |
|---|---|
| `confidence_score` | The ranking score: `0.8 × complex_plddt + 0.2 × iptm` (`ptm` for a single chain) |
| `ptm` | Predicted TM-score for the whole complex |
| `iptm` | Predicted TM-score aggregated **at interfaces** — the number that matters for a complex |
| `ligand_iptm` | ipTM at protein–ligand interfaces only |
| `protein_iptm` | ipTM at protein–protein interfaces only |
| `complex_plddt` | Mean per-residue confidence |
| `complex_iplddt` | pLDDT with interface residues upweighted |
| `complex_pde` / `complex_ipde` | Predicted distance error, **in Angstrom — lower is better** |
| `chains_ptm`, `pair_chains_iptm` | Per-chain and per-chain-pair breakdown |

pTM/pLDDT-style scores run 0–1 and higher is better. PDE is in Angstrom and lower is better —
the one field where the direction flips.

**Rules of thumb for a protein–ligand complex:**

| ipTM / ligand_ipTM | Reading |
|---|---|
| > 0.8 | Confident interface; the pose is worth using |
| 0.6 – 0.8 | Plausible; verify against known site residues or a crystal structure |
| < 0.6 | The model does not believe its own interface. Any affinity computed on it is being computed on a pose the model rejects |

A high `complex_plddt` with a low `iptm` is the classic trap: both partners are folded correctly
and their arrangement is a guess. For a docking question, **read ipTM first**.

## Affinity JSON

```json
{
  "affinity_pred_value": -1.2,
  "affinity_probability_binary": 0.87,
  "affinity_pred_value1": -1.5,
  "affinity_probability_binary1": 0.83,
  "affinity_pred_value2": -0.9,
  "affinity_probability_binary2": 0.91
}
```

The two head outputs are trained on different data, with different supervision, and answer
**different questions**:

### `affinity_probability_binary` — is this a binder at all?

0 to 1, the predicted probability that the ligand binds. This is the hit-discovery output: use
it to triage a screen, separate actives from decoys, and decide what to test.

### `affinity_pred_value` — how strongly, relative to other actives?

**`log10(IC50)` with IC50 in micromolar.** Lower is stronger. This is the one people misread, so
convert it before reporting:

```
pIC50 = 6 - value
IC50  = 10 ** value        micromolar
dG    = -1.364 * pIC50     kcal/mol at 298 K
```

| value | IC50 | pIC50 | Reading |
|---|---|---|---|
| −3 | 1 nM | 9 | Strong binder |
| −1 | 100 nM | 7 | Good binder |
| 0 | 1 µM | 6 | Moderate |
| +2 | 100 µM | 4 | Weak / decoy |

**Only use it to compare active molecules with each other** — hit-to-lead and lead optimisation,
where you are asking how a small change moves potency. It is not meaningful for inactives, which
is what the binary head is for.

`collect_results.py` emits `pIC50`, `IC50_uM`, and `dG_kcal_mol` columns so the sign convention
cannot be misread downstream.

### The ensemble members

`*_value1`/`*_value2` and `*_probability_binary1`/`2` are the two models whose average forms the
headline number. Their spread is the cheapest available uncertainty estimate: a disagreement of
more than one log unit means the ensemble is not converged on that compound, and the averaged
value should not be quoted alone. `collect_results.py` reports it as `ensemble_spread`.

## A workable screening protocol

1. Rank by `affinity_probability_binary`.
2. Drop anything with `iptm < 0.6` or `ligand_iptm < 0.6` — the pose is not believed, so neither
   number means anything.
3. Among survivors, order by `pIC50` for follow-up.
4. Check `ensemble_spread` on the top candidates.
5. Cross-check the pose: does it sit in the known site, and do the contacts match the SAR? An
   affinity attached to a pose in the wrong pocket is a coincidence.

## What this is not

Boltz-2's affinity head is trained on measured bioactivity data, so it is *not* a physics-based
free-energy calculation and does not have the transferability of one. It is closest in spirit to
a very good structure-aware QSAR model:

- It reflects the chemistry and target classes in its training data. Novel scaffolds against
  under-studied targets are extrapolation.
- It cannot be sanity-checked by a thermodynamic cycle the way FEP can.
- Agreement with an orthogonal method — a docking score from `autodock-vina`, measured analogues
  from `chembl`, an MD stability check — is worth more than any single number.

Report it as "Boltz-2 predicted pIC50", with the ipTM alongside, and say which release was used.
