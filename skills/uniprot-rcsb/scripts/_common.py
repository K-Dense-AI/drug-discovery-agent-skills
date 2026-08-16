"""Shared HTTP and table helpers for the UniProt / RCSB / AlphaFold scripts.

Standard library only. All three services are unauthenticated HTTPS.

The two service-specific behaviours encoded here:

* UniProt paginates with an **RFC 5988 `Link` header**, not a field in the
  body. A client that reads only the JSON silently stops at the first page --
  which looks like "only 25 kinases are reviewed".
* RCSB's search API is POST-with-a-JSON-body and returns **HTTP 204 with an
  empty body** when nothing matches. `json.loads("")` raises, so a naive
  client reports a parse error instead of "no hits".
"""

from __future__ import annotations

import csv
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterator, Mapping, Sequence

USER_AGENT = "drug-discovery-agent-skills-uniprot-rcsb/1.0"

UNIPROT_REST = "https://rest.uniprot.org"
RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_DATA = "https://data.rcsb.org/rest/v1/core"
RCSB_GRAPHQL = "https://data.rcsb.org/graphql"
RCSB_FILES = "https://files.rcsb.org/download"
ALPHAFOLD_API = "https://alphafold.ebi.ac.uk/api/prediction"

TIMEOUT_SECONDS = 90
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 2.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')


class ServiceError(RuntimeError):
    """A transport or API-level failure worth surfacing to the caller."""


def request_bytes(
    url: str,
    *,
    data: bytes | None = None,
    headers: Mapping[str, str] | None = None,
    method: str | None = None,
    timeout: int = TIMEOUT_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
) -> tuple[int, dict[str, str], bytes]:
    """Perform one request, retrying transient failures. Returns (status, headers, body)."""
    merged = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    merged.update(headers or {})

    last_error = "no attempt made"
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, data=data, headers=merged, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, dict(response.headers), _decoded(response.read())
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:400]
            last_error = f"HTTP {error.code} for {url}: {detail}"
            if error.code not in RETRYABLE_STATUS or attempt == max_attempts:
                raise ServiceError(last_error) from error
            _sleep_before_retry(attempt, error.headers.get("Retry-After"))
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = f"{type(error).__name__} for {url}: {error}"
            if attempt == max_attempts:
                raise ServiceError(last_error) from error
            _sleep_before_retry(attempt, None)
    raise ServiceError(last_error)  # pragma: no cover


#: urllib does not decompress, so a gzip-encoded reply arrives raw. One round
#: is not always enough: UniProt serves some payloads that are *already* gzip
#: on disk and then applies transport gzip on top, so `Accept-Encoding: gzip`
#: yields a doubly-wrapped stream. Decompressing once leaves bytes that still
#: start with the gzip magic, and the failure surfaces far away as a
#: UnicodeDecodeError on byte 1. Loop on the magic bytes, bounded so a
#: pathological payload cannot spin.
MAX_GZIP_ROUNDS = 3


def _decoded(body: bytes) -> bytes:
    for _ in range(MAX_GZIP_ROUNDS):
        if body[:2] != b"\x1f\x8b":
            return body
        body = gzip.decompress(body)
    return body


def _sleep_before_retry(attempt: int, retry_after: str | None) -> None:
    delay = BACKOFF_BASE_SECONDS ** attempt
    if retry_after:
        try:
            delay = max(delay, float(retry_after))
        except ValueError:
            pass
    time.sleep(min(delay, 30.0))


def get_json(url: str, params: Mapping[str, Any] | None = None) -> Any:
    """GET a JSON document. Returns None for an empty 204 body."""
    if params:
        query = urllib.parse.urlencode(
            {key: value for key, value in params.items() if value is not None}
        )
        url = f"{url}?{query}"
    status, _, body = request_bytes(url, headers={"Accept": "application/json"})
    if status == 204 or not body.strip():
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ServiceError(f"non-JSON response from {url}: {body[:200]!r}") from error


def post_json(url: str, payload: Mapping[str, Any]) -> Any:
    """POST a JSON body and parse the reply. `None` when the service answers 204.

    RCSB's search service uses 204-with-no-body for "no hits", which is a
    successful request with an empty result -- not a parse failure.
    """
    status, _, body = request_bytes(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    if status == 204 or not body.strip():
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ServiceError(f"non-JSON response from {url}: {body[:200]!r}") from error


def uniprot_pages(url: str, params: Mapping[str, Any] | None = None) -> Iterator[Any]:
    """Yield each page of a UniProt search, following the `Link: rel="next"` header.

    UniProt puts pagination in an HTTP header rather than the payload, so a
    client that reads only the body stops after the first page and reports a
    truncated result as a complete one.
    """
    if params:
        query = urllib.parse.urlencode(
            {key: value for key, value in params.items() if value is not None}
        )
        url = f"{url}?{query}"
    while url:
        status, headers, body = request_bytes(url, headers={"Accept": "application/json"})
        if status == 204 or not body.strip():
            return
        text = body.decode("utf-8")
        yield json.loads(text) if text.lstrip().startswith(("{", "[")) else text
        match = _NEXT_LINK.search(headers.get("Link", "") or "")
        url = match.group(1) if match else ""


#: A guard, not a policy. The largest structures in the PDB are a few hundred
#: MB of mmCIF; anything past this is a mistyped identifier or a redirect to
#: something that is not a structure file, and streaming it to disk unbounded
#: is how a batch download fills a volume.
MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024


def download(
    url: str,
    destination,
    *,
    timeout: int = TIMEOUT_SECONDS,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
) -> int:
    """Fetch a file to `destination`, returning its size in bytes."""
    _, _, body = request_bytes(url, timeout=timeout)
    if len(body) > max_bytes:
        raise ServiceError(
            f"{url} returned {len(body)} bytes, above the {max_bytes}-byte cap. "
            "Check the identifier, or raise max_bytes deliberately."
        )
    destination = str(destination)
    with open(destination, "wb") as handle:
        handle.write(body)
    return len(body)


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
