# From IC50 to a dose

Judgement, not syntax. This is the chain that connects a number from a plate to a number on a
label, and almost every link in it can be got wrong quietly.

## The free drug hypothesis

**Only unbound drug crosses membranes and engages the target.** Protein-bound drug is a
circulating reservoir, not an active species. So the comparison that means anything is:

```
free plasma concentration   versus   free-drug potency
C_free = C_total × fu
```

This is the single most common translation error, and it is large. At 99% protein binding
(fu = 0.01), a total Cmax of 1000 nM is 10 nM of free drug — comparing that total against a 100 nM
IC50 says you have tenfold coverage when you actually have tenfold *under*-coverage. A hundredfold
error, in the dangerous direction.

Two corollaries people miss:

- **A cell-based IC50 is already a free-ish number** if the assay had little protein, but a
  10% FBS assay has its own binding. Ideally correct both sides; at minimum, know which side is
  which.
- **Increasing protein binding does not reduce efficacy at steady state** for a hepatically
  cleared drug — clearance of free drug falls in proportion, so free concentration is unchanged.
  Optimising fu upward is usually a mirage. What matters is free concentration at the target.

## Which exposure metric drives effect

The right metric depends on the pharmacology, and picking the wrong one produces a confident wrong
dose.

| Metric | Drives | Examples |
|---|---|---|
| **Time above threshold** | slow, saturable, or resynthesis-limited targets | beta-lactam antibiotics (T>MIC), many enzyme inhibitors |
| **Cmax** | rapidly reversible binding; most tolerability ceilings | aminoglycosides, hERG-driven QT risk |
| **AUC** | cumulative exposure | cytotoxics, fluoroquinolones (AUC/MIC) |

The tolerability limit and the efficacy driver are frequently **different metrics**, and that is
what makes a dosing regimen a real optimisation rather than a single number. A drug whose efficacy
is driven by time above threshold and whose toxicity is driven by Cmax should be given more often
in smaller doses; the reverse argues for less frequent, larger doses.

`exposure_margin.py coverage` reports time above a free-drug target across the interval, and both
Cmax and Cmin, precisely so the choice is explicit.

## Target engagement, not target concentration

IC50 is a 50% number. Most targets need considerably more than 50% inhibition for a phenotype:

```
occupancy = C_free / (C_free + Ki)
```

50% occupancy needs 1 × Ki; 90% needs 9 × Ki; 95% needs 19 × Ki. For a target with rapid turnover
or substantial pathway reserve, the required occupancy can be above 90% *continuously*, which is a
completely different exposure requirement from "exceed the IC50 at Cmax".

Ask what fraction of inhibition the biology requires, and for how long, before choosing a target
concentration. That question is usually answerable only from *in vivo* pharmacology, not from the
plate.

## Steady state, accumulation, and the trough

Accumulation depends on half-life and interval, **not on dose**:

```
R = 1 / (1 − e^(−k·τ))
```

Doubling the dose moves every concentration but leaves R unchanged. Time to steady state depends
only on half-life — about 4.3 half-lives to 95%, whatever the dose or interval — which is why
loading doses exist.

The consequence for translation: **single-dose PK does not tell you the steady-state trough**, and
the trough is what determines whether coverage is maintained. `pk_compartmental.py steady`
computes Css,max, Css,min, Css,avg and the accumulation ratio together for this reason. Css,avg
alone hides both ends.

## Safety margins

```
margin = exposure at the NOAEL / exposure at the efficacious dose
```

Rules that are easy to break:

- **Same metric on both sides.** Cmax margin against Cmax, AUC against AUC. Mixing them is
  meaningless.
- **Same binding basis on both sides.** A total-drug tox Cmax against a free-drug efficacy target
  inflates the margin by 1/fu — a hundredfold for a highly bound compound.
- **Same species basis.** Animal exposure at the NOAEL, compared against *projected human*
  exposure at the efficacious dose.

A margin below about 10 is generally uncomfortable for a first-in-human candidate in healthy
volunteers. It is routinely accepted in oncology, and where the toxicity is monitorable,
reversible, and not the thing that kills the patient. Report the margin and the reasoning; do not
report a verdict.

## What this arithmetic cannot do

Everything here is a one- or two-compartment plasma model. It has no tissue compartments, no
enterohepatic recirculation, no transporters, no metabolites, and no between-subject variability.
It gives a central estimate for a typical subject, and real populations vary severalfold.

Reach for more when:

- **The site of action is not plasma** — brain, tumour, lung, intracellular. Plasma concentration
  can be a poor proxy, and Kp,uu (unbound tissue-to-plasma ratio) is the quantity that matters.
- **Transporters or first-pass metabolism dominate** — needs PBPK.
- **You need a population, not a typical subject** — needs population PK with covariates and
  simulated variability.
- **The PD is delayed, indirect, or tolerance-developing** — hysteresis means concentration and
  effect do not track, and an indirect-response or turnover model is required.

Tools: **PK-Sim / MoBi** (Open Systems Pharmacology, open source) for PBPK; **NONMEM**,
**Monolix**, or **nlmixr2** for population PK/PD; **Simcyp** and **GastroPlus** commercially.

## Reporting

Give the free concentration and the fu used to compute it. Name the exposure metric you consider
the efficacy driver and say why. Give Cmax, Cmin, and Cavg at steady state, not one of them. Give
margins on a stated, matched basis. State that the model is a one-compartment plasma
approximation for a typical subject, and that population variability is not represented.
