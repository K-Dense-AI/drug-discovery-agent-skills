# Turning ChEMBL rows into a dataset you can model

ChEMBL is an aggregation of what was published, not a curated benchmark. Every field below exists
because someone's dataset was wrong without it. `scripts/target_activities.py` applies all of it
and prints what each step removed; this document is why each step is there.

## The one-paragraph version

Pick **one target of one type**, **one measurement type**, keep only rows where
`standard_relation` is `=`, drop rows with a `data_validity_comment`, require a `pchembl_value`,
prefer assays with `confidence_score` ≥ 8, and aggregate replicates per molecule with a median —
then look at the spread before you trust the median.

## 1. Target selection

A UniProt accession maps to several ChEMBL targets:

```
CHEMBL203      Epidermal growth factor receptor              SINGLE PROTEIN
CHEMBL2363049  Epidermal growth factor receptor              PROTEIN FAMILY
CHEMBL2111431  EGFR and ErbB2 (HER1 and HER2)                PROTEIN FAMILY
CHEMBL4802031  BIRC2/EGFR                                    PROTEIN-PROTEIN INTERACTION
```

`SINGLE PROTEIN` is what you want for SAR against one protein. `PROTEIN FAMILY` rows are assays
that could not be attributed to one member — including them mixes "inhibits EGFR" with "inhibits
something in the EGFR family". `PROTEIN COMPLEX` and `PROTEIN-PROTEIN INTERACTION` are different
experiments again.

Other target types you will meet: `CELL-LINE`, `ORGANISM`, `TISSUE`, `NUCLEIC-ACID`,
`SUBCELLULAR`, `UNCHECKED`. Phenotypic cell-line data is legitimate and often valuable — just
never pooled with biochemical data as if it measured the same thing.

Check the organism too. `target_organism` on the activity row is the fastest filter; human and
rodent orthologue data pooled together is a common silent contaminant.

## 2. Assay type

| `assay_type` | Meaning | Use for |
|---|---|---|
| `B` | Binding | Affinity SAR, docking validation |
| `F` | Functional | Cellular/enzymatic potency, agonist/antagonist |
| `A` | ADMET | PK/permeability/metabolism endpoints |
| `T` | Toxicity | Cytotoxicity and safety endpoints |
| `P` | Physicochemical | Solubility, logD |
| `U` | Unclassified | Inspect before use |

`B` and `F` answer different questions and their absolute values are not interchangeable — a
cell-based IC50 is routinely 10–100× a biochemical one for the same compound.

## 3. Assay confidence score

`assay.confidence_score` is how confidently the assay was mapped to the target. Only the
`assay` endpoint carries it — the `activity` endpoint does not, so a join is required
(`target_activities.py` batches it for you).

| Score | Meaning | ChEMBL_37 assays |
|---|---|---|
| 9 | Direct single protein target assigned | 436,802 |
| 8 | Homologous single protein target assigned | 90,636 |
| 7 | Direct protein complex subunits assigned | 17,611 |
| 6 | Homologous protein complex subunits assigned | 2,846 |
| 5 | Multiple direct protein targets may be assigned | 30,162 |
| 4 | Multiple homologous protein targets may be assigned | 8,991 |
| 3 | Molecular non-protein target | 20,956 |
| 1 | Non-molecular target (e.g. whole organism) | 992,848 |
| 0 | Not yet curated | 363,777 |

For protein SAR use **≥ 8**; **9** if you want only direct assignments. Below 5 the target
assignment is an inference, not a fact. Note there is no score 2.

## 4. `standard_relation` — the censored-data trap

| Relation | Meaning | Keep? |
|---|---|---|
| `=` | A measured value | Yes |
| `>` / `>=` | No activity up to the top concentration tested | Only as a labelled inactive |
| `<` / `<=` | Below the lowest concentration or the assay floor | Rarely |
| `~` | Approximate | Case by case |

A `>` row with `standard_value = 10000 nM` means "inactive at 10 µM", not "IC50 = 10 µM".
Feeding it into a regression as 10 µM places an unmeasured compound in the middle of your
dynamic range and flattens the model. For classification, `>` rows are the honest source of
negatives — but label them as censored, do not average them with measurements.

## 5. `data_validity_comment`

ChEMBL's own flag on values it believes are wrong. Common values: `Potential author error`,
`Outside typical range`, `Potential transcription error`, `Non standard unit for type`,
`Author confirmed error`. **Drop every non-null row.** These are the entries responsible for
picomolar solubilities and femtomolar IC50s in published QSAR sets.

`potential_duplicate = 1` marks a row ChEMBL believes was extracted twice from related
publications. Dropping them prevents one measurement counting several times toward a mean.

## 6. pChEMBL, and why to use it

`pchembl_value = −log10(molar value)` for a comparable subset of endpoint types
(IC50, XC50, EC50, AC50, Ki, Kd, Potency), computed only where the units convert cleanly.

- A pChEMBL of 7 is 100 nM; 9 is 1 nM. Higher is more potent.
- It is the one field where the unit conversion has already been done and checked. Requiring
  `pchembl_value__isnull=false` eliminates the entire class of unit bugs — µM read as nM,
  percent-inhibition rows treated as concentrations, `standard_units` of `%` or `ug.mL-1`.
- The cost is coverage: rows with unusual units or non-standard endpoint types drop out. That
  is usually the right trade.

If you must keep non-pChEMBL rows, filter `standard_units` explicitly (`nM`) and never mix unit
systems in one column.

## 7. Aggregating replicates

The same compound is measured against the same target in many papers. Collapse per molecule:

- **Median**, not mean — one bad row moves a mean.
- Report the **spread** (max − min). A compound with pIC50 5.1 and 8.9 is not a 7.0; it is two
  incompatible measurements, and something about the assay, the target, or the compound identity
  differs. ChEMBL-derived sets routinely contain 10–20 % of such molecules.
- Report **n measurements** and **n distinct documents**. One value from one paper is weaker
  evidence than four values from four groups, and downstream weighting may want to know.
- Aggregate on the **parent** compound, not the salt. `molecule_form` maps salts to parents; the
  activity row's `parent_molecule_chembl_id` gives it directly.

`target_activities.py` does all of this and flags molecules whose replicates span ≥ 1 log unit.

## 8. Before modelling

- **Deduplicate structures**, not just ids. Standardise SMILES (the `datamol` or `rdkit` skill),
  strip salts, and neutralise before comparing — the same compound appears under several
  ChEMBL ids.
- **Split by scaffold, not at random.** ChEMBL data comes in congeneric series from single
  papers; a random split leaves near-duplicates on both sides and reports a fantasy R². The
  `pytdc` skill has scaffold and cold-start splitters.
- **Watch the activity floor.** Screening decks are biased toward actives; the inactive tail is
  under-reported, so a model trained on ChEMBL alone is calibrated on an unrepresentative
  population.
- **Check publication year.** Assay technology drifts; a 1995 IC50 and a 2024 one are not
  necessarily comparable.
- **Look for frequent hitters** before believing a promiscuous compound — the `medchem` skill's
  PAINS and NIBR alerts are the right follow-up.

## 9. Realistic attrition

For EGFR (`CHEMBL203`) Ki data in ChEMBL_37, filtered to binding assays: 538 activity rows →
386 after dropping potential duplicates and censored relations → ~250 unique molecules, of which
roughly 15 % carry replicate measurements spanning more than a log unit. Expect to lose a third
of the raw rows, and treat any pipeline that loses none as not having filtered.
