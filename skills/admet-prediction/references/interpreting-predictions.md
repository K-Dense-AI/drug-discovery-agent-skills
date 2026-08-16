# What an ADMET prediction is worth

Judgement, not syntax. The numbers arrive with four decimal places and no error bars, which is a
misleading combination.

## Ranking is reliable; absolute values are not

The single most useful framing. A model trained on public data has systematic offsets against your
assay — different protocol, different lab, different chemistry. But within a congeneric series
those offsets are largely shared, so **the ordering survives even when the values do not**.

Use predictions to decide *which of these twenty to make and assay*. Do not use them to decide
*whether this compound will pass*. A predicted hERG of 0.7 versus 0.3 within a series is a real
signal about which analogue to deprioritise; a predicted 0.7 in absolute terms is not a
measurement.

## Applicability domain, which is not reported

Every model is reliable only for molecules resembling its training data, and **ADMET-AI outputs no
applicability-domain estimate**. A prediction on a macrocycle, a PROTAC, a highly charged
zwitterion, or anything outside conventional drug-like space is extrapolation presented with the
same confident precision as an interpolation.

`admet_report.py` flags molecules outside a drug-like physicochemical window (MW 150–700,
logP −2 to 6, HBD ≤ 6, HBA ≤ 12, TPSA ≤ 180) as a crude proxy. It is crude — being inside the
window does not put you inside the domain, since the domain is about structural similarity, not
properties. For a better estimate, compute Tanimoto similarity to the nearest training compounds.

This matters acutely for `degraders`: bifunctional degraders sit far outside rule-of-five space by
design, so essentially every ADMET model is extrapolating on them.

## The DrugBank percentile is the right frame

Raw values invite false precision. Percentiles against approved drugs invite the right question.

"Predicted clearance 12 µL/min/10⁶ cells" is hard to act on. "More extreme than 92% of approved
drugs" prompts the correct response: *drugs do exist out here, but not many, so what is the
argument that this one works?*

It also handles the endpoints where a threshold is genuinely arbitrary. There is no universal
solubility cut; there is a distribution of what got approved.

## Classification outputs are probabilities

0.5 is a convention, not a decision boundary the model was optimised for. Three consequences:

- **Values near 0.5 carry almost no information.** Do not report them as calls.
- **The threshold should move with the cost of being wrong.** For hERG, where a false negative
  costs a programme, screen at 0.3. For an endpoint where a false positive discards a good
  compound, screen at 0.7.
- **Calibration is not guaranteed.** A predicted 0.8 does not mean 80% of such compounds are
  positive unless the model was calibrated, and these generally are not.

## Weak endpoints, named

Do not treat all 41 endpoints as equally trustworthy:

| Reasonably predicted | Poorly predicted |
|---|---|
| lipophilicity, solubility | DILI |
| Caco-2 permeability | clearance and half-life |
| CYP inhibition (reversible) | Vd |
| Ames (structural alerts do much of the work) | idiosyncratic toxicity of any kind |
| BBB penetration | time-dependent CYP inhibition (absent) |

Clearance and half-life deserve particular caution: they depend on transporters, protein binding,
and enzyme expression that a structure alone does not determine, and in vitro–in vivo
extrapolation from real microsomal data will beat any structural model.

## The failure that matters most

**Over-filtering early.** It is easy to run ADMET predictions on a hit list, discard everything
with a flag, and be left with clean, weak compounds. Most ADMET liabilities are fixable by
medicinal chemistry; poor potency and a bad target are not.

The right sequence is to establish a potent series first, then optimise ADMET within it, using
predictions to prioritise which analogues to make. Filtering a primary screen on predicted DILI —
an endpoint the models barely predict — throws away real chemistry on the basis of noise.

The exception is genuine hard stops on obvious structural grounds: a nitroaromatic, a Michael
acceptor where covalency is not intended, a known toxicophore. Those are `medchem`'s job and cost
nothing.

## Reporting

Give the percentile alongside the value. Say which endpoints were flagged and at what threshold,
and that the thresholds are conventions. State whether the molecule is inside a drug-like property
window. Never write "this compound is a hERG blocker" from a prediction — write "predicted hERG
0.82, above the 90th percentile of approved drugs; assay before progressing."

And say what the predictions decided: they should be choosing what to assay, not replacing it.

## When to build your own

If your project has more than a few hundred measured compounds for an endpoint, a Chemprop model
trained on your own data will beat any public model on your own chemistry — the applicability
domain finally matches. `deepchem` and `pytdc` in this bundle cover the training and benchmarking
side; ADMET-AI is the ready-made answer for when you have nothing of your own.
