"""Shared transport for the gnomAD GraphQL and GWAS Catalog REST clients.

Standard library only. Both services are unauthenticated, so a dependency
would buy nothing.

Four behaviours are encoded here because each one is quiet rather than loud:

* **gnomAD returns GraphQL errors with HTTP 200.** A misspelled field or an
  unknown gene arrives as `{"errors": [...]}` in a successful response, so a
  client that only checks the status code reads `None` and reports no
  constraint data for a gene that simply was not found.
* **The GWAS Catalog silently ignores unrecognised query parameters.** Asking
  for `?gene=LRRK2` (the wrong name -- it is `mappedGene`) does not 400. It
  returns the entire unfiltered catalogue: 1142122 associations instead of 93.
  `gwas_get` refuses parameters that are not on the known list.
* **The GWAS Catalog is slow.** Six to ten seconds for a single page is normal,
  so the timeout here is deliberately generous.
* **Constraint is absent for many genes**, not zero. A gene with no
  `gnomad_constraint` block has too little coverage to estimate, which is not
  the same as being unconstrained.
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

GNOMAD_URL = os.environ.get("GNOMAD_API_URL", "https://gnomad.broadinstitute.org/api")
GWAS_URL = os.environ.get("GWAS_API_URL", "https://www.ebi.ac.uk/gwas/rest/api/v2")
USER_AGENT = "drug-discovery-agent-skills-target-safety/1.0"

#: The GWAS Catalog routinely takes 6-10 s for one page.
TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 2.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

MAX_PAGE_SIZE = 500

#: Query parameters the associations endpoint actually honours. Anything else
#: is ignored in silence and you get the whole catalogue back.
GWAS_ASSOCIATION_PARAMS = frozenset(
    {"mappedGene", "efoTrait", "reportedTrait", "accessionId", "rsId", "page", "size", "sort"}
)

#: LOEUF bands. gnomAD recommends LOEUF over pLI: it is a continuous measure
#: with a confidence interval, where pLI is a posterior forced toward 0 or 1.
LOEUF_BANDS = (
    (0.35, "constrained", "loss of function is depleted in humans; systemic inhibition carries risk"),
    (0.60, "moderately constrained", "some depletion; check tissue and dose dependence"),
    (1.00, "tolerant", "loss of function is roughly as common as expected"),
    (float("inf"), "unconstrained", "loss of function is well tolerated; human knockouts likely exist"),
)

#: Genome-wide significance. Anything weaker is a candidate, not a finding.
GWAS_SIGNIFICANCE = 5e-8


class TargetSafetyError(RuntimeError):
    """A transport or API-level failure worth surfacing to the caller."""


# --------------------------------------------------------------------------
# gnomAD (GraphQL)
# --------------------------------------------------------------------------


def gnomad_post(
    query: str,
    variables: Mapping[str, Any] | None = None,
    *,
    api_url: str = GNOMAD_URL,
    timeout: int = TIMEOUT_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
) -> dict[str, Any]:
    """POST a GraphQL document to gnomAD and return `data`, raising on `errors`.

    gnomAD answers schema and lookup errors with HTTP 200 and an `errors`
    array, so the status code alone never tells you the request worked.
    """
    body = json.dumps({"query": query, "variables": dict(variables or {})}).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    last_error = "no attempt made"
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(api_url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                document = json.loads(response.read().decode("utf-8"))
            errors = document.get("errors")
            if errors:
                messages = "; ".join(str(error.get("message", error)) for error in errors)
                raise TargetSafetyError(f"gnomAD GraphQL error: {messages}")
            return document.get("data") or {}
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:400]
            last_error = f"HTTP {error.code} for {api_url}: {detail}"
            if error.code not in RETRYABLE_STATUS or attempt == max_attempts:
                raise TargetSafetyError(last_error) from error
            _sleep_before_retry(attempt, error.headers.get("Retry-After"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = f"{type(error).__name__} for {api_url}: {error}"
            if attempt == max_attempts:
                raise TargetSafetyError(last_error) from error
            _sleep_before_retry(attempt, None)
    raise TargetSafetyError(last_error)  # pragma: no cover - loop returns or raises


# --------------------------------------------------------------------------
# GWAS Catalog (REST)
# --------------------------------------------------------------------------


def gwas_get(
    path: str,
    params: Mapping[str, Any] | None = None,
    *,
    base_url: str = GWAS_URL,
    timeout: int = TIMEOUT_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
    known_params: frozenset[str] | None = None,
) -> dict[str, Any]:
    """GET a JSON document from the GWAS Catalog, refusing unknown parameters.

    The service ignores parameters it does not recognise instead of rejecting
    them, so `?gene=X` silently returns every association in the catalogue.
    Validating locally is the only way to notice.
    """
    supplied = {key: value for key, value in (params or {}).items() if value is not None}
    if known_params is not None:
        unknown = sorted(set(supplied) - known_params)
        if unknown:
            raise TargetSafetyError(
                f"{', '.join(unknown)} is not a recognised filter. The GWAS Catalog "
                f"ignores unknown parameters silently and returns the whole "
                f"catalogue; accepted here are {', '.join(sorted(known_params))}."
            )

    query = urllib.parse.urlencode(supplied)
    url = f"{base_url}/{path.lstrip('/')}" + (f"?{query}" if query else "")
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}

    last_error = "no attempt made"
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            last_error = f"HTTP {error.code} for {url}: {detail}"
            if error.code not in RETRYABLE_STATUS or attempt == max_attempts:
                raise TargetSafetyError(last_error) from error
            _sleep_before_retry(attempt, error.headers.get("Retry-After"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = f"{type(error).__name__} for {url}: {error}"
            if attempt == max_attempts:
                raise TargetSafetyError(last_error) from error
            _sleep_before_retry(attempt, None)
    raise TargetSafetyError(last_error)  # pragma: no cover - loop returns or raises


def gwas_paged(
    path: str,
    params: Mapping[str, Any],
    key: str,
    *,
    limit: int | None = None,
    page_size: int = 100,
    base_url: str = GWAS_URL,
    known_params: frozenset[str] | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield records from a HAL-paged collection."""
    request_params = dict(params)
    request_params["size"] = min(page_size, MAX_PAGE_SIZE)
    page = 0
    yielded = 0
    while True:
        request_params["page"] = page
        document = gwas_get(
            path, request_params, base_url=base_url, known_params=known_params
        )
        records = (document.get("_embedded") or {}).get(key) or []
        if not records:
            return
        for record in records:
            yield record
            yielded += 1
            if limit is not None and yielded >= limit:
                return
        meta = document.get("page") or {}
        page += 1
        if page >= int(meta.get("totalPages", 0)):
            return


def _sleep_before_retry(attempt: int, retry_after: str | None) -> None:
    delay = BACKOFF_BASE_SECONDS ** attempt
    if retry_after:
        try:
            delay = max(delay, float(retry_after))
        except ValueError:
            pass
    time.sleep(min(delay, 30.0))


# --------------------------------------------------------------------------
# Interpretation
# --------------------------------------------------------------------------


def loeuf_band(loeuf: float | None) -> tuple[str, str]:
    """Map a LOEUF value onto its band and what the band implies for a target."""
    if loeuf is None:
        return ("unknown", "no constraint estimate; usually too little coverage, not zero constraint")
    for ceiling, label, meaning in LOEUF_BANDS:
        if loeuf < ceiling:
            return (label, meaning)
    return ("unconstrained", "")  # pragma: no cover - the last band is unbounded


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
        return f"{value:.4g}"
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
        "--gnomad-url", default=GNOMAD_URL, help="override the gnomAD GraphQL endpoint"
    )
    parser.add_argument(
        "--gwas-url", default=GWAS_URL, help="override the GWAS Catalog REST root"
    )
