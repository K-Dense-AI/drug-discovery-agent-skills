#!/usr/bin/env python3
"""Apply beyond-rule-of-five property rules to bifunctional degraders.

Standard library only. Descriptors are read from a table you supply -- compute
them with `rdkit` or `datamol` and pass the CSV here.

Four things this handles that applying ordinary drug-likeness usually gets wrong:

* **Lipinski is the wrong yardstick and rejects every PROTAC.** A degrader is
  two ligands joined by a linker: 700-1100 Da, a dozen or more rotatable
  bonds, and TPSA well past 140. Filtering a degrader series on Ro5 discards
  all of it, including the ones that work.
* **The windows are two-sided.** Degraders occupy a narrow habitable band, and
  the failure at the top (no permeability) is as real as the failure at the
  bottom (no ternary complex). Optimising anything in one direction is wrong.
* **Permeability is the binding constraint, and it is not predicted by TPSA
  alone.** Successful oral degraders behave as molecular chameleons, forming
  intramolecular hydrogen bonds that shield polarity in membranes. Static
  descriptors cannot see that.
* The E3 ligand fixes much of the property budget before the linker is drawn.
  A CRBN binder is small and permeable; a VHL binder is large and polar, and
  spends most of the allowance on its own.

Commands:
    check      score degraders against the bRo5 windows
    windows    the property windows applied, and why each has two sides
    ligases    E3 ligands and what each costs in property budget

Examples:
    python protac_properties.py check --csv descriptors.csv
    python protac_properties.py windows
    python protac_properties.py ligases
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

#: Property windows for bifunctional degraders, from the published
#: physicochemical surveys of PROTACs in the clinic. Two-sided by design.
WINDOWS = {
    "mw": {
        "range": (700.0, 1100.0),
        "why_low": "below ~700 it is probably not a complete bifunctional molecule",
        "why_high": "above ~1100 permeability collapses and exposure follows",
    },
    "clogp": {
        "range": (3.0, 7.0),
        "why_low": "too polar to cross a membrane at this size",
        "why_high": "aggregation, promiscuity, and metabolic instability",
    },
    "tpsa": {
        "range": (150.0, 250.0),
        "why_low": "unusually low for a molecule this size; check it is complete",
        "why_high": "above ~250 passive permeability is essentially lost",
    },
    "hbd": {
        "range": (2.0, 6.0),
        "why_low": "few donors is fine; this bound is soft",
        "why_high": "donors cost the most permeability per unit of polarity",
    },
    "rotb": {
        "range": (8.0, 20.0),
        "why_low": "a degrader has a linker; very few rotatable bonds is suspicious",
        "why_high": "beyond ~20 the entropic cost of the ternary complex is punishing",
    },
    "heavy_atoms": {
        "range": (45.0, 80.0),
        "why_low": "small for a bifunctional",
        "why_high": "size is the dominant driver of poor exposure",
    },
}

#: Column aliases, so a descriptor table from RDKit or datamol works unchanged.
ALIASES = {
    "mw": ("mw", "molecular_weight", "molwt", "exactmw"),
    "clogp": ("clogp", "logp", "slogp", "mollogp"),
    "tpsa": ("tpsa", "psa"),
    "hbd": ("hbd", "numhdonors", "num_hbd", "hydrogen_bond_donors"),
    "rotb": ("rotb", "numrotatablebonds", "num_rotatable_bonds", "rotatable_bonds"),
    "heavy_atoms": ("heavy_atoms", "heavyatomcount", "num_heavy_atoms"),
}

#: The common E3 ligands, and what each spends of the property budget.
E3_LIGANDS = {
    "CRBN": {
        "ligand": "thalidomide / pomalidomide / lenalidomide analogues",
        "mw": "~250-300 Da",
        "note": "small and comparatively permeable; leaves the most budget for the linker "
                "and target ligand. Cereblon neosubstrate biology is also its liability -- "
                "IMiD scaffolds degrade IKZF1/3 whether you asked or not",
    },
    "VHL": {
        "ligand": "VH032 and analogues",
        "mw": "~450-500 Da",
        "note": "large and polar; spends much of the budget before the linker is drawn. "
                "Well characterised structurally, with many ternary complex structures",
    },
    "IAP": {
        "ligand": "LCL161 / SMAC mimetics",
        "mw": "~450-550 Da",
        "note": "auto-degradation of the E3 itself is a recurring problem",
    },
    "MDM2": {
        "ligand": "nutlin analogues",
        "mw": "~500-600 Da",
        "note": "less used; p53 pathway engagement confounds the phenotype",
    },
    "DCAF15": {
        "ligand": "indisulam-type",
        "mw": "~350 Da",
        "note": "molecular glue rather than bifunctional; a different design problem",
    },
    "DCAF1": {
        "ligand": "recent chemical matter",
        "mw": "~400 Da",
        "note": "newer; broader tissue expression than CRBN in some settings",
    },
}


class DegraderError(RuntimeError):
    """Input that cannot be scored."""


def resolve_columns(fieldnames: list[str]) -> dict[str, str]:
    lowered = {name.lower().strip().replace(" ", "_"): name for name in fieldnames}
    resolved = {}
    for key, candidates in ALIASES.items():
        for candidate in candidates:
            if candidate in lowered:
                resolved[key] = lowered[candidate]
                break
    return resolved


def as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def command_check(args: argparse.Namespace) -> None:
    stream = sys.stdin if args.csv == "-" else open(args.csv, newline="", encoding="utf-8")
    with stream as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise DegraderError(f"{args.csv} has no rows")

    columns = resolve_columns(list(rows[0]))
    if not columns:
        raise DegraderError(
            f"no recognised descriptor columns in {args.csv}. Expected some of "
            f"{', '.join(sorted(ALIASES))} -- compute them with rdkit or datamol first."
        )
    missing = sorted(set(WINDOWS) - set(columns))
    if missing:
        print(f"# not scored (no column): {', '.join(missing)}", file=sys.stderr)

    identifier = next(
        (name for name in rows[0] if name.lower() in ("id", "name", "smiles", "compound")), None
    )

    out = []
    for index, row in enumerate(rows):
        flags = []
        values = {}
        for key, column in columns.items():
            value = as_float(row.get(column))
            values[key] = value
            if value is None:
                continue
            low, high = WINDOWS[key]["range"]
            if value < low:
                flags.append(f"{key}_low")
            elif value > high:
                flags.append(f"{key}_high")
        out.append(
            {
                "compound": row.get(identifier) if identifier else f"row{index}",
                **{key: values.get(key) for key in WINDOWS},
                "flags": flags,
                "in_window": not flags,
            }
        )

    inside = sum(1 for row in out if row["in_window"])
    print(f"# {len(out)} degraders, {inside} inside every scored window", file=sys.stderr)
    print(
        "# Lipinski is the wrong yardstick here and would reject all of them. "
        "These windows are the bRo5 habitable band for bifunctionals.",
        file=sys.stderr,
    )
    print(
        "# permeability is the binding constraint and static descriptors cannot "
        "see it -- successful oral degraders form intramolecular hydrogen bonds "
        "that shield polarity in membranes. Measure PAMPA or Caco-2.",
        file=sys.stderr,
    )
    emit(out, ["compound", *WINDOWS, "in_window", "flags"], args)


def command_windows(args: argparse.Namespace) -> None:
    rows = [
        {
            "property": key,
            "low": spec["range"][0],
            "high": spec["range"][1],
            "why_low": spec["why_low"],
            "why_high": spec["why_high"],
        }
        for key, spec in WINDOWS.items()
    ]
    print(
        "# every window is two-sided. The failure at the top (no permeability) is "
        "as real as the one at the bottom (no ternary complex), so optimising in "
        "one direction is always wrong.",
        file=sys.stderr,
    )
    emit(rows, ["property", "low", "high", "why_low", "why_high"], args)


def command_ligases(args: argparse.Namespace) -> None:
    rows = [
        {"e3": name, "ligand": spec["ligand"], "ligand_mw": spec["mw"], "note": spec["note"]}
        for name, spec in E3_LIGANDS.items()
    ]
    print(
        "# the E3 ligand fixes much of the property budget before the linker is "
        "drawn. Only a handful of the ~600 human E3 ligases have usable chemical "
        "matter, and CRBN and VHL account for most published degraders.",
        file=sys.stderr,
    )
    emit(rows, ["e3", "ligand", "ligand_mw", "note"], args)


def emit(rows: list[dict], columns: list[str], args: argparse.Namespace) -> None:
    if args.output_format == "json":
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    writer = csv.writer(
        sys.stdout, delimiter="," if args.output_format == "csv" else "\t", lineterminator="\n"
    )
    writer.writerow(columns)
    for row in rows:
        writer.writerow(
            [
                "" if row.get(c) is None
                else "|".join(str(item) for item in row[c]) if isinstance(row[c], list)
                else "true" if row[c] is True
                else "false" if row[c] is False
                else f"{row[c]:.4g}" if isinstance(row[c], float)
                else row[c]
                for c in columns
            ]
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="score degraders against bRo5 windows")
    check.add_argument("--csv", required=True, help="descriptor table, or - for stdin")
    check.set_defaults(handler=command_check)

    windows = subparsers.add_parser("windows", help="the property windows applied")
    windows.set_defaults(handler=command_windows)

    ligases = subparsers.add_parser("ligases", help="E3 ligands and their property cost")
    ligases.set_defaults(handler=command_ligases)

    for sub in (check, windows, ligases):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except DegraderError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
