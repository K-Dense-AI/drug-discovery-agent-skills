# Filtering designs, and confirming them

Judgement, not syntax. The in-silico metrics decide what to order; only the assay decides what
binds.

## ipTM is not pTM

The most common and most consequential confusion.

- **pTM** scores the predicted accuracy of the *whole complex*. A large, well-folded target
  dominates it, so a design can have excellent pTM and no interface at all.
- **ipTM** scores the *interface* specifically, and it is the single most predictive in-silico
  metric for binder success.

Filter on ipTM. If a metrics table only has pTM, it is not telling you what you need.

## The standard filter set

| Metric | Threshold | Measures |
|---|---|---|
| **ipTM** | ≥ 0.80 | interface predicted TM-score |
| **i_pAE** | ≤ 10 Å | confidence in the relative placement of the two chains |
| **binder pLDDT** | ≥ 80 | a binder the model cannot fold confidently will not fold |
| **ΔSASA** | ≥ 1000 Å² | buried interface area; below this, too small for useful affinity |
| **Shape complementarity** | ≥ 0.55 | geometric fit; loose packing gives weak, non-specific binding |
| **Unsatisfied buried H-bonds** | ≤ 4 | each is a large desolvation penalty |

**These are a conjunction.** Published success rates come from designs passing all of them
together. Ranking on any single metric selects for that metric's failure mode — sort by ΔSASA
alone and you get large, loosely packed interfaces.

The thresholds are common practice, not guarantees. `binder_filter.py metrics` prints them with
the reasoning, and every one can be overridden.

## What the metrics are, and are not

They come from **the same model family that generated the designs**. AlphaFold2 hallucination
optimises a design until AlphaFold2 is confident about it, and then AlphaFold2 confidence is used
to judge it.

That circularity is not fatal — the metrics do correlate with experimental success, which is the
empirical finding the whole field rests on — but it means:

- They are **self-consistency measures**, not affinity predictions.
- They cannot rank a plate. Among filter survivors, the metrics do not identify which one binds.
- An orthogonal check adds real information: a different structure predictor, a Rosetta interface
  energy, or a short molecular dynamics run to see whether the interface survives.

## Order diverse designs

Because the metrics cannot pick the winner, the plate is the experiment. Ranking by ipTM alone
returns near-identical designs — variations on one trajectory's solution — so a plate of the top 24
by ipTM may be one design tested 24 times.

`binder_filter.py diverse` picks survivors under a pairwise identity ceiling. **Order at least 20**;
fewer wastes the campaign, given that success rates run from 10% upward.

## Experimental validation

In order, cheapest first:

1. **Expression and solubility.** Many designs fail here. Small helical binders in *E. coli* are
   the easy case.
2. **Thermal stability** (nanoDSF, DSF). A designed binder should be very stable — Tm above 70 °C
   is common and a low Tm is a warning.
3. **Binding**, by BLI or SPR. Gives kon, koff, and Kd. `adaptyv` in this bundle runs these as a
   service.
4. **Specificity counter-screen** against paralogues and an unrelated protein. Not optional: a
   binder that binds everything is a sticky peptide.
5. **Function** — does binding block what you wanted blocked?
6. **A structure** of the complex, if it matters. This is also the only way to know whether the
   design binds *where and how* it was designed to, and the answer is sometimes no even when the
   affinity is good.

Step 6 is worth emphasising: a binder can have excellent affinity through an interface entirely
different from the designed one. Affinity confirms binding, not the model.

## Reading a failed campaign

**Nothing passes the filters.** Usually the epitope: flat, polar, flexible, or too small. Revisit
the site before generating more trajectories — more compute against a bad epitope produces more
confident failures.

**Designs pass but do not express.** Look at the sequences — unusual composition, long loops,
odd cysteine counts. Constrain the design to simpler topologies.

**Designs express but do not bind.** The commonest outcome, and expected: a 10% success rate means
nine of ten fail. Order more. If the whole plate fails, suspect the epitope or that a natural
ligand is outcompeting you.

**Designs bind but not specifically.** Usually a hydrophobic patch acting non-specifically.
Counter-screen early so this is discovered before optimisation.

## Reporting

Give every filter and its threshold, and say the filters were applied as a conjunction. Say how
many trajectories were run and how many survived — the pass rate is the informative number. State
that the metrics come from the same model family that generated the designs. Report how many were
ordered, how many expressed, and how many bound, because that chain is what the campaign actually
produced. Never quote ipTM as a predicted affinity.
