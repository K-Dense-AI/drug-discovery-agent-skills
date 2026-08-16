# Open Targets Platform GraphQL — schema map

Endpoint: `https://api.platform.opentargets.org/api/v4/graphql` (POST, JSON body
`{"query": ..., "variables": ...}`). No key, no account, no per-key quota. There is a
GraphQL playground at <https://api.platform.opentargets.org/api/v4/graphql/browser>.

Checked against **API 26.6.3 / data release 26.06**. Confirm the release you are talking to
before quoting numbers, because scores are recomputed every release:

```graphql
{ meta { name apiVersion { x y z } dataVersion { year month iteration } } }
```

## Root fields

| Field | Argument | Returns |
|---|---|---|
| `target` | `ensemblId: String` | `Target` |
| `targets` | `ensemblIds: [String!]` | `[Target]` |
| `disease` | `efoId: String` | `Disease` |
| `diseases` | `efoIds: [String!]` | `[Disease]` |
| `drug` | `chemblId: String` | `Drug` |
| `drugs` | `chemblIds: [String!]` | `[Drug]` |
| `search` | `queryString`, `entityNames`, `page` | `SearchResults` (fuzzy) |
| `mapIds` | `queryTerms: [String!]`, `entityNames` | `MappingResults` (exact-ish) |
| `facets` | `queryString`, `entityNames`, `category`, `page` | `SearchFacetsResults` |
| `variant` | `variantId: String` | `Variant` |
| `study` / `studies` | `studyId`, `diseaseIds`, `page` | GWAS/QTL studies |
| `credibleSet` / `credibleSets` | `studyLocusId`, `variantIds`, … | fine-mapped loci |
| `clinicalReport` / `clinicalReports` | `clinicalReportId(s)` | trial-level records |
| `geneOntologyTerms` | `goIds: [String!]` | `GeneOntologyTerm` |
| `associationDatasources` | — | returns `[]` in 26.06; use the list in [datasources.md](datasources.md) |

`targets`/`diseases`/`drugs` take a list and are the right way to fetch many records — one
request instead of N, and unknown ids come back as `null` in place rather than erroring.

## Identifier rules

| Entity | Id form | Example |
|---|---|---|
| Target | Ensembl **gene** id | `ENSG00000146648` |
| Disease | MONDO id, mostly (see below) | `MONDO_0005233` |
| Drug | ChEMBL molecule id | `CHEMBL939` |

Targets are Ensembl gene ids only — not symbols, not UniProt accessions, not transcript ids.
Go the other way with `target { proteinIds { id source } }`, where `source` is
`uniprot_swissprot`, `uniprot_trembl`, `uniprot_obsolete`, or `ensembl_PRO`.

**The disease-id trap.** The argument is still named `efoId`, but the ontology is MONDO-first.
Most `EFO_*` ids that older tutorials use were superseded and now return `null` — silently, with
no error:

```graphql
{ disease(efoId: "EFO_0000305") { id name } }   # -> {"disease": null}
{ disease(efoId: "MONDO_0004989") { id name } } # -> breast carcinoma
```

Some nodes legitimately keep a non-MONDO id (`EFO_1000016`, `HP_0002014`, `OTAR_0000017`), so
you cannot just rewrite the prefix. Always resolve names through `mapIds`/`search` and use what
comes back.

## Target

Selected fields, grouped by what you would ask for them.

**Identity** — `id`, `approvedSymbol`, `approvedName`, `biotype`, `synonyms {label source}`,
`nameSynonyms`, `symbolSynonyms`, `obsoleteSymbols`, `proteinIds {id source}`, `dbXrefs`,
`genomicLocation {chromosome start end strand}`, `transcriptIds`, `canonicalTranscript`.

**Biology** — `functionDescriptions`, `subcellularLocations {location labelSL termSL source}`,
`targetClass {id label level}`, `pathways {pathwayId pathway topLevelTerm}`, `geneOntology`,
`hallmarks`, `homologues {speciesName targetGeneSymbol queryPercentageIdentity homologyType}`,
`mousePhenotypes`, `baselineExpression(page:)`.

**Druggability** — `tractability {label modality value}`, `chemicalProbes {id drugId
isHighQuality probeMinerScore probesDrugsScore mechanismOfAction origin control}`,
`tep {name uri therapeuticArea description}`.

**Risk** — `safetyLiabilities {event eventId datasource literature effects{direction dosing}
biosamples{tissueLabel cellLabel} studies}`, `geneticConstraint {constraintType score exp obs
oe oeLower oeUpper upperRank}`, `pharmacogenomics`.

**Prioritisation** — `prioritisation { items { key value } }`. An untyped key/value list; the
values are strings holding a number in `[-1, 1]`. Keys are listed in [datasources.md](datasources.md).

**Essentiality** — `isEssential`, `depMapEssentiality {tissueId tissueName screens
{cellLineName depmapId geneEffect expression mutation diseaseFromSource}}`. Gene effect is the
DepMap Chronos score: more negative is more essential, roughly ≤ −0.5 is a dependency. This is
the same underlying data the `depmap` skill loads locally, pre-joined to the target.

**Clinical** — `drugAndClinicalCandidates { count rows { id maxClinicalStage drug {…}
diseases { diseaseFromSource disease {id name} } clinicalReports {…} } }`.
This replaced the old `knownDrugs` field; a query written against `knownDrugs` fails outright.

**Connections** — `associatedDiseases(...)`, `evidences(...)`, `interactions(scoreThreshold:,
sourceDatabase:, page:)`, `similarEntities(...)`, `literatureOcurrences(...)`,
`credibleSets(page:)`, `proteinCodingCoordinates(page:)`, `associationTimeSeries(...)`.

## Disease

`id`, `name`, `description`, `synonyms {relation terms}`, `dbXRefs`, `therapeuticAreas {id name}`,
`parents`, `children`, `ancestors`, `descendants`, `resolvedAncestors`, `isTherapeuticArea`,
`phenotypes(page:) {count rows {phenotypeHPO {id name} phenotypeEFO {id name} evidence}}`,
`associatedTargets(...)`, `evidences(...)`, `drugAndClinicalCandidates`, `otarProjects`.

## Drug

`id`, `name`, `drugType`, `description`, `maximumClinicalStage`, `tradeNames {label source}`,
`synonyms {label source}`, `crossReferences`, `molblock`, `parentMolecule`, `childMolecules`,
`mechanismsOfAction {uniqueActionTypes uniqueTargetTypes rows {actionType mechanismOfAction
targetName targets {id approvedSymbol} references}}`,
`indications {count rows {maxClinicalStage disease {id name} clinicalReports}}`,
`drugWarnings {warningType description toxicityClass country year efoTerm references}`,
`adverseEvents(page:)`, `pharmacogenomics`.

There is **no `isApproved` field**. Approval is `maximumClinicalStage == "APPROVAL"`. The stage
vocabulary is words, not numbers: `APPROVAL`, `PHASE_3`, `PHASE_2`, `PHASE_1_2`, `PHASE_1`,
`PRECLINICAL`.

## Associations

```graphql
target(ensemblId: $id) {
  associatedDiseases(
    page: {index: 0, size: 50}
    datasources: [{id: "eva", weight: 1.0, propagate: true, required: true}]
    enableIndirect: false
    BFilter: "carcinoma"        # substring filter on the other entity's name
    orderByScore: "desc"
    facetFilters: []
    Bs: ["MONDO_0005233"]       # restrict to these specific partner ids
  ) {
    count
    rows { score disease {id name} datatypeScores {id score} datasourceScores {id score} }
  }
}
```

`Disease.associatedTargets` mirrors it exactly. The odd argument names (`Bs`, `BFilter`) are the
schema's own — "B" is the far side of the association.

- `score` is a harmonic-sum aggregate in `[0, 1]`. Not a probability, not calibrated across
  releases, and only comparable within one result set.
- `datatypeScores` / `datasourceScores` are the **unweighted** per-source scores. They do not
  change when you pass `datasources` settings — only the aggregate `score` and the row set do.
- `enableIndirect: true` propagates evidence up the disease ontology, so a query for "lung
  carcinoma" also counts evidence attached to its descendants. Counts jump substantially; say
  which mode you used when reporting numbers.

## Two different pagination models

**Index pagination** (`associatedDiseases`, `associatedTargets`, `indications`, `phenotypes`,
`adverseEvents`, …) takes `page: {index: Int, size: Int}` where `index` counts pages, not rows.
`size` is capped at 500. Past the end you get an empty `rows` array, not an error. `count` is the
total, so `index * size >= count` is the stop condition. `scripts/_common.py:paged` implements it.

**Cursor pagination** (`evidences`) takes `size` and `cursor`, and returns the next `cursor`
alongside `rows`. A `null` cursor means the last page. Cursors are opaque and expire; do not
store one.

## Error behaviour

GraphQL returns **HTTP 200 with an `errors` array** for a bad field, a bad argument type, or a
missing sub-selection. A client that only checks the status code reports success on a typo, so
check `errors` explicitly — `scripts/_common.py:post` raises on any `errors` entry, including
the partial case where `data` is present too. Requesting an object-typed field without a
sub-selection is the most common failure and it names the exact line and column.

Transport: `429`, `502`, `503`, `504` happen under load and are worth retrying with backoff;
everything else is a client bug. There is no documented published rate limit, but the API is a
shared public resource — batch with the plural root fields rather than firing N requests.
