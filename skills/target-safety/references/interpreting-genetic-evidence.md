# Reading genetic evidence for a target

Judgement, not syntax. The numbers are easy to fetch and easy to over-read.

## Why this evidence class is worth more than the others

Targets with human genetic support are roughly **twice as likely** to survive clinical
development. The reason is mechanistic rather than statistical: a genetic variant is a
randomised, lifelong, human experiment in modulating one protein. Randomised at conception, so
unconfounded by the things that wreck observational evidence. Human, so it does not need to
translate across species. And it reports the *consequence* of altered protein dose, which is what
a drug produces.

No cell assay and no mouse gives you that. It is also the only evidence available before a
molecule exists, which is why it belongs at the start of a programme rather than the end.

## The two axes

The dossier is a 2×2 over constraint and association, and each cell means something different:

| | **Genome-wide association** | **No association** |
|---|---|---|
| **Tolerant** (LOEUF ≥ 0.6) | **genetically supported** — human knockouts exist and losing the protein moves a trait | **tolerated, unvalidated** — safe to inhibit, no evidence it helps |
| **Constrained** (LOEUF < 0.6) | **associated but constrained** — the biology is real, expect mechanism-based toxicity | **constrained, unvalidated** — the weakest cell |

Live examples:

- **PCSK9** — LOEUF 1.14, 44 genome-wide traits dominated by LDL and cholesterol measures.
  Genetically supported, and the reason evolocumab and alirocumab exist.
- **LRRK2** — LOEUF 0.75, Parkinson disease at p = 4e-148 with 18 sole-mapping associations.
  Genetically supported, and the published safety argument for LRRK2 inhibitors.
- **HTT** — LOEUF 0.34, plenty of associations. Associated but constrained: huntingtin lowering
  is an active clinical strategy *and* carries real concern about losing wild-type protein.

The heuristic is a starting point for a conversation, not an answer. Always report the inputs
beside the verdict.

## What the direction of effect does and does not tell you

A GWAS association says the locus is involved. It does not say which direction helps.

To get direction you need the **allelic series**: does a variant that *lowers* protein function
lower disease risk, or raise it? That is the difference between "inhibit this" and "activate
this", and getting it backwards is the most expensive mistake available. PCSK9 again: LoF
variants lower LDL and lower cardiovascular risk, so the drug is an inhibitor. Had it been the
other way round, an inhibitor would have been actively harmful.

Sources of direction: the sign of `beta` when present, coding variants of known functional
consequence, dose-response across an allelic series, and Mendelian randomisation using a
protein-altering instrument. None of this comes free from the association table.

## Mendelian randomisation, briefly

MR uses genetic variants as instruments to estimate the causal effect of a modifiable exposure —
here, protein level or activity — on an outcome. When the instrument is a *cis* variant at the
gene encoding the drug target, MR is close to a natural trial of that drug, and it can even
estimate effect size and surface unexpected on-target effects.

Its assumptions are strong: the variant must affect the outcome only through the exposure (no
horizontal pleiotropy), and it must be unconfounded by population structure. It is a specialist
analysis needing summary statistics rather than the association table, so this skill does not
implement it. `open-targets` surfaces some MR-derived evidence; the full analysis wants
`TwoSampleMR` or `MendelianRandomization` in R with GWAS summary statistics.

## Six honest limits

**1. Constraint is only informative for inhibition.** An agonist is not phenocopied by loss of
function, and constraint says nothing about it.

**2. Lifelong heterozygous loss is not a drug.** A drug is partial, reversible, adult-onset, and
often tissue-restricted. Constrained targets are drugged successfully all the time; the metric
raises the burden of proof, it does not veto.

**3. Late-onset effects are invisible.** Selection acts on reproductive fitness, so a gene whose
loss causes disease at seventy looks unconstrained. Absence of constraint is not a promise of
safety in an ageing population — which is most patients.

**4. Association is positional.** The gene named is the nearest one. Without fine-mapping or
colocalisation, "associated with gene X" means "associated with a locus near gene X".

**5. Ancestry coverage is skewed.** The catalogue is predominantly European. Absence of an
association can mean nobody has looked in the right population.

**6. Genetic support raises the odds; it does not remove risk.** Doubling a 10% probability still
leaves a majority of programmes failing. Phase II attrition has many causes — dose, exposure,
patient selection, endpoint choice — that no amount of genetics addresses.

## What to say when reporting

Give LOEUF with its band and the observed/expected counts that produced it, so the reader can see
how much data is behind it. Give the best p-value, the number of independent studies, and how
many associations map to the gene alone. Name the verdict as a heuristic and show both axes.

Say "loss of function is tolerated in humans", not "the target is safe". Say "this locus is
associated with", not "this gene causes". And state plainly when constraint is absent that it is
missing data, not a zero.

## Where to go next

- `open-targets` — aggregated evidence including L2G locus-to-gene scoring, which does some of
  the causal-gene work this API leaves undone.
- `depmap` — cellular essentiality, a different question from human constraint.
- `openfda` — for a target already drugged, what actually happened in people.
- gnomAD browser directly for variant-level detail, homozygous LoF counts, and per-population
  frequencies.
