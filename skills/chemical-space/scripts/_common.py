"""Shared transport and identifier helpers for the CartBlanche/ZINC-22 client.

Standard library only. CartBlanche is unauthenticated, so a dependency would
buy nothing.

Four behaviours are encoded here because each one is quiet rather than loud:

* **An unknown route returns HTTP 200 with an HTML single-page-app shell, and
  a `Content-Type: application/json` header.** Checked live: `/tranches.json`
  and `/substance.json?zinc_id=...` both answer 200 and claim JSON while
  returning `<!doctype html>`. Neither the status code nor the header can be
  trusted; only parsing the body can. `get_json` raises on a shell response.
* **Only one route is reliably JSON**: `/substance/<ZINC id>.json`. The plural
  and query-string forms that look like they should work are shells.
* **ZINC identifiers are zero-padded to twelve digits.** `ZINC53` and
  `ZINC000000000053` are the same substance, but only the padded form
  resolves. `normalise_zinc_id` pads.
* **A substance existing is not the same as it being purchasable.** The
  `catalogs` block carries price, supplier, and lead time, and it can be empty
  for a substance that is only computationally enumerated.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping, Sequence

BASE_URL = os.environ.get("CARTBLANCHE_URL", "https://cartblanche.docking.org")
USER_AGENT = "drug-discovery-agent-skills-chemical-space/1.0"

TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 2.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

ZINC_PATTERN = re.compile(r"^(?:ZINC)?0*(\d+)$", re.IGNORECASE)

#: ZINC-22 scale, from the 2023 J. Chem. Inf. Model. paper and the current site.
ZINC22_2D_COMPOUNDS = 54_900_000_000
ZINC22_3D_COMPOUNDS = 5_900_000_000

#: Enamine REAL Space, synthon-enumerable rather than stored.
ENAMINE_REAL_SPACE = 94_000_000_000


class ChemicalSpaceError(RuntimeError):
    """A transport or lookup failure worth surfacing to the caller."""


def normalise_zinc_id(value: str) -> str:
    """Return the twelve-digit padded form, the only one the API resolves."""
    match = ZINC_PATTERN.match(value.strip())
    if not match:
        raise ChemicalSpaceError(
            f"`{value}` is not a ZINC identifier. They look like ZINC000019632618 "
            "-- the letters ZINC followed by digits, zero-padded to twelve."
        )
    return f"ZINC{int(match.group(1)):012d}"


def get_json(
    path: str,
    *,
    base_url: str = BASE_URL,
    timeout: int = TIMEOUT_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
) -> Any:
    """GET a JSON document, refusing the HTML shell that unknown routes return.

    CartBlanche answers an unrecognised path with the app's HTML, HTTP 200, and
    a JSON content type, so the body is the only evidence of what happened.
    """
    url = path if path.startswith("http") else f"{base_url}/{path.lstrip('/')}"
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}

    last_error = "no attempt made"
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", "replace")
            return _parse_or_explain(raw, url)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            last_error = f"HTTP {error.code} for {url}: {detail}"
            if error.code not in RETRYABLE_STATUS or attempt == max_attempts:
                raise ChemicalSpaceError(last_error) from error
            _sleep_before_retry(attempt, error.headers.get("Retry-After"))
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = f"{type(error).__name__} for {url}: {error}"
            if attempt == max_attempts:
                raise ChemicalSpaceError(last_error) from error
            _sleep_before_retry(attempt, None)
    raise ChemicalSpaceError(last_error)  # pragma: no cover - loop returns or raises


def _parse_or_explain(raw: str, url: str) -> Any:
    stripped = raw.lstrip()
    if stripped.startswith("<"):
        raise ChemicalSpaceError(
            f"{url} returned the CartBlanche HTML app shell, not data -- the "
            "route does not exist. Despite that, the response was HTTP 200 with "
            "a JSON content type. The only reliable JSON route is "
            "/substance/<ZINC id>.json"
        )
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as error:
        raise ChemicalSpaceError(f"{url} returned unparseable JSON: {error}") from error


def _sleep_before_retry(attempt: int, retry_after: str | None) -> None:
    delay = BACKOFF_BASE_SECONDS ** attempt
    if retry_after:
        try:
            delay = max(delay, float(retry_after))
        except ValueError:
            pass
    time.sleep(min(delay, 30.0))


def substance(zinc_id: str, *, base_url: str = BASE_URL) -> dict[str, Any]:
    """Fetch one substance record by ZINC identifier."""
    identifier = normalise_zinc_id(zinc_id)
    record = get_json(f"substance/{identifier}.json", base_url=base_url)
    if not isinstance(record, dict) or not record.get("smiles"):
        raise ChemicalSpaceError(f"no substance record for {identifier}")
    return record


def summarise(record: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten the useful parts of a substance record."""
    tranche = record.get("tranche_details") or {}
    catalogs = record.get("catalogs") or []
    prices = [item.get("price") for item in catalogs if isinstance(item.get("price"), (int, float))]
    return {
        "zinc_id": record.get("zinc_id"),
        "smiles": record.get("smiles"),
        "mol_formula": record.get("mol_formula"),
        "mwt": tranche.get("mwt"),
        "logp": tranche.get("logp"),
        "heavy_atoms": tranche.get("heavy_atoms"),
        "rings": record.get("rings"),
        "hetero_atoms": record.get("hetero_atoms"),
        "inchikey": tranche.get("inchikey"),
        "db": record.get("db"),
        "catalogs": len(catalogs),
        "purchasable": any(item.get("purchase") for item in catalogs),
        "min_price": min(prices) if prices else None,
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
        "--base-url", default=BASE_URL, help="override the CartBlanche root"
    )


def read_ids(values: Sequence[str], path: str | None) -> list[str]:
    """Identifiers from the command line, or one per line from a file."""
    identifiers = list(values)
    if path:
        text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
        identifiers += [line.strip() for line in text.splitlines() if line.strip()]
    if not identifiers:
        raise ChemicalSpaceError("give at least one ZINC id, or --from-file")
    return identifiers
