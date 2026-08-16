---
name: pkpd-translation
description: Turn in vitro potency and animal pharmacokinetics into a defensible human dose projection — the arithmetic that decides whether a compound can reach its target concentration safely. Use this skill for non-compartmental analysis of a concentration-time profile (AUC, Cmax, terminal half-life, clearance, volume of distribution), one- and two-compartment simulation of a dosing regimen, interspecies allometric scaling, human-equivalent dose conversion by body surface area, and the exposure margin between a projected therapeutic concentration and a toxicology no-effect level. Also trigger on non-compartmental analysis, AUC, clearance, volume of distribution, allometric scaling, human equivalent dose, first-in-human, NOAEL, therapeutic index, or exposure margin.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+ only. Every calculation is closed-form or a fixed-step numerical integration implemented in the standard library, so there is no install, no network access, and no API key. Results are planning arithmetic, not a regulatory submission.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "📈"
    homepage: https://www.fda.gov/media/72309/download
  hermes:
    category: research
---

# PK/PD Translation

The arithmetic between a number on a plate and a number on a label. It decides whether a compound
can reach its target concentration at a dose people can tolerate — and it is where a surprising
number of programmes discover, late, that it cannot.

**No installation, no network, no key.** Every calculation here is closed-form or a fixed-step
numerical integration in the standard library.
**Reference:** FDA, *Estimating the Maximum Safe Starting Dose in Initial Clinical Trials for
Therapeutics in Adult Healthy Volunteers* (2005) — the Km factors are its Table 1.

Read [references/nca-and-parameters.md](references/nca-and-parameters.md) before quoting a PK
parameter, [references/interspecies-scaling.md](references/interspecies-scaling.md) before
converting a dose between species, and
[references/translating-potency-to-dose.md](references/translating-potency-to-dose.md) before
turning an IC50 into a dose — **that one is judgement, not syntax.**

## The four scripts

| Script | Answers |
|---|---|
| `nca.py` | What are this profile's clearance, volume, and half-life? |
| `pk_compartmental.py` | What does this regimen look like at steady state? |
| `allometry.py` | What is the human equivalent of this animal dose? |
| `exposure_margin.py` | Does the projected exposure cover the target, and is it safe? |

## Free drug, or the answer is wrong by 1/fu

This is the one to get right. **Only unbound drug engages the target.** Comparing a total plasma
concentration against a free-drug IC50 is the most common translation error, and at 99% protein
binding it is a hundredfold error in the dangerous direction:

```
C_free = C_total x fu       1000 nM total at fu = 0.01  ->  10 nM free
```

Against a 100 nM IC50 that is tenfold *under*-coverage, not the tenfold coverage the total number
suggests. `exposure_margin.py coverage` takes `--fu` and reports both.

A related trap: 50% inhibition is rarely enough. Occupancy is `C/(C+Ki)`, so 90% needs nine times
Ki and 95% needs nineteen. Ask what fraction the biology requires, and for how long.

## Non-compartmental analysis

```bash
python skills/pkpd-translation/scripts/nca.py --times 0.25,0.5,1,2,4,6,8,12,18,24,36,48 \
    --conc 9.75,9.51,9.05,8.19,6.70,5.49,4.49,3.01,1.65,0.91,0.27,0.08 --dose 100 --route iv
```

Validated against an analytic one-compartment case (D = 100, V = 10, k = 0.1), this returns
CL = 1.000000, Vz = 10.000000, t½ = 6.931472, AUC(0–∞) = 100.000000 — exact.

Three defaults that matter. **Linear-up / log-down trapezoid**, because a straight line between
two descending points sits above an exponential and inflates AUC. **Back-extrapolation to C0** for
IV bolus, because sampling never starts at t = 0 and the missing first segment was 2.5% of AUC in
the case above. And **CL/F and Vz/F labelling** after oral dosing, because calling them CL and V
assumes complete bioavailability.

`nca.py` warns when the terminal fit is poor or when more than 20% of AUC(0–∞) is extrapolated
past the last sample — above that, CL and Vz are guesses.

## Steady state

```bash
python skills/pkpd-translation/scripts/pk_compartmental.py steady --dose 100 --cl 5 --v 50 --tau 24
```

```
half_life_h  accumulation_ratio  time_to_95pct_ss_h  css_max  css_min  css_avg  auc_tau
6.93147      1.09977             29.9573             2.19954  0.199538 0.833333 20
```

**Accumulation depends on half-life and interval, never on dose** — `R = 1/(1 − e^(−kτ))`. Doubling
the dose moves every concentration and leaves the ratio alone. Time to steady state depends only
on half-life, about 4.3 half-lives to 95%, which is why loading doses exist.

Note Css,min of 0.2 against Css,avg of 0.83: the average hides a fourfold swing. Report all three.

## Species conversion

```bash
python skills/pkpd-translation/scripts/allometry.py hed --species rat --species dog --dose 50
```

```
species  km  divide_by  hed_mg_kg  hed_total_mg_60kg
rat      6   6.167      8.10811    486.486
dog      20  1.85       27.027     1621.62
```

**Never transfer mg/kg directly.** Metabolic rate scales with surface area, so a rat dose divides
by about 6.2 and a dog dose by 1.8. Skipping that step overdoses the first human cohort by exactly
that factor.

`fih` takes NOAELs across species, converts each, and applies a safety factor to the **lowest** —
the most sensitive species sets the dose, not the average. The default factor of 10 should rise
for steep dose–response, irreversible toxicity, or a novel target. For biologics and agonists,
MABEL usually governs instead of the NOAEL route; TGN1412 started 500-fold below the NOAEL HED and
still nearly killed six volunteers.

## Coverage and margin

```bash
python skills/pkpd-translation/scripts/exposure_margin.py coverage \
    --dose 100 --cl 5 --v 50 --tau 24 --target-conc 0.05 --fu 0.02
python skills/pkpd-translation/scripts/exposure_margin.py margin \
    --tox-cmax 12000 --eff-cmax 400
```

Both sides of a margin must be the **same metric** and the **same binding basis**. A total-drug
toxicology Cmax against a free-drug efficacy target inflates the margin by 1/fu.

## Four ways this arithmetic misleads

1. **The efficacy driver and the tolerability driver are often different metrics.** Time above
   threshold versus Cmax argues for smaller, more frequent doses; the reverse argues the opposite.
2. **Single-dose PK does not give the steady-state trough**, and the trough is what determines
   whether coverage holds through the interval.
3. **Everything assumes linear PK.** Saturable metabolism, absorption, or binding breaks
   superposition, and then none of the accumulation arithmetic applies.
4. **This is a typical subject, not a population.** Real between-subject variability is severalfold
   and is not represented anywhere here.

## When to stop using these scripts

When the site of action is not plasma (brain, tumour, intracellular), when transporters or
first-pass metabolism dominate, when you need a population rather than a typical subject, or when
the PD is delayed or tolerance-developing. Use PK-Sim/MoBi (Open Systems Pharmacology, open
source) for PBPK, and NONMEM, Monolix, or nlmixr2 for population PK/PD.

## Composing with the rest of the bundle

- `admet-prediction` → here: predicted clearance, half-life, and plasma protein binding as inputs.
- `chembl` → here: a measured IC50 or Ki to translate into a target concentration.
- `openfda` → alongside: the approved label's dose and interval as a real-world anchor.
- `clinicaltrials` → alongside: what doses have actually been taken into humans.
- `free-energy-perturbation` → before: a potency number worth translating.

## Reporting results honestly

Give the free concentration and the fu behind it. Name the exposure metric you believe drives
efficacy and say why. Give Cmax, Cmin, and Cavg, not one. Give margins on a stated matched basis.
Say that this is a one- or two-compartment plasma approximation for a typical subject with no
population variability — it is planning arithmetic, not a regulatory submission.
