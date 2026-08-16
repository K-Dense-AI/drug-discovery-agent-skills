"""Shared HTTP, paging, and table helpers for the ChEMBL web-service scripts.

Standard library only. The ChEMBL API is an unauthenticated REST service, so
the only thing a dependency would add is an install step.

Three behaviours of the API are encoded here because getting them wrong is
quiet rather than loud:

* `limit` is silently capped at 1000. Ask for 2000 and you get 1000 back with
  `page_meta.limit == 1000` -- no error, just a short result that looks
  complete. `paged` follows `page_meta.next` instead of trusting one request.
* Numeric fields are returned as **strings** (`"41.0"`, `"7.39"`, `"493.62"`).
  Sorting or comparing them without conversion silently misorders results.
* A filter on a field that does not exist raises 400 with a helpful message,
  but a filter with a misspelled *lookup* suffix is treated as a field name --
  so `pchembl_value__gt3` filters nothing and returns everything.
"""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable, Iterator, Mapping, Sequence

BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
USER_AGENT = "drug-discovery-agent-skills-chembl/1.0"

TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 2.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

#: The server's hard cap. Requests above it are truncated, not rejected.
MAX_LIMIT = 1000

#: Endpoints whose JSON payload key is not simply `<endpoint> + "s"`.
PAYLOAD_KEYS = {
    "activity": "activities",
    "assay": "assays",
    "atc_class": "atc",
    "binding_site": "binding_sites",
    "biotherapeutic": "biotherapeutics",
    "cell_line": "cell_lines",
    "chembl_id_lookup": "chembl_id_lookups",
    "compound_record": "compound_records",
    "compound_structural_alert": "compound_structural_alerts",
    "document": "documents",
    "drug": "drugs",
    "drug_indication": "drug_indications",
    "drug_warning": "drug_warnings",
    "mechanism": "mechanisms",
    "metabolism": "metabolisms",
    "molecule": "molecules",
    "molecule_form": "molecule_forms",
    "organism": "organisms",
    "protein_classification": "protein_classifications",
    "similarity": "molecules",
    "source": "sources",
    "substructure": "molecules",
    "target": "targets",
    "target_component": "target_components",
    "target_relation": "target_relations",
    "tissue": "tissues",
    "xref_source": "xref_sources",
}


class ChemblError(RuntimeError):
    """A transport or API-level failure worth surfacing to the caller."""


def payload_key(endpoint: str) -> str:
    """The key holding the result list for `endpoint`."""
    root = endpoint.strip("/").split("/")[0]
    return PAYLOAD_KEYS.get(root, f"{root}s")


def get(
    path: str,
    params: Mapping[str, Any] | None = None,
    *,
    base_url: str = BASE_URL,
    timeout: int = TIMEOUT_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
) -> dict[str, Any]:
    """GET a JSON document from the ChEMBL API, retrying transient failures.

    `path` may be an endpoint name (`"activity"`), a resource path
    (`"molecule/CHEMBL25"`), or an absolute path taken from
    `page_meta.next` (`"/chembl/api/data/activity.json?..."`).
    """
    url = _build_url(path, params, base_url)
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}

    last_error = "no attempt made"
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:400]
            last_error = f"HTTP {error.code} for {url}: {detail}"
            if error.code not in RETRYABLE_STATUS or attempt == max_attempts:
                raise ChemblError(last_error) from error
            _sleep_before_retry(attempt, error.headers.get("Retry-After"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = f"{type(error).__name__} for {url}: {error}"
            if attempt == max_attempts:
                raise ChemblError(last_error) from error
            _sleep_before_retry(attempt, None)
    raise ChemblError(last_error)  # pragma: no cover - loop returns or raises


def _build_url(path: str, params: Mapping[str, Any] | None, base_url: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if path.startswith("/"):
        # A `page_meta.next` value: already absolute-on-host and already
        # query-encoded, so it must not be re-encoded.
        host = base_url.split("/chembl/api/data")[0]
        return f"{host}{path}"
    path = path.strip("/")
    if not path.endswith(".json"):
        path = f"{path}.json"
    query = urllib.parse.urlencode(
        {key: value for key, value in (params or {}).items() if value is not None},
        safe=",",
    )
    return f"{base_url}/{path}" + (f"?{query}" if query else "")


def _sleep_before_retry(attempt: int, retry_after: str | None) -> None:
    delay = BACKOFF_BASE_SECONDS ** attempt
    if retry_after:
        try:
            delay = max(delay, float(retry_after))
        except ValueError:
            pass
    time.sleep(min(delay, 30.0))


def paged(
    endpoint: str,
    params: Mapping[str, Any] | None = None,
    *,
    limit: int | None = None,
    page_size: int = MAX_LIMIT,
    base_url: str = BASE_URL,
    progress: bool = False,
) -> Iterator[dict[str, Any]]:
    """Yield every record from a filtered endpoint, following `page_meta.next`.

    `limit` caps the total yielded; `page_size` is per request and is clamped
    to the server's maximum of 1000.
    """
    key = payload_key(endpoint)
    request_params = dict(params or {})
    request_params["limit"] = min(page_size, MAX_LIMIT)
    request_params.setdefault("offset", 0)

    yielded = 0
    path: str | None = endpoint
    while path:
        document = get(path, request_params if path == endpoint else None, base_url=base_url)
        records = document.get(key)
        if records is None:
            raise ChemblError(
                f"no `{key}` in the response for `{endpoint}` -- "
                f"got keys {sorted(document)[:8]}"
            )
        for record in records:
            yield record
            yielded += 1
            if limit is not None and yielded >= limit:
                return
        meta = document.get("page_meta") or {}
        if progress and meta.get("total_count") is not None:
            print(
                f"\r  fetched {yielded}/{meta['total_count']}", end="", file=sys.stderr, flush=True
            )
        path = meta.get("next")
    if progress:
        print("", file=sys.stderr)


def total_count(endpoint: str, params: Mapping[str, Any] | None = None, *, base_url: str = BASE_URL) -> int:
    """How many records a filter matches, without downloading them."""
    document = get(endpoint, {**(params or {}), "limit": 1}, base_url=base_url)
    return int((document.get("page_meta") or {}).get("total_count", 0))


def as_float(value: Any) -> float | None:
    """ChEMBL returns numbers as strings; this is the only safe way to compare."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def median(values: Sequence[float]) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def parse_filters(assignments: Iterable[str]) -> dict[str, str]:
    """Turn `field__lookup=value` strings into query parameters.

    A misspelled lookup suffix is not an error to the API -- it is read as
    part of the field name, and an unknown field returns 400. The check here
    catches the more dangerous case: a single `_` where a lookup needs two.
    """
    filters: dict[str, str] = {}
    for assignment in assignments:
        if "=" not in assignment:
            raise ChemblError(f"filter must be field=value, got `{assignment}`")
        field, _, value = assignment.partition("=")
        field = field.strip()
        for lookup in ("gte", "lte", "gt", "lt", "in", "exact", "iexact", "contains",
                       "icontains", "startswith", "istartswith", "endswith", "isnull",
                       "range", "regex", "search", "flexmatch"):
            if field.endswith(f"_{lookup}") and not field.endswith(f"__{lookup}"):
                raise ChemblError(
                    f"`{field}` looks like a lookup written with one underscore; "
                    f"ChEMBL lookups use two (`{field[: -len(lookup) - 1]}__{lookup}`). "
                    "Written this way it is read as a field name."
                )
        filters[field] = value.strip()
    return filters


def write_table(
    rows: Sequence[Mapping[str, Any]],
    columns: Sequence[str],
    *,
    stream=None,
    delimiter: str = "\t",
) -> None:
    stream = sys.stdout if stream is None else stream
    writer = csv.writer(stream, delimiter=delimiter, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(row.get(column)) for column in columns])


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, (list, tuple)):
        return "|".join(_cell(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, separators=(",", ":"))
    return str(value)


def emit(rows: Sequence[Mapping[str, Any]], columns: Sequence[str], output_format: str) -> None:
    if output_format == "json":
        json.dump(list(rows), sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif output_format == "csv":
        write_table(rows, columns, delimiter=",")
    else:
        write_table(rows, columns)


def add_common_arguments(parser) -> None:
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("tsv", "csv", "json"),
        default="tsv",
        help="output format (default: tsv)",
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help="override the API root (default: the public EBI endpoint)",
    )
