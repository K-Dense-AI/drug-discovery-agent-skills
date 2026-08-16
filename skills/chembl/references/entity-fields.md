# Field reference for the main ChEMBL entities

Fields as returned by ChEMBL_37. Types are what the JSON actually contains — note how many
numbers arrive as strings.

## `activity`

One measured value for one compound in one assay.

| Field | Type | Notes |
|---|---|---|
| `activity_id` | int | Stable primary key |
| `molecule_chembl_id` | str | The compound as tested |
| `parent_molecule_chembl_id` | str | Salt stripped; aggregate on this |
| `canonical_smiles` | str | Convenience copy of the structure |
| `target_chembl_id` | str | Check the target's type before pooling |
| `target_organism`, `target_pref_name`, `target_tax_id` | str | |
| `assay_chembl_id` | str | Join here for `confidence_score` |
| `assay_type` | str | `B`, `F`, `A`, `T`, `P`, `U` |
| `assay_description` | str | Read this when a value looks wrong |
| `standard_type` | str | `IC50`, `Ki`, `Kd`, `EC50`, `Potency`, … |
| `standard_relation` | str | `=`, `>`, `<`, `>=`, `<=`, `~` |
| `standard_value` | **str** | Numeric as text |
| `standard_units` | str | Usually `nM` after standardisation |
| `standard_upper_value` | str | Present for ranges |
| `pchembl_value` | **str** | −log10(molar); the safe comparable column |
| `type`, `value`, `units` | str | The **author-reported** originals, unstandardised |
| `data_validity_comment` | str/null | Non-null means ChEMBL doubts the value |
| `data_validity_description` | str/null | Why |
| `potential_duplicate` | int | `1` = probably extracted twice |
| `standard_flag` | int | `1` = value was standardised |
| `activity_comment` | str/null | `Not Active`, `inconclusive`, … |
| `ligand_efficiency` | obj | `{bei, le, lle, sei}`, all strings |
| `document_chembl_id`, `document_journal`, `document_year` | | Provenance |
| `bao_endpoint`, `bao_format`, `bao_label` | str | BioAssay Ontology terms |
| `assay_variant_accession`, `assay_variant_mutation` | str/null | **Mutant assays.** A `T790M` row is not wild-type data |
| `action_type` | str/null | `INHIBITOR`, `AGONIST`, … where curated |
| `src_id` | int | Data source (1 = scientific literature) |

The `type`/`value`/`units` trio is what the paper said; the `standard_*` trio is what ChEMBL
made of it. Always model the `standard_*` fields, and read the originals only when auditing.

`assay_variant_mutation` is the field most often missed: point-mutant assays sit alongside
wild-type ones under the same target id.

## `molecule`

| Field | Type | Notes |
|---|---|---|
| `molecule_chembl_id` | str | |
| `pref_name` | str/null | Often null for non-drugs |
| `molecule_type` | str | `Small molecule`, `Protein`, `Antibody`, `Oligosaccharide`, … |
| `max_phase` | **str** | `"4.0"` approved … `"0.5"` early clinical; null = preclinical |
| `first_approval` | int/null | Year |
| `withdrawn_flag`, `black_box_warning` | bool/int | |
| `oral`, `parenteral`, `topical` | bool | Route flags |
| `natural_product`, `prodrug`, `polymer_flag`, `inorganic_flag` | int | |
| `chirality` | int | 0 racemic, 1 single stereoisomer, 2 achiral, −1 unknown |
| `structure_type` | str | `MOL`, `SEQ`, `NONE` — `SEQ` has no SMILES |
| `molecule_structures` | obj/null | `canonical_smiles`, `standard_inchi`, `standard_inchi_key`, `molfile` |
| `molecule_properties` | obj/null | See below |
| `molecule_hierarchy` | obj | `parent_chembl_id`, `active_chembl_id` |
| `molecule_synonyms` | list | Names with their source |
| `cross_references` | list | PubChem, DrugBank, Wikipedia, … |
| `atc_classifications` | list | WHO ATC codes |
| `usan_stem`, `usan_year`, `usan_stem_definition` | | `-tinib`, `-mab` and friends |
| `chemical_probe` | int | Flagged as a chemical probe |
| `therapeutic_flag`, `dosed_ingredient`, `availability_type` | | Development status |

`molecule_structures` is **null** for biologics and for compounds with an undisclosed structure —
guard the access. `molecule_properties` is null for the same reason.

### `molecule_properties`

The complete set returned by ChEMBL_37:

| Strings | Integers | Other |
|---|---|---|
| `full_mwt`, `mw_freebase`, `alogp`, `psa`, `qed_weighted`, `np_likeness_score` | `hba`, `hbd`, `rtb`, `aromatic_rings`, `heavy_atoms`, `num_ro5_violations` | `full_molformula` (str), `ro3_pass` (`"Y"`/`"N"`) |

**Fields that older tutorials use and ChEMBL_37 no longer exposes:** `cx_logp`, `cx_logd`,
`cx_most_apka`, `cx_most_bpka`, `molecular_species`, `hba_lipinski`, `hbd_lipinski`,
`num_lipinski_ro5_violations`. These were ChemAxon-derived. Filtering on one now returns
**400** with `The path 'cx_logp' is not valid in the filter expression` — a loud failure, but
only if you check the status code. For logD or pKa, compute them yourself (`rowan` for
macro-pKa, `rdkit` for cheap approximations) rather than looking for them here.

Everything here is **calculated**, not measured, and was computed with the toolkit of that
release. Recomputing with RDKit gives slightly different numbers; do not mix the two sources in
one column.

## `target`

| Field | Type | Notes |
|---|---|---|
| `target_chembl_id` | str | |
| `pref_name` | str | |
| `target_type` | str | `SINGLE PROTEIN`, `PROTEIN FAMILY`, `PROTEIN COMPLEX`, `CELL-LINE`, `ORGANISM`, … |
| `organism`, `tax_id` | | |
| `species_group_flag` | bool | True = the target spans species |
| `target_components` | list | Each with `accession` (UniProt), `component_type`, `component_description`, `target_component_synonyms`, `target_component_xrefs` |
| `cross_references` | list | |

Go from UniProt to ChEMBL with `target.json?target_components__accession=P00533`; go back by
reading `target_components[].accession`.

## `assay`

| Field | Type | Notes |
|---|---|---|
| `assay_chembl_id` | str | |
| `assay_type`, `assay_type_description` | str | |
| `confidence_score` | int | 0–9, see [data-curation.md](data-curation.md) |
| `description` | str | |
| `assay_organism`, `assay_tax_id`, `assay_strain`, `assay_tissue`, `assay_cell_type` | | |
| `relationship_type` | str | How the assay relates to the target: `D` direct, `H` homologous, `U` undefined, … |
| `bao_format`, `bao_label` | str | Assay format ontology |
| `target_chembl_id` | str | |
| `document_chembl_id` | str | |
| `variant_sequence` | obj/null | Mutation details when the assay used a variant |
| `assay_category`, `assay_subcellular_fraction`, `assay_test_type` | | |

## `mechanism`

`molecule_chembl_id`, `target_chembl_id`, `action_type` (`INHIBITOR`, `AGONIST`, `ANTAGONIST`,
`BLOCKER`, `MODULATOR`, `OPENER`, `PARTIAL AGONIST`, …), `mechanism_of_action`,
`direct_interaction` (0/1), `molecular_mechanism` (0/1), `disease_efficacy` (0/1), `max_phase`
(**int** here), `mechanism_comment`, `selectivity_comment`, `binding_site_comment`,
`mechanism_refs` (list of `{ref_type, ref_id, ref_url}`).

Curated for approved and clinical-stage drugs only — absence here is not evidence a compound has
no mechanism, just that no one curated one.

## `drug_indication`

`molecule_chembl_id`, `mesh_id`, `mesh_heading`, `efo_id`, `efo_term`, `max_phase_for_ind`
(**str** float), `indication_refs`. Indications are per molecule/disease pair, so one drug
appears many times. `efo_id` is the join to the `open-targets` skill's disease ontology — though
Open Targets is MONDO-first, so expect to remap.

## `drug_warning`

`molecule_chembl_id`, `warning_type` (`Withdrawn`, `Black Box Warning`), `warning_class`,
`warning_description`, `warning_country`, `warning_year`, `efo_id`, `efo_term`. Withdrawals are
country-specific: a drug withdrawn in one jurisdiction may still be marketed elsewhere, so read
`warning_country` before calling anything "withdrawn".
