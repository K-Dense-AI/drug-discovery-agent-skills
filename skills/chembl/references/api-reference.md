# ChEMBL web services — API reference

Base URL: `https://www.ebi.ac.uk/chembl/api/data`. No key, no account.
Interactive schema: <https://www.ebi.ac.uk/chembl/api/data/docs>.

Checked against **ChEMBL_37** (released 2026-05-01): 24,527,044 activities, 2,921,148 distinct
compounds, 18,552 targets. Confirm with `python scripts/chembl_query.py status` — every count and
id below is release-specific.

## Request shape

```
GET /chembl/api/data/<endpoint>.json?<filters>&limit=<n>&offset=<n>&only=<fields>&order_by=<field>
```

- **Format** is the path suffix: `.json`, `.xml`, `.yaml`. `format=json` as a query parameter also
  works. Without a suffix you get XML.
- **`limit` is capped at 1000, silently.** Request 2000 and the response has 1000 rows with
  `page_meta.limit == 1000` — no error, no warning. Follow `page_meta.next` instead.
- **`offset`** works for deep paging, but re-sorting between requests can shift rows. For a
  reproducible dump add `order_by=<a stable id>`.
- **`only=a,b,c`** trims the payload. It is a hint rather than a contract — related fields
  sometimes come along — so read by key, not by position.
- **`order_by=field`**, `-field` for descending.
- Responses are heavily cached upstream (`cache-control: max-age=30000000`), so repeated
  identical requests are cheap. There is no documented rate limit; be polite and batch anyway.

## Pagination envelope

```json
{
  "page_meta": {"limit": 20, "offset": 0, "total_count": 19719,
                "next": "/chembl/api/data/activity.json?limit=20&offset=20&...",
                "previous": null},
  "activities": [ ... ]
}
```

The payload key is not always the endpoint plus `s` — `activity` → `activities`,
`mechanism` → `mechanisms`, `similarity`/`substructure` → `molecules`, `atc_class` → `atc`.
`scripts/_common.py:PAYLOAD_KEYS` has the full mapping.

`next` is a host-relative path that is already query-encoded — pass it through unmodified rather
than rebuilding it, or the encoding is applied twice.

## Filters

Django-style lookups, joined by `&` (AND). There is no OR across different fields; use `__in`
for OR within one field.

| Lookup | Example |
|---|---|
| exact | `standard_type=IC50` |
| `__in` | `molecule_chembl_id__in=CHEMBL25,CHEMBL941` |
| `__gte` `__lte` `__gt` `__lt` | `pchembl_value__gte=6` |
| `__range` | `year__range=2015,2020` |
| `__isnull` | `pchembl_value__isnull=false` |
| `__iexact` | `pref_name__iexact=aspirin` |
| `__icontains` `__contains` | `pref_name__icontains=kinase` |
| `__istartswith` `__startswith` `__endswith` | `standard_inchi_key__startswith=BSYNRYMUTXBXSQ` |
| `__search` | full-text on supported fields |
| `__flexmatch` | `molecule_structures__canonical_smiles__flexmatch=CCO` |
| relation traversal | `target_components__accession=P00533` |

**The lookup that silently does nothing.** Lookups take *two* underscores. Written with one —
`pchembl_value_gte=8` — the whole string is read as a field name, and depending on the endpoint
you get either a 400 or a completely unfiltered result set that looks like a successful query.
`scripts/_common.py:parse_filters` rejects the single-underscore spelling.

## Structure search

Query goes in the **path**, not the query string:

```
/similarity/{SMILES}/{threshold}.json      threshold 40-100, percent Tanimoto
/similarity/{ChEMBL_ID}/{threshold}.json
/substructure/{SMILES}.json
/substructure/{ChEMBL_ID}.json
```

Percent-encode the query: an unencoded `#` (triple bond) truncates the URL at the fragment
marker, and `+`, `/`, and `\` are all meaningful in a path. These endpoints are GET-only —
POST returns 500. For a long SMILES that overflows a URL, look the compound up by InChIKey
instead. Similarity results carry an extra `similarity` field (a percentage as a string).

Exact structure lookup goes through the molecule endpoint:

- `molecule_structures__canonical_smiles__flexmatch=<SMILES>` — salt-, charge-, and
  tautomer-tolerant. This is what "is this compound in ChEMBL?" almost always means.
- `molecule_structures__canonical_smiles__exact=<SMILES>` — byte-identical canonical string.
  Misses the parent of a salt, and misses any SMILES you did not canonicalise the same way.
- `molecule_structures__standard_inchi_key=<27-char key>` — exact including stereochemistry.
  The first 14 characters alone (with `__startswith`) match the connectivity skeleton across
  stereoisomers and protonation states.

## Free-text search

```
/molecule/search.json?q=imatinib
/target/search.json?q=kinase
/chembl_id_lookup/search.json?q=imatinib      # any entity type, plus ACTIVE/OBSOLETE status
```

Ranked by relevance with a `score` field. `chembl_id_lookup` is the one to use when you have an
id of unknown type, or need to know whether an id was retired and superseded.

## Endpoints worth knowing

| Endpoint | Holds |
|---|---|
| `activity` | One measured value per assay/compound pair — the core table |
| `assay` | Assay description, type, organism, and **`confidence_score`** |
| `molecule` | Structures, calculated properties, development flags |
| `target` | Targets and their protein components |
| `mechanism` | Curated mechanism of action for approved and clinical drugs |
| `drug_indication` | Indication with the maximum phase reached |
| `drug_warning` | Withdrawals and black-box warnings |
| `document` | Source publications (DOI, PubMed id, year, journal) |
| `molecule_form` | Salt ↔ parent relationships |
| `compound_structural_alert` | Structural-alert hits per compound |
| `protein_classification` | The ChEMBL protein family tree |
| `atc_class`, `cell_line`, `tissue`, `binding_site`, `metabolism`, `target_relation` | Supporting vocabularies |

`python scripts/chembl_query.py endpoints` prints this with the useful filters for each.

## Types are strings

Numeric fields come back as JSON strings: `"standard_value": "41.0"`, `"pchembl_value": "7.39"`,
`"full_mwt": "493.62"`, `"max_phase": "4.0"`. Sorting or comparing them as text misorders
everything (`"9"` > `"41"`). Convert on ingest — `_common.as_float` does it safely, returning
`None` for `""` and nulls.

`max_phase` is a *string* float on `molecule` (`"4.0"`) and an *integer* on `mechanism` (`4`).
Coerce before comparing across endpoints.

## Errors

| Status | Cause |
|---|---|
| 400 | Unknown field or malformed filter — the body names the field |
| 404 | Unknown id, or an unencoded structure query that truncated |
| 500 | Malformed structure query, or POST to a GET-only endpoint |
| 429 / 502 / 503 / 504 | Transient; retry with backoff |

## Other access routes

- **`chembl_webresource_client`** (pip) — the official Python client, with lazy `QuerySet`
  objects and local caching. Convenient, but it hides paging behaviour and its cache can serve
  stale rows across releases. The bundled scripts stay stdlib-only for that reason.
- **Bulk downloads** — <https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/>. Once you
  want more than ~10⁵ activities, take the Postgres/SQLite dump instead of paging the API.
- **RDF / SPARQL** — the EBI RDF Platform that hosted the ChEMBL SPARQL endpoint is gone:
  checked live in August 2026, `https://www.ebi.ac.uk/rdf/` and every service path under it return
  404. For federated or whole-database questions, take the FTP dump above and query it locally.
