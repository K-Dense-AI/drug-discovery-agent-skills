#!/usr/bin/env python3
"""Look up FDA approvals, products, and submission history in Drugs@FDA.

Four things this handles that a hand-written query usually gets wrong:

* One application holds many products and many submissions. Keytruda's BLA has
  127 submissions; the original approval is the earliest `ORIG` with status
  `AP`, not `submissions[0]`, which arrives in no useful order.
* `submission_status_date` is a bare `YYYYMMDD` string. Sorting the records as
  returned gives an arbitrary order, so every listing here sorts explicitly.
* An efficacy supplement is a new indication, and it is the only place
  Drugs@FDA records label expansion -- counting them is how you see a drug's
  indication history without reading 127 documents.
* Drugs@FDA covers applications, not marketing. A product with
  `marketing_status: Discontinued` is still an approved product; withdrawal is
  a separate fact this endpoint does not carry.

Commands:
    application   applications matching a drug, sponsor, or ingredient
    products      the products (strengths, forms, routes) under an application
    timeline      submission history for an application

Examples:
    python fda_approvals.py application --drug keytruda
    python fda_approvals.py application --ingredient pembrolizumab
    python fda_approvals.py products --appno BLA125514
    python fda_approvals.py timeline --appno BLA125514 --type SUPPL --approved-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    OpenFdaError,
    add_common_arguments,
    clamp_limit,
    emit,
    get,
    quote,
)

ENDPOINT = "drug/drugsfda"

#: `AP` is the only status that means the submission was approved. The others
#: (`TA` tentative, `CR` complete response, `RL` and `WD`) are not approvals.
APPROVED = "AP"


def _search_clause(args: argparse.Namespace) -> str:
    if args.appno:
        return f"application_number:{quote(args.appno)}"
    if args.drug:
        term = quote(args.drug)
        return f"(openfda.brand_name:{term}+OR+openfda.generic_name:{term})"
    if args.ingredient:
        return f"products.active_ingredients.name:{quote(args.ingredient)}"
    if args.sponsor:
        return f"sponsor_name:{quote(args.sponsor)}"
    raise OpenFdaError("give one of --appno, --drug, --ingredient, or --sponsor")


def _fetch(args: argparse.Namespace, limit: int) -> list[dict]:
    document = get(
        ENDPOINT,
        {"search": _search_clause(args), "limit": clamp_limit(limit)},
        base_url=args.base_url,
    )
    return list(document.get("results") or [])


def _original_approval(record: dict) -> str:
    """Date of the earliest approved original submission, or ''."""
    dates = [
        submission.get("submission_status_date", "")
        for submission in record.get("submissions") or []
        if submission.get("submission_type") == "ORIG"
        and submission.get("submission_status") == APPROVED
    ]
    return min((date for date in dates if date), default="")


# --------------------------------------------------------------------------
# application
# --------------------------------------------------------------------------


def command_application(args: argparse.Namespace) -> None:
    records = _fetch(args, args.limit)
    if not records:
        print("# no applications matched", file=sys.stderr)
        return

    rows = []
    for record in records:
        products = record.get("products") or []
        submissions = record.get("submissions") or []
        efficacy_supplements = sum(
            1
            for submission in submissions
            if submission.get("submission_class_code") == "EFFICACY"
            and submission.get("submission_status") == APPROVED
        )
        rows.append(
            {
                "application_number": record.get("application_number"),
                "sponsor": record.get("sponsor_name"),
                "brand_names": sorted({p.get("brand_name") for p in products if p.get("brand_name")}),
                "ingredients": sorted(
                    {
                        ingredient.get("name")
                        for product in products
                        for ingredient in product.get("active_ingredients") or []
                        if ingredient.get("name")
                    }
                ),
                "original_approval": _original_approval(record),
                "products": len(products),
                "submissions": len(submissions),
                "efficacy_supplements": efficacy_supplements,
            }
        )
    rows.sort(key=lambda row: row["original_approval"] or "99999999")
    print(f"# {len(rows)} application(s)", file=sys.stderr)
    print(
        "# efficacy_supplements counts approved EFFICACY submissions -- roughly, "
        "how many times the label gained an indication",
        file=sys.stderr,
    )
    emit(
        rows,
        [
            "application_number",
            "sponsor",
            "brand_names",
            "ingredients",
            "original_approval",
            "products",
            "submissions",
            "efficacy_supplements",
        ],
        args.output_format,
    )


# --------------------------------------------------------------------------
# products
# --------------------------------------------------------------------------


def command_products(args: argparse.Namespace) -> None:
    records = _fetch(args, args.limit)
    rows = []
    for record in records:
        application = record.get("application_number")
        for product in record.get("products") or []:
            rows.append(
                {
                    "application_number": application,
                    "product_number": product.get("product_number"),
                    "brand_name": product.get("brand_name"),
                    "ingredients": [
                        f"{item.get('name')} {item.get('strength')}".strip()
                        for item in product.get("active_ingredients") or []
                    ],
                    "dosage_form": product.get("dosage_form"),
                    "route": product.get("route"),
                    "marketing_status": product.get("marketing_status"),
                    "reference_drug": product.get("reference_drug"),
                }
            )
    if not rows:
        print("# no products matched", file=sys.stderr)
        return
    print(f"# {len(rows)} product(s)", file=sys.stderr)
    print(
        "# marketing_status Discontinued still means approved -- Drugs@FDA "
        "records applications, not whether a product is on the shelf",
        file=sys.stderr,
    )
    emit(
        rows,
        [
            "application_number",
            "product_number",
            "brand_name",
            "ingredients",
            "dosage_form",
            "route",
            "marketing_status",
            "reference_drug",
        ],
        args.output_format,
    )


# --------------------------------------------------------------------------
# timeline
# --------------------------------------------------------------------------


def command_timeline(args: argparse.Namespace) -> None:
    records = _fetch(args, args.limit)
    rows = []
    for record in records:
        application = record.get("application_number")
        for submission in record.get("submissions") or []:
            if args.type and submission.get("submission_type") != args.type:
                continue
            if args.approved_only and submission.get("submission_status") != APPROVED:
                continue
            rows.append(
                {
                    "application_number": application,
                    "date": submission.get("submission_status_date"),
                    "type": submission.get("submission_type"),
                    "number": submission.get("submission_number"),
                    "status": submission.get("submission_status"),
                    "priority": submission.get("review_priority"),
                    "class": submission.get("submission_class_code_description")
                    or submission.get("submission_class_code"),
                }
            )
    if not rows:
        print("# no submissions matched", file=sys.stderr)
        return
    rows.sort(key=lambda row: row["date"] or "")
    print(f"# {len(rows)} submission(s), oldest first", file=sys.stderr)
    emit(
        rows,
        ["application_number", "date", "type", "number", "status", "priority", "class"],
        args.output_format,
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _add_selectors(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--appno", help="e.g. BLA125514 or NDA021986")
    parser.add_argument("--drug", help="brand or generic name")
    parser.add_argument("--ingredient", help="active ingredient, e.g. pembrolizumab")
    parser.add_argument("--sponsor", help="sponsor/company name")
    parser.add_argument("--limit", type=int, default=25, help="applications to fetch (default: 25)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    application = subparsers.add_parser("application", help="applications matching a selector")
    _add_selectors(application)
    add_common_arguments(application)
    application.set_defaults(handler=command_application)

    products = subparsers.add_parser("products", help="products under matching applications")
    _add_selectors(products)
    add_common_arguments(products)
    products.set_defaults(handler=command_products)

    timeline = subparsers.add_parser("timeline", help="submission history")
    _add_selectors(timeline)
    timeline.add_argument("--type", help="restrict to ORIG or SUPPL")
    timeline.add_argument(
        "--approved-only", action="store_true", help="only submissions with status AP"
    )
    add_common_arguments(timeline)
    timeline.set_defaults(handler=command_timeline)

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
