# Synthesisability scores, and when a full search is worth it

Route search costs seconds to minutes per molecule. Scores cost microseconds. For a library of any
size the practical answer is both, in that order.

## The scores

**SAscore** (Ertl & Schuffenhauer, 2009). Fragment contributions from PubChem frequency, plus
penalties for ring complexity, stereocentres, and size. Range 1 (easy) to 10 (hard).

- *Strength*: essentially free, no training, available in RDKit's contrib directory.
- *Weakness*: it measures **structural unusualness**, not synthesisability. A common motif made by
  difficult chemistry scores well; an easily made but unusual-looking molecule scores badly.
- Practical cut: below 4 is unremarkable, above 6 deserves a look.

**SCScore** (Coley et al., 2018). A neural network trained on Reaxys reactions to satisfy the
constraint that a product is more complex than its reactants. Range 1–5.

- Learns synthetic *complexity* as reaction data implies it, rather than fragment frequency.
- Better correlated with real difficulty than SAscore for many series.

**RAscore** (Thakkar et al., 2021). A classifier trained on **AiZynthFinder's own solved/unsolved
outcomes** over ChEMBL. Outputs the probability that a full retrosynthetic search would find a
route.

- The most directly relevant score here, because it predicts precisely the thing you would
  otherwise spend minutes computing.
- Its limitation follows from its definition: it predicts *AiZynthFinder's* verdict, inheriting
  every blind spot of the template model. It is a fast approximation of a specific tool, not of
  reality.

**SYBA**, **GASA**, and others exist; the three above cover the useful range.

## Choosing

| Situation | Use |
|---|---|
| Millions of molecules, coarse triage | SAscore |
| A generative scoring-function component | SAscore or RAscore — both are fast enough for the inner loop |
| Thousands, deciding what to search properly | RAscore |
| Hundreds, deciding what to make | full route search |
| The compounds you will actually order | full route search, read by a chemist |

The published comparisons agree on the shape of the answer: these scores separate obviously
feasible from obviously infeasible reliably, and are much weaker in the middle — which is where
most real molecules sit. Use them to remove the tail, not to rank the body.

## Why a score cannot replace a search

A score maps a structure to a number. A search returns a **route**, and the route is the useful
object:

- It names the starting materials, so you can price and order them.
- It shows where the disconnections are, which determines whether analogues are cheap.
- It exposes shared intermediates across a series.
- It can be read and rejected by a chemist, which a score cannot.

A score tells you a molecule is probably makeable. A route tells you how, and how much.

## Building it into generation

Two ways to keep `generative-design` inside makeable space, and doing both is better:

**During the run.** Add SAscore as a scoring component so synthesisability is part of the
objective. Cheap enough for the inner loop, and it stops the agent drifting into
difficult-to-synthesise space in the first place — which matters because the drift is progressive:
the harder you optimise everything else, the further out it goes.

**After the run.** Full route search over the output, and report the solved fraction alongside
whatever else you report. This is honest and slow.

The failure of doing only the second is that you discover, at the end, that your best-scoring
molecules are the least makeable — because the optimiser was rewarded for exploring exactly where
the chemistry runs out.

## A caution about circularity

If RAscore gates a library and AiZynthFinder then evaluates it, the reported solved fraction is
inflated: RAscore was trained to predict AiZynthFinder's verdict, so it has already removed the
molecules AiZynthFinder would have failed. That is fine as a pipeline and misleading as a
statistic. Report the pre-filter.

The same applies to using SAscore in a generative objective and then reporting SAscore of the
output.

## Where the ground truth is

None of this is validated until a chemist makes the compound. The honest hierarchy:

```
SAscore  <  RAscore  <  route search  <  a chemist's opinion  <  the compound in a vial
```

Every step right is more expensive and more real. Spend the cheap ones broadly and the expensive
ones narrowly, and never report a number from the left of that chain as though it came from the
right.
