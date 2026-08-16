# Combinatorial chemical spaces

A stored library is a list of molecules. A **combinatorial space** is a set of reagents plus
reaction rules, from which molecules can be produced on demand. The distinction decides which
algorithms are available to you, and it is the central fact of giga-scale screening.

## The spaces

| Space | Size | Form |
|---|---|---|
| Enamine REAL Space | ~94 billion | synthon-based, combinatorial |
| Enamine REAL Database | ~6 billion | enumerated, downloadable |
| ZINC-22 (2D) | ~54.9 billion | enumerated, tranche files |
| ZINC-22 (3D) | ~5.9 billion | enumerated, with conformers |
| WuXi GalaXi | ~30 billion | combinatorial |
| Otava CHEMriya | ~12 billion | combinatorial |
| eXplore (BioSolveIT) | ~5 trillion | combinatorial |

Sizes drift upward constantly; treat any figure as a snapshot. Enamine REAL grew from 120 million
to over 94 billion in about a decade.

## Why "make-on-demand" is the enabling idea

None of these compounds sit on a shelf. They are combinations of validated reagents through
reactions with high, measured success rates — Enamine reports roughly 80% synthesis success at a
few weeks' turnaround. The compound is made only when ordered.

Two consequences that matter more than the headline number:

**You are ordering a synthesis, not a vial.** Roughly one in five requested compounds fails to
materialise. Order more than you need, and never design a follow-up experiment that depends on
one specific analogue arriving.

**The space is shaped by what is easy to make.** Amide couplings, Suzuki couplings, reductive
aminations, and sulfonamide formation dominate. This is why REAL Space is enormous and yet
chemically narrower than its size suggests: it is a Cartesian product over a modest set of
robust reactions. Novel scaffolds and unusual ring systems are systematically underrepresented.

## Synthons, and why enumeration stops working

A synthon is a reagent fragment with an attachment point. REAL Space is defined as
`synthon_A x reaction x synthon_B (x synthon_C)`, so the compound count is a product of a few
thousand reagents across a few hundred reactions.

At 94 billion compounds, enumeration fails on arithmetic alone. Writing SMILES at 100 bytes each
is roughly 9 TB before any conformer generation, and docking each for three seconds is about
78 000 core-years.

The escape is to **search the space without enumerating it**:

- **V-SYNTHES / V-SYNTHES2** — dock a Minimal Enumeration Library of fragments representing every
  scaffold and synthon, keep the best-scoring, enumerate only those with their compatible
  partners, and iterate. V-SYNTHES2 (2026) reports this over 36 billion REAL Space compounds.
- **FTrees-FS / SpaceLight (BioSolveIT)** — feature-tree similarity searching directly over the
  combinatorial definition, returning near-neighbours without enumeration.
- **SmallWorld** — graph-based nearest-neighbour search across REAL Space and ZINC.
- **Chemical-space docking with fragment growing** — the general family the above belong to.

The common shape: **evaluate reagents and fragments, not products.** Anything that requires
touching each product is off the table.

## Choosing between an enumerated and a combinatorial approach

| Library size | Approach |
|---|---|
| ≤ 10⁶ | enumerate and dock everything; spend compute on pose quality |
| 10⁶–10⁸ | enumerate, property-filter and remove PAINS hard, then dock |
| ≥ 10⁸ | synthon-based; do not enumerate |

`space_plan.py strategy` reports this, and `space_plan.py cascade` makes the wall-clock explicit
so the boundary is visible rather than asserted.

## Access and licensing

- **ZINC-22** is fully open — tranche files at files.docking.org, no account.
- **Enamine REAL Database** (the enumerated ~6 billion subset) is downloadable free for
  non-commercial use after registering with Enamine.
- **Enamine REAL Space** (the full synthon definition) requires an agreement with Enamine.
  Identifiers and the general structure are public; the reagent and reaction files are not.
- **BioSolveIT** tools (infiniSee, SpaceLight, FTrees) are commercial, with academic terms.
- **WuXi GalaXi**, **Otava CHEMriya** — through the vendor.

This is why the bundled scripts stop at ZINC-22: it is the part that is genuinely open. The rest
is documented so you know what to ask for.

## Practical cautions

**Compound identity across vendors is not guaranteed.** The same structure may appear under
different ZINC ids, vendor codes, and stereochemical specifications. Deduplicate on InChIKey, and
watch that the first block matching does not imply the same stereoisomer.

**Property filters must be applied before docking, not after.** In a giga-scale library the
majority of compounds fail an ordinary property window, and filtering is thousands of times
cheaper per compound than posing.

**A hit rate applied to a giga-scale library gives an unaffordable number of hits.** A 0.1% hit
rate over a billion compounds is a million "hits". The funnel exists to make the final list small
enough to buy — the last stage should be sized by your budget, not by a score threshold.

**Bigger is not automatically better.** Published ultra-large screens do report higher potency
hits from larger spaces, but the gain is sublinear and comes with more scoring-function artefacts
— rank-ordering errors that a docking score cannot distinguish from real affinity, and which
appear in absolute numbers proportional to library size.
