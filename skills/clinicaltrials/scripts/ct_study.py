#!/usr/bin/env python3
"""Read one registered study: design, endpoints, eligibility, and why it stopped.

Four things this handles that a hand-written query usually gets wrong:

* Everything is optional. A study may have no `outcomesModule`, no enrolment
  count, no completion date. Direct subscripting raises far more often than it
  succeeds, so every field is read through `dig`.
* `COMPLETED` does not mean the drug worked, and it does not mean results were
  posted. `hasResults` is a separate flag, and most completed studies never
  post. `show` reports both.
* `whyStopped` is free text and is only present on stopped studies. It is the
  single most informative field in the registry for competitive intelligence,
  and it is absent from every summary view.
* Eligibility criteria are one newline-delimited blob, not a structured list.
  `eligibility` splits it back into inclusion and exclusion.

Commands:
    show          design, status, sponsor, and dates for an NCT id
    outcomes      primary and secondary outcome measures
    eligibility   parsed inclusion and exclusion criteria

Examples:
    python ct_study.py show NCT02142738
    python ct_study.py outcomes NCT02142738
    python ct_study.py eligibility NCT02142738
"""

from __future__ import annotations

import argparse
import re
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    STOPPED,
    ClinicalTrialsError,
    add_common_arguments,
    dig,
    emit,
    get,
    summarise,
)

NCT_PATTERN = re.compile(r"^NCT\d{8}$")


def _fetch(nct_id: str, base_url: str) -> dict:
    if not NCT_PATTERN.match(nct_id.upper()):
        raise ClinicalTrialsError(
            f"`{nct_id}` is not an NCT id. They look like NCT01234567 "
            "(the letters NCT followed by exactly eight digits)."
        )
    return get(f"studies/{nct_id.upper()}", base_url=base_url)


def command_show(args: argparse.Namespace) -> None:
    study = _fetch(args.nct_id, args.base_url)
    protocol = study.get("protocolSection") or {}
    row = summarise(study)
    row["allocation"] = dig(protocol, "designModule.designInfo.allocation")
    row["masking"] = dig(protocol, "designModule.designInfo.maskingInfo.masking")
    row["primary_purpose"] = dig(protocol, "designModule.designInfo.primaryPurpose")
    row["collaborators"] = [
        item.get("name")
        for item in dig(protocol, "sponsorCollaboratorsModule.collaborators", []) or []
        if item.get("name")
    ]

    if row["status"] in STOPPED:
        print(f"# {row['status']}: {row['why_stopped'] or 'no reason given'}", file=sys.stderr)
    if row["status"] == "COMPLETED" and not row["has_results"]:
        print(
            "# completed but no results posted -- completion is not evidence the "
            "intervention worked",
            file=sys.stderr,
        )

    columns = [
        "nct_id", "status", "why_stopped", "phase", "study_type", "allocation",
        "masking", "primary_purpose", "enrollment", "enrollment_type", "sponsor",
        "collaborators", "start", "completion", "has_results", "conditions",
        "interventions", "title",
    ]
    if args.output_format == "tsv":
        for column in columns:
            value = row.get(column)
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            print(f"{column:<18} {value}")
        return
    emit([row], columns, args.output_format)


def command_outcomes(args: argparse.Namespace) -> None:
    study = _fetch(args.nct_id, args.base_url)
    protocol = study.get("protocolSection") or {}
    rows = []
    for kind, key in (("primary", "primaryOutcomes"), ("secondary", "secondaryOutcomes")):
        for outcome in dig(protocol, f"outcomesModule.{key}", []) or []:
            rows.append(
                {
                    "kind": kind,
                    "measure": outcome.get("measure"),
                    "time_frame": outcome.get("timeFrame"),
                    "description": " ".join((outcome.get("description") or "").split()),
                }
            )
    if not rows:
        print(f"# {args.nct_id} registers no outcome measures", file=sys.stderr)
        return
    primary = sum(1 for row in rows if row["kind"] == "primary")
    print(f"# {primary} primary, {len(rows) - primary} secondary", file=sys.stderr)
    print(
        "# the primary endpoint is what the study was powered for; a positive "
        "secondary in a failed study is hypothesis-generating, not evidence",
        file=sys.stderr,
    )
    emit(rows, ["kind", "measure", "time_frame", "description"], args.output_format)


def command_eligibility(args: argparse.Namespace) -> None:
    study = _fetch(args.nct_id, args.base_url)
    protocol = study.get("protocolSection") or {}
    module = protocol.get("eligibilityModule") or {}

    meta = {
        "sex": module.get("sex"),
        "minimum_age": module.get("minimumAge"),
        "maximum_age": module.get("maximumAge"),
        "healthy_volunteers": module.get("healthyVolunteers"),
        "std_ages": module.get("stdAges"),
    }
    for key, value in meta.items():
        if value not in (None, "", []):
            printable = ", ".join(value) if isinstance(value, list) else value
            print(f"{key:<20} {printable}", file=sys.stderr)

    inclusion, exclusion = _split_criteria(module.get("eligibilityCriteria") or "")
    if not inclusion and not exclusion:
        print(f"# {args.nct_id} registers no eligibility criteria text", file=sys.stderr)
        return

    rows = [{"kind": "inclusion", "criterion": item} for item in inclusion]
    rows += [{"kind": "exclusion", "criterion": item} for item in exclusion]
    if args.output_format == "tsv":
        for kind, items in (("Inclusion", inclusion), ("Exclusion", exclusion)):
            if not items:
                continue
            print(f"\n## {kind}")
            for item in items:
                print(textwrap.fill(f"- {item}", width=95, subsequent_indent="  "))
        return
    emit(rows, ["kind", "criterion"], args.output_format)


def _split_criteria(text: str) -> tuple[list[str], list[str]]:
    """Split the single criteria blob into inclusion and exclusion bullets.

    The registry stores one string with headings inside it. There is no
    structured form, so the headings are all there is to split on.
    """
    inclusion: list[str] = []
    exclusion: list[str] = []
    bucket = inclusion
    seen_heading = False
    for raw in text.splitlines():
        line = raw.strip().lstrip("*-• ").strip()
        if not line:
            continue
        lowered = line.lower().rstrip(":")
        if lowered.startswith("inclusion criteria"):
            bucket, seen_heading = inclusion, True
            continue
        if lowered.startswith("exclusion criteria"):
            bucket, seen_heading = exclusion, True
            continue
        bucket.append(line)
    if not seen_heading:
        # No headings at all: everything is unlabelled, so do not pretend to
        # know which half it belongs to.
        return text.split("\n") if text else [], []
    return inclusion, exclusion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler, help_text in (
        ("show", command_show, "design, status, sponsor, and dates"),
        ("outcomes", command_outcomes, "primary and secondary outcome measures"),
        ("eligibility", command_eligibility, "parsed inclusion and exclusion criteria"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("nct_id", help="e.g. NCT02142738")
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
