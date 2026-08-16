"""Shared HTTP and table helpers for the patent-landscape scripts.

Standard library only.

Four behaviours are encoded here because each one surprises people:

* **SureChEMBL has no public REST API.** Checked live: `/api/*` on
  surechembl.org returns 404. Everything programmatic goes through the EMBL-EBI
  bulk tree, which is large -- the compound, patent, and mapping tables are
  about 15 GB together.
* **The bulk format changed with SureChEMBL 2.0.** Current releases are
  Parquet plus an FPSim2 fingerprint index, released fortnightly. The legacy
  `data/` directory still holds the old quarterly txt and SDF dumps, last
  described by a 2016 README, and it is not the same data.
* **PatentsView needs a free API key** and returns a connection failure rather
  than a 401 without one, which looks like a network problem.
* Nothing here is a freedom-to-operate opinion. A structure search finds
  disclosed compounds; it does not read claims, and claims are what infringe.
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
from typing import Any, Mapping, Sequence

SURECHEMBL_FTP = os.environ.get(
    "SURECHEMBL_FTP", "https://ftp.ebi.ac.uk/pub/databases/chembl/SureChEMBL"
)
PATENTSVIEW_URL = os.environ.get(
    "PATENTSVIEW_URL", "https://search.patentsview.org/api/v1"
)
USER_AGENT = "drug-discovery-agent-skills-patent-landscape/1.0"

TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 2.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

#: The Parquet tables in a SureChEMBL 2.0 bulk release, and what each holds.
BULK_TABLES = {
    "compounds.parquet": "one row per extracted compound: id, SMILES, InChI, InChIKey",
    "patents.parquet": "one row per patent document: id, title, dates, classifications",
    "patent_compound_map.parquet": "the join between them, with the field the compound came from",
    "biomedical_entities.parquet": "recognised genes, proteins, diseases mentioned",
    "biomedical_locations.parquet": "where in the document each entity occurred",
    "biomedical_types.parquet": "the entity type vocabulary",
    "fields.parquet": "the document-field vocabulary (title, abstract, claims, description, image)",
    "fpsim2_fingerprints.h5": "an FPSim2 index for local similarity search over the compounds",
}

#: The document fields a compound can be extracted from, most to least
#: legally meaningful.
DOCUMENT_FIELDS = (
    "claims",
    "title",
    "abstract",
    "description",
    "image",
    "attachment",
)


class PatentError(RuntimeError):
    """A transport or configuration failure worth surfacing to the caller."""


def patentsview_key() -> str | None:
    key = os.environ.get("PATENTSVIEW_API_KEY", "").strip()
    return key or None


def get(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: int = TIMEOUT_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
) -> str:
    """GET a URL and return the body as text, retrying transient failures."""
    request_headers = {"User-Agent": USER_AGENT, **(headers or {})}

    last_error = "no attempt made"
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, headers=request_headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            last_error = _explain(error.code, detail, url)
            if error.code not in RETRYABLE_STATUS or attempt == max_attempts:
                raise PatentError(last_error) from error
            _sleep_before_retry(attempt, error.headers.get("Retry-After"))
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = (
                f"{type(error).__name__} for {url}: {error}. If this is PatentsView, "
                "an absent API key shows up as a connection failure rather than a 401."
            )
            if attempt == max_attempts:
                raise PatentError(last_error) from error
            _sleep_before_retry(attempt, None)
    raise PatentError(last_error)  # pragma: no cover - loop returns or raises


def _explain(status: int, detail: str, url: str) -> str:
    if status in (401, 403) and "patentsview" in url:
        return (
            f"HTTP {status} for {url}: {detail} -- PatentsView needs a free API key. "
            "Request one at patentsview.org/apis and set PATENTSVIEW_API_KEY."
        )
    if status == 404 and "surechembl.org" in url:
        return (
            f"HTTP 404 for {url}: SureChEMBL has no public REST API. Use the bulk "
            f"tree at {SURECHEMBL_FTP} instead."
        )
    return f"HTTP {status} for {url}: {detail}"


def _sleep_before_retry(attempt: int, retry_after: str | None) -> None:
    delay = BACKOFF_BASE_SECONDS ** attempt
    if retry_after:
        try:
            delay = max(delay, float(retry_after))
        except ValueError:
            pass
    time.sleep(min(delay, 30.0))


def get_json(url: str, *, headers: Mapping[str, str] | None = None) -> Any:
    body = get(url, headers=headers)
    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise PatentError(f"{url} did not return JSON: {body[:200]}") from error


def list_directory(url: str) -> list[str]:
    """Entry names from an EBI FTP-over-HTTPS directory listing."""
    body = get(url if url.endswith("/") else f"{url}/")
    names = []
    for match in _href_values(body):
        if match.startswith(("/", "?", "http")):
            continue
        names.append(match)
    return sorted(set(names))


def _href_values(body: str) -> list[str]:
    values = []
    cursor = 0
    needle = 'href="'
    while True:
        start = body.find(needle, cursor)
        if start == -1:
            return values
        start += len(needle)
        end = body.find('"', start)
        if end == -1:
            return values
        values.append(body[start:end])
        cursor = end


def content_length(url: str) -> int | None:
    """Size in bytes from a HEAD request, or None when the server declines."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            value = response.headers.get("Content-Length")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def human_bytes(size: int | None) -> str:
    if size is None:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024.0
    return ""  # pragma: no cover - the loop always returns


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
