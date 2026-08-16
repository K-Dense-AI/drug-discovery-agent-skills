# Disproportionality analysis on FAERS — the maths and its limits

What `fda_adverse.py signal` computes, why each number is defined the way it is, and the
conditions under which all of them are meaningless. Every worked figure below was produced
against the live API in August 2026 and will drift as FAERS grows.

## The 2x2 table

For a drug D and an event E, over the whole FAERS report corpus:

|  | event E | not E | total |
|---|---|---|---|
| **drug D** | a | b | a+b |
| **not D** | c | d | c+d |
| **total** | a+c | b+d | N |

openFDA gives no cross-tabulation endpoint, so the table is built from four independent totals:

```
a     = total_matching("drug/event", "<D>+AND+<E>")
a + b = total_matching("drug/event", "<D>")
a + c = total_matching("drug/event", "<E>")
N     = total_matching("drug/event", "_exists_:safetyreportid")
```

then `b = (a+b) - a`, `c = (a+c) - a`, `d = N - a - b - c`. Four requests. Against an anonymous
1000-request daily quota that is 250 pairs a day.

**The unit is a report, not a patient and not an exposure.** Every quantity below inherits that.

## The three statistics

**Proportional Reporting Ratio.** How much more of D's reports mention E than the rest of the
database's do.

```
PRR = [a / (a+b)] / [c / (c+d)]
```

**Reporting Odds Ratio.** The odds form, and the one with a tractable confidence interval.

```
ROR    = (a·d) / (b·c)
95% CI = exp( ln(ROR) ± 1.96 · sqrt(1/a + 1/b + 1/c + 1/d) )
```

**Chi-squared**, one degree of freedom, summed over all four cells against expectation under
independence. With N above 20 million it is enormous for almost anything, which is exactly why it
is never used alone.

## The screening rule

The EMA/MHRA convention, and what `signal` reports as `signal: true`:

```
a ≥ 3   AND   PRR ≥ 2   AND   chi² ≥ 4
```

All three must hold. Worked, live:

| Pair | a | PRR | ROR (95% CI) | chi² | signal |
|---|---|---|---|---|---|
| atorvastatin × RHABDOMYOLYSIS | 5713 | 6.28 | 6.33 (6.16–6.51) | 21855 | **true** |
| atorvastatin × ALOPECIA | 5344 | 1.08 | 1.08 (1.05–1.11) | 28.3 | false |

The second row is the argument for the conjunction. Alopecia clears `a ≥ 3` easily and clears
`chi² ≥ 4` by a factor of seven — on chi-squared alone it would be flagged. PRR 1.08 says
atorvastatin reports mention alopecia at essentially the background rate. The chi-squared is
large only because N is large.

The first row is a known true positive: statin-associated rhabdomyolysis, the toxicity that
withdrew cerivastatin in 2001. A method that cannot recover it is broken.

A useful sanity rule: `ROR` and `PRR` converge when the event is rare in both arms, and diverge
as `a/(a+b)` grows. If they disagree substantially, the event is common in D's reports and the
odds ratio is inflating it.

## Six reasons a signal is not a risk

**1. There is no denominator.** FAERS records reports, never exposure. A drug given to ten
million people generates more reports than one given to a thousand, and disproportionality is
computed against *other drugs' reports* rather than against patients treated. Nothing here is an
incidence, a rate, or a probability.

**2. Notoriety bias.** Publicity causes reporting. After a safety communication, litigation
advertising, or a journal paper, reports for that drug-event pair rise sharply with no change in
biology. The 2001 cerivastatin withdrawal raised rhabdomyolysis reporting for every statin.

**3. Confounding by indication.** The disease is reported alongside the drug that treats it.
Antidiabetics disproportionately report hyperglycaemia; oncology drugs disproportionately report
death. The signal is the indication, not the molecule.

**4. Masking.** A single drug with overwhelming reports for an event raises `c` for every other
drug, suppressing their PRRs for that event. Removing the dominant drug from the comparator set
can reveal signals hidden by it.

**5. Duplicates and quality.** The same case reaches FAERS through the manufacturer, the
physician, and the patient. `safetyreportid` deduplicates versions of one submission, not
independent submissions of one case. Reporter qualification
(`primarysource.qualification: 5` = consumer) is not filtered by default.

**6. Concomitant medication.** A drug search matches reports where it was merely
`drugcharacterization: 2` — present, not suspected. `fda_adverse.py` deliberately does not filter
to suspect drugs, because the conventional denominators are computed over all reports; adding
`+AND+patient.drug.drugcharacterization:1` changes both numerator and the comparison base, so
change it on both sides or not at all.

## Data currency

FAERS publishes quarterly and `meta.last_updated` lags by three months or more — 2026-07-30 when
this was written. Consequences: a drug approved in the last two quarters has essentially no data,
and the absence of a signal for a new drug carries no information at all.

## Stronger methods this skill does not implement

The screening rule above is the crude frequentist one. Regulators use shrinkage estimators that
behave far better when `a` is small:

- **BCPNN** (Bayesian Confidence Propagation Neural Network) — the WHO/UMC Information Component,
  which shrinks toward the null when counts are sparse.
- **MGPS/EBGM** (Multi-item Gamma Poisson Shrinker) — the FDA's own empirical-Bayes method.
- **Stratification** by age, sex, and reporting year, which addresses some confounding.
- **LASSO / disproportionality regression** for multi-drug adjustment.

All require the full quarterly FAERS extract rather than the API, because they estimate a prior
across the whole contingency space at once. Download the quarterly files from
<https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html> and use
[`openEBGM`](https://cran.r-project.org/package=openEBGM) or `PhViD` in R.

Use the API method for triage and hypothesis generation. Do not use it to make a claim about
whether a drug causes something.

## Reporting a result honestly

State `a` alongside every ratio — a PRR of 12 built on `a = 4` is noise, and the confidence
interval will show it. Give the ROR with its interval rather than the point estimate. Name the
data cut (`meta.last_updated`). Say "reports mention this event disproportionately", never "the
drug causes" or "the risk is".
