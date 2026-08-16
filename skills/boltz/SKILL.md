---
name: boltz
description: Cofold protein-ligand, protein-protein, and nucleic-acid complexes with Boltz-2, and predict binding affinity with its trained affinity head. Use this skill to build Boltz input YAML, run structure prediction with MSAs, pocket constraints, templates, and modified residues, screen compound libraries by cofolding, and interpret confidence scores (pLDDT, pTM, ipTM, PDE) and affinity output (binder probability and log10 IC50). Also trigger on Boltz, Boltz-1, Boltz-2, cofolding, boltz predict, affinity_pred_value, affinity_probability_binary, ipTM, or open-weights AlphaFold3 alternatives.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: The bundled scripts need only Python 3.10+ and the standard library. Running a prediction needs boltz 2.2+ (pip install boltz, Python >=3.10 and <3.13) and an NVIDIA GPU; 24 GB is a practical minimum for a typical protein-ligand complex, CPU works but is 50-100x slower. Weights download to ~/.boltz on first run. --use_msa_server sends sequences to the public ColabFold server.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "⚡"
    homepage: https://github.com/jwohlwend/boltz
  hermes:
    category: research
---

# Boltz-2

An open-weights cofolding model in the AlphaFold3 family, plus something AlphaFold3 does not
have: a **trained binding-affinity head**. Give it a protein sequence and a ligand SMILES and it
returns a complex structure, per-interface confidence, and a predicted potency — with weights
licensed for commercial use.

**Repo:** [github.com/jwohlwend/boltz](https://github.com/jwohlwend/boltz)
**Checked against:** boltz 2.2.1 (PyPI), Python ≥3.10 <3.13.

Read [references/yaml-schema.md](references/yaml-schema.md) before writing an input,
[references/confidence-and-affinity.md](references/confidence-and-affinity.md) before believing an
output, and [references/running.md](references/running.md) for install, GPU sizing, flags, and
errors.

## When to reach for this

| Situation | Use |
|---|---|
| No experimental structure, and you need a ligand in the pocket | **Boltz** — folding and docking in one step |
| Experimental structure exists, defined site, need to rank thousands | `autodock-vina` |
| Experimental structure exists, need a pose without a box | `diffdock` |
| Need a defensible free energy for a congeneric series | Alchemical FEP, not this |
| No GPU | `tamarind` runs Boltz as a service |

## The loop

```bash
# 1. write the input
python skills/boltz/scripts/make_boltz_yaml.py \
    --protein-fasta target.fasta \
    --ligand-smiles "Cc1ccc(cc1Nc1nccc(n1)c1cccnc1)NC(=O)c1ccc(CN2CCN(C)CC2)cc1" \
    --affinity --out complex.yaml

# 2. predict (external, needs a GPU)
boltz predict complex.yaml --out_dir predictions/ --use_msa_server \
    --use_potentials --diffusion_samples 5

# 3. read the results with the units converted
python skills/boltz/scripts/collect_results.py predictions/
```

```
name  sample  confidence_score  iptm  ligand_iptm  binder_probability  pIC50  IC50_uM  dG_kcal_mol
lig1  0       0.84              0.82  0.79         0.93                8.10   0.0079   -11.05
lig2  0       0.51              0.42  0.31         0.21                4.60   25.1189  -6.27
```

`make_boltz_yaml.py` catches at write time the four things that otherwise fail after the GPU has
already spun up: non-amino-acid characters in a sequence, an affinity binder that is not a ligand
chain, `--pocket` with no ligand, and an out-of-range `max_distance`. It also quotes SMILES —
an unquoted `#` (an alkyne) starts a YAML comment and silently truncates the molecule.

## The affinity number, and its sign

`affinity_pred_value` is **log10 of an IC50 in micromolar**. It runs the opposite way to
everything else in the field: **−3 is a nanomolar binder, +2 is a decoy.**

```
pIC50 = 6 - value        IC50 = 10**value  µM        ΔG = -1.364 × pIC50  kcal/mol
```

`collect_results.py` emits `pIC50`, `IC50_uM`, and `dG_kcal_mol` so the sign cannot be misread
downstream. Report those, never the raw value.

There are **two** affinity outputs and they answer different questions:

- **`affinity_probability_binary`** — probability the ligand binds at all. This is the
  hit-discovery output; use it to triage a screen.
- **`affinity_pred_value`** — relative potency. Only meaningful **between active molecules**, for
  hit-to-lead and lead optimisation. Applying it to inactives is a category error.

The two ensemble members are reported separately in the JSON; `collect_results.py` turns their
disagreement into an `ensemble_spread` column, which is the cheapest uncertainty estimate on
offer. More than one log unit of spread means the number should not be quoted alone.

## Read ipTM before anything else

`complex_plddt` high and `iptm` low is the classic trap: both partners folded correctly, and
their arrangement is a guess. For a binding question, the interface score is the score.

| ipTM / ligand_ipTM | Reading |
|---|---|
| > 0.8 | Confident interface; the pose is usable |
| 0.6 – 0.8 | Plausible; check it against known site residues |
| < 0.6 | The model does not believe its own interface — an affinity computed on it is meaningless |

`collect_results.py --min-iptm 0.6` filters, and warns about what it dropped. Note that `pde`
and `ipde` are in Angstrom, so for those alone **lower is better**.

## Constrain the pocket when you know it

Without a pocket constraint, Boltz decides where the ligand goes — usually right for a
well-defined site, less so for a shallow or multi-site protein.

```bash
python skills/boltz/scripts/make_boltz_yaml.py --protein-fasta target.fasta \
    --ligand-ccd SAH --pocket A:790,A:797,A:855 --pocket-distance 6 --out cofactor.yaml
```

`--pocket-force` makes it a hard constraint rather than a bias. Use it only when you are sure:
forcing a wrong pocket produces a confident wrong answer, which is worse than an unconstrained
one.

## Screening a library

```bash
python skills/boltz/scripts/screen_library.py --protein-fasta target.fasta \
    --smiles library.smi --out-dir screen/ --affinity --msa-path target.a3m

boltz predict screen/ --out_dir screen/predictions --use_potentials --diffusion_samples 5
python skills/boltz/scripts/collect_results.py screen/predictions --min-iptm 0.6 --out hits.tsv
```

One YAML per ligand, plus a manifest. **Precompute the MSA and pass `--msa-path`** — every input
shares the same protein, and rebuilding its MSA N times is the single largest waste in a screen.
The script says so if you forget.

It also flags compounds above the affinity head's 128-atom limit (`--skip-oversized` drops them);
past that limit Boltz returns a number that means nothing.

Scale honestly: a few minutes per ligand on a 24 GB GPU with a precomputed MSA. This is a
hundreds-to-low-thousands method. Filter a large library with `autodock-vina` or `medchem` first
and bring the survivors here.

## What it is, and is not

The affinity head is trained on measured bioactivity, so it behaves like a very good
structure-aware QSAR model, not a physics calculation. It reflects the chemistry and target
classes in its training data; a novel scaffold against an under-studied target is extrapolation,
and there is no thermodynamic cycle to check it against.

Treat agreement with an orthogonal method as the evidence — a docking score from
`autodock-vina`, measured analogues from `chembl`, or a stability check in
`molecular-dynamics`. Report the release, the ipTM, and the pIC50 with its ensemble spread.

## Composing with the rest of the bundle

- `uniprot-rcsb` → here: the sequence, and a template CIF if an apo structure exists.
- `binding-site-analysis` → before: which site to focus on, and whether it is druggable.
- `chembl` → here: known actives against the target, to calibrate what the affinity head says
  about chemistry you already have data for.
- `medchem` / `rdkit` → before: triage and standardise the library.
- `autodock-vina` → alongside: an orthogonal score on the same compounds.
- `molecular-dynamics` → after: does the predicted pose survive 10 ns?
- `tamarind` → instead: hosted Boltz when there is no local GPU.
