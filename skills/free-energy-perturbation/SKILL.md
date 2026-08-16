---
name: free-energy-perturbation
description: Compute relative and absolute binding free energies with the Open Free Energy toolkit — the rigorous alchemical alternative to docking scores when a congeneric series needs reliable potency ranking. Use this skill to plan a perturbation network over a ligand set, choose atom mappings, run hybrid-topology or separated-topology protocols, and analyse the result — per-edge ΔΔG with uncertainty, cycle-closure error, and mean unsigned error against measured affinities. Also trigger on OpenFE, alchemical transformation, thermodynamic cycle, RBFE, ABFE, SepTop, lambda window, MBAR, cycle closure, or perturbation map.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+. The bundled scripts plan networks and parse result JSON with the standard library only. Running a calculation needs openfe 1.12+ installed from conda-forge, docker, or singularity — note that `pip install openfe` fetches an unrelated 0.0.12 placeholder. An NVIDIA GPU is effectively mandatory — a single edge is hours of MD.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🔥"
    homepage: https://openfree.energy
  hermes:
    category: research
---

# Alchemical Free Energy

The rigorous end of affinity prediction. Where a docking score is a heuristic that correlates
weakly with potency, FEP computes a real thermodynamic quantity from statistical mechanics —
including entropy and explicit water — and reaches about 1 kcal/mol RMSE on a congeneric series.
It costs GPU-days for tens of compounds, which places it precisely: immediately before synthesis,
choosing which twenty analogues to make.

**Tool:** [OpenFE](https://openfree.energy) 1.12, MIT. **`pip install openfe` fetches an unrelated
0.0.12 placeholder** — install from conda-forge, docker, or singularity. An NVIDIA GPU is
effectively mandatory.
**Checked against:** v1.12, June 2026.

Read [references/openfe-setup.md](references/openfe-setup.md) before your first run,
[references/network-design.md](references/network-design.md) before committing GPU time, and
[references/interpreting-fep.md](references/interpreting-fep.md) before quoting a number —
**that one is judgement, not syntax.**

## The two scripts

| Script | Answers |
|---|---|
| `fep_network.py` | What shape is the network, can it be validated, and what will it cost? |
| `fep_report.py` | Do the results hang together, and what do they say? |

## Install the right package

```bash
mamba create -n openfe -c conda-forge openfe
```

PyPI's `openfe` is a placeholder at version 0.0.12 with no relation to this toolkit. Checked live;
it is the first thing that goes wrong.

## A star map cannot be checked

This is the thing to get right. Free energy is a **state function**, so the sum around any closed
loop must be zero. It never is, and the deviation is a direct measure of the error that assumes
nothing — no experimental data, no reference, no error model.

A star map has no cycles, so it forfeits the only internal validation FEP offers:

```bash
python skills/free-energy-perturbation/scripts/fep_network.py plan --ligands a,b,c,d,e --shape star
```

```
# 5 ligands, 4 edges, 0 independent cycle(s)
# no cycles: this network has NO internal error check.
# every result is relative to `a`. A bad reference corrupts the whole map.
```

```bash
... --shape cyclic
# 5 ligands, 8 edges, 4 independent cycle(s)
# 576 GPU-hours at 24 h/edge x 3 repeats
```

Double the edges buys four independent checks. The count is the circuit rank,
`edges − nodes + components`.

## Reading the closure

```bash
python skills/free-energy-perturbation/scripts/fep_report.py cycles --results ddg.tsv
```

```
cycle             length  closure_kcal  acceptable
a -> b -> c -> a  3       0.5           true

# 1 cycle(s); RMS closure 0.500 kcal/mol, 0 above 1
```

Edges of +1.0, +1.0, and −1.5 sum to +0.5 instead of zero. That is real error in those three
edges, visible with no experimental data at all.

**Per-edge uncertainty does not substitute for this.** It measures sampling convergence, not
whether the force field is right — a tight uncertainty on a wrong number is entirely normal.

A consequence worth internalising: a per-ligand ΔG depends on which path you take from the
reference, and paths disagree by exactly the closure error. `rank` follows one path and says so;
use cinnabar for a maximum-likelihood estimate over all paths.

## What 1 kcal/mol means

| Error | Affinity factor |
|---|---|
| 0.5 kcal/mol | 2.3× |
| 1.0 kcal/mol | 5.4× |
| 1.4 kcal/mol | 10× |

So FEP separates 10 nM from 1 µM reliably, and **cannot** separate 10 nM from 30 nM. Rank-ordering
within that gap over-reads the method. The ~1–1.5 kcal/mol ceiling is the force fields, not the
implementation — OpenFE, FEP+, and the rest all land there.

## Four ways FEP fails confidently

1. **A different binding mode.** FEP assumes both ligands bind the same way. If B flips, the answer
   is meaningless and nothing in the output says so. The most dangerous failure available.
2. **Protonation state changes.** If A and B differ in dominant ionisation at pH 7.4, the
   transformation is not the one you think. Check pKa first.
3. **Net charge changes.** Finite-size electrostatic artefacts needing explicit correction; the
   least reliable edges in any network. Route around them where possible.
4. **A bad atom mapping.** Too many atoms transformed, or a mapping across a ring, makes the
   alchemical path long and the result wrong rather than imprecise. **Look at the mappings before
   running** — the highest-value ten minutes in the workflow.

## Chemical similarity beats topology

Topology decides how many checks you get; similarity decides whether an edge converges at all. An
edge should change fewer than about ten heavy atoms and should not alter the ring system. Let
LOMAP or Konnektor pick the edges, then add cycles to whatever tree they produce.

Three repeats minimum — a single replicate reports only within-run sampling error and understates
the real spread.

## Where this sits

```
chemical-space   10^9 compounds   docking score   seconds each
autodock-vina    10^4 compounds   poses           minutes each
FEP              10^1 compounds   ΔΔG             GPU-days each
synthesis        10^1 compounds   real data       weeks each
```

GPU-days are cheaper than chemist-weeks, which is the entire argument for running it — and the
reason running it earlier is a category error.

## Composing with the rest of the bundle

- `uniprot-rcsb` → before: FEP inherits the binding mode you give it; start from a crystal
  structure with a ligand from the series.
- `binding-site-analysis` → before: confirm the pocket and that the pose is in it.
- `autodock-vina` / `diffdock` → before: narrow hundreds to tens; FEP cannot triage.
- `rowan` → before: pKa and tautomers, so the species being perturbed is the right one.
- `pkpd-translation` → after: a reliable potency is the input to a dose projection.
- `molecular-dynamics` → alongside: pose stability, and whether the protein rearranges.

## Reporting results honestly

Give ΔΔG with its uncertainty, the number of repeats, and the cycle-closure RMS. Name the
reference and say values are relative to it. When comparing to experiment, say it is
offset-corrected, give MUE and a rank correlation, and name the assay. Flag edges that changed net
charge. And frame precision truthfully: "0.8 kcal/mol more potent, roughly fourfold, against a
method RMSE near 1 kcal/mol" is honest; "4-fold more potent" is not.
