"""Shared HTTP, paging, and table helpers for the openFDA scripts.

Standard library only. openFDA is an unauthenticated REST service (a free key
only raises the rate limit), so a dependency would buy nothing.

Four behaviours of this API are encoded here because each one fails in a way
that looks like something else:

* **An empty result set is returned as HTTP 404**, with
  `{"error": {"code": "NOT_FOUND", "message": "No matches found!"}}`. Treating
  that as a transport failure turns "this drug has no reports" into a crash,
  so `get` converts it into an ordinary empty payload.
* **Asking for `limit` above 1000 returns HTTP 403 `API_KEY_MISSING`**, not a
  limit error -- the message tells you to get an API key, which does not
  actually raise the per-request cap. `clamp_limit` prevents the request.
* **`skip` is hard-capped at 25000** (HTTP 400 above it), so deep pagination is
  impossible: past 25k records you must narrow the search, not page further.
  `paged` stops with an explicit message instead of looping.
* **Counts are not paginated.** A `count=` query ignores `limit`'s usual
  meaning, returns `meta.results = null`, and yields at most 1000 terms.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterator, Mapping, Sequence

BASE_URL = os.environ.get("OPENFDA_API_URL", "https://api.fda.gov")
USER_AGENT = "drug-discovery-agent-skills-openfda/1.0"

TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 2.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

#: Per-request record cap. Above this the API answers 403 API_KEY_MISSING,
#: which is misleading -- a key raises the daily quota, not this ceiling.
MAX_LIMIT = 1000

#: Hard ceiling on `skip`. HTTP 400 above it, so the reachable window is the
#: first 25000 records of any search, key or no key.
MAX_SKIP = 25000

#: The drug endpoints this skill drives, and what one record represents.
DRUG_ENDPOINTS = {
    "event": "one adverse-event report submitted to FAERS",
    "label": "one Structured Product Label (SPL)",
    "drugsfda": "one FDA application (NDA/ANDA/BLA) with its products",
    "ndc": "one entry in the National Drug Code directory",
    "enforcement": "one recall enforcement report",
    "shortages": "one drug-shortage record",
}


class OpenFdaError(RuntimeError):
    """A transport or API-level failure worth surfacing to the caller."""


def api_key() -> str | None:
    """The optional free key that raises the daily quota to 120000 requests."""
    key = os.environ.get("OPENFDA_API_KEY", "").strip()
    return key or None


def clamp_limit(limit: int) -> int:
    """Keep `limit` inside the server's cap.

    Asking for more does not fail with a limit error -- it fails with
    `API_KEY_MISSING`, which sends people hunting for credentials that would
    not have helped.
    """
    return max(1, min(int(limit), MAX_LIMIT))


def get(
    endpoint: str,
    params: Mapping[str, Any] | None = None,
    *,
    base_url: str = BASE_URL,
    timeout: int = TIMEOUT_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
) -> dict[str, Any]:
    """GET a JSON document from openFDA, retrying transient failures.

    `endpoint` is a path such as `"drug/event"`; `.json` is appended if absent.
    A `NOT_FOUND` response becomes an empty payload rather than an exception,
    because openFDA reports "zero matches" as HTTP 404.
    """
    url = _build_url(endpoint, params, base_url)
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}

    last_error = "no attempt made"
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            code, message = _error_fields(body)
            if error.code == 404 and code == "NOT_FOUND":
                return {"meta": {"results": {"skip": 0, "limit": 0, "total": 0}}, "results": []}
            last_error = _explain(error.code, code, message, url)
            if error.code not in RETRYABLE_STATUS or attempt == max_attempts:
                raise OpenFdaError(last_error) from error
            _sleep_before_retry(attempt, error.headers.get("Retry-After"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = f"{type(error).__name__} for {url}: {error}"
            if attempt == max_attempts:
                raise OpenFdaError(last_error) from error
            _sleep_before_retry(attempt, None)
    raise OpenFdaError(last_error)  # pragma: no cover - the loop returns or raises


def _error_fields(body: str) -> tuple[str, str]:
    try:
        error = json.loads(body).get("error") or {}
    except json.JSONDecodeError:
        return "", body[:300]
    return str(error.get("code", "")), str(error.get("message", ""))


def _explain(status: int, code: str, message: str, url: str) -> str:
    """Turn openFDA's terser errors into something actionable."""
    if code == "API_KEY_MISSING":
        return (
            f"HTTP {status} {code} for {url}: {message} -- this is usually a "
            f"`limit` above {MAX_LIMIT}, not a credential problem. A key raises "
            "the daily quota, not the per-request cap; lower `limit` instead."
        )
    if status == 400 and "skip" in message.lower():
        return (
            f"HTTP {status} for {url}: {message} -- openFDA cannot page past "
            f"{MAX_SKIP} records. Narrow the search (by date range, route, or "
            "product) rather than paging further."
        )
    return f"HTTP {status} {code} for {url}: {message}".rstrip()


def _build_url(endpoint: str, params: Mapping[str, Any] | None, base_url: str) -> str:
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    path = endpoint.strip("/")
    if not path.endswith(".json"):
        path = f"{path}.json"
    query = {key: value for key, value in (params or {}).items() if value is not None}
    key = api_key()
    if key:
        query.setdefault("api_key", key)
    encoded = urllib.parse.urlencode(query, safe=":+[]{}\"")
    return f"{base_url}/{path}" + (f"?{encoded}" if encoded else "")


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
    search: str,
    *,
    limit: int | None = None,
    page_size: int = MAX_LIMIT,
    base_url: str = BASE_URL,
    progress: bool = False,
) -> Iterator[dict[str, Any]]:
    """Yield records from a search, advancing `skip` until the window closes.

    Stops at `MAX_SKIP` with a message on stderr rather than raising -- hitting
    the ceiling means the search was too broad, and the caller usually still
    wants the 25000 records already retrieved.
    """
    page_size = clamp_limit(page_size)
    skip = 0
    yielded = 0
    while True:
        document = get(
            endpoint,
            {"search": search, "limit": page_size, "skip": skip},
            base_url=base_url,
        )
        records = document.get("results") or []
        if not records:
            break
        for record in records:
            yield record
            yielded += 1
            if limit is not None and yielded >= limit:
                return
        total = ((document.get("meta") or {}).get("results") or {}).get("total")
        if progress and total is not None:
            print(f"\r  fetched {yielded}/{total}", end="", file=sys.stderr, flush=True)
        skip += len(records)
        if total is not None and skip >= total:
            break
        if skip >= MAX_SKIP:
            print(
                f"\nstopped at the openFDA skip ceiling ({MAX_SKIP} records) with "
                f"{total} matching; narrow the search to see the rest",
                file=sys.stderr,
            )
            break
    if progress:
        print("", file=sys.stderr)


def count_terms(
    endpoint: str,
    search: str | None,
    field: str,
    *,
    limit: int = 100,
    base_url: str = BASE_URL,
) -> list[dict[str, Any]]:
    """Run a `count=` aggregation and return its `[{term, count}, ...]` list.

    Counts are computed server-side over the whole matching set, not over one
    page, so this is the only honest way to rank anything above 25000 records.
    Use an `.exact` field suffix unless you want tokenised counting.
    """
    document = get(
        endpoint,
        {"search": search, "count": field, "limit": clamp_limit(limit)},
        base_url=base_url,
    )
    return list(document.get("results") or [])


def total_matching(endpoint: str, search: str, *, base_url: str = BASE_URL) -> int:
    """How many records a search matches, without downloading them."""
    document = get(endpoint, {"search": search, "limit": 1}, base_url=base_url)
    return int(((document.get("meta") or {}).get("results") or {}).get("total", 0))


def last_updated(endpoint: str, *, base_url: str = BASE_URL) -> str:
    """The `meta.last_updated` stamp -- FAERS lags reality by a quarter or more."""
    document = get(endpoint, {"limit": 1}, base_url=base_url)
    return str((document.get("meta") or {}).get("last_updated", "unknown"))


def quote(value: str) -> str:
    """Quote a search value so spaces do not split it into two terms."""
    cleaned = value.replace('"', "")
    return f'"{cleaned}"' if " " in cleaned else cleaned


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
        help="override the API root (default: the public openFDA endpoint)",
    )
