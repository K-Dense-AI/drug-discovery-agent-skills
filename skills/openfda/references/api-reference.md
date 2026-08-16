# openFDA query language and transport

Base URL `https://api.fda.gov`. Every behaviour below was read back from the live API in
August 2026; the status codes and caps are what the service actually returned, not what the
documentation claims.

## Request shape

```
https://api.fda.gov/<area>/<endpoint>.json?search=<query>&limit=<n>&skip=<n>
```

`<area>` is `drug`, `device`, `food`, `animalandveterinary`, `tobacco`, or `other`. This skill
drives the six `drug` endpoints; the query language is identical across all areas.

| Parameter | Meaning | Cap |
|---|---|---|
| `search` | Lucene-style query over the record | — |
| `limit` | records per request | **1000** |
| `skip` | records to offset | **25000** |
| `count` | aggregate on a field instead of returning records | 1000 terms |
| `sort` | `field:asc` or `field:desc` | — |
| `api_key` | free key, raises the daily quota | — |

## The search grammar

- `field:value` — a term match. Values are tokenised and lowercased.
- `field:"two words"` — a phrase. **Without the quotes, `medicinalproduct:foo bar` parses as
  `medicinalproduct:foo` OR a loose `bar`, silently widening the search.**
- `field:value+AND+other:value` — boolean. `+AND+`, `+OR+`, `+NOT+`, all uppercase, all
  surrounded by `+`. Lowercase `and` is treated as a search term.
- `(a+OR+b)+AND+c` — parentheses group.
- `field:[2020-01-01+TO+2024-12-31]` — inclusive range. Also works on numbers.
- `_exists_:field` — records where the field is present. `_missing_:field` is the inverse.
- `field.exact:"Value"` — the untokenised value. Required for counting; see below.

Everything after `search=` must be URL-encoded, but `+` is the separator openFDA expects, not
`%20`. The bundled `_common.py` encodes with `safe=':+[]{}"'` so the operators survive.

## `.exact` is not optional for counting

`count=patient.reaction.reactionmeddrapt` counts **tokens** — "MYOCARDIAL INFARCTION" is counted
once as `myocardial` and once as `infarction`. `count=patient.reaction.reactionmeddrapt.exact`
counts the whole phrase, which is almost always what you meant. Only some fields have an
`.exact` variant; the API returns 400 when one does not exist.

Counts are computed server-side over the entire matching set, not over one page. This is the
only way to rank anything in a search bigger than the 25000-record `skip` window.

## Pagination and its ceiling

`skip` is capped at 25000. There is no cursor, no `search_after`, and a key does not raise it:

```
GET /drug/event.json?limit=1&skip=26000
-> HTTP 400  {"error":{"code":"BAD_REQUEST","message":"Skip value must 25000 or less."}}
```

So a search matching 500000 reports has 25000 reachable records. To go deeper you must
**partition the search** — most usefully by date:

```
search=<query>+AND+receivedate:[20240101+TO+20240630]
```

and run the partitions separately. `paged()` in `scripts/_common.py` stops at the ceiling and
says so on stderr rather than looping forever.

## Three error responses that do not mean what they say

**1. Zero matches is HTTP 404.**

```
GET /drug/event.json?search=patient.drug.medicinalproduct:zzzznotadrug&limit=1
-> HTTP 404  {"error":{"code":"NOT_FOUND","message":"No matches found!"}}
```

This is a successful query with an empty result set, not a failure. Code that treats non-200 as
an exception turns "this drug has no reports" into a crash. `get()` converts it to
`{"results": [], "meta": {...}}`.

**2. `limit` above 1000 is HTTP 403 `API_KEY_MISSING`.**

```
GET /drug/event.json?search=...&limit=1001
-> HTTP 403  {"error":{"code":"API_KEY_MISSING","message":"No api_key was supplied..."}}
```

The message sends you to get credentials. Credentials do not help: a key raises the **daily
quota**, not the per-request cap, which is 1000 for everyone. `clamp_limit()` prevents the
request from being made.

**3. A misspelled field name is HTTP 404, not 400.** `patient.reaction.reactionmedrapt` (one `d`)
matches nothing and returns `NOT_FOUND` — indistinguishable from a real zero. When a count comes
back empty, check the field name against `references/endpoint-fields.md` before believing it.

## Rate limits and the key

| | Per minute | Per day |
|---|---|---|
| No key | 240 | 1000 |
| With key | 240 | 120000 |

Get one at <https://open.fda.gov/apis/authentication/>. Set `OPENFDA_API_KEY` and `_common.py`
adds it to every request automatically. The 1000/day anonymous limit is easy to exhaust: a single
`signal` run costs four requests.

`Retry-After` is honoured on 429. Retries cover `{429, 500, 502, 503, 504}` with exponential
backoff capped at 30 s.

## `meta`, and how stale the data is

Every response carries a `meta` block:

```json
{"disclaimer": "...", "terms": "...", "license": "...",
 "last_updated": "2026-08-14",
 "results": {"skip": 0, "limit": 1, "total": 388}}
```

`meta.results.total` is the honest match count even when `skip` cannot reach it. `last_updated`
matters: **FAERS is published quarterly and lags by three months or more**, so a drug approved
this quarter has no adverse-event data yet, and a recent signal may simply not have landed.
`last_updated()` in `_common.py` reports it.

`count=` queries set `meta.results` to `null` — there is nothing to page.

## Licence

All openFDA data is public domain (CC0). The API disclaimer is explicit that results are
unvalidated and must not drive medical care; reproduce that framing in anything you generate.
