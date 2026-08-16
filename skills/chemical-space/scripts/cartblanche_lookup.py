#!/usr/bin/env python3
"""Resolve ZINC identifiers to structures, properties, and purchasability.

Four things this handles that a hand-written query usually gets wrong:

* CartBlanche answers an unknown route with its **HTML app shell, HTTP 200,
  and a JSON content type**. Only parsing the body reveals it, so every
  response is checked before use.
* Identifiers must be zero-padded to twelve digits. `ZINC53` does not resolve;
  `ZINC000000000053` does. Both are accepted here and padded.
* **Existing in ZINC is not the same as being purchasable.** The `catalogs`
  block carries supplier, price, quantity, and lead time, and it is empty for
  substances that are only computationally enumerated.
* Quoted lead times are frequently weeks, and make-on-demand compounds carry a
  real synthesis failure rate. A "purchasable" set is a set of orders, not a
  set of vials.

Commands:
    substance   structure and computed properties for ZINC ids
    catalogs    who sells it, at what price, with what lead time

Examples:
    python cartblanche_lookup.py substance ZINC000019632618
    python cartblanche_lookup.py substance --from-file ids.txt --format json
    python cartblanche_lookup.py catalogs ZINC000019632618
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    ChemicalSpaceError,
    add_common_arguments,
    emit,
    read_ids,
    substance,
    summarise,
)

SUBSTANCE_COLUMNS = (
    "zinc_id", "smiles", "mol_formula", "mwt", "logp", "heavy_atoms",
    "rings", "hetero_atoms", "purchasable", "catalogs", "min_price", "db",
)

CATALOG_COLUMNS = (
    "zinc_id", "catalog_name", "supplier_code", "price", "currency",
    "quantity", "units", "shipping", "purchase",
)


def command_substance(args: argparse.Namespace) -> None:
    rows = []
    for identifier in read_ids(args.zinc_ids, args.from_file):
        try:
            rows.append(summarise(substance(identifier, base_url=args.base_url)))
        except ChemicalSpaceError as error:
            print(f"# skipping {identifier}: {error}", file=sys.stderr)
    if not rows:
        raise ChemicalSpaceError("nothing resolved")

    purchasable = sum(1 for row in rows if row["purchasable"])
    print(f"# {len(rows)} resolved, {purchasable} with a purchasable catalog entry", file=sys.stderr)
    emit(rows, SUBSTANCE_COLUMNS, args.output_format)


def command_catalogs(args: argparse.Namespace) -> None:
    rows = []
    for identifier in read_ids(args.zinc_ids, args.from_file):
        try:
            record = substance(identifier, base_url=args.base_url)
        except ChemicalSpaceError as error:
            print(f"# skipping {identifier}: {error}", file=sys.stderr)
            continue
        entries = record.get("catalogs") or []
        if not entries:
            print(
                f"# {record.get('zinc_id')}: no catalog entries -- enumerated but "
                "not offered by any supplier in this snapshot",
                file=sys.stderr,
            )
        for entry in entries:
            rows.append(
                {
                    "zinc_id": record.get("zinc_id"),
                    "catalog_name": entry.get("catalog_name"),
                    "supplier_code": entry.get("supplier_code"),
                    "price": entry.get("price"),
                    "currency": entry.get("currency"),
                    "quantity": entry.get("quantity"),
                    "units": entry.get("units"),
                    "shipping": entry.get("shipping"),
                    "purchase": entry.get("purchase"),
                }
            )
    if not rows:
        print("# no catalog entries found", file=sys.stderr)
        return

    rows.sort(key=lambda row: (row["zinc_id"] or "", row["price"] if isinstance(row["price"], (int, float)) else 1e12))
    print(
        "# prices and lead times are supplier quotes in a periodic snapshot, not "
        "live availability; make-on-demand compounds also carry a synthesis "
        "failure rate that no catalog reports",
        file=sys.stderr,
    )
    emit(rows, CATALOG_COLUMNS, args.output_format)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler, help_text in (
        ("substance", command_substance, "structure and computed properties"),
        ("catalogs", command_catalogs, "supplier, price, and lead time"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("zinc_ids", nargs="*", help="e.g. ZINC000019632618")
        sub.add_argument(
            "--from-file", help="read ids one per line from a file, or - for stdin"
        )
        add_common_arguments(sub)
        sub.set_defaults(handler=handler)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except ChemicalSpaceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
