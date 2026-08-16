#!/usr/bin/env python3
"""Filter designed binders on the in-silico metrics that predict experimental success.

Standard library only. Reads the metrics CSV BindCraft writes, or any table
with the same column names.

Four things this handles that eyeballing the metrics usually gets wrong:

* **ipTM is the single most predictive metric and it is not pTM.** pTM scores
  the whole complex, which a large well-folded target dominates; ipTM scores
  the *interface*. A design can have excellent pTM and a nonexistent interface.
* **The filters are a conjunction, and passing one is meaningless.** Published
  success rates come from designs passing all of them together; ranking by any
  single metric selects for that metric's failure mode.
* **These are in-silico metrics from the same model family that generated the
  designs.** They are self-consistency measures, not affinity predictions, and
  they correlate with success rather than guaranteeing it.
* Ranking by ipTM alone selects near-identical designs. Interface diversity is
  what makes a plate worth ordering, since the metrics cannot distinguish the
  one in ten that actually binds.

Commands:
    filter    apply the standard filter set and report what survives
    metrics   the metrics, thresholds, and what each measures
    diverse   pick a diverse subset of the survivors to order

Examples:
    python binder_filter.py filter --csv bindcraft_metrics.csv
    python binder_filter.py filter --csv out.csv --iptm 0.85 --format json
    python binder_filter.py diverse --csv out.csv --n 24
    python binder_filter.py metrics
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

#: Standard filter set. Thresholds follow common BindCraft/RFdiffusion practice;
#: they are conventions to argue with, not guarantees.
FILTERS = {
    "iptm": {
        "min": 0.80,
        "measures": "AlphaFold2 interface predicted TM-score",
        "why": "the single most predictive in-silico metric for binder success",
    },
    "ipae": {
        "max": 10.0,
        "measures": "predicted aligned error across the interface, angstrom",
        "why": "how confident the model is about the relative placement of the two chains",
    },
    "plddt": {
        "min": 80.0,
        "measures": "binder per-residue confidence",
        "why": "a binder the model cannot fold confidently will not fold",
    },
    "dsasa": {
        "min": 1000.0,
        "measures": "buried surface area at the interface, square angstrom",
        "why": "below ~1000 the interface is too small for useful affinity",
    },
    "shape_complementarity": {
        "min": 0.55,
        "measures": "geometric fit of the two surfaces",
        "why": "loose packing gives weak, non-specific binding",
    },
    "unsat_hbonds": {
        "max": 4.0,
        "measures": "buried polar atoms with no hydrogen-bond partner",
        "why": "each unsatisfied buried polar atom is a large desolvation penalty",
    },
}

#: Column aliases, so BindCraft output and hand-assembled tables both work.
ALIASES = {
    "iptm": ("iptm", "i_ptm", "interface_iptm", "ipTM"),
    "ipae": ("ipae", "i_pae", "interface_pae", "pae_interaction"),
    "plddt": ("plddt", "binder_plddt", "i_plddt", "average_plddt"),
    "dsasa": ("dsasa", "d_sasa", "interface_dsasa", "buried_sasa", "interface_area"),
    "shape_complementarity": ("shape_complementarity", "sc", "interface_sc", "shapecomplementarity"),
    "unsat_hbonds": ("unsat_hbonds", "interface_unsathbonds", "unsatisfied_hbonds", "n_unsat"),
}

#: Binder length bands, for diversity selection.
LENGTH_ALIASES = ("length", "binder_length", "n_residues")


class FilterError(RuntimeError):
    """Input that cannot be filtered."""


def resolve_columns(fieldnames: list[str]) -> dict[str, str]:
    lowered = {name.lower().strip().replace(" ", "_"): name for name in fieldnames}
    resolved = {}
    for key, candidates in ALIASES.items():
        for candidate in candidates:
            if candidate.lower() in lowered:
                resolved[key] = lowered[candidate.lower()]
                break
    return resolved


def as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_designs(path: str) -> tuple[list[dict], dict[str, str], str | None]:
    stream = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8")
    with stream as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise FilterError(f"{path} has no rows")

    columns = resolve_columns(list(rows[0]))
    if "iptm" not in columns:
        raise FilterError(
            f"no interface pTM column in {path}. Expected one of "
            f"{', '.join(ALIASES['iptm'])} -- pass the BindCraft metrics CSV. "
            "Note that pTM is not ipTM: pTM scores the whole complex, which a "
            "large target dominates."
        )
    identifier = next(
        (name for name in rows[0] if name.lower() in ("design", "name", "id", "sequence")), None
    )
    return rows, columns, identifier


def thresholds_from(args: argparse.Namespace) -> dict[str, dict]:
    thresholds = {key: dict(spec) for key, spec in FILTERS.items()}
    for key in thresholds:
        override = getattr(args, key, None)
        if override is None:
            continue
        bound = "min" if "min" in thresholds[key] else "max"
        thresholds[key][bound] = override
    return thresholds


def evaluate(row: dict, columns: dict[str, str], thresholds: dict[str, dict]) -> dict:
    values = {}
    failures = []
    for key, column in columns.items():
        value = as_float(row.get(column))
        values[key] = value
        if value is None:
            continue
        spec = thresholds[key]
        if "min" in spec and value < spec["min"]:
            failures.append(f"{key}<{spec['min']:g}")
        if "max" in spec and value > spec["max"]:
            failures.append(f"{key}>{spec['max']:g}")
    return {**values, "failures": failures, "passes": not failures}


def command_filter(args: argparse.Namespace) -> None:
    rows, columns, identifier = read_designs(args.csv)
    thresholds = thresholds_from(args)

    missing = sorted(set(FILTERS) - set(columns))
    if missing:
        print(f"# not filtered (no column): {', '.join(missing)}", file=sys.stderr)

    out = []
    for index, row in enumerate(rows):
        result = evaluate(row, columns, thresholds)
        out.append({"design": row.get(identifier) if identifier else f"design{index}", **result})

    survivors = [row for row in out if row["passes"]]
    out.sort(key=lambda row: (not row["passes"], -(row.get("iptm") or 0.0)))

    print(f"# {len(out)} designs, {len(survivors)} pass every applied filter", file=sys.stderr)
    print(
        "# the filters are a conjunction. Published success rates come from "
        "designs passing all of them together; ranking on any single metric "
        "selects for that metric's failure mode.",
        file=sys.stderr,
    )
    print(
        "# these are in-silico metrics from the same model family that generated "
        "the designs -- self-consistency measures, not affinity predictions.",
        file=sys.stderr,
    )
    if survivors and len(survivors) < args.expect:
        print(
            f"# fewer than {args.expect} survivors. Either generate more "
            "trajectories or reconsider the epitope -- a hard site produces "
            "confident designs that all fail the interface filters.",
            file=sys.stderr,
        )

    columns_out = ["design", *FILTERS, "passes", "failures"]
    emit(out if args.all else survivors, columns_out, args)


def command_diverse(args: argparse.Namespace) -> None:
    rows, columns, identifier = read_designs(args.csv)
    thresholds = thresholds_from(args)

    survivors = []
    for index, row in enumerate(rows):
        result = evaluate(row, columns, thresholds)
        if not result["passes"]:
            continue
        sequence = ""
        for name in row:
            if name.lower() in ("sequence", "binder_sequence", "seq"):
                sequence = (row[name] or "").strip()
                break
        survivors.append(
            {
                "design": row.get(identifier) if identifier else f"design{index}",
                "iptm": result.get("iptm"),
                "sequence": sequence,
                "length": len(sequence) if sequence else None,
            }
        )

    if not survivors:
        print("# no designs pass the filters, so there is nothing to diversify", file=sys.stderr)
        return

    survivors.sort(key=lambda row: -(row["iptm"] or 0.0))
    chosen: list[dict] = []
    for candidate in survivors:
        if len(chosen) >= args.n:
            break
        if candidate["sequence"] and any(
            similarity(candidate["sequence"], picked["sequence"]) > args.max_identity
            for picked in chosen
            if picked["sequence"]
        ):
            continue
        chosen.append(candidate)

    print(
        f"# {len(chosen)} of {len(survivors)} survivors chosen, at most "
        f"{args.max_identity:.0%} identical to each other",
        file=sys.stderr,
    )
    print(
        "# ranking by ipTM alone selects near-identical designs. The metrics "
        "cannot pick the one in ten that binds, so order diverse ones.",
        file=sys.stderr,
    )
    emit(chosen, ["design", "iptm", "length", "sequence"], args)


def similarity(first: str, second: str) -> float:
    """Fraction of aligned positions that match, over the shorter sequence."""
    if not first or not second:
        return 0.0
    shortest = min(len(first), len(second))
    matches = sum(1 for a, b in zip(first, second) if a == b)
    return matches / shortest


def command_metrics(args: argparse.Namespace) -> None:
    rows = []
    for key, spec in FILTERS.items():
        bound = f">= {spec['min']:g}" if "min" in spec else f"<= {spec['max']:g}"
        rows.append(
            {"metric": key, "threshold": bound, "measures": spec["measures"], "why": spec["why"]}
        )
    print(
        "# ipTM scores the INTERFACE; pTM scores the whole complex and is "
        "dominated by a large well-folded target. A design can have excellent "
        "pTM and no interface at all.",
        file=sys.stderr,
    )
    print(
        "# thresholds are common practice, not guarantees. They are here to be "
        "argued with.",
        file=sys.stderr,
    )
    emit(rows, ["metric", "threshold", "measures", "why"], args)


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


def add_threshold_arguments(parser: argparse.ArgumentParser) -> None:
    for key, spec in FILTERS.items():
        bound = spec.get("min", spec.get("max"))
        parser.add_argument(
            f"--{key.replace('_', '-')}",
            type=float,
            help=f"override the {key} threshold (default: {bound:g})",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    filter_cmd = subparsers.add_parser("filter", help="apply the standard filter set")
    filter_cmd.add_argument("--csv", required=True, help="metrics CSV, or - for stdin")
    filter_cmd.add_argument("--all", action="store_true", help="show failures too")
    filter_cmd.add_argument(
        "--expect", type=int, default=10, help="warn below this many survivors (default: 10)"
    )
    add_threshold_arguments(filter_cmd)
    filter_cmd.set_defaults(handler=command_filter)

    diverse = subparsers.add_parser("diverse", help="pick a diverse subset to order")
    diverse.add_argument("--csv", required=True, help="metrics CSV, or - for stdin")
    diverse.add_argument("--n", type=int, default=24, help="designs to pick (default: 24)")
    diverse.add_argument(
        "--max-identity", type=float, default=0.7, help="pairwise identity ceiling (default: 0.7)"
    )
    add_threshold_arguments(diverse)
    diverse.set_defaults(handler=command_diverse)

    metrics = subparsers.add_parser("metrics", help="the metrics and thresholds")
    metrics.set_defaults(handler=command_metrics)

    for sub in (filter_cmd, diverse, metrics):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except FilterError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
