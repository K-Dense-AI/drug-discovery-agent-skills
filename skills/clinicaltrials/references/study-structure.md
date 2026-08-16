# The shape of a study record

Field paths as returned by the live API in August 2026. **Almost every module and every field is
optional**, which is why `scripts/_common.py` reads everything through `dig(record, "a.b.c")`
rather than subscripting.

## Top level

```json
{
  "protocolSection":  { ... eleven modules ... },
  "derivedSection":   { ... registry-computed annotations ... },
  "hasResults":       true
}
```

`hasResults` is a **top-level sibling of `protocolSection`**, not part of the status module. It is
the single most useful flag in the record and the easiest one to miss.

## `protocolSection` modules

| Module | Carries |
|---|---|
| `identificationModule` | `nctId`, `briefTitle`, `officialTitle`, `orgStudyIdInfo`, `acronym` |
| `statusModule` | status, dates, `whyStopped` |
| `sponsorCollaboratorsModule` | `leadSponsor.name`, `leadSponsor.class`, `collaborators[]` |
| `oversightModule` | FDA-regulated flags, DMC presence |
| `descriptionModule` | `briefSummary`, `detailedDescription` |
| `conditionsModule` | `conditions[]`, `keywords[]` |
| `designModule` | study type, phases, allocation, masking, enrolment |
| `armsInterventionsModule` | `armGroups[]`, `interventions[]` |
| `outcomesModule` | `primaryOutcomes[]`, `secondaryOutcomes[]` |
| `eligibilityModule` | criteria text, age bounds, sex, healthy volunteers |
| `contactsLocationsModule` | investigators, sites, countries |

## The paths worth knowing

```
protocolSection.identificationModule.nctId
protocolSection.identificationModule.briefTitle
protocolSection.statusModule.overallStatus
protocolSection.statusModule.whyStopped
protocolSection.statusModule.statusVerifiedDate
protocolSection.statusModule.startDateStruct.date
protocolSection.statusModule.primaryCompletionDateStruct.date
protocolSection.statusModule.primaryCompletionDateStruct.type      ACTUAL | ESTIMATED
protocolSection.statusModule.completionDateStruct.date
protocolSection.designModule.studyType                             INTERVENTIONAL | OBSERVATIONAL | EXPANDED_ACCESS
protocolSection.designModule.phases                                a LIST
protocolSection.designModule.enrollmentInfo.count
protocolSection.designModule.enrollmentInfo.type                   ACTUAL | ESTIMATED
protocolSection.designModule.designInfo.allocation                 RANDOMIZED | NON_RANDOMIZED
protocolSection.designModule.designInfo.interventionModel          PARALLEL | CROSSOVER | SINGLE_GROUP | ...
protocolSection.designModule.designInfo.primaryPurpose             TREATMENT | PREVENTION | DIAGNOSTIC | ...
protocolSection.designModule.designInfo.maskingInfo.masking        NONE | SINGLE | DOUBLE | TRIPLE | QUADRUPLE
protocolSection.sponsorCollaboratorsModule.leadSponsor.name
protocolSection.armsInterventionsModule.interventions[].name
protocolSection.armsInterventionsModule.interventions[].type       DRUG | BIOLOGICAL | DEVICE | PROCEDURE | ...
protocolSection.outcomesModule.primaryOutcomes[].measure
protocolSection.outcomesModule.primaryOutcomes[].timeFrame
protocolSection.eligibilityModule.eligibilityCriteria              ONE STRING
protocolSection.eligibilityModule.minimumAge                       "18 Years"
hasResults
```

## Five fields that are not what they look like

**1. `phases` is a list, and a phase 2/3 study is in both.** Never `phases[0]`.

**2. `enrollmentInfo.type` decides whether the count means anything.** `ESTIMATED` is the
sponsor's plan at registration; `ACTUAL` is what happened. A recruiting study always shows
`ESTIMATED`, and terminated studies frequently show an `ACTUAL` far below the original target —
which is itself the finding.

**3. `primaryCompletionDateStruct` is the one that matters**, not `completionDateStruct`. Primary
completion is when the last patient was measured for the primary endpoint — the data cut the
readout comes from. Overall completion trails it by months or years of follow-up.

**4. `statusVerifiedDate` is not the last-update date.** It is when the sponsor last confirmed the
record is accurate. Frequently years stale; when it is old and the status is `RECRUITING`, the
status is not trustworthy. `UNKNOWN` is what the registry assigns when it gives up waiting.

**5. `eligibilityCriteria` is a single newline-delimited blob**, with "Inclusion Criteria:" and
"Exclusion Criteria:" as headings inside the text. There is no structured form. `ct_study.py
eligibility` splits on those headings, and reports the text unsplit when they are absent rather
than guessing.

## `interventions[]` is free text

The registry does not normalise drug names. One molecule appears as its code name (`MK-3475`), its
INN (`pembrolizumab`), and its brand (`Keytruda`), sometimes within one indication. There is no
identifier to join on — no ChEMBL id, no UNII, no RxCUI.

Practical consequences: `ct_landscape.py interventions` casefolds and nothing more, so treat its
grouping as a first pass. To do this properly, resolve names to a compound identifier with
`chembl` first, then search the registry for each synonym separately.

`interventions[].type` is worth filtering on: a `DRUG` or `BIOLOGICAL` arm is a therapeutic
candidate, while `OTHER` and `PROCEDURE` frequently mark placebo arms, imaging, or standard care.

## `derivedSection`

Registry-computed annotations, most usefully:

```
derivedSection.conditionBrowseModule.meshes[]        MeSH terms for the conditions
derivedSection.interventionBrowseModule.meshes[]     MeSH terms for the interventions
```

These are the closest thing to normalised vocabulary in the record, and they are assigned by the
NLM rather than the sponsor — so they are more consistent than the free-text fields, but they are
also coarser and are absent on newer registrations that have not been indexed yet.
