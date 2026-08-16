#!/usr/bin/env python3
"""Survey the competitive and feasibility landscape for an indication.

Four things this handles that a hand-written query usually gets wrong:

* The registry has no aggregation endpoint. Every breakdown here is computed
  by walking the matching studies once and tallying locally, so a broad query
  is genuinely expensive -- `--limit` is a real constraint, not a formality.
* Interventions are free text. "Pembrolizumab", "MK-3475", and "Keytruda" are
  the same molecule under three names and will not group together; the
  normalisation here is casefolding and nothing more.
* A sponsor's study count is not its investment. One phase 3 with 800 patients
  outweighs twenty investigator-initiated phase 1s, so `sponsors` reports
  enrolment and the highest phase reached, not just a count.
* Termination rate is the closest thing the registry has to a feasibility
  signal, and `whyStopped` says whether a programme died of futility, toxicity,
  or slow enrolment -- three very different facts.

Commands:
    sponsors        who is running studies, at what phase and scale
    interventions   what is being tested, ranked by study count
    attrition       status mix by phase, and why studies stopped

Examples:
    python ct_landscape.py sponsors --condition "pancreatic cancer" --limit 300
    python ct_landscape.py interventions --condition "alzheimer disease" --phase PHASE3
    python ct_landscape.py attrition --condition "pancreatic cancer" --limit 500
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    PHASES,
    STOPPED,
    ClinicalTrialsError,
    add_common_arguments,
    add_query_arguments,
    build_query,
    emit,
    paged,
    summarise,
    total_count,
)

#: Ordered worst-to-best so "highest phase reached" is a max over this index.
PHASE_RANK = {phase: index for index, phase in enumerate(("NA", "EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4"))}


def _collect(args: argparse.Namespace) -> list[dict]:
    params = build_query(args)
    total = total_count(params, base_url=args.base_url)
    print(f"# {total} studies match", file=sys.stderr)
    if total == 0:
        return []
    if total > args.limit:
        print(
            f"# walking the first {args.limit} of {total} -- the breakdown below "
            f"describes that sample, not the whole set",
            file=sys.stderr,
        )
    rows = [summarise(study) for study in paged(params, limit=args.limit, base_url=args.base_url)]
    print(f"# walked {len(rows)} studies", file=sys.stderr)
    return rows


def _highest_phase(phases: list[str]) -> str:
    ranked = [phase for phase in phases if phase in PHASE_RANK]
    if not ranked:
        return ""
    return max(ranked, key=lambda phase: PHASE_RANK[phase])


def command_sponsors(args: argparse.Namespace) -> None:
    rows = _collect(args)
    if not rows:
        return

    grouped: dict[str, dict] = defaultdict(
        lambda: {"studies": 0, "enrollment": 0, "phases": set(), "stopped": 0, "with_results": 0}
    )
    for row in rows:
        entry = grouped[row["sponsor"] or "(unnamed)"]
        entry["studies"] += 1
        entry["enrollment"] += row["enrollment"] or 0
        entry["phases"].update(phase for phase in (row["phase"] or "").split("|") if phase)
        entry["stopped"] += 1 if row["status"] in STOPPED else 0
        entry["with_results"] += 1 if row["has_results"] else 0

    table = [
        {
            "sponsor": name,
            "studies": entry["studies"],
            "total_enrollment": entry["enrollment"],
            "highest_phase": _highest_phase(sorted(entry["phases"])),
            "stopped": entry["stopped"],
            "with_results": entry["with_results"],
        }
        for name, entry in grouped.items()
    ]
    table.sort(key=lambda row: (-row["total_enrollment"], -row["studies"]))
    emit(
        table[: args.top],
        ["sponsor", "studies", "total_enrollment", "highest_phase", "stopped", "with_results"],
        args.output_format,
    )


def command_interventions(args: argparse.Namespace) -> None:
    rows = _collect(args)
    if not rows:
        return

    grouped: dict[str, dict] = defaultdict(lambda: {"studies": 0, "phases": set(), "sponsors": set()})
    for row in rows:
        for name in row["interventions"] or []:
            entry = grouped[name.strip().casefold()]
            entry["studies"] += 1
            entry["phases"].update(phase for phase in (row["phase"] or "").split("|") if phase)
            if row["sponsor"]:
                entry["sponsors"].add(row["sponsor"])

    table = [
        {
            "intervention": name,
            "studies": entry["studies"],
            "highest_phase": _highest_phase(sorted(entry["phases"])),
            "sponsors": len(entry["sponsors"]),
        }
        for name, entry in grouped.items()
    ]
    table.sort(key=lambda row: -row["studies"])
    print(
        "# names are free text and only casefolded -- one molecule may appear "
        "under its code name, generic name, and brand name",
        file=sys.stderr,
    )
    emit(
        table[: args.top],
        ["intervention", "studies", "highest_phase", "sponsors"],
        args.output_format,
    )


def command_attrition(args: argparse.Namespace) -> None:
    rows = _collect(args)
    if not rows:
        return

    by_phase: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        phases = [phase for phase in (row["phase"] or "").split("|") if phase] or ["NA"]
        for phase in phases:
            by_phase[phase][row["status"] or "UNKNOWN"] += 1

    table = []
    for phase in PHASES:
        counts = by_phase.get(phase)
        if not counts:
            continue
        total = sum(counts.values())
        stopped = sum(count for status, count in counts.items() if status in STOPPED)
        table.append(
            {
                "phase": phase,
                "studies": total,
                "completed": counts.get("COMPLETED", 0),
                "recruiting": counts.get("RECRUITING", 0),
                "terminated": counts.get("TERMINATED", 0),
                "withdrawn": counts.get("WITHDRAWN", 0),
                "stopped_pct": round(100.0 * stopped / total, 1),
            }
        )
    emit(
        table,
        ["phase", "studies", "completed", "recruiting", "terminated", "withdrawn", "stopped_pct"],
        args.output_format,
    )

    reasons = [row["why_stopped"] for row in rows if row["status"] in STOPPED and row["why_stopped"]]
    if reasons:
        print(f"\n# {len(reasons)} stated reasons for stopping", file=sys.stderr)
        print(
            "# free text, so these are read not counted -- futility, toxicity, "
            "and slow enrolment are very different facts",
            file=sys.stderr,
        )
        for reason in reasons[: args.reasons]:
            print(f"  - {' '.join(reason.split())[:160]}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler, help_text in (
        ("sponsors", command_sponsors, "who is running studies, at what phase and scale"),
        ("interventions", command_interventions, "what is being tested"),
        ("attrition", command_attrition, "status mix by phase, and why studies stopped"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        add_query_arguments(sub)
        sub.add_argument("--limit", type=int, default=200, help="studies to walk (default: 200)")
        sub.add_argument("--top", type=int, default=25, help="rows to show (default: 25)")
        if name == "attrition":
            sub.add_argument(
                "--reasons", type=int, default=15, help="stop reasons to print (default: 15)"
            )
        add_common_arguments(sub)
        sub.set_defaults(handler=handler)

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
