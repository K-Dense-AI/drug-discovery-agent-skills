# Query cookbook

Every document here was executed against release 26.06 and returned data. Save one to a file and
run it with `python scripts/ot_query.py raw <file>.graphql --var name=value`, or paste it into
the [playground](https://api.platform.opentargets.org/api/v4/graphql/browser).

Substitute ids, not field names — the schema is stricter than it looks, and a field that does not
exist fails the whole document.

---

## 1. Resolve names to ids

```graphql
query Resolve($terms: [String!]!) {
  mapIds(queryTerms: $terms, entityNames: ["target", "disease", "drug"]) {
    mappings { term hits { id name entity score } }
  }
}
```

`{"terms": ["EGFR", "non-small cell lung carcinoma", "gefitinib"]}`. Hits are **not sorted by
score** — read the `name` field rather than taking `hits[0]`. Use `search` instead when the input
is fuzzy or partial.

---

## 2. Target dossier in one request

```graphql
query Dossier($id: String!) {
  target(ensemblId: $id) {
    approvedSymbol
    approvedName
    biotype
    proteinIds { id source }
    targetClass { label level }
    subcellularLocations { location source }
    tractability { modality label value }
    safetyLiabilities { event datasource effects { direction } }
    geneticConstraint { constraintType score upperRank }
    prioritisation { items { key value } }
    isEssential
    tep { name uri therapeuticArea }
    chemicalProbes { id isHighQuality probeMinerScore }
  }
}
```

One round trip replaces six. `scripts/ot_query.py target <id>` runs this and formats it.

---

## 3. Is this a selective dependency, and what is it linked to?

```graphql
query Dependency($id: String!) {
  target(ensemblId: $id) {
    approvedSymbol
    isEssential
    depMapEssentiality {
      tissueName
      screens { cellLineName depmapId geneEffect expression }
    }
    associatedDiseases(page: {index: 0, size: 10}) {
      count
      rows { score disease { id name } datatypeScores { id score } }
    }
  }
}
```

Chronos gene effect: ≤ −1 is a strong dependency, ≈ 0 is no effect. A target essential in
*every* tissue is a toxicity risk, not an opportunity — which is why the `geneEssentiality`
prioritisation metric scores it negative. Cross-check against the `depmap` skill when you need
the full cell-line matrix rather than the tissue roll-up.

---

## 4. Genetics-only view of a target's diseases

```graphql
query GeneticsOnly($id: String!, $ds: [DatasourceSettingsInput!]) {
  target(ensemblId: $id) {
    associatedDiseases(page: {index: 0, size: 25}, datasources: $ds) {
      count
      rows { score disease { id name } datasourceScores { id score } }
    }
  }
}
```

The `$ds` array must set `weight: 0.0` for every source you are *not* keeping, or the others keep
contributing at full weight. `scripts/ot_associations.py --only-datasources gwas_credible_sets
gene_burden eva` builds it correctly; see [datasources.md](datasources.md).

---

## 5. Best targets for a disease, filtered to tractable ones

```graphql
query DiseaseTargets($id: String!) {
  disease(efoId: $id) {
    name
    associatedTargets(page: {index: 0, size: 50}, orderByScore: "desc") {
      count
      rows {
        score
        target {
          id
          approvedSymbol
          biotype
          tractability { modality label value }
        }
      }
    }
  }
}
```

Filter client-side on `tractability` where `modality == "SM"` and `value == true`; there is no
server-side tractability filter.

---

## 6. Evidence behind one target–disease pair

```graphql
query Evidence($ensemblId: String!, $efoIds: [String!]!, $sources: [String!], $cursor: String) {
  target(ensemblId: $ensemblId) {
    evidences(efoIds: $efoIds, datasourceIds: $sources, size: 100, cursor: $cursor) {
      count
      cursor
      rows {
        datasourceId
        datatypeId
        score
        literature
        publicationYear
        variantRsId
        pValueMantissa
        pValueExponent
        clinicalSignificances
        drug { id name }
        clinicalStage
        studyId
        diseaseFromSource
      }
    }
  }
}
```

Cursor-paginated, not index-paginated: pass the returned `cursor` back until it is `null`.
`Disease.evidences(ensemblIds: [...])` is the mirror image and takes the same shape.

---

## 7. Drugs and clinical candidates against a target

```graphql
query Candidates($id: String!) {
  target(ensemblId: $id) {
    drugAndClinicalCandidates {
      count
      rows {
        maxClinicalStage
        drug {
          id
          name
          drugType
          mechanismsOfAction { rows { actionType mechanismOfAction targetName } }
        }
        diseases { diseaseFromSource disease { id name } }
        clinicalReports { id type title trialPhase trialOverallStatus url countries }
      }
    }
  }
}
```

`knownDrugs` no longer exists; this field replaced it. `clinicalReports` carries the trial
identifiers (`nct…`) if you need to follow up on ClinicalTrials.gov.

---

## 8. Drug record with mechanism, indications, and warnings

```graphql
query DrugRecord($id: String!) {
  drug(chemblId: $id) {
    name
    drugType
    maximumClinicalStage
    tradeNames { label source }
    mechanismsOfAction {
      uniqueActionTypes
      rows { actionType mechanismOfAction targets { id approvedSymbol } }
    }
    indications { count rows { maxClinicalStage disease { id name } } }
    drugWarnings { warningType toxicityClass description year country }
    adverseEvents(page: {index: 0, size: 25}) {
      count
      criticalValue
      rows { name count logLR meddraCode }
    }
  }
}
```

`adverseEvents` is FAERS disproportionality: `logLR` above `criticalValue` is the significance
test. These are reporting signals, not incidence rates, and are confounded by indication.

---

## 9. Protein–protein interactions

```graphql
query Interactions($id: String!) {
  target(ensemblId: $id) {
    interactions(scoreThreshold: 0.5, sourceDatabase: intact, page: {index: 0, size: 50}) {
      count
      rows {
        intB
        targetB { id approvedSymbol }
        score
        sourceDatabase
        evidences { interactionDetectionMethodShortName }
      }
    }
  }
}
```

`sourceDatabase` is an enum (`intact`, `signor`, `reactome`, `string`), not a string literal —
unquoted in the query, or passed as a `$db: InteractionSourceEnum` variable. STRING scores
include text-mining and are not comparable with IntAct's experimental scores.

---

## 10. Baseline expression (target safety by tissue)

```graphql
query Expression($id: String!) {
  target(ensemblId: $id) {
    baselineExpression(page: {index: 0, size: 100}) {
      count
      rows {
        datasourceId
        datatypeId
        median
        q1
        q3
        unit
        specificity_score
        distribution_score
        tissueBiosample { biosampleId biosampleName }
        celltypeBiosample { biosampleId biosampleName }
      }
    }
  }
}
```

Mixed sources (`gtex` bulk RNA-seq, single-cell datasets), so filter on `datasourceId` before
comparing values, and read `unit` rather than assuming TPM. High expression in heart, liver, or
brain is the standard first-pass safety flag.

---

## 11. GWAS credible sets touching a target

```graphql
query CredibleSets($id: String!) {
  target(ensemblId: $id) {
    credibleSets(page: {index: 0, size: 25}) {
      count
      rows {
        studyLocusId
        variant { id rsIds }
        study { id traitFromSource projectId }
        pValueMantissa
        pValueExponent
      }
    }
  }
}
```

Reconstruct the p-value as `mantissa × 10^exponent`; it is split in two fields to survive JSON.

---

## 12. Batch fetch, and faceted browse

```graphql
query Batch($ids: [String!]!) {
  targets(ensemblIds: $ids) { id approvedSymbol biotype }
}
```

Unknown ids come back as `null` **in position**, so zip against your input rather than assuming
alignment by index of the non-null entries.

```graphql
{
  facets(queryString: "kinase", entityNames: ["target"], page: {index: 0, size: 20}) {
    total
    hits { id label category entityIds datasourceId }
  }
}
```

`facets` is how you go from a class ("kinase", "GPCR") to the member target ids in `entityIds`.

---

## 13. Mouse knockouts and pharmacogenomics

```graphql
query Translational($id: String!) {
  target(ensemblId: $id) {
    mousePhenotypes {
      modelPhenotypeId
      modelPhenotypeLabel
      biologicalModels { allelicComposition geneticBackground }
    }
    pharmacogenomics {
      variantRsId
      genotypeId
      phenotypeText
      evidenceLevel
      pgxCategory
      drugs { drugId drugFromSource }
    }
  }
}
```

---

## 14. Gene Ontology annotation

```graphql
query GO($id: String!) {
  target(ensemblId: $id) {
    geneOntology { aspect evidence geneProduct source term { id label } }
  }
}
```

`term` has `id` and **`label`** — there is no `name` field on `GeneOntologyTerm`, which is the
kind of near-miss that fails the whole document. `aspect` is `F`/`P`/`C`.
