# Designing an ultra-large screen

Judgement, not syntax. Scaling a docking campaign is mostly about knowing which errors grow with
the library and which do not.

## The funnel is the design

A screening cascade is a sequence of filters, each more expensive and more accurate than the
last. The whole craft is choosing the keep-fractions so that every stage costs about the same and
the final stage is small enough to buy.

Default cascade from `space_plan.py cascade`, over a billion compounds:

```
stage              input          keep   survivors    sec/cpd  core_hours  wall_days@1000
property filter    1,000,000,000  0.30   300,000,000  0.0005   139         0.01
fast dock          300,000,000    0.01   3,000,000    3        250,000     10.42
standard dock      3,000,000      0.10   300,000      30       25,000      1.04
rescore / MM-GBSA  300,000        0.10   30,000       300      25,000      1.04
visual triage      30,000         0.20   6,000        60       500         0.02
```

Three things to read off it. The property filter is free and removes 70% — always do it first.
The fast-dock stage dominates at 83% of total compute, so any speedup belongs there. And the
final 6000 is still far more than anyone buys, so a real campaign adds diversity selection and a
hard budget cut at the end.

Substitute your own measured rates with `--stage name:keep:seconds`. The defaults are plausible,
not measured on your hardware.

## What giga-scale actually buys

The published result is real: screening billions rather than millions yields hits with better
potency, more often, and sometimes novel chemotypes. The mechanism is simply that the tail of a
score distribution is better populated when you sample more of it.

But the gain is **sublinear**. Going from 10⁶ to 10⁹ is a thousandfold increase in compute for
something closer to a one-log improvement in the best affinity found. Decide whether that log is
worth it for your target before committing.

## What grows with library size, and what does not

**Grows in absolute terms: false positives.** A docking score is a rough estimate with a large
error. At a fixed score threshold, the number of compounds scoring well *by error* scales with
library size, so a giga-scale screen's top list is proportionally more contaminated than a
million-compound screen's. Enrichment does not improve just because N did.

**Grows: scoring-function artefacts.** Very large libraries reliably surface the specific things
your scoring function overrates — high molecular weight, excessive hydrophobic burial, unusual
charge states, strained conformers presented as favourable. These are not random errors; they are
systematic, and the search finds them precisely because it is thorough.

**Does not grow: the quality of your receptor.** A wrong protonation state, a missing structural
water, or a side chain in the wrong rotamer costs you the same fraction of the answer at any
library size. Effort spent on the receptor has a better return than effort spent on N. Check the
structure with `uniprot-rcsb` and the pocket with `binding-site-analysis` first.

**Does not grow: your ability to confirm.** You can still only assay a few hundred compounds.

## Countermeasures worth the trouble

- **Property-filter before docking**, not after. Cheapest possible removal of the compounds most
  likely to be artefacts.
- **Remove PAINS and reactive groups** early — `medchem` in this bundle.
- **Rescore the survivors with an orthogonal method.** Agreement between two methods that fail
  differently is much stronger than a good score from one.
- **Cluster before buying.** A top-500 list is typically dozens of near-identical analogues of a
  handful of scaffolds; buying 100 diverse compounds beats buying 100 near-duplicates.
- **Include decoys and known actives** when you have them, and measure enrichment rather than
  assuming it.
- **Redock a known ligand** into your prepared receptor and check the pose reproduces. If the
  method cannot recover a crystal pose, its ranking over a billion compounds is not meaningful.

## The step people skip

Before any of this: **is the pocket worth screening?** A shallow, solvent-exposed, or highly
polar site will not yield a good small-molecule hit no matter how many compounds you push through
it, and the screen will still return a ranked list that looks like an answer. `fpocket`
druggability scoring via `binding-site-analysis` costs minutes and can save a month.

## Reporting honestly

Say how many compounds were screened, what fraction survived each stage, and what the last stage
actually was — a docking score is not a binding affinity, and a rank is not a prediction of
potency. Report whether a redocking control was run. Give the number of compounds ordered and the
number that arrived, because make-on-demand synthesis fails roughly one time in five and a hit
rate computed against ordered rather than received compounds is wrong.
