# gnomAD constraint metrics

Endpoint `https://gnomad.broadinstitute.org/api`, GraphQL over POST, no key. Values below were
read from the live API in August 2026 against gnomAD v4.1.

## What constraint measures

For every gene, gnomAD counts the loss-of-function variants **observed** in its population sample
and compares them against the number **expected** under a mutational model that accounts for
sequence context, coverage, and methylation. A gene with far fewer LoF variants than expected is
*constrained*: those variants existed and were removed by selection, because losing the protein
harms carriers.

That is the whole idea, and it is why this is the single most useful safety readout available
before a molecule exists. **A drug that inhibits a protein is a chemical phenocopy of a
loss-of-function variant.** If humans who carry such variants are healthy, systemic inhibition is
likely survivable. If they are not represented in the population at all, that is a warning.

## The metrics, and which to use

| Field | What it is |
|---|---|
| `oe_lof` | observed / expected LoF — the point estimate |
| `oe_lof_lower`, `oe_lof_upper` | its 90% confidence interval |
| **`oe_lof_upper`** | **LOEUF** — the upper bound, and the metric to use |
| `pLI` | probability the gene is LoF-intolerant, 0–1 |
| `lof_z` | z-score for LoF depletion |
| `oe_mis`, `oe_mis_upper`, `mis_z` | the same for missense |
| `syn_z` | synonymous z-score — a quality control, should be near 0 |

**Use LOEUF, not pLI.** gnomAD's own recommendation. pLI is a posterior probability that saturates
at 0 and 1, so it cannot rank two intolerant genes and it is unstable for short genes where there
is little power. LOEUF is continuous, carries its uncertainty in the value itself (it is an upper
bound), and orders genes sensibly across the whole range.

Using the *upper* bound rather than the point estimate is deliberate: it is conservative in the
direction that matters, because a gene with few expected LoF variants gets a wide interval and
should not be called tolerant on thin evidence.

## Bands used by this skill

| LOEUF | Band | What it implies for a target |
|---|---|---|
| < 0.35 | constrained | LoF depleted; systemic inhibition carries risk |
| 0.35–0.60 | moderately constrained | some depletion; check tissue and dose dependence |
| 0.60–1.00 | tolerant | LoF roughly as common as expected |
| ≥ 1.00 | unconstrained | well tolerated; human knockouts likely exist |

Bands are a convenience, not a standard. gnomAD's own guidance suggests LOEUF < 0.6 as a
conservative cut for "constrained"; the deciles are more informative than any threshold.

## Worked comparison, live

```
symbol  loeuf   band            pLI        obs_lof  exp_lof
SCN2A   0.154   constrained     1          20       188.7
KRAS    0.2264  constrained     0.9998     1        20.95
HTT     0.3379  constrained     1          104      362.3
LRRK2   0.7537  tolerant        1.317e-43  203      302.6
PCSK9   1.144   unconstrained   2.765e-18  57       62.12
```

Read the `obs_lof` / `exp_lof` columns — they are the whole argument. KRAS: one observed LoF
variant where 21 were expected. PCSK9: 57 observed against 62 expected, essentially no depletion.

**PCSK9 is the canonical case.** Human PCSK9 loss-of-function carriers are healthy and have low
LDL cholesterol; that observation drove the development of evolocumab and alirocumab. The
constraint data says exactly what the clinical outcome later confirmed.

**LRRK2 is the second canonical case.** LOEUF 0.75 and pLI effectively zero, with 203 observed LoF
variants — healthy human LRRK2 knockouts exist in numbers. That is the published safety argument
for LRRK2 inhibition in Parkinson's disease.

## Five ways to misread this

**1. Absent is not zero.** A gene with no `gnomad_constraint` block has too little coverage to
model. Reporting that as LOEUF 0 inverts the conclusion completely. The scripts return `unknown`.

**2. Constraint is about germline heterozygous loss, lifelong.** A drug is partial, reversible,
adult-onset, and often tissue-restricted. Constrained genes are drugged successfully all the time
— the metric raises the burden of proof, it does not veto.

**3. It says nothing about gain of function.** An agonist is not phenocopied by a LoF variant.
Constraint is only informative for inhibition, degradation, and knockdown.

**4. Essentiality is a different question.** DepMap measures whether a cancer cell line dies
without the gene in culture. Constraint measures whether a human survives to reproduce with one
broken copy. A gene can be pan-essential in cells and unconstrained in people, and vice versa.
Use `depmap` for the first and this for the second.

**5. Selection acts on reproductive fitness.** A gene whose loss causes late-onset disease is
invisible to constraint, because carriers reproduce before it matters. Absence of constraint is
not a promise of safety in an ageing population.

## Query shape

```graphql
{
  gene(gene_symbol: "LRRK2", reference_genome: GRCh38) {
    gene_id symbol
    gnomad_constraint { oe_lof oe_lof_upper pLI obs_lof exp_lof mis_z }
  }
}
```

**gnomAD returns errors with HTTP 200.** A misspelled field or an unknown gene arrives as
`{"errors": [{"message": "..."}]}` in a successful response. `gnomad_post()` raises on that array;
checking only the status code silently yields "no constraint data".

Gene symbols are matched exactly against current HGNC symbols. Aliases and withdrawn symbols are
not resolved — resolve them with `uniprot-rcsb` or `open-targets` first.
