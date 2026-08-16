#!/usr/bin/env python3
"""Read FDA Structured Product Labels: boxed warnings, indications, and drug class.

Four things this handles that a hand-written query usually gets wrong:

* One drug has many labels -- every manufacturer of a generic files its own.
  A search for `metformin` returns hundreds of near-identical documents, so
  every command here reports how many labels matched and de-duplicates the
  text it shows.
* **Absence of a `boxed_warning` field is not proof there is no boxed warning.**
  It means this particular SPL has no such section, and generic labels are
  often less complete than the reference product's. `boxed` reports the ratio.
* Label sections are lists of long strings, not scalars. Printing a record
  raw dumps tens of kilobytes per label.
* `openfda.pharm_class_epc` is the Established Pharmacologic Class -- an FDA
  regulatory label, not a mechanism. The mechanism is `pharm_class_moa`, and a
  drug can carry several of each or none at all.

Commands:
    section     pull one label section for a drug
    boxed       whether a drug carries a boxed warning, and its text
    classes     established pharmacologic class and mechanism of action

Examples:
    python fda_labels.py section --drug metformin --section indications_and_usage
    python fda_labels.py boxed --drug metformin
    python fda_labels.py classes --drug atorvastatin
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    OpenFdaError,
    add_common_arguments,
    clamp_limit,
    emit,
    get,
    quote,
    total_matching,
)

ENDPOINT = "drug/label"

#: The SPL sections worth pulling by name. There are many more; these are the
#: ones that carry a regulatory decision rather than administrative detail.
SECTIONS = (
    "boxed_warning",
    "indications_and_usage",
    "dosage_and_administration",
    "contraindications",
    "warnings_and_cautions",
    "adverse_reactions",
    "drug_interactions",
    "use_in_specific_populations",
    "mechanism_of_action",
    "clinical_pharmacology",
    "pharmacokinetics",
)

PHARM_CLASSES = {
    "pharm_class_epc": "established pharmacologic class",
    "pharm_class_moa": "mechanism of action",
    "pharm_class_cs": "chemical structure",
    "pharm_class_pe": "physiologic effect",
}


def drug_clause(drug: str) -> str:
    term = quote(drug)
    fields = (
        "openfda.brand_name",
        "openfda.generic_name",
        "openfda.substance_name",
    )
    return "(" + "+OR+".join(f"{field}:{term}" for field in fields) + ")"


def _labels(args: argparse.Namespace, limit: int) -> list[dict]:
    document = get(
        ENDPOINT,
        {"search": drug_clause(args.drug), "limit": clamp_limit(limit)},
        base_url=args.base_url,
    )
    return list(document.get("results") or [])


def _label_name(record: dict) -> str:
    openfda = record.get("openfda") or {}
    for key in ("brand_name", "generic_name", "substance_name"):
        values = openfda.get(key) or []
        if values:
            return str(values[0])
    return "unknown"


# --------------------------------------------------------------------------
# section
# --------------------------------------------------------------------------


def command_section(args: argparse.Namespace) -> None:
    if args.section not in SECTIONS:
        print(
            f"error: unknown section `{args.section}`; known sections are "
            + ", ".join(SECTIONS),
            file=sys.stderr,
        )
        raise SystemExit(1)

    total = total_matching(ENDPOINT, drug_clause(args.drug), base_url=args.base_url)
    records = _labels(args, args.limit)
    if not records:
        print(f"# no labels for {args.drug}", file=sys.stderr)
        return

    seen: set[str] = set()
    rows = []
    for record in records:
        for text in record.get(args.section) or []:
            collapsed = " ".join(str(text).split())
            fingerprint = collapsed[:400]
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            rows.append(
                {
                    "label": _label_name(record),
                    "manufacturer": (record.get("openfda") or {}).get("manufacturer_name", [""])[:1],
                    "text": collapsed,
                }
            )

    print(f"# {total} labels match {args.drug}; showing {len(records)}", file=sys.stderr)
    print(f"# {len(rows)} distinct `{args.section}` text(s)", file=sys.stderr)
    if not rows:
        print(
            f"# none of the labels examined carry a `{args.section}` section -- "
            "that is a property of these SPLs, not proof the section does not exist",
            file=sys.stderr,
        )
        return

    if args.output_format == "tsv" and not args.full:
        for row in rows:
            print(f"\n## {row['label']}")
            print(textwrap.fill(row["text"][: args.chars], width=95))
            if len(row["text"]) > args.chars:
                print(f"... [{len(row['text']) - args.chars} more characters; --full for all]")
        return
    emit(rows, ["label", "manufacturer", "text"], args.output_format)


# --------------------------------------------------------------------------
# boxed
# --------------------------------------------------------------------------


def command_boxed(args: argparse.Namespace) -> None:
    records = _labels(args, args.limit)
    if not records:
        print(f"# no labels for {args.drug}", file=sys.stderr)
        return

    with_box = [record for record in records if record.get("boxed_warning")]
    print(
        f"# {len(with_box)}/{len(records)} labels examined carry a boxed warning",
        file=sys.stderr,
    )
    if not with_box:
        print(
            "# no boxed warning in these labels. Generic SPLs are often less "
            "complete than the reference product's -- confirm against the RLD "
            "before concluding the drug has none",
            file=sys.stderr,
        )
        return

    seen: set[str] = set()
    rows = []
    for record in with_box:
        for text in record.get("boxed_warning") or []:
            collapsed = " ".join(str(text).split())
            if collapsed[:400] in seen:
                continue
            seen.add(collapsed[:400])
            rows.append({"label": _label_name(record), "boxed_warning": collapsed})

    if args.output_format == "tsv" and not args.full:
        for row in rows:
            print(f"\n## {row['label']}")
            print(textwrap.fill(row["boxed_warning"][: args.chars], width=95))
        return
    emit(rows, ["label", "boxed_warning"], args.output_format)


# --------------------------------------------------------------------------
# classes
# --------------------------------------------------------------------------


def command_classes(args: argparse.Namespace) -> None:
    records = _labels(args, args.limit)
    if not records:
        print(f"# no labels for {args.drug}", file=sys.stderr)
        return

    collected: dict[str, set[str]] = {key: set() for key in PHARM_CLASSES}
    for record in records:
        openfda = record.get("openfda") or {}
        for key in PHARM_CLASSES:
            collected[key].update(openfda.get(key) or [])

    rows = [
        {"kind": PHARM_CLASSES[key], "field": key, "values": sorted(values)}
        for key, values in collected.items()
        if values
    ]
    if not rows:
        print(
            f"# no pharmacologic class recorded on the labels for {args.drug} -- "
            "openfda annotations are absent on many older and generic SPLs",
            file=sys.stderr,
        )
        return
    print(f"# from {len(records)} label(s)", file=sys.stderr)
    emit(rows, ["kind", "field", "values"], args.output_format)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    section = subparsers.add_parser("section", help="pull one label section")
    section.add_argument("--drug", required=True, help="brand, generic, or substance name")
    section.add_argument(
        "--section", default="indications_and_usage", help="one of: " + ", ".join(SECTIONS)
    )
    section.add_argument("--limit", type=int, default=5, help="labels to examine (default: 5)")
    section.add_argument("--chars", type=int, default=1500, help="characters to show (default: 1500)")
    section.add_argument("--full", action="store_true", help="do not truncate the text")
    add_common_arguments(section)
    section.set_defaults(handler=command_section)

    boxed = subparsers.add_parser("boxed", help="boxed warning presence and text")
    boxed.add_argument("--drug", required=True, help="brand, generic, or substance name")
    boxed.add_argument("--limit", type=int, default=20, help="labels to examine (default: 20)")
    boxed.add_argument("--chars", type=int, default=2000, help="characters to show (default: 2000)")
    boxed.add_argument("--full", action="store_true", help="do not truncate the text")
    add_common_arguments(boxed)
    boxed.set_defaults(handler=command_boxed)

    classes = subparsers.add_parser("classes", help="pharmacologic class annotations")
    classes.add_argument("--drug", required=True, help="brand, generic, or substance name")
    classes.add_argument("--limit", type=int, default=10, help="labels to examine (default: 10)")
    add_common_arguments(classes)
    classes.set_defaults(handler=command_classes)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except OpenFdaError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
