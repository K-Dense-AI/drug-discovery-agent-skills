---
name: open-targets
description: Query the Open Targets Platform GraphQL API for target-disease associations, genetic and clinical evidence, tractability and safety liabilities, target prioritisation metrics, known drugs and mechanisms of action, and disease ontology. Use this skill for target identification and validation, target-disease evidence review, druggability assessment, drug repurposing, and resolving gene, disease, and drug names to Ensembl, MONDO, and ChEMBL identifiers. Also trigger when a query mentions Open Targets, platform.opentargets.org, association scores, tractability buckets, or api.platform.opentargets.org.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+ and outbound HTTPS access to api.platform.opentargets.org. The bundled client uses only the Python standard library and needs no API key or account. Data is CC0; the API is a shared public resource, so batch requests rather than looping.
metadata:
  version: "1.1"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🎯"
    homepage: https://platform.opentargets.org
  hermes:
    category: research
---

# Open Targets Platform

Open Targets aggregates genetic, somatic, clinical, pathway, expression, animal-model, and
literature evidence into scored target–disease associations, and attaches druggability and safety
annotation to every target. It answers the question that comes before any modelling work: *is
this target worth working on for this disease, and what is already known about it?*

**Endpoint:** `https://api.platform.opentargets.org/api/v4/graphql` — POST, JSON, no key.
**Docs:** [platform-docs.opentargets.org](https://platform-docs.opentargets.org) ·
[playground](https://api.platform.opentargets.org/api/v4/graphql/browser)
**Checked against:** the live API, August 2026 — `meta` reports API 26.6.3, data release 26.06.

Read [references/graphql-schema.md](references/graphql-schema.md) before writing a query by hand,
[references/datasources.md](references/datasources.md) before interpreting or filtering a score,
and [references/query-cookbook.md](references/query-cookbook.md) for tested documents to adapt.

## Start here: three identifier rules

Everything else fails downstream of getting these wrong.

1. **Targets are Ensembl gene ids** (`ENSG00000146648`) — never symbols, UniProt accessions, or
   transcript ids.
2. **Diseases are MONDO ids** (`MONDO_0005233`) in almost all cases, even though the argument is
   still named `efoId`. Most `EFO_*` ids from older tutorials now return `null` **silently**.
   A few nodes legitimately keep `EFO_`, `HP_`, or `OTAR_` ids, so you cannot rewrite the prefix —
   resolve the name and use what comes back.
3. **Drugs are ChEMBL molecule ids** (`CHEMBL939`).

Always resolve first:

```bash
python skills/open-targets/scripts/ot_query.py resolve EGFR "non-small cell lung carcinoma" gefitinib
```

```
term                             id                name                           entity  score
EGFR                             ENSG00000146648   EGFR                           target  1
non-small cell lung carcinoma    MONDO_0005233     non-small cell lung carcinoma  disease 1
gefitinib                        CHEMBL2087361     ICOTINIB                       drug    1
gefitinib                        CHEMBL553         ERLOTINIB                      drug    1
gefitinib                        CHEMBL939         GEFITINIB                      drug    1
```

`resolve` uses `mapIds` (exact-ish); use `search` when the input is partial or misspelled. Hits
come back **unsorted by score**, so read the names rather than taking the first row. Note the drug
rows above: one term returned three molecules, all scored 1, with the one actually asked for last.
Taking `[0]` here silently hands the rest of the analysis a different drug.

## Workflow

1. Resolve every name to a canonical id and report what matched.
2. Pull the target dossier — tractability, safety, prioritisation, essentiality — before looking
   at associations. A target that is untractable or pan-essential ends the conversation early.
3. Pull associations, and immediately ask *which datatype carries the score*. An association
   driven only by `literature` is a very different claim from one driven by `genetic_association`.
4. Drop to individual evidence records for anything you intend to act on.
5. State the release (`26.06`) and whether `enableIndirect` was on with any number you report.

## Target dossier

```bash
python skills/open-targets/scripts/ot_query.py target ENSG00000146648            # everything
python skills/open-targets/scripts/ot_query.py target ENSG00000146648 --section tractability
```

Sections: `core`, `tractability`, `safety`, `prioritisation`, `essentiality`, `probes`,
`pathways`, `all`. Add `--format json` for the raw records.

```
## TRACTABILITY
modality  label                  value
SM        Approved Drug          true
SM        Structure with Ligand  true
SM        High-Quality Pocket    true
AB        UniProt loc high conf  true
```

Reading these:

- **Tractability is a ladder**, not a score. `High-Quality Pocket` without `Structure with Ligand`
  means a pocket was *predicted*. `AB` buckets mostly assert the target is cell-surface or
  secreted — reachable, not that a useful antibody exists.
- **Prioritisation values run −1 to +1**, where +1 favours the target. `hasSafetyEvent` and
  `geneEssentiality` are already signed so that bad news is negative; do not re-negate them.
- **DepMap gene effect** is Chronos: ≤ −1 is a strong dependency, ≈ 0 is nothing. Essential
  everywhere is a toxicity flag. The `depmap` skill has the full cell-line matrix.
- **Safety liabilities** carry a direction. An event reported for *inhibition* does not apply to
  an agonist programme.

## Associations

```bash
# diseases for a target, with the per-datatype breakdown
python skills/open-targets/scripts/ot_associations.py target-diseases ENSG00000146648 --limit 25

# targets for a disease, tractability-annotated
python skills/open-targets/scripts/ot_associations.py disease-targets MONDO_0004979 \
    --limit 100 --min-score 0.4

# what does the human genetics alone say?
python skills/open-targets/scripts/ot_associations.py target-diseases ENSG00000146648 \
    --only-datasources gwas_credible_sets gene_burden eva --limit 25
```

Paging, the datatype flattening, and the datasource-weighting arithmetic are handled for you.
`--indirect` propagates evidence from ontology descendants and inflates counts substantially.

**What the score is:** a harmonic-sum aggregate in `[0, 1]`. Not a probability, not calibrated
across releases, only comparable within one result set. It is evidence-weighted rather than
literature-normalised, so well-studied targets score high partly because they are well studied.
A zero means "no evidence indexed here", never "evidence of no association".

**Restricting to some datasources is a weighting operation, not a filter.** Passing a settings
array resets the Platform's default weights, so keeping three sources means explicitly zeroing
all the others — get that wrong by hand and scores go *up* while looking restricted. Two ids were
renamed and silently match nothing under their old names: `chembl` → `clinical_precedence`,
`ot_genetics_portal` → `gwas_credible_sets`. Likewise the datatype `known_drug` → `clinical`.

## Evidence records

```bash
python skills/open-targets/scripts/ot_associations.py evidence ENSG00000146648 MONDO_0005233 \
    --datasources clinical_precedence --limit 50
```

```
datasourceId         datatypeId  score  drug         clinicalStage  literature
clinical_precedence  clinical    1      OSIMERTINIB  PHASE_4        35343187
eva                  genetic_association  0.92                      rs121913465
```

`evidences` is **cursor-paginated**, unlike everything else in the schema — the script follows the
cursor for you. Each row keeps its source's own fields, so a ClinVar row has `variantRsId` and
`clinicalSignificances` while a drug row has `drug` and `clinicalStage`.

## Disease and drug records

```bash
python skills/open-targets/scripts/ot_query.py disease MONDO_0005233
python skills/open-targets/scripts/ot_query.py drug CHEMBL939 --section mechanisms
```

Disease output includes parents, children, and phenotypes — useful for deciding whether to query
a specific subtype or its parent. Drug output covers mechanism of action with resolved target
ids, indications by phase, and black-box warnings.

There is no `isApproved` field: approval is `maximumClinicalStage == "APPROVAL"`. The stage
vocabulary is words (`APPROVAL`, `PHASE_3`, `PHASE_1_2`, `PRECLINICAL`), so map to ChEMBL's
numeric `max_phase` deliberately rather than string-matching.

## Arbitrary queries

For anything the subcommands do not cover, write the GraphQL document and run it:

```bash
python skills/open-targets/scripts/ot_query.py raw dossier.graphql --var id=ENSG00000146648
```

Two failure modes to expect. GraphQL answers **HTTP 200 with an `errors` array** for a bad field
or a missing sub-selection, so a client that only checks the status code reports success on a
typo — the bundled client raises instead. And the plural root fields (`targets`, `diseases`,
`drugs`) exist so you can batch: one request for 200 ids rather than 200 requests.

## Composing with the rest of the bundle

- `depmap` — full DepMap cell-line dependency matrix behind the `depMapEssentiality` roll-up.
- `chembl` — measured bioactivity for the compounds Open Targets names as known drugs.
- `uniprot-rcsb` — turn `proteinIds` into sequences and structures for modelling.
- `primekg` / `ncats-arax` — mechanistic paths and provenance for an association worth chasing.
- `target-safety` — gnomAD constraint, which this API does not carry: whether healthy humans
  who have lost the protein actually exist.
- `clinicaltrials` — whether anyone has taken the genetic hypothesis into a trial.

## Scope and honesty

Open Targets is an evidence aggregator, not an oracle. It reflects what has been published and
indexed, so it under-represents novel biology and over-represents fashionable targets. Report
scores with their release and their datatype breakdown, never as a probability of success, and
verify anything decision-relevant against the primary source the evidence record names.
