# Field reference for the six openFDA drug endpoints

Fields as returned by the live API in August 2026. Types are what the JSON actually contains —
note that several "numbers" are strings, and that most fields are optional on any given record.

## What one record is

| Endpoint | One record is | Rough scale |
|---|---|---|
| `drug/event` | one adverse-event report submitted to FAERS | ~20.6 M |
| `drug/label` | one Structured Product Label (SPL) | ~150 k |
| `drug/drugsfda` | one FDA application (NDA/ANDA/BLA) | ~30 k |
| `drug/ndc` | one entry in the National Drug Code directory | ~130 k |
| `drug/enforcement` | one recall enforcement report | ~25 k |
| `drug/shortages` | one drug-shortage record | ~5 k |

Counts drift; get the live number with `total_matching(endpoint, "_exists_:<a required field>")`.

## `drug/event` — FAERS

The record is a **report**, and a report has many drugs and many reactions. A report naming five
drugs appears in searches for all five. Nothing here is a patient count.

| Field | Type | Notes |
|---|---|---|
| `safetyreportid` | string | report identifier |
| `receivedate` | `YYYYMMDD` string | when FDA received it; use for range partitioning |
| `receiptdate` | `YYYYMMDD` string | most recent version received |
| `serious` | `"1"`/`"2"` | 1 = serious, 2 = not. A **string**, so `serious:1` not `serious:true` |
| `seriousnessdeath` | `"1"` | present only when the outcome was death; likewise `...hospitalization`, `...lifethreatening`, `...disabling`, `...congenitalanomali`, `...other` |
| `occurcountry` | 2-letter string | where the event occurred |
| `primarysource.qualification` | `"1"`–`"5"` | 1 physician, 2 pharmacist, 3 other HCP, 4 lawyer, 5 consumer |
| `patient.patientonsetage` | string | paired with `patientonsetageunit` (`"801"` = years) |
| `patient.patientsex` | `"1"`/`"2"` | 1 male, 2 female |
| `patient.reaction[].reactionmeddrapt` | string | MedDRA Preferred Term, uppercase |
| `patient.reaction[].reactionoutcome` | `"1"`–`"6"` | 1 recovered … 5 fatal, 6 unknown |
| `patient.drug[].medicinalproduct` | string | **as typed by the reporter** — misspellings included |
| `patient.drug[].drugcharacterization` | `"1"`–`"3"` | **1 suspect, 2 concomitant, 3 interacting** |
| `patient.drug[].drugindication` | string | MedDRA term for why it was given |
| `patient.drug[].openfda.*` | arrays | normalised names; **absent on many reports** |

**`drugcharacterization` is the field most analyses forget.** A search for a drug returns reports
where it was merely a concomitant medication — present in the patient, not suspected of causing
anything. For causality work, add `+AND+patient.drug.drugcharacterization:1`. The bundled
`fda_adverse.py` deliberately does *not* apply this filter by default, because the standard
disproportionality denominators are computed over all reports; apply it consciously.

Search a drug across both raw and normalised names — `medicinalproduct` alone misses reports that
only carry openFDA annotations, and `openfda.generic_name` alone misses everything unnormalised.

## `drug/label` — Structured Product Labels

Every manufacturer files its own SPL, so a generic drug has hundreds of near-identical records.
Section fields are **arrays of long strings**.

| Field | Notes |
|---|---|
| `boxed_warning` | absent when this SPL has none — not proof the drug has none |
| `indications_and_usage` | the approved indication text |
| `dosage_and_administration`, `contraindications`, `warnings_and_cautions` | |
| `adverse_reactions`, `drug_interactions`, `use_in_specific_populations` | |
| `mechanism_of_action`, `clinical_pharmacology`, `pharmacokinetics` | |
| `effective_time` | `YYYYMMDD` of this label version |
| `openfda.brand_name` / `generic_name` / `substance_name` | arrays |
| `openfda.pharm_class_epc` | Established Pharmacologic Class, e.g. `Factor Xa Inhibitor [EPC]` |
| `openfda.pharm_class_moa` | mechanism, e.g. `Factor Xa Inhibitors [MoA]` |
| `openfda.pharm_class_cs` / `pharm_class_pe` | chemical structure / physiologic effect |
| `openfda.rxcui`, `unii`, `spl_set_id` | cross-references |

**`openfda.*` annotations are frequently missing.** Checked live: pembrolizumab and apixaban
labels carry `pharm_class_epc`, while every atorvastatin label examined carried none. Absence is
a property of the SPL, not of the drug.

`pharm_class_epc` is a regulatory classification, not a mechanism — pembrolizumab returns both
`Programmed Death Receptor-1 Blocking Antibody [EPC]` and, from the co-formulated hyaluronidase,
`Endoglycosidase [EPC]`. Read every value before attributing one to the active moiety.

## `drug/drugsfda` — applications and approvals

| Field | Notes |
|---|---|
| `application_number` | `NDA021986`, `ANDA…`, `BLA125514` |
| `sponsor_name` | uppercase company name |
| `products[]` | `product_number`, `brand_name`, `dosage_form`, `route`, `marketing_status`, `reference_drug` |
| `products[].active_ingredients[]` | `{name, strength}` |
| `submissions[]` | `submission_type` (`ORIG`/`SUPPL`), `submission_number`, `submission_status`, `submission_status_date`, `review_priority`, `submission_class_code` |

`submission_status` is `AP` (approved), `TA` (tentative), `CR` (complete response), `RL`, `WD`.
**Only `AP` is an approval.**

`submission_class_code` of `EFFICACY` on an approved `SUPPL` is a new indication — counting those
is how you see label expansion. Keytruda's BLA125514 has 127 submissions and 108 approved
efficacy supplements against an original approval of 2014-09-04.

`marketing_status: Discontinued` still means approved. Drugs@FDA records applications, not
whether the product is on a shelf, and carries no withdrawal-for-safety flag.

## `drug/ndc` — National Drug Code directory

`product_ndc`, `generic_name`, `brand_name`, `labeler_name`, `dosage_form`, `route`,
`marketing_category` (`NDA`, `ANDA`, `BLA`, `OTC monograph…`), `marketing_start_date`,
`marketing_end_date`, `active_ingredients[]`, `pharm_class[]`, `dea_schedule`.

The directory lists what companies *report* marketing, so it is the closest thing openFDA has to
a current-availability signal — but a listing is a self-report, not verification.

## `drug/enforcement` — recalls

`recall_number`, `classification` (`Class I` most serious … `Class III`), `status`,
`reason_for_recall`, `product_description`, `recalling_firm`, `report_date`, `voluntary_mandated`,
`distribution_pattern`, `openfda.*`.

Class I means reasonable probability of serious harm or death. A recall is about a *batch*, not
the molecule — most are manufacturing defects, not pharmacology.

## `drug/shortages`

`generic_name`, `company_name`, `status` (`Current`, `Resolved`), `shortage_reason`,
`initial_posting_date`, `update_date`, `dosage_form`, `presentation`, `therapeutic_category`.

Useful as a supply-chain and commercial-opportunity signal; irrelevant to pharmacology.
