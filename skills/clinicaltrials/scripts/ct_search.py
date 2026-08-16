#!/usr/bin/env python3
"""Search the ClinicalTrials.gov registry and count what a query matches.

Four things this handles that a hand-written query usually gets wrong:

* `totalCount` is opt-in. Without `countTotal=true` the response carries no
  total, so code that reads it reports zero matches for a query that matched
  thousands. Both commands here always request it.
* Paging is by opaque cursor (`nextPageToken`), not offset. A token belongs to
  the query that produced it, so changing any parameter mid-walk restarts.
* Filtering to `PHASE3` also returns studies tagged `PHASE2|PHASE3`. That is
  usually what you want, but it means phase counts do not sum to the total.
* Status values are upper snake case and validated server-side; `Completed`
  is a 400. `build_query` rejects a bad value before the request.

Commands:
    search   list studies matching a query
    count    totals broken down by phase or by status

Examples:
    python ct_search.py search --condition "non-small cell lung cancer" --phase PHASE3
    python ct_search.py search --intervention pembrolizumab --status RECRUITING --limit 20
    python ct_search.py count --condition melanoma --by phase
    python ct_search.py count --intervention osimertinib --by status
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    PHASES,
    STATUSES,
    ClinicalTrialsError,
    add_common_arguments,
    add_query_arguments,
    build_query,
    emit,
    paged,
    summarise,
    total_count,
)

SUMMARY_COLUMNS = (
    "nct_id",
    "status",
    "phase",
    "enrollment",
    "sponsor",
    "start",
    "completion",
    "has_results",
    "title",
)


def command_search(args: argparse.Namespace) -> None:
    params = build_query(args)
    total = total_count(params, base_url=args.base_url)
    print(f"# {total} studies match", file=sys.stderr)
    if total == 0:
        print(
            "# nothing matched -- condition and intervention are matched against "
            "registry text, so try a synonym or the generic drug name",
            file=sys.stderr,
        )
        return
    if total > args.limit:
        print(f"# showing the first {args.limit}; raise --limit for more", file=sys.stderr)

    rows = [
        summarise(study)
        for study in paged(params, limit=args.limit, base_url=args.base_url)
    ]
    rows.sort(key=lambda row: (row["start"] or ""), reverse=True)
    emit(rows, SUMMARY_COLUMNS, args.output_format)


def command_count(args: argparse.Namespace) -> None:
    params = build_query(args)
    total = total_count(params, base_url=args.base_url)
    print(f"# {total} studies match before breakdown", file=sys.stderr)
    if total == 0:
        return

    if args.by == "phase":
        rows = _count_by_phase(params, args.base_url)
        print(
            "# a PHASE2|PHASE3 study is counted under both, so these do not sum "
            "to the total",
            file=sys.stderr,
        )
    else:
        rows = _count_by_status(params, args.base_url)

    emit(rows, [args.by, "studies", "share_pct"], args.output_format)


def _count_by_phase(params: dict, base_url: str) -> list[dict]:
    rows = []
    for phase in PHASES:
        scoped = dict(params)
        existing = scoped.get("filter.advanced")
        clause = f"AREA[Phase]{phase}"
        scoped["filter.advanced"] = f"{existing} AND {clause}" if existing else clause
        count = total_count(scoped, base_url=base_url)
        if count:
            rows.append({"phase": phase, "studies": count})
    grand = sum(row["studies"] for row in rows) or 1
    for row in rows:
        row["share_pct"] = round(100.0 * row["studies"] / grand, 1)
    return rows


def _count_by_status(params: dict, base_url: str) -> list[dict]:
    rows = []
    for status in STATUSES:
        scoped = dict(params)
        scoped["filter.overallStatus"] = status
        count = total_count(scoped, base_url=base_url)
        if count:
            rows.append({"status": status, "studies": count})
    grand = sum(row["studies"] for row in rows) or 1
    for row in rows:
        row["share_pct"] = round(100.0 * row["studies"] / grand, 1)
    rows.sort(key=lambda row: row["studies"], reverse=True)
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="list studies matching a query")
    add_query_arguments(search)
    search.add_argument("--limit", type=int, default=50, help="studies to return (default: 50)")
    add_common_arguments(search)
    search.set_defaults(handler=command_search)

    count = subparsers.add_parser("count", help="totals by phase or status")
    add_query_arguments(count)
    count.add_argument(
        "--by", choices=("phase", "status"), default="phase", help="breakdown axis (default: phase)"
    )
    add_common_arguments(count)
    count.set_defaults(handler=command_count)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except ClinicalTrialsError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
