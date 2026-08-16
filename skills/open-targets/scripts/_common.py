"""Shared GraphQL transport and output helpers for the Open Targets scripts.

Standard library only: the Open Targets Platform API is an unauthenticated
HTTPS POST endpoint, so a dependency would buy nothing and cost an install.

Everything here is deliberately boring except two behaviours worth knowing:

* GraphQL answers `200 OK` with an `errors` array when a query is wrong, so a
  naive client reports success on a typo. `post` raises on any `errors` entry.
* The API rate-limits with `429` and occasionally `502`/`503` behind its CDN.
  `post` retries those with exponential backoff and honours `Retry-After`.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Iterable, Mapping, Sequence

API_URL = os.environ.get(
    "OPEN_TARGETS_API_URL", "https://api.platform.opentargets.org/api/v4/graphql"
)
USER_AGENT = "drug-discovery-agent-skills-open-targets/1.0"

TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 2.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

#: The API caps `page.size`. Ask for more and the request is rejected outright
#: rather than silently truncated, so paged callers must respect it.
MAX_PAGE_SIZE = 500


class OpenTargetsError(RuntimeError):
    """A GraphQL-level or transport-level failure that callers should surface."""


def post(
    query: str,
    variables: Mapping[str, Any] | None = None,
    *,
    url: str = API_URL,
    timeout: int = TIMEOUT_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
) -> dict[str, Any]:
    """Execute one GraphQL document and return its `data` object.

    Raises `OpenTargetsError` on transport failure, on a non-retryable HTTP
    status, or when the response carries a GraphQL `errors` array -- including
    the partial case where `data` is present alongside `errors`, because a
    half-filled result read as a complete one is the worst outcome here.
    """
    body = json.dumps({"query": query, "variables": dict(variables or {})}).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }

    last_error: str = "no attempt made"
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:500]
            last_error = f"HTTP {error.code}: {detail}"
            if error.code not in RETRYABLE_STATUS or attempt == max_attempts:
                raise OpenTargetsError(last_error) from error
            _sleep_before_retry(attempt, error.headers.get("Retry-After"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = f"{type(error).__name__}: {error}"
            if attempt == max_attempts:
                raise OpenTargetsError(last_error) from error
            _sleep_before_retry(attempt, None)
    else:  # pragma: no cover - the loop always breaks or raises
        raise OpenTargetsError(last_error)

    if payload.get("errors"):
        messages = "; ".join(
            str(item.get("message", item)) for item in payload["errors"][:5]
        )
        raise OpenTargetsError(f"GraphQL error: {messages}")
    data = payload.get("data")
    if data is None:
        raise OpenTargetsError("response carried neither `data` nor `errors`")
    return data


def _sleep_before_retry(attempt: int, retry_after: str | None) -> None:
    delay = BACKOFF_BASE_SECONDS ** attempt
    if retry_after:
        try:
            delay = max(delay, float(retry_after))
        except ValueError:
            pass
    time.sleep(min(delay, 30.0))


def paged(
    query: str,
    variables: Mapping[str, Any],
    *,
    path: Sequence[str],
    size: int = 50,
    limit: int | None = None,
    url: str = API_URL,
) -> Iterable[dict[str, Any]]:
    """Yield `rows` from a paginated field, following `page: {index, size}`.

    `path` names the keys from `data` down to the object holding `count` and
    `rows`, e.g. `("target", "associatedDiseases")`. The caller's query must
    accept `$index` and `$size` variables and select both `count` and `rows`.

    Open Targets pages by index, not cursor, so a page beyond the end returns
    an empty `rows` rather than an error -- that, `count`, and `limit` are the
    three stop conditions.
    """
    size = max(1, min(size, MAX_PAGE_SIZE))
    yielded = 0
    index = 0
    while True:
        data = post(query, {**variables, "index": index, "size": size}, url=url)
        node: Any = data
        for key in path:
            if node is None:
                raise OpenTargetsError(
                    f"no object at `{'.'.join(path)}` -- check the identifier exists"
                )
            node = node.get(key)
        if node is None:
            raise OpenTargetsError(
                f"no object at `{'.'.join(path)}` -- check the identifier exists"
            )
        rows = node.get("rows") or []
        for row in rows:
            yield row
            yielded += 1
            if limit is not None and yielded >= limit:
                return
        total = node.get("count")
        index += 1
        if not rows or (total is not None and index * size >= total):
            return


def write_table(
    rows: Sequence[Mapping[str, Any]],
    columns: Sequence[str],
    *,
    stream=None,
    delimiter: str = "\t",
) -> None:
    """Write rows as a delimited table with a fixed column order."""
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


def emit(payload: Any, *, output_format: str, columns: Sequence[str] | None = None) -> None:
    """Print `payload` as JSON, or as a table when the caller supplied columns."""
    if output_format == "json" or columns is None:
        json.dump(payload, sys.stdout, indent=2, sort_keys=False)
        sys.stdout.write("\n")
        return
    rows = payload if isinstance(payload, list) else [payload]
    write_table(rows, columns)


def add_common_arguments(parser) -> None:
    """Options every Open Targets CLI in this skill accepts."""
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("json", "tsv"),
        default="tsv",
        help="output format (default: tsv)",
    )
    parser.add_argument(
        "--api-url",
        default=API_URL,
        help="override the GraphQL endpoint (default: the public Platform API)",
    )
