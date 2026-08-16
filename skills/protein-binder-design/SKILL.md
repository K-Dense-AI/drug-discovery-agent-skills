---
name: protein-binder-design
description: Design new proteins that bind a chosen surface, using BindCraft's AlphaFold2-guided hallucination or the RFdiffusion backbone plus ProteinMPNN sequence pipeline. Use this skill to specify a target epitope by hotspot residue, trim a receptor to the region worth designing against, set up a design campaign, and filter the output on the in-silico metrics that predict experimental success — interface predicted TM-score, predicted aligned error at the interface, buried surface area, and shape complementarity. Also trigger on BindCraft, RFdiffusion, ProteinMPNN, minibinder, hallucination, inverse folding, hotspot residue, epitope targeting, ipTM, or de novo binder.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+. The bundled scripts prepare target specifications and filter design metrics using only the standard library. Running a campaign needs BindCraft 1.5+ (MIT, from GitHub) with AlphaFold2 weights, or RFdiffusion plus ProteinMPNN, and an NVIDIA GPU — a single binder trajectory is tens of minutes.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🧷"
    homepage: https://github.com/martinpacesa/BindCraft
  hermes:
    category: research
---

# De Novo Protein Binder Design

Designing a new protein that binds a chosen surface used to be a research project. BindCraft
reports 10–100% experimental success without high-throughput screening, and the pipeline is open
source. The hard part is no longer the algorithm — it is choosing where to bind, and knowing that
the metrics which select designs cannot tell you which one works.

**Tools:** [BindCraft](https://github.com/martinpacesa/BindCraft) 1.5+ (Nature 2025, MIT), or
RFdiffusion + ProteinMPNN + AlphaFold2. Both need AlphaFold2 weights and an NVIDIA GPU; a single
trajectory is roughly half an hour. The bundled scripts prepare targets and filter output, and run
anywhere.

Read [references/epitope-selection.md](references/epitope-selection.md) **before** anything else,
[references/bindcraft-and-rfdiffusion.md](references/bindcraft-and-rfdiffusion.md) to choose a
pipeline, and
[references/filtering-and-validation.md](references/filtering-and-validation.md) before ordering —
**that one is judgement, not syntax.**

## The three scripts

| Script | Answers |
|---|---|
| `binder_target_spec.py` | Where should the binder bind, and is that site usable? |
| `design_manifest.py` | Which pipeline, how many trajectories, what will it cost? |
| `binder_filter.py` | Which designs survive, and which should I actually order? |

## The epitope decides the campaign

Everything downstream is compute spent on this one choice, and a bad site produces designs that
fold beautifully and bind nothing — **with no signal that the site was the problem**.

```bash
python skills/protein-binder-design/scripts/binder_target_spec.py hotspots \
    --pdb target.pdb --chain A --hotspots 45,47,52,89
```

```
# 4 hotspot residues, maximum separation 14.2 A
resseq  resname  neighbours  exposure  issue
45      TYR      16          surface
47      LEU      24          buried    buried -- cannot be contacted
```

Three checks it applies: hotspots must be **surface-exposed** (a buried residue cannot be
contacted, and neither design tool will say so), there should be **3–6** of them, and they must sit
**within ~25 Å** — a wider spread is asking a single binder to do something impossible.

Then trim: designing against a 900-residue protein spends nearly all the compute on regions the
binder never touches. `trim` selects 100–200 residues around the epitope and warns outside that
band. Remove glycans and disorder first — neither is modelled, and both bias the interface toward
surface that is occluded in the real protein.

## ipTM is not pTM

The most consequential confusion in reading design output. **pTM scores the whole complex** and is
dominated by a large well-folded target; **ipTM scores the interface**. A design can have excellent
pTM and no interface at all.

```bash
python skills/protein-binder-design/scripts/binder_filter.py filter --csv metrics.csv --all
```

```
design  iptm  ipae  plddt  dsasa  shape_complementarity  unsat_hbonds  passes  failures
d1      0.88  7.2   88     1450   0.62                   2             true
d2      0.61  14    72     800    0.48                   7             false   iptm<0.8|ipae>10|plddt<80|...
```

| Metric | Threshold |
|---|---|
| ipTM | ≥ 0.80 |
| i_pAE | ≤ 10 Å |
| binder pLDDT | ≥ 80 |
| ΔSASA | ≥ 1000 Å² |
| shape complementarity | ≥ 0.55 |
| unsatisfied buried H-bonds | ≤ 4 |

**These are a conjunction.** Published success rates come from designs passing all of them
together; sorting by ΔSASA alone gets you large, loosely packed interfaces.

## The metrics cannot pick the winner

They come from **the same model family that generated the designs** — AlphaFold2 hallucination
optimises until AlphaFold2 is confident, then AlphaFold2 confidence judges the result. That
circularity is not fatal (the correlation with experimental success is the empirical finding the
field rests on) but it means the metrics are **self-consistency measures, not affinity
predictions**, and among survivors they cannot rank.

So the plate is the experiment:

```bash
python skills/protein-binder-design/scripts/binder_filter.py diverse --csv metrics.csv --n 24
```

Ranking by ipTM alone returns near-identical designs — a top-24 list can be one solution tested 24
times. `diverse` enforces a pairwise identity ceiling. **Order at least 20.**

## Cost is trajectories per ordered design

```bash
python skills/protein-binder-design/scripts/design_manifest.py plan --want 24 --pass-rate 0.03 --gpus 4
```

```
# 801 trajectories to expect 24 filter survivors at a 3% pass rate
# 400.5 GPU-hours -> 4.17 days on 4 GPU(s)
```

The **filter pass rate is the hidden cost**, and it is target-dependent. Set the trajectory count
from it, not from the number of binders you want.

## BindCraft or RFdiffusion

**BindCraft co-folds binder and target at every iteration**, so target flexibility is accounted
for and no known binding site is needed. **RFdiffusion generates against a fixed target**, so
induced fit is invisible to it — but it gives explicit control of binder length, fold, and
secondary structure. On a flexible epitope, prefer BindCraft.

## Four things to expect

1. **Most designs fail, and that is normal.** A 10% success rate means nine of ten do not bind.
2. **Affinity confirms binding, not the model.** A binder can bind well through an interface
   entirely different from the designed one. Only a structure tells you.
3. **Specificity is not predictable.** Designs frequently bind close paralogues; counter-screen
   early, before optimisation.
4. **Nothing passing the filters usually means the epitope**, not the trajectory count. More
   compute against a bad site produces more confident failures.

## Composing with the rest of the bundle

- `uniprot-rcsb` → before: an experimental structure beats an AlphaFold model, which biases toward
  closed apo states with unreliable surface side chains.
- `binding-site-analysis` → before: the hydrophobic-patch logic transfers, though protein-protein
  interfaces are flatter than small-molecule pockets and score lower.
- `esm` → alongside: sequence-level sanity checks on the designs.
- `immunogenicity` → after, **not optional**: a de novo binder is entirely non-germline.
- `glycoengineering` → after: check the designs for introduced N-glycosylation sequons.
- `adaptyv` → after: BLI/SPR on the plate you designed.
- `tamarind` → instead: runs both pipelines in the cloud when there is no local GPU.

## Reporting results honestly

Give every filter and threshold and say they were applied as a conjunction. Report trajectories
run and survivors — the pass rate is the informative number. State that the metrics come from the
same model family that produced the designs. Report ordered, expressed, and bound as three
separate counts, because that chain is what the campaign actually delivered. Never quote ipTM as a
predicted affinity.
