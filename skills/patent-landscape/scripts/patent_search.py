#!/usr/bin/env python3
"""Search PatentsView for assignees, dates, and legal metadata.

Standard library only. Key-gated: PatentsView requires a free API key, and
this is the optional half of the skill -- the SureChEMBL side needs no
credentials.

Four things this handles that a hand-written query usually gets wrong:

* **A missing key looks like a network failure**, not a 401. `urlopen` raises
  a connection error before any HTTP status arrives, so the obvious diagnosis
  is wrong. Checked for explicitly here.
* **The query language is nested JSON**, url-encoded into `q`. A malformed
  operator is a 400 with a terse message, so the query is built rather than
  hand-written.
* **PatentsView covers US grants and pre-grant publications only.** A molecule
  with no US filing is invisible, and the EPO, WIPO, CNIPA, and JPO are
  entirely absent. Absence here is not absence of patent protection.
* **Assignee names are not normalised.** "Merck", "Merck Sharp & Dohme",
  "Merck & Co., Inc." and "MSD" appear as distinct strings, so a naive count
  by assignee undercounts a company's real portfolio.

Commands:
    patents    search grants by title, assignee, or date
    assignees  which organisations hold patents matching a query

Examples:
    python patent_search.py patents --title "kinase inhibitor" --after 2020-01-01
    python patent_search.py patents --assignee "Merck Sharp" --limit 25
    python patent_search.py assignees --title "PROTAC"
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    PATENTSVIEW_URL,
    PatentError,
    add_common_arguments,
    emit,
    get_json,
    patentsview_key,
)

#: Fields the patent endpoint returns that are worth asking for.
PATENT_FIELDS = (
    "patent_id",
    "patent_title",
    "patent_date",
    "patent_type",
    "assignees.assignee_organization",
    "assignees.assignee_country",
)

MAX_PAGE = 1000


def build_query(args: argparse.Namespace) -> dict:
    """Assemble the nested JSON PatentsView expects in `q`."""
    clauses: list[dict] = []
    if args.title:
        clauses.append({"_text_any": {"patent_title": args.title}})
    if args.assignee:
        clauses.append({"_contains": {"assignees.assignee_organization": args.assignee}})
    if args.after:
        clauses.append({"_gte": {"patent_date": args.after}})
    if args.before:
        clauses.append({"_lte": {"patent_date": args.before}})
    if not clauses:
        raise PatentError("give at least one of --title, --assignee, --after, or --before")
    return clauses[0] if len(clauses) == 1 else {"_and": clauses}


def search(args: argparse.Namespace, size: int) -> list[dict]:
    key = patentsview_key()
    if not key:
        raise PatentError(
            "PATENTSVIEW_API_KEY is not set. PatentsView requires a free key -- "
            "request one at patentsview.org/apis. Without it the request fails as "
            "a connection error rather than a 401, which is misleading. The "
            "SureChEMBL half of this skill needs no credentials."
        )

    params = {
        "q": json.dumps(build_query(args)),
        "f": json.dumps(list(PATENT_FIELDS)),
        "o": json.dumps({"size": min(size, MAX_PAGE)}),
    }
    url = f"{PATENTSVIEW_URL}/patent/?{urllib.parse.urlencode(params)}"
    document = get_json(url, headers={"X-Api-Key": key})

    if isinstance(document, dict) and document.get("error"):
        raise PatentError(f"PatentsView error: {document.get('error')}")
    return list((document or {}).get("patents") or [])


def organisations(record: dict) -> list[str]:
    return [
        item.get("assignee_organization")
        for item in record.get("assignees") or []
        if item.get("assignee_organization")
    ]


def command_patents(args: argparse.Namespace) -> None:
    records = search(args, args.limit)
    if not records:
        print("# no patents matched", file=sys.stderr)
        return

    rows = [
        {
            "patent_id": record.get("patent_id"),
            "date": record.get("patent_date"),
            "type": record.get("patent_type"),
            "assignees": organisations(record),
            "title": record.get("patent_title"),
        }
        for record in records
    ]
    rows.sort(key=lambda row: (row["date"] or ""), reverse=True)
    print(f"# {len(rows)} patent(s), newest first", file=sys.stderr)
    print(
        "# US grants and pre-grant publications only. EPO, WIPO, CNIPA, and JPO "
        "filings are absent, so silence here is not absence of protection.",
        file=sys.stderr,
    )
    emit(rows, ["patent_id", "date", "type", "assignees", "title"], args.output_format)


def command_assignees(args: argparse.Namespace) -> None:
    records = search(args, args.limit)
    if not records:
        print("# no patents matched", file=sys.stderr)
        return

    counter: Counter[str] = Counter()
    for record in records:
        counter.update(organisations(record))
    if not counter:
        print("# no assignee organisations on these records", file=sys.stderr)
        return

    rows = [
        {"assignee": name, "patents": count} for name, count in counter.most_common(args.top)
    ]
    print(f"# {len(counter)} distinct assignee strings across {len(records)} patents", file=sys.stderr)
    print(
        "# names are NOT normalised: 'Merck', 'Merck Sharp & Dohme', and "
        "'Merck & Co., Inc.' count separately, so a company's real portfolio is "
        "split across rows",
        file=sys.stderr,
    )
    emit(rows, ["assignee", "patents"], args.output_format)


def add_query_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--title", help="words in the patent title")
    parser.add_argument("--assignee", help="assignee organisation substring")
    parser.add_argument("--after", help="grant date on or after, YYYY-MM-DD")
    parser.add_argument("--before", help="grant date on or before, YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=100, help="records to fetch (default: 100)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    patents = subparsers.add_parser("patents", help="search grants")
    add_query_arguments(patents)
    patents.set_defaults(handler=command_patents)

    assignees = subparsers.add_parser("assignees", help="who holds matching patents")
    add_query_arguments(assignees)
    assignees.add_argument("--top", type=int, default=25, help="default: 25")
    assignees.set_defaults(handler=command_assignees)

    for sub in (patents, assignees):
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
