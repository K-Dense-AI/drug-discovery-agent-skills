---
name: target-safety
description: Assemble the human genetic evidence for and against a target before a programme commits to it — the evidence class that most improves the odds of surviving clinical development. Use this skill to pull gnomAD constraint metrics (LOEUF, pLI, observed/expected) that show whether loss of function is tolerated in people, retrieve GWAS Catalog associations and fine-mapped credible sets for a gene, and read a natural human knockout as a safety readout. Also trigger on gnomAD, LOEUF, pLI, loss-of-function intolerance, mutational constraint, GWAS Catalog, credible set, human knockout, genetic support, or target safety dossier.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+ and outbound HTTPS access to gnomad.broadinstitute.org and www.ebi.ac.uk. The bundled clients use only the Python standard library and need no API key. gnomAD is queried through its public GraphQL endpoint; the GWAS Catalog v2 REST service can be slow, so timeouts are generous.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🧬"
    homepage: https://gnomad.broadinstitute.org
  hermes:
    category: research
---

# Target Safety Assessment

Two public datasets answer the question that comes before every programme: *what happens to
people who naturally have less of this protein?* gnomAD says whether such people exist. The GWAS
Catalog says what else changes when they do. Targets with human genetic support are roughly twice
as likely to survive clinical development, and this is the only evidence class available before a
molecule does.

**Services:** `https://gnomad.broadinstitute.org/api` (GraphQL, POST) ·
`https://www.ebi.ac.uk/gwas/rest/api/v2` (REST). Both unauthenticated.
**Checked against:** gnomAD v4.1 and the live GWAS Catalog v2 API, August 2026.

Read [references/gnomad-constraint.md](references/gnomad-constraint.md) before quoting a
constraint number, [references/gwas-catalog.md](references/gwas-catalog.md) before writing a query
by hand, and
[references/interpreting-genetic-evidence.md](references/interpreting-genetic-evidence.md) before
drawing a conclusion — **that one is judgement, not syntax.**

## The three scripts

| Script | Answers |
|---|---|
| `gnomad_constraint.py` | Do healthy humans exist who have lost this protein? |
| `gwas_evidence.py` | What traits is this gene associated with, and how solidly? |
| `safety_dossier.py` | Both at once, as a verdict with its inputs beside it |

## A drug is a chemical phenocopy of a loss-of-function variant

That equivalence is the whole idea. If people carrying LoF variants in a gene are healthy and
common, inhibiting the protein is likely survivable. If those variants have been removed from the
population by selection, that is a warning you can read years before a tox study.

```bash
python skills/target-safety/scripts/gnomad_constraint.py compare LRRK2 PCSK9 SCN2A KRAS HTT
```

```
symbol  loeuf   band            pLI        obs_lof  exp_lof
SCN2A   0.154   constrained     1          20       188.7
KRAS    0.2264  constrained     0.9998     1        20.95
HTT     0.3379  constrained     1          104      362.3
LRRK2   0.7537  tolerant        1.317e-43  203      302.6
PCSK9   1.144   unconstrained   2.765e-18  57       62.12
```

`obs_lof` against `exp_lof` is the whole argument. KRAS: one observed loss-of-function variant
where twenty-one were expected. PCSK9: fifty-seven observed against sixty-two expected — no
depletion at all. **Human PCSK9 knockouts are healthy and have low LDL cholesterol**, which is
exactly why evolocumab and alirocumab exist. The constraint table said so before the drugs did.

**Use LOEUF, not pLI.** pLI is a posterior forced toward 0 or 1 and cannot rank two intolerant
genes; LOEUF is continuous and carries its uncertainty in the value. Note how pLI calls both
SCN2A and HTT exactly `1` while LOEUF separates them by a factor of two.

## An unrecognised GWAS filter returns the entire catalogue

This is the trap to get right on the association side:

```
GET /associations?mappedGene=LRRK2   ->  93 associations
GET /associations?gene=LRRK2         ->  1142122 associations
```

Both are HTTP 200. `gene` is not a parameter, so it was silently dropped and the response is the
whole catalogue. Nothing says the filter was ignored. `gwas_get()` validates parameter names
locally and refuses anything unknown, because there is no server-side signal to react to.

## Association is positional, not causal

```bash
python skills/target-safety/scripts/gwas_evidence.py traits LRRK2
```

```
trait                     best_p    associations  studies  sole_mapping
bone density              1e-300    1             1        0
Parkinson disease         4e-148    23            18       18
cathepsin L1 measurement  4e-39     2             2        0
```

The strongest p-value in that table is not the answer. Bone density at 1e-300 has **zero**
associations mapping to LRRK2 alone — the causal gene at that locus is almost certainly a
neighbour. Parkinson disease has eighteen sole-mapping associations across eighteen studies.
Ranking by p-value alone picks the wrong one.

Never rank by association count either: the same locus is rediscovered by every new cohort, so a
count measures genotyping effort.

## The combined readout

```bash
python skills/target-safety/scripts/safety_dossier.py gene PCSK9 LRRK2 HTT
```

```
symbol  loeuf   band           genome_wide_traits  sole_mapped_hits  verdict
PCSK9   1.144   unconstrained  44                  115               genetically supported
LRRK2   0.7537  tolerant       37                  39                genetically supported
HTT     0.3379  constrained    59                  92                associated but constrained
```

The two axes are independent and mean opposite things. Tolerant plus associated is the pattern
that most improves the odds. Constrained plus associated — HTT — means the biology is real but
systemic inhibition should expect mechanism-based toxicity, which is precisely the live debate
about lowering wild-type huntingtin.

## Four ways this evidence misleads

1. **Absent constraint is missing data, not zero.** A gene with too little coverage has no
   estimate. Reporting that as LOEUF 0 inverts the conclusion. The scripts return `unknown`.
2. **Constraint only speaks to inhibition.** An agonist is not phenocopied by loss of function.
3. **Late-onset effects are invisible.** Selection acts on reproductive fitness, so a gene whose
   loss causes disease at seventy looks unconstrained — in a population that is mostly patients.
4. **Association gives no direction.** Whether to inhibit or activate needs an allelic series or
   Mendelian randomisation, not the association table.

## When to stop using these APIs

Direction of effect, effect size, and causal-gene resolution all need summary statistics rather
than the association table — fine-mapping, colocalisation, and MR with `TwoSampleMR`. For
variant-level detail, homozygous LoF counts, and per-population frequencies, use the gnomAD
browser directly.

## Composing with the rest of the bundle

- `open-targets` → alongside: aggregated evidence plus L2G scoring, which resolves some of the
  causal-gene ambiguity this API leaves open.
- `depmap` → alongside: cellular essentiality is a different question from human constraint — a
  gene can be pan-essential in culture and unconstrained in people.
- `uniprot-rcsb` → before: resolve an alias to a current HGNC symbol; neither API resolves them.
- `openfda` → after: for a target already drugged, what actually happened in people.
- `clinicaltrials` → alongside: whether anyone has taken the genetic hypothesis into a trial.

## Reporting results honestly

Give LOEUF with its band and the observed/expected counts behind it. Give the best p-value, the
number of independent studies, and how many associations map to the gene alone. Call the verdict
a heuristic and show both axes. Say "loss of function is tolerated in humans", not "the target is
safe"; say "this locus is associated with", not "this gene causes". Genetic support roughly
doubles the odds of approval — from low to less low.
