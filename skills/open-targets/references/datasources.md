# Vocabularies and scoring — data release 26.06

Every id below was read back from the live API for release 26.06. Names change between releases;
`meta { dataVersion { year month } }` tells you which release you are on.

## How an association score is built

1. Each **evidence record** gets a source-specific score in `[0, 1]` — a rescaled p-value for a
   GWAS, a clinical phase for a drug, a text-mining confidence for a publication.
2. Records from one datasource are collapsed into a **datasource score** with a harmonic sum
   (`Σ sᵢ/i²` over records sorted descending, normalised). Many weak records never add up to one
   strong one; this is deliberate.
3. Datasource scores are rolled up into **datatype scores**, then into the overall association
   `score`, weighted per datasource.

Consequences worth stating whenever you report a number:

- The score is **not a probability** and not calibrated across releases. Compare within one
  result set, never against a number from a paper or an older release.
- It is **evidence-weighted, not literature-normalised**. Well-studied targets score high partly
  because they are well studied; `europepmc` alone can carry an association.
- A **zero is "no evidence indexed here"**, never "evidence of no association".
- `enableIndirect: true` propagates evidence from ontology descendants and inflates counts —
  always say which mode produced the table.

## Datatype ids

| Datatype | Meaning |
|---|---|
| `genetic_association` | Germline genetics: GWAS, rare-disease variants, gene burden |
| `genetic_literature` | Genetic findings from text mining (split out of `literature`) |
| `somatic_mutation` | Cancer somatic drivers and biomarkers |
| `clinical` | Drugs in trials or approved for the disease |
| `affected_pathway` | Pathway-level and perturbation evidence |
| `literature` | Co-occurrence text mining |
| `rna_expression` | Differential expression |
| `animal_model` | Model-organism phenotypes |

**Renamed since most tutorials were written:** `known_drug` → `clinical`, and `genetic_literature`
was split out of `literature`. A filter on `known_drug` silently matches nothing.

## Datasource ids

| Datasource | Datatype | What it is |
|---|---|---|
| `gwas_credible_sets` | genetic_association | Fine-mapped GWAS loci (**replaces `ot_genetics_portal`**) |
| `gene_burden` | genetic_association | Rare-variant burden tests |
| `eva` | genetic_association | ClinVar germline |
| `genomics_england` | genetic_association | PanelApp gene panels |
| `gene2phenotype` | genetic_association | Curated developmental-disorder panels |
| `orphanet` | genetic_association | Rare-disease gene curation |
| `clingen` | genetic_association | ClinGen gene–disease validity |
| `uniprot_variants` / `uniprot_literature` | genetic_association | UniProt curation |
| `eva_somatic` | somatic_mutation | ClinVar somatic |
| `cancer_gene_census` | somatic_mutation | COSMIC census |
| `intogen` | somatic_mutation | Cancer driver calls |
| `cancer_biomarkers` | affected_pathway | Genomic biomarkers of drug response |
| `clinical_precedence` | clinical | Drugs from ChEMBL/trials (**replaces `chembl`**) |
| `reactome` | affected_pathway | Pathway-level curation |
| `crispr` / `crispr_screen` | affected_pathway | Functional-genomics screens |
| `progeny` / `slapenrich` / `sysbio` | affected_pathway | Pathway inference (legacy) |
| `impc` | animal_model | Mouse knockouts |
| `expression_atlas` | rna_expression | Differential expression |
| `europepmc` | literature | Text mining |

Two renames are the usual cause of an empty result from an otherwise correct query:
**`chembl` → `clinical_precedence`** and **`ot_genetics_portal` → `gwas_credible_sets`**. The root
`associationDatasources` field returns `[]` in 26.06, so this table — not the API — is the
enumeration to trust.

## Restricting a score to some datasources

`DatasourceSettingsInput` is `{id, weight, propagate, required}`, and the two knobs do different
things:

- **`required: true`** filters the rows to associations carrying at least one required source. It
  is an OR across the sources you mark, it trims the zero-scoring tail, and it does not change
  the ranking of what remains.
- **`weight`** scales that source's contribution to the aggregate score. Sending any settings
  array resets the Platform's default weights, so "genetics only" means weight `1.0` for the
  sources you want *and weight `0.0` for every other source*, listed explicitly.

Observed on EGFR (`ENSG00000146648`), release 26.06:

| Query | `count` | Top disease | Score |
|---|---|---|---|
| unrestricted | 6459 | non-small cell lung carcinoma | 0.853 |
| `europepmc` only | 2257 | non-small cell lung carcinoma | 0.608 |
| `clinical_precedence` only | 242 | non-small cell lung carcinoma | 0.606 |
| `gwas_credible_sets` + `gene_burden` + `eva` | 57 | EGFR-related lung cancer | 0.568 |

`scripts/ot_associations.py --only-datasources` builds these settings correctly. Doing it by
hand and forgetting the zero weights leaves every other source contributing at weight 1.0, which
*raises* scores instead of restricting them — the failure looks like success.

## Tractability buckets

`tractability { label modality value }`, where `value` is a boolean. Modalities:

| Modality | Meaning |
|---|---|
| `SM` | Small molecule |
| `AB` | Antibody |
| `PR` | PROTAC / degrader |
| `OC` | Other clinical modality |

Labels, by modality:

- **SM** — `Approved Drug`, `Advanced Clinical`, `Phase 1 Clinical`, `Structure with Ligand`,
  `High-Quality Ligand`, `High-Quality Pocket`, `Med-Quality Pocket`, `Druggable Family`
- **AB** — `Approved Drug`, `Advanced Clinical`, `Phase 1 Clinical`, `UniProt loc high conf`,
  `UniProt loc med conf`, `GO CC high conf`, `GO CC med conf`, `UniProt SigP or TMHMM`,
  `Human Protein Atlas loc`
- **PR** — `Approved Drug`, `Advanced Clinical`, `Phase 1 Clinical`, `Literature`,
  `UniProt Ubiquitination`, `Database Ubiquitination`, `Half-life Data`, `Small Molecule Binder`
- **OC** — `Approved Drug`, `Advanced Clinical`, `Phase 1 Clinical`

The buckets are a ladder: clinical precedence at the top, then structural/ligand evidence, then
family- or location-based inference. `SM: High-Quality Pocket` without `Structure with Ligand`
means a pocket was predicted, not that anything has been shown to bind it. Antibody tractability
is essentially a cell-surface/secreted call — it says the target is *reachable*, not that a
useful antibody exists.

## Prioritisation metrics

`prioritisation { items { key value } }` — values are strings holding a float in `[-1, 1]`, where
**+1 favours the target and −1 counts against it**. The keys present vary by target:

| Key | +1 means |
|---|---|
| `maxClinicalStage` | Clinically precedented modality exists |
| `hasLigand`, `hasPocket`, `hasSmallMoleculeBinder` | Chemically tractable |
| `hasHighQualityChemicalProbes` | A usable tool compound exists |
| `hasSafetyEvent` | **−1** when a known safety liability exists |
| `geneticConstraint` | Tolerant to LoF (constrained genes score negative) |
| `geneEssentiality` | **−1** when pan-essential — a toxicity flag, not a good sign |
| `isCancerDriverGene` | Context-dependent; −1 outside oncology |
| `isInMembrane`, `isSecreted` | Accessible to biologics |
| `mouseKOScore` | Informative knockout phenotype |
| `mouseOrthologMaxIdentityPercentage` | Mouse model likely to translate |
| `paralogMaxIdentityPercentage` | **−1** when close paralogs threaten selectivity |
| `tissueSpecificity`, `tissueDistribution` | Restricted expression |
| `celltypeSpecificity`, `celltypeDistribution` | Restricted cell-type expression |

Two of these read backwards if you skim: high `geneEssentiality` and high `hasSafetyEvent` are
*bad* for a target, and the sign already encodes that. Do not re-negate them.

## Clinical stage vocabulary

`APPROVAL`, `PHASE_3`, `PHASE_2`, `PHASE_1_2`, `PHASE_1`, `PRECLINICAL` — words, not the numeric
`max_phase` that ChEMBL uses. When joining Open Targets to ChEMBL, map `APPROVAL` ↔ `max_phase 4`
rather than string-matching.

## Safety liabilities

`safetyLiabilities` mixes curated literature reviews (`Brennan et al. (2024)`), pharmacovigilance
(`ClinPGx`), and experimental panels. `eventId` may be MONDO, EFO, or HP — do not assume one
ontology. `effects.direction` says whether **inhibiting** or **activating** the target produced
the event, which is the difference between a liability that applies to your programme and one
that does not.
