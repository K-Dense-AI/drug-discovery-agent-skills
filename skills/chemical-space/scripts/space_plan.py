#!/usr/bin/env python3
"""Plan an ultra-large screen: which tranches to pull, and what the funnel costs.

No network access. Everything here is arithmetic and the ZINC-22 naming
convention, both of which are cheaper to get right before downloading a
terabyte than after.

Four things this handles that a hand-written plan usually gets wrong:

* **ZINC-22 tranches are named by heavy-atom count and logP**, not molecular
  weight, and the logP sign is carried by a letter: `H25P200` is 25 heavy
  atoms and logP 2.0, `H25M100` is logP -1.0. Filtering by MW alone cannot
  address the directory tree.
* Docking a billion compounds is not a bigger version of docking a million.
  `cascade` makes the wall-clock explicit, because the answer is usually "this
  needs a synthon method, not more cores".
* **Enumerated and combinatorial spaces need different algorithms.** ZINC-22
  is stored and can be filtered; Enamine REAL Space is defined by reagents and
  reaction rules and mostly is not.
* A hit rate applied to a giga-scale library produces an unaffordable number
  of "hits". The funnel exists to make the last stage small enough to buy.

Commands:
    tranches   the ZINC-22 tranche paths covering a property window
    cascade    survivors and wall-clock for a staged screening funnel
    strategy   enumerated versus synthon, for a given library size

Examples:
    python space_plan.py tranches --hac-min 18 --hac-max 26 --logp-min 1 --logp-max 4
    python space_plan.py cascade --library-size 1e9
    python space_plan.py cascade --library-size 5e6 --stage dock:1:15 --stage rescore:0.01:120
    python space_plan.py strategy --library-size 4e10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    ENAMINE_REAL_SPACE,
    ZINC22_2D_COMPOUNDS,
    ChemicalSpaceError,
    add_common_arguments,
    emit,
)

FILES_ROOT = "https://files.docking.org/zinc22"

#: ZINC-22 splits the catalogue across three sibling trees.
SUBSETS = ("zinc-22a", "zinc-22b", "zinc-22c")

#: logP bins are 0.5 wide in the directory names, encoded as the value times
#: 100 with `P` for non-negative and `M` for negative.
LOGP_STEP = 0.5

#: A default funnel, shaped like the published V-SYNTHES-style workflows:
#: cheap and broad first, expensive and narrow last.
#: (name, fraction kept, seconds per compound)
DEFAULT_CASCADE = (
    ("property filter", 0.30, 0.0005),
    ("fast dock", 0.01, 3.0),
    ("standard dock", 0.10, 30.0),
    ("rescore / MM-GBSA", 0.10, 300.0),
    ("visual triage", 0.20, 60.0),
)


def logp_code(value: float) -> str:
    """Directory code for a logP bin: 2.0 -> P200, -1.0 -> M100."""
    hundredths = int(round(abs(value) * 100))
    return f"{'M' if value < 0 else 'P'}{hundredths:03d}"


def tranche_codes(
    hac_min: int, hac_max: int, logp_min: float, logp_max: float
) -> list[tuple[int, float, str]]:
    """Every (heavy atoms, logP bin, code) triple inside the window."""
    if hac_min > hac_max:
        raise ChemicalSpaceError("--hac-min is above --hac-max")
    if logp_min > logp_max:
        raise ChemicalSpaceError("--logp-min is above --logp-max")

    codes = []
    for hac in range(hac_min, hac_max + 1):
        steps = int(round((logp_max - logp_min) / LOGP_STEP))
        for index in range(steps + 1):
            logp = logp_min + index * LOGP_STEP
            codes.append((hac, logp, f"H{hac:02d}{logp_code(logp)}"))
    return codes


def command_tranches(args: argparse.Namespace) -> None:
    codes = tranche_codes(args.hac_min, args.hac_max, args.logp_min, args.logp_max)
    subsets = args.subset or list(SUBSETS)
    for subset in subsets:
        if subset not in SUBSETS:
            raise ChemicalSpaceError(f"`{subset}` is not a ZINC-22 subset; use one of {SUBSETS}")

    rows = [
        {
            "tranche": code,
            "heavy_atoms": hac,
            "logp_bin": logp,
            "subset": subset,
            "path": f"{FILES_ROOT}/{subset}/H{hac:02d}/{code}/",
        }
        for subset in subsets
        for hac, logp, code in codes
    ]
    print(
        f"# {len(codes)} tranches x {len(subsets)} subsets = {len(rows)} directories",
        file=sys.stderr,
    )
    print(
        "# heavy-atom count and logP address the tree; molecular weight does not. "
        "Each directory holds .smi.gz shards named <tranche>-<letter>.a.smi.gz",
        file=sys.stderr,
    )
    emit(rows, ["tranche", "heavy_atoms", "logp_bin", "subset", "path"], args.output_format)


def parse_stage(text: str) -> tuple[str, float, float]:
    """`name:keep_fraction:seconds_per_compound`."""
    parts = text.split(":")
    if len(parts) != 3:
        raise ChemicalSpaceError(
            f"`{text}` is not a stage. Use name:keep_fraction:seconds_per_compound, "
            "e.g. dock:0.01:3"
        )
    name, keep, seconds = parts
    try:
        keep_value = float(keep)
        seconds_value = float(seconds)
    except ValueError as error:
        raise ChemicalSpaceError(f"`{text}` has a non-numeric field") from error
    if not 0 < keep_value <= 1:
        raise ChemicalSpaceError(f"keep fraction for `{name}` must be in (0, 1]")
    if seconds_value < 0:
        raise ChemicalSpaceError(f"seconds for `{name}` must not be negative")
    return (name, keep_value, seconds_value)


def command_cascade(args: argparse.Namespace) -> None:
    stages = [parse_stage(text) for text in args.stage] if args.stage else list(DEFAULT_CASCADE)
    remaining = float(args.library_size)
    total_core_hours = 0.0

    rows = []
    for name, keep, seconds in stages:
        core_hours = remaining * seconds / 3600.0
        total_core_hours += core_hours
        survivors = remaining * keep
        rows.append(
            {
                "stage": name,
                "input": int(remaining),
                "keep_fraction": keep,
                "survivors": int(survivors),
                "sec_per_compound": seconds,
                "core_hours": round(core_hours, 1),
                "wall_days_at_cores": round(core_hours / max(args.cores, 1) / 24.0, 2),
            }
        )
        remaining = survivors

    print(f"# {int(args.library_size):,} in, {int(remaining):,} out", file=sys.stderr)
    print(
        f"# {total_core_hours:,.0f} core-hours total; "
        f"{total_core_hours / max(args.cores, 1) / 24.0:,.1f} days on {args.cores} cores",
        file=sys.stderr,
    )
    if total_core_hours / max(args.cores, 1) / 24.0 > 30:
        print(
            "# over a month of wall-clock. This is the point where a synthon "
            "method (V-SYNTHES, or docking a fragment library and enumerating "
            "only the winners) beats buying more cores -- see `strategy`",
            file=sys.stderr,
        )
    emit(
        rows,
        ["stage", "input", "keep_fraction", "survivors", "sec_per_compound", "core_hours", "wall_days_at_cores"],
        args.output_format,
    )


def command_strategy(args: argparse.Namespace) -> None:
    size = float(args.library_size)
    rows = [
        {
            "library_size": f"{int(size):,}",
            "zinc22_2d_total": f"{ZINC22_2D_COMPOUNDS:,}",
            "enamine_real_total": f"{ENAMINE_REAL_SPACE:,}",
        }
    ]

    if size <= 1e6:
        verdict = "enumerate and dock everything"
        detail = (
            "a million compounds is an ordinary docking run; use the full "
            "receptor treatment and spend the compute on pose quality"
        )
    elif size <= 1e8:
        verdict = "enumerate, filter hard, then dock"
        detail = (
            "still tractable enumerated, but property-filter and remove PAINS "
            "before docking -- most of the library is not worth a pose"
        )
    else:
        verdict = "synthon-based screening"
        detail = (
            "do not enumerate. Dock a minimal fragment library covering the "
            "scaffolds and synthons, keep the best, and enumerate only those -- "
            "V-SYNTHES2 reports this over 36 billion REAL Space compounds"
        )
    rows[0]["verdict"] = verdict
    rows[0]["detail"] = detail

    print(f"# {verdict}", file=sys.stderr)
    print(f"# {detail}", file=sys.stderr)
    print(
        "# ZINC-22 is stored and can be filtered directly; Enamine REAL Space is "
        "defined by reagents plus reaction rules, so most of it does not exist "
        "as a file and must be searched combinatorially",
        file=sys.stderr,
    )
    emit(
        rows,
        ["library_size", "verdict", "detail", "zinc22_2d_total", "enamine_real_total"],
        args.output_format,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    tranches = subparsers.add_parser("tranches", help="tranche paths for a property window")
    tranches.add_argument("--hac-min", type=int, default=18, help="minimum heavy atoms (default: 18)")
    tranches.add_argument("--hac-max", type=int, default=26, help="maximum heavy atoms (default: 26)")
    tranches.add_argument("--logp-min", type=float, default=1.0, help="minimum logP (default: 1.0)")
    tranches.add_argument("--logp-max", type=float, default=4.0, help="maximum logP (default: 4.0)")
    tranches.add_argument(
        "--subset", action="append", help=f"repeatable; one of {', '.join(SUBSETS)}"
    )
    add_common_arguments(tranches)
    tranches.set_defaults(handler=command_tranches)

    cascade = subparsers.add_parser("cascade", help="survivors and wall-clock for a funnel")
    cascade.add_argument("--library-size", type=float, required=True, help="e.g. 1e9")
    cascade.add_argument(
        "--stage",
        action="append",
        help="repeatable; name:keep_fraction:seconds_per_compound. Omit for a default funnel",
    )
    cascade.add_argument("--cores", type=int, default=1000, help="cores available (default: 1000)")
    add_common_arguments(cascade)
    cascade.set_defaults(handler=command_cascade)

    strategy = subparsers.add_parser("strategy", help="enumerated versus synthon")
    strategy.add_argument("--library-size", type=float, required=True, help="e.g. 4e10")
    add_common_arguments(strategy)
    strategy.set_defaults(handler=command_strategy)

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
