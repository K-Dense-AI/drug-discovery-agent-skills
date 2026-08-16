#!/usr/bin/env python3
"""Navigate the SureChEMBL bulk tree and plan a download before committing disk.

Standard library only. SureChEMBL has no public REST API, so the bulk tree is
the only programmatic route, and it is large enough that planning matters.

Four things this handles that browsing the FTP site usually gets wrong:

* **Two directories hold different data.** `bulk_data/` is SureChEMBL 2.0 --
  Parquet tables plus an FPSim2 index, released fortnightly. `data/` is the
  legacy quarterly txt and SDF dump, last described by a 2016 README. They are
  not the same data and are easily confused.
* **The full set is around 15 GB.** compounds, patents, and the mapping are
  4-6 GB each. Pulling everything to answer one structure query is avoidable;
  `plan` shows which tables a given question actually needs.
* **The mapping table is the interesting one.** compounds and patents are just
  entities; `patent_compound_map.parquet` carries which document field a
  compound was extracted from, and a compound in the claims means something
  very different from one in the description.
* Releases are dated directories. Pinning one makes an analysis reproducible;
  taking "latest" silently changes the answer between runs.

Commands:
    releases   the available bulk releases, newest first
    tables     the tables in a release, with sizes
    plan       which tables to download for a given question

Examples:
    python surechembl_bulk.py releases --limit 5
    python surechembl_bulk.py tables --release 2026-08-04
    python surechembl_bulk.py plan --question structure-to-patent
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    BULK_TABLES,
    DOCUMENT_FIELDS,
    SURECHEMBL_FTP,
    PatentError,
    add_common_arguments,
    content_length,
    emit,
    human_bytes,
    list_directory,
)

RELEASE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}/?$")

#: What each common question needs, so nobody downloads 15 GB for a lookup.
QUESTIONS = {
    "structure-to-patent": {
        "tables": ["compounds.parquet", "patent_compound_map.parquet", "patents.parquet"],
        "why": "match a structure to compound ids, then to the documents disclosing it",
    },
    "similarity-search": {
        "tables": ["fpsim2_fingerprints.h5", "compounds.parquet"],
        "why": "FPSim2 searches the index; compounds resolves the hits back to structures",
    },
    "assignee-landscape": {
        "tables": ["patents.parquet"],
        "why": "document metadata alone answers who filed what and when",
    },
    "target-mentions": {
        "tables": ["biomedical_entities.parquet", "biomedical_locations.parquet", "patents.parquet"],
        "why": "which documents mention a gene or protein, and where in the text",
    },
    "everything": {
        "tables": list(BULK_TABLES),
        "why": "the full release, for building a local database",
    },
}


def command_releases(args: argparse.Namespace) -> None:
    entries = list_directory(f"{SURECHEMBL_FTP}/bulk_data")
    releases = sorted(
        (entry.rstrip("/") for entry in entries if RELEASE_PATTERN.match(entry)), reverse=True
    )
    if not releases:
        raise PatentError(f"no dated releases under {SURECHEMBL_FTP}/bulk_data")

    rows = [
        {"release": release, "url": f"{SURECHEMBL_FTP}/bulk_data/{release}/"}
        for release in releases[: args.limit]
    ]
    print(
        f"# {len(releases)} releases, newest {releases[0]}. Updated fortnightly.",
        file=sys.stderr,
    )
    print(
        "# pin a release for a reproducible analysis -- taking the newest silently "
        "changes the answer between runs",
        file=sys.stderr,
    )
    emit(rows, ["release", "url"], args.output_format)


def resolve_release(release: str | None) -> str:
    if release and release != "latest":
        return release
    entries = list_directory(f"{SURECHEMBL_FTP}/bulk_data")
    releases = sorted(
        (entry.rstrip("/") for entry in entries if RELEASE_PATTERN.match(entry)), reverse=True
    )
    if not releases:
        raise PatentError("could not determine the latest release")
    return releases[0]


def command_tables(args: argparse.Namespace) -> None:
    release = resolve_release(args.release)
    base = f"{SURECHEMBL_FTP}/bulk_data/{release}"
    entries = [entry for entry in list_directory(base) if not entry.endswith("/")]
    if not entries:
        raise PatentError(f"no files in release {release}")

    rows = []
    total = 0
    for name in entries:
        size = content_length(f"{base}/{name}") if not args.no_sizes else None
        if size:
            total += size
        rows.append(
            {
                "table": name,
                "size": human_bytes(size),
                "bytes": size,
                "holds": BULK_TABLES.get(name, ""),
            }
        )
    rows.sort(key=lambda row: -(row["bytes"] or 0))

    print(f"# release {release}: {len(rows)} files, {human_bytes(total)} total", file=sys.stderr)
    print(
        "# patent_compound_map is the interesting one -- it records which document "
        f"field a compound came from ({', '.join(DOCUMENT_FIELDS[:4])}...), and a "
        "compound in the claims means something very different from one in the "
        "description",
        file=sys.stderr,
    )
    emit(rows, ["table", "size", "holds"], args.output_format)


def command_plan(args: argparse.Namespace) -> None:
    if args.question not in QUESTIONS:
        raise PatentError(
            f"`{args.question}` is not a known question; choose from "
            f"{', '.join(QUESTIONS)}"
        )
    release = resolve_release(args.release)
    spec = QUESTIONS[args.question]
    base = f"{SURECHEMBL_FTP}/bulk_data/{release}"

    rows = []
    total = 0
    for name in spec["tables"]:
        size = content_length(f"{base}/{name}") if not args.no_sizes else None
        if size:
            total += size
        rows.append(
            {
                "table": name,
                "size": human_bytes(size),
                "bytes": size,
                "url": f"{base}/{name}",
            }
        )

    print(f"# {args.question}: {spec['why']}", file=sys.stderr)
    print(
        f"# {len(rows)} table(s), {human_bytes(total)} for release {release}",
        file=sys.stderr,
    )
    emit(rows, ["table", "size", "url"], args.output_format)

    if args.output_format == "tsv":
        print("\n# download with:", file=sys.stderr)
        for row in rows:
            print(f"curl -O {row['url']}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    releases = subparsers.add_parser("releases", help="available bulk releases")
    releases.add_argument("--limit", type=int, default=10, help="default: 10")
    releases.set_defaults(handler=command_releases)

    tables = subparsers.add_parser("tables", help="tables in a release, with sizes")
    tables.add_argument("--release", default="latest", help="e.g. 2026-08-04 (default: latest)")
    tables.set_defaults(handler=command_tables)

    plan = subparsers.add_parser("plan", help="which tables a question needs")
    plan.add_argument(
        "--question", choices=tuple(QUESTIONS), required=True, help="what you want to answer"
    )
    plan.add_argument("--release", default="latest", help="default: latest")
    plan.set_defaults(handler=command_plan)

    for sub in (tables, plan):
        sub.add_argument(
            "--no-sizes", action="store_true", help="skip HEAD requests for file sizes"
        )
    for sub in (releases, tables, plan):
        add_common_arguments(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except PatentError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
