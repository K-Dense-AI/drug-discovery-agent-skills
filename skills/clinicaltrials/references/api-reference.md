# ClinicalTrials.gov API v2 — query reference

Base URL `https://clinicaltrials.gov/api/v2`. The version 2 API replaced the classic API, which
was retired in June 2024. Every behaviour below was read back from the live service in August
2026. No key, no account, no quota published.

## Endpoints

| Path | Returns |
|---|---|
| `/studies` | search results |
| `/studies/{nctId}` | one study |
| `/studies/metadata` | the field dictionary |
| `/stats/size` | corpus statistics |
| `/version` | API and data version |

## Query parameters

| Parameter | Meaning |
|---|---|
| `query.cond` | condition or disease |
| `query.intr` | intervention or treatment |
| `query.term` | free text across the record |
| `query.spons` | sponsor or collaborator |
| `query.titles` | title / acronym |
| `query.locn` | location terms |
| `query.outc` | outcome measure text |
| `query.id` | study identifiers |
| `filter.overallStatus` | comma-separated status enum |
| `filter.ids` | comma-separated NCT ids |
| `filter.advanced` | Essie expression, e.g. `AREA[Phase]PHASE3` |
| `fields` | comma-separated field names to return |
| `pageSize` | up to 1000 |
| `pageToken` | opaque cursor from the previous response |
| `countTotal` | `true` to include `totalCount` |
| `sort` | e.g. `@relevance`, `LastUpdatePostDate:desc` |

## Paging is a cursor, and `totalCount` is opt-in

```json
{"studies": [...], "totalCount": 5259, "nextPageToken": "ZVt07cGHkvI2wRk2CJf6..."}
```

Pass `nextPageToken` back as `pageToken`. There is no offset parameter — and, usefully, **no
ceiling of the kind openFDA imposes**: the cursor walks the whole result set.

Two consequences. A token is only valid for the query that produced it, so changing any parameter
mid-walk invalidates the walk. And **without `countTotal=true` there is no `totalCount` key at
all** — code that reads it gets `None` and reports zero matches for a query that matched
thousands. `paged()` and `total_count()` in `scripts/_common.py` always send it.

## Enum values are validated server-side

`filter.overallStatus=Completed` returns:

```
Invalid value in parameter `overallStatus`: `Completed`
```

Accepted statuses, all upper snake case:

```
NOT_YET_RECRUITING  RECRUITING  ENROLLING_BY_INVITATION  ACTIVE_NOT_RECRUITING
SUSPENDED  TERMINATED  COMPLETED  WITHDRAWN  UNKNOWN
```

Combine with commas — `filter.overallStatus=COMPLETED,TERMINATED` — which is an OR.

`UNKNOWN` is not an error state: it means the sponsor has not verified the record recently
enough, and the registry has stopped believing the last status. It is common among older studies
and should usually be read as "probably abandoned".

## Phase filtering, and why counts do not sum

Phase is not a top-level filter; it goes through the Essie expression language:

```
filter.advanced=AREA[Phase]PHASE3
```

Accepted values: `EARLY_PHASE1`, `PHASE1`, `PHASE2`, `PHASE3`, `PHASE4`, `NA`.

**`designModule.phases` is a list.** A phase 2/3 study carries `["PHASE2", "PHASE3"]` and is
returned by a filter for either one. Checked live: melanoma + `AREA[Phase]PHASE3` returns 219
studies, and the second result has `["PHASE2","PHASE3"]`. So per-phase counts overlap and do not
sum to the total. `ct_search.py count --by phase` says so in its output.

`NA` means the study has no phase — device, behavioural, and observational studies. It does not
mean the phase is unknown.

Other useful `filter.advanced` areas: `AREA[StudyType]INTERVENTIONAL`,
`AREA[LeadSponsorClass]INDUSTRY`, `AREA[StartDate]RANGE[2020-01-01,MAX]`.

## Field selection

`fields=NCTId,BriefTitle,Phase,EnrollmentCount,OverallStatus,LeadSponsorName` cuts the payload
dramatically on a broad walk. Two things to know:

- The names are **field names from the data dictionary** (`NCTId`, `Phase`, `EnrollmentCount`),
  not the JSON paths they land at.
- **The response keeps the full module nesting regardless.** Asking for `Phase` still returns it
  at `protocolSection.designModule.phases`. Field selection prunes the tree; it does not flatten
  it. This is why `dig()` exists.

Get the full dictionary from `/studies/metadata`.

## Errors

| Status | Meaning |
|---|---|
| 400 | bad enum, malformed Essie expression, or an unknown field name |
| 404 | no such NCT id |

There is no "empty result is an error" behaviour here — a query matching nothing returns
`{"studies": [], "totalCount": 0}` with HTTP 200. That is the opposite of openFDA, and worth
remembering when moving between the two.

## Rate limits

None documented, and none observed. That is not licence to hammer it: `ct_landscape.py` walks
studies one page at a time because the registry has no aggregation endpoint, and a broad
condition can be tens of thousands of records. Use `--limit` deliberately.

## Data currency and licence

Records are updated when sponsors submit changes; `statusVerifiedDate` says when the sponsor last
confirmed the record, and it is frequently years old. Public domain, courtesy of the U.S.
National Library of Medicine. Attribution to ClinicalTrials.gov is expected.
