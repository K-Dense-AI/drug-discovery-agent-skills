# Running ADMET-AI

ADMET-AI is a Chemprop-RDKit graph neural network trained on **41 ADMET datasets from Therapeutics
Data Commons**. It has the highest average rank on the TDC ADMET leaderboard and is the fastest
public web predictor. MIT licensed, <https://github.com/swansonk14/admet_ai>.

## Install

```bash
pip install admet-ai
```

PyPI 2.0.1 declares `requires-python >=3.11` with no upper bound. It pulls chemprop, RDKit, and
PyTorch. Model weights download on first use.

CPU is adequate — thousands of molecules a minute. There is no reason to provision a GPU for this.

## Command line

```bash
admet_predict --smiles_path input.csv --save_path predictions.csv --smiles_column smiles
```

**The input must be a CSV with a header row.** A bare `.smi` list silently loses its first
molecule to the header. `admet_batch.py prepare` writes the right shape and emits the exact
commands to run.

## Python API

```python
from admet_ai import ADMETModel

model = ADMETModel()
predictions = model.predict(smiles=["CCO", "c1ccccc1"])
```

Returns a pandas DataFrame, one row per molecule.

## Web server

<https://admet.ai.greenstonebio.com> for a handful of molecules interactively. Do not push
proprietary structures to a public web service.

## Output shape

One row per input molecule. Columns fall into three groups:

**Physicochemistry**, computed by RDKit rather than predicted:
`molecular_weight`, `logP`, `hydrogen_bond_acceptors`, `hydrogen_bond_donors`, `Lipinski`,
`QED`, `stereo_centers`, `tpsa`.

**Predictions**, named after their TDC dataset: `hERG`, `AMES`, `DILI`, `Caco2_Wang`,
`Solubility_AqSolDB`, `CYP3A4_Veith`, `Clearance_Hepatocyte_AZ`, `Half_Life_Obach`, and so on.

**Percentiles**, one per prediction, suffixed `_drugbank_approved_percentile`.

## The percentile columns are the point

A raw prediction is hard to act on. `Clearance_Hepatocyte_AZ = 12` means nothing without knowing
what approved drugs look like. The percentile places each prediction against **the distribution of
approved drugs in DrugBank**, so the 90th percentile means "more extreme than 90% of drugs that
made it".

This is the most useful thing ADMET-AI adds over a bare model, and it is the column most often
ignored. `admet_report.py` carries it through into every flagged liability.

## Classification versus regression

The two kinds need different reading:

- **Classification endpoints** (hERG, AMES, DILI, CYP inhibition, BBB, Pgp, HIA, Bioavailability,
  ClinTox, Carcinogens) output a **probability in [0, 1]**, not a class. 0.5 is the conventional
  cut and it is arbitrary; a value of 0.55 is a coin flip from a model with real error.
- **Regression endpoints** (Caco2, Solubility, Lipophilicity, PPBR, VDss, clearance, half-life,
  LD50) output a value in that dataset's units, which are frequently logarithmic. Check the units
  before comparing to an experiment: `Solubility_AqSolDB` is log mol/L, `Caco2_Wang` is
  log cm/s, `LD50_Zhu` is log mol/kg.

## Units and directions worth memorising

| Endpoint | Units | Liability direction |
|---|---|---|
| `Caco2_Wang` | log cm/s | low (< −5.15 is poorly permeable) |
| `Solubility_AqSolDB` | log mol/L | low (< −5 is poorly soluble) |
| `Lipophilicity_AstraZeneca` | logD7.4 | high (> 4) |
| `PPBR_AZ` | % bound | high (> 99% leaves little free drug) |
| `VDss_Lombardo` | L/kg | context dependent |
| `Half_Life_Obach` | hours | low (< 3 h makes once-daily hard) |
| `Clearance_Hepatocyte_AZ` | µL/min/10⁶ cells | high |
| `LD50_Zhu` | log mol/kg | low is more toxic |
| all classification | probability | high, except BBB and HIA |

`admet_report.py endpoints` prints the full registry with the thresholds it applies. Those
thresholds are this skill's conventions, not ADMET-AI's, and are meant to be argued with.

## Desalt first

ADMET-AI predicts on the structure as given. A SMILES containing `.` is a salt, mixture, or
counterion, and the prediction will describe whatever the model makes of the whole string rather
than the parent compound. `admet_batch.py prepare` flags these; use `datamol` or `rdkit` in this
bundle to strip salts and standardise before predicting.

Tautomers are the same problem in a subtler form: the model sees one tautomer and has no notion
that another exists.

## Alternatives

| Tool | Notes |
|---|---|
| **ADMETlab 3.0** | broader endpoint coverage, web + API, free for academics |
| **pkCSM** | web only, older, still widely cited |
| **SwissADME** | fast, rule-based plus simple models, no batch API |
| **ADMET Predictor** (Simulations Plus) | commercial, the industry reference, includes PBPK links |
| **Chemprop** directly | train on your own internal data — usually better than any public model on your own chemistry |

The last row matters most. A model trained on your project's measured data will beat a public
model on your project's chemistry, because the applicability domain finally matches.
