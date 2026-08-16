---
name: admet-prediction
description: Turn a set of structures into absorption, distribution, metabolism, excretion, and toxicity estimates with ADMET-AI, and read them as a developability verdict rather than a table of numbers. Use this skill to run batch prediction over a library, interpret each endpoint against its DrugBank-approved percentile, and flag the liabilities that stop a series — hERG blockade, CYP inhibition, poor Caco-2 permeability, high clearance, and plasma protein binding. Also trigger on ADMET-AI, admet_ai, Chemprop-RDKit, hERG liability, CYP3A4 inhibition, Caco-2, bioavailability prediction, or developability triage.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+. The bundled scripts chunk input and parse ADMET-AI CSV output with the standard library only. Generating predictions needs admet-ai 2.0+ (pip, requires-python >=3.11, MIT) plus chemprop and RDKit; models download on first use. CPU is adequate for thousands of molecules.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "💊"
    homepage: https://github.com/swansonk14/admet_ai
  hermes:
    category: research
---

# ADMET Prediction

Potency gets a compound into a programme; ADMET decides whether it survives one. ADMET-AI is a
Chemprop-RDKit graph network trained on 41 Therapeutics Data Commons datasets, tops the TDC ADMET
leaderboard, and runs thousands of molecules a minute on a CPU. This skill is about reading its
output as a developability verdict rather than a wall of numbers.

**Tool:** [ADMET-AI](https://github.com/swansonk14/admet_ai) 2.0.1, MIT, `pip install admet-ai`
(requires Python 3.11+). Weights download on first use. No GPU needed.
**Checked against:** PyPI 2.0.1, February 2026.

Read [references/running-admet-ai.md](references/running-admet-ai.md) before your first run,
[references/endpoints.md](references/endpoints.md) to know which endpoints actually stop
programmes, and
[references/interpreting-predictions.md](references/interpreting-predictions.md) before acting on
a number — **that one is judgement, not syntax.**

## The two scripts

| Script | Answers |
|---|---|
| `admet_batch.py` | How do I feed a library in without wasting the run? |
| `admet_report.py` | Which of these compounds has a liability worth acting on? |

## Rank within a series; do not trust absolute values

This is the thing to get right. A public model has systematic offsets against your assay —
different protocol, different lab, different chemistry. Within a congeneric series those offsets
are largely **shared**, so the ordering survives even where the values do not.

Use predictions to decide *which twenty of these hundred to make and assay*. Do not use them to
decide *whether this compound will pass*. A predicted hERG of 0.7 versus 0.3 within a series is a
real signal; 0.7 in absolute terms is not a measurement.

## The percentile column is the point

ADMET-AI reports every prediction against the distribution of **approved drugs in DrugBank**, in
`<endpoint>_drugbank_approved_percentile`. It is the most useful thing the tool adds over a bare
model and the column most often ignored.

"Predicted clearance 12" is hard to act on. "More extreme than 92% of approved drugs" prompts the
right question: drugs exist out here, but not many — what is the argument that this one works?

## Flagging a set

```bash
python skills/admet-prediction/scripts/admet_report.py report --csv predictions.csv
```

```
smiles                              liabilities  flagged                                             out_of_domain
c1ccccc1CCNC(=O)c1ccc(Cl)cc1        5            hERG|DILI|Solubility_AqSolDB|Lipophilicity|Half_Life
CCO                                 0                                                                molecular_weight=46.07 outside [150, 700]
```

Each endpoint is flagged against **its own direction** — high solubility is good, high clearance is
bad, high hERG is very bad — so a single summed "score" over the columns would be meaningless.
`admet_report.py endpoints` prints the full registry with thresholds; they are this skill's
conventions and are meant to be argued with.

Note the second row. Ethanol is flagged as **out of domain**, not clean. ADMET-AI reports no
applicability domain, so a prediction on anything unlike its training data arrives with the same
confident four decimal places as a reliable one.

**BBB penetration has no liability direction** — essential for a CNS target, a liability
everywhere else. The script leaves it unflagged rather than guessing your programme.

## Preparing input

```bash
python skills/admet-prediction/scripts/admet_batch.py prepare --smiles library.smi --out-dir admet_in
```

```
# 3 input, 2 unique (1 duplicates collapsed), 1 chunk(s)
# warning: 1 SMILES contain `.` -- a salt, mixture, or counterion.
admet_predict --smiles_path admet_in/chunk_0000.csv --save_path admet_in/chunk_0000_pred.csv --smiles_column smiles
```

Three things this prevents. **ADMET-AI needs a CSV with a header** — a bare `.smi` list silently
loses its first molecule. **Duplicates cost twice and add nothing**, since the model is
deterministic. And **a `.` in a SMILES is a salt or mixture**: the model predicts on the string as
given, so the answer describes the wrong species. Desalt with `datamol` first.

## Four ways predictions mislead

1. **Classification outputs are probabilities, not classes.** hERG at 0.55 is a coin flip. Move
   the threshold with the cost of being wrong — screen hERG at 0.3, not 0.5.
2. **Endpoints are not equally trustworthy.** Lipophilicity and solubility are well predicted;
   DILI, clearance, and Vd are barely better than a coin flip. The leaderboard's average rank
   hides that.
3. **Real liabilities are simply absent.** Time-dependent CYP inhibition, reactive metabolites,
   transporters beyond Pgp, phospholipidosis, mitochondrial toxicity — none are covered.
4. **Over-filtering early is the expensive mistake.** Most ADMET liabilities are fixable by
   medicinal chemistry; poor potency and a wrong target are not. Filtering a primary screen on
   predicted DILI discards real chemistry on the basis of noise.

## When to stop using this

If your project has more than a few hundred measured compounds for an endpoint, train a Chemprop
model on your own data — the applicability domain finally matches your chemistry, and it will beat
any public model on it. For time-dependent CYP inhibition, transporters, or reactive metabolites,
there is no model; run the assay.

## Composing with the rest of the bundle

- `medchem` → before: structural alerts and PAINS cost nothing and catch much of this first.
- `rdkit` / `datamol` → before: desalt and standardise, or you predict on the wrong species.
- `chemical-space` → before: this is a good filter stage in an ultra-large cascade.
- `pkpd-translation` → after: predicted clearance, half-life, and PPB become dose projections.
- `deepchem` / `pytdc` → instead: when you want to train on your own data rather than use a
  ready-made model.

## Reporting results honestly

Give the percentile beside the value. Name the thresholds used and say they are conventions. State
whether the molecule sits inside a drug-like property window. Never write "this compound is a hERG
blocker" from a prediction — write "predicted hERG 0.82, above the 90th percentile of approved
drugs; assay before progressing". Say what the predictions decided: they choose what to assay,
they do not replace it.
