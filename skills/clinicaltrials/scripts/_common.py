"""Shared HTTP, paging, and field-extraction helpers for the ClinicalTrials.gov scripts.

Standard library only. The version 2 API is an unauthenticated REST service, so
a dependency would buy nothing.

Four behaviours of this API are encoded here because each one is quiet rather
than loud:

* **Paging is by opaque cursor, not offset.** The response carries
  `nextPageToken`; there is no `skip`, and a token is only valid for the query
  that produced it. `paged` follows the cursor, which also means there is no
  25000-record ceiling of the kind openFDA imposes.
* **`totalCount` is opt-in.** Without `countTotal=true` the response has no
  total at all, so code that reads `totalCount` gets `None` and reports zero.
* **A study is a nest of modules**, not a flat record. `phases` lives at
  `protocolSection.designModule.phases`, enrolment two levels down from there.
  `dig` exists so a typo in a path returns a default instead of an exception.
* **Enum filters are validated server-side.** `filter.overallStatus=Completed`
  is a 400 -- the values are upper snake case. The vocabularies below are the
  accepted sets, checked against the live API.
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

BASE_URL = os.environ.get("CTGOV_API_URL", "https://clinicaltrials.gov/api/v2")
USER_AGENT = "drug-discovery-agent-skills-clinicaltrials/1.0"

TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 2.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

#: Server cap on `pageSize`. Above this the API clamps silently.
MAX_PAGE_SIZE = 1000

#: Accepted `filter.overallStatus` values. Upper snake case; anything else 400s.
STATUSES = (
    "NOT_YET_RECRUITING",
    "RECRUITING",
    "ENROLLING_BY_INVITATION",
    "ACTIVE_NOT_RECRUITING",
    "SUSPENDED",
    "TERMINATED",
    "COMPLETED",
    "WITHDRAWN",
    "UNKNOWN",
)

#: Accepted phase values. `NA` covers device, behavioural, and observational
#: studies -- it does not mean "phase unknown".
PHASES = ("EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4", "NA")

#: A status that means the study stopped before answering its question.
STOPPED = frozenset({"TERMINATED", "WITHDRAWN", "SUSPENDED"})


class ClinicalTrialsError(RuntimeError):
    """A transport or API-level failure worth surfacing to the caller."""


def get(
    path: str,
    params: Mapping[str, Any] | None = None,
    *,
    base_url: str = BASE_URL,
    timeout: int = TIMEOUT_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
) -> dict[str, Any]:
    """GET a JSON document from the registry, retrying transient failures."""
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
            last_error = _explain(error.code, detail, url)
            if error.code not in RETRYABLE_STATUS or attempt == max_attempts:
                raise ClinicalTrialsError(last_error) from error
            _sleep_before_retry(attempt, error.headers.get("Retry-After"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = f"{type(error).__name__} for {url}: {error}"
            if attempt == max_attempts:
                raise ClinicalTrialsError(last_error) from error
            _sleep_before_retry(attempt, None)
    raise ClinicalTrialsError(last_error)  # pragma: no cover - loop returns or raises


def _explain(status: int, detail: str, url: str) -> str:
    if status == 400 and "status" in detail.lower():
        return (
            f"HTTP {status} for {url}: {detail} -- status values are upper snake "
            f"case; accepted values are {', '.join(STATUSES)}"
        )
    if status == 404:
        return f"HTTP 404 for {url}: no such study. NCT ids look like NCT01234567."
    return f"HTTP {status} for {url}: {detail}"


def _build_url(path: str, params: Mapping[str, Any] | None, base_url: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    query = {key: value for key, value in (params or {}).items() if value is not None}
    encoded = urllib.parse.urlencode(query, safe=",|[]")
    return f"{base_url}/{path.lstrip('/')}" + (f"?{encoded}" if encoded else "")


def _sleep_before_retry(attempt: int, retry_after: str | None) -> None:
    delay = BACKOFF_BASE_SECONDS ** attempt
    if retry_after:
        try:
            delay = max(delay, float(retry_after))
        except ValueError:
            pass
    time.sleep(min(delay, 30.0))


def paged(
    params: Mapping[str, Any],
    *,
    limit: int | None = None,
    page_size: int = 100,
    base_url: str = BASE_URL,
    progress: bool = False,
) -> Iterator[dict[str, Any]]:
    """Yield studies, following `nextPageToken` until the cursor runs out."""
    request_params = dict(params)
    request_params["pageSize"] = min(page_size, MAX_PAGE_SIZE)
    request_params["countTotal"] = "true"

    yielded = 0
    token: str | None = None
    total: int | None = None
    while True:
        if token:
            request_params["pageToken"] = token
        document = get("studies", request_params, base_url=base_url)
        if total is None:
            total = document.get("totalCount")
        studies = document.get("studies") or []
        if not studies:
            break
        for study in studies:
            yield study
            yielded += 1
            if limit is not None and yielded >= limit:
                return
        if progress and total is not None:
            print(f"\r  fetched {yielded}/{total}", end="", file=sys.stderr, flush=True)
        token = document.get("nextPageToken")
        if not token:
            break
    if progress:
        print("", file=sys.stderr)


def total_count(params: Mapping[str, Any], *, base_url: str = BASE_URL) -> int:
    """How many studies a query matches.

    `countTotal=true` is required -- without it the response carries no total
    and any code reading `totalCount` silently sees nothing.
    """
    document = get(
        "studies",
        {**params, "pageSize": 1, "countTotal": "true"},
        base_url=base_url,
    )
    return int(document.get("totalCount") or 0)


def dig(record: Mapping[str, Any] | None, path: str, default: Any = None) -> Any:
    """Walk a dotted path through the module nest, returning `default` on a miss.

    Studies are deeply nested and most modules are optional, so a direct
    subscript raises far more often than it succeeds.
    """
    current: Any = record
    for key in path.split("."):
        if not isinstance(current, Mapping):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def summarise(study: Mapping[str, Any]) -> dict[str, Any]:
    """The fields worth putting in a table, pulled out of the module nest."""
    protocol = study.get("protocolSection") or {}
    return {
        "nct_id": dig(protocol, "identificationModule.nctId"),
        "title": dig(protocol, "identificationModule.briefTitle"),
        "status": dig(protocol, "statusModule.overallStatus"),
        "why_stopped": dig(protocol, "statusModule.whyStopped"),
        "phase": "|".join(dig(protocol, "designModule.phases", []) or []),
        "study_type": dig(protocol, "designModule.studyType"),
        "enrollment": dig(protocol, "designModule.enrollmentInfo.count"),
        "enrollment_type": dig(protocol, "designModule.enrollmentInfo.type"),
        "sponsor": dig(protocol, "sponsorCollaboratorsModule.leadSponsor.name"),
        "start": dig(protocol, "statusModule.startDateStruct.date"),
        "completion": dig(protocol, "statusModule.completionDateStruct.date"),
        "conditions": dig(protocol, "conditionsModule.conditions", []),
        "interventions": [
            item.get("name")
            for item in dig(protocol, "armsInterventionsModule.interventions", []) or []
            if item.get("name")
        ],
        "has_results": bool(study.get("hasResults")),
    }


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
        help="override the API root (default: the public registry endpoint)",
    )


def add_query_arguments(parser) -> None:
    """The search selectors shared by every command that takes a query."""
    parser.add_argument("--condition", help="disease or condition, e.g. 'non-small cell lung cancer'")
    parser.add_argument("--intervention", help="drug or treatment name")
    parser.add_argument("--sponsor", help="lead sponsor or collaborator")
    parser.add_argument("--term", help="free-text search across the record")
    parser.add_argument(
        "--status",
        action="append",
        help=f"repeatable; one of {', '.join(STATUSES)}",
    )
    parser.add_argument(
        "--phase",
        action="append",
        help=f"repeatable; one of {', '.join(PHASES)}",
    )


def build_query(args) -> dict[str, Any]:
    """Turn the shared selectors into API query parameters, validating enums."""
    params: dict[str, Any] = {}
    if getattr(args, "condition", None):
        params["query.cond"] = args.condition
    if getattr(args, "intervention", None):
        params["query.intr"] = args.intervention
    if getattr(args, "sponsor", None):
        params["query.spons"] = args.sponsor
    if getattr(args, "term", None):
        params["query.term"] = args.term

    statuses = getattr(args, "status", None) or []
    for status in statuses:
        if status not in STATUSES:
            raise ClinicalTrialsError(
                f"`{status}` is not a valid status. Accepted: {', '.join(STATUSES)}"
            )
    if statuses:
        params["filter.overallStatus"] = ",".join(statuses)

    phases = getattr(args, "phase", None) or []
    for phase in phases:
        if phase not in PHASES:
            raise ClinicalTrialsError(
                f"`{phase}` is not a valid phase. Accepted: {', '.join(PHASES)}"
            )
    if phases:
        params["filter.advanced"] = " AND ".join(f"AREA[Phase]{phase}" for phase in phases)

    if not params:
        raise ClinicalTrialsError(
            "give at least one of --condition, --intervention, --sponsor, or --term"
        )
    return params
