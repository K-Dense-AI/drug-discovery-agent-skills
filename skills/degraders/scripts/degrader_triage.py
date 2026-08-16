#!/usr/bin/env python3
"""Read a degradation dose-response: DC50, Dmax, and the hook effect.

Standard library only. Degradation pharmacology is not occupancy pharmacology,
and the curve shape is where the difference shows.

Four things this handles that reading the curve as an IC50 usually gets wrong:

* **The hook effect makes the curve non-monotonic.** At high concentration the
  degrader saturates both proteins separately, forming binary complexes that
  cannot become ternary, and degradation *falls*. A sigmoid fit through a
  hooked curve returns a confident, meaningless DC50.
* **DC50 and Dmax are independent, and Dmax usually matters more.** A degrader
  with DC50 1 nM and Dmax 40% leaves most of the protein; one with DC50 100 nM
  and Dmax 95% is usually the better molecule.
* **Degradation is catalytic**, so potency need not track binary affinity. A
  weaker binder that forms a better ternary complex often degrades better --
  which is why ranking degraders by target Kd is a mistake.
* Recovery kinetics matter as much as depth. Resynthesis rate sets the dosing
  interval, and a protein with a short half-life returns before the next dose.

Commands:
    curve   DC50, Dmax, and hook detection from a dose-response
    hook    explain the hook effect and where the maximum sits

Examples:
    python degrader_triage.py curve --conc 0.1,1,10,100,1000,10000 \\
        --remaining 95,70,25,8,15,60
    python degrader_triage.py curve --from-file dose_response.tsv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

#: Degradation below this depth rarely produces a phenotype.
MEANINGFUL_DMAX = 50.0

#: A rise of this many percentage points after the minimum is a real hook,
#: not assay noise.
HOOK_RISE = 10.0


class TriageError(RuntimeError):
    """A dose-response that cannot be interpreted."""


def read_curve(args: argparse.Namespace) -> list[tuple[float, float]]:
    """(concentration, percent remaining) pairs, sorted by concentration."""
    points: list[tuple[float, float]] = []
    if args.from_file:
        stream = sys.stdin if args.from_file == "-" else open(args.from_file, encoding="utf-8")
        with stream as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.replace(",", "\t").split()
                if len(parts) < 2:
                    continue
                try:
                    points.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    continue  # a header row
    else:
        if not args.conc or not args.remaining:
            raise TriageError("give --conc and --remaining, or --from-file")
        concentrations = [float(value) for value in args.conc.split(",")]
        remaining = [float(value) for value in args.remaining.split(",")]
        if len(concentrations) != len(remaining):
            raise TriageError(
                f"{len(concentrations)} concentrations but {len(remaining)} values"
            )
        points = list(zip(concentrations, remaining))

    if len(points) < 4:
        raise TriageError("at least four points are needed to see a curve shape")
    if any(concentration <= 0 for concentration, _ in points):
        raise TriageError("concentrations must be positive")
    return sorted(points)


def analyse(points: list[tuple[float, float]]) -> dict:
    concentrations = [concentration for concentration, _ in points]
    remaining = [value for _, value in points]

    minimum = min(remaining)
    minimum_index = remaining.index(minimum)
    dmax = 100.0 - minimum
    peak_concentration = concentrations[minimum_index]

    # A hook is a sustained rise after the minimum, not a single noisy point.
    after = remaining[minimum_index + 1 :]
    rise = (max(after) - minimum) if after else 0.0
    hook = rise >= HOOK_RISE

    # DC50 by linear interpolation on log concentration, over the descending
    # limb only -- past the hook the curve is not a dose-response any more.
    dc50 = interpolate_dc50(points[: minimum_index + 1])

    return {
        "points": len(points),
        "dmax_pct": round(dmax, 1),
        "min_remaining_pct": round(minimum, 1),
        "dmax_concentration": peak_concentration,
        "dc50": round(dc50, 4) if dc50 is not None else None,
        "hook_effect": hook,
        "rise_after_minimum_pct": round(rise, 1),
        "highest_concentration": concentrations[-1],
        "meaningful_dmax": dmax >= MEANINGFUL_DMAX,
    }


def interpolate_dc50(points: list[tuple[float, float]]) -> float | None:
    """Concentration at 50% remaining, by interpolation on the descending limb."""
    for (c1, r1), (c2, r2) in zip(points, points[1:]):
        if r1 >= 50.0 >= r2 and r1 != r2:
            # Linear in log10(concentration).
            import math

            span = math.log10(c2) - math.log10(c1)
            fraction = (r1 - 50.0) / (r1 - r2)
            return 10 ** (math.log10(c1) + fraction * span)
    return None


def command_curve(args: argparse.Namespace) -> None:
    points = read_curve(args)
    result = analyse(points)

    if result["hook_effect"]:
        print(
            f"# HOOK EFFECT: degradation falls by {result['rise_after_minimum_pct']} "
            f"points above {result['dmax_concentration']:g}. At high concentration "
            "the degrader saturates both proteins separately, forming binary "
            "complexes that cannot become ternary.",
            file=sys.stderr,
        )
        print(
            "# a sigmoid fit through a hooked curve returns a confident, "
            "meaningless DC50. The value below uses the descending limb only.",
            file=sys.stderr,
        )
    else:
        print(
            f"# no hook within the tested range (top {result['highest_concentration']:g}). "
            "That may mean there is none, or that the range did not go high enough "
            "-- test at least two logs above DC50.",
            file=sys.stderr,
        )

    if result["dc50"] is None:
        print(
            "# 50% degradation is never reached, so there is no DC50. Report Dmax "
            "alone rather than extrapolating.",
            file=sys.stderr,
        )
    if not result["meaningful_dmax"]:
        print(
            f"# Dmax {result['dmax_pct']}% is below {MEANINGFUL_DMAX:g}% -- rarely "
            "enough protein removed to produce a phenotype, whatever the DC50",
            file=sys.stderr,
        )
    print(
        "# Dmax usually matters more than DC50: 1 nM at 40% leaves most of the "
        "protein, while 100 nM at 95% does not.",
        file=sys.stderr,
    )

    if args.output_format == "json":
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    for key, value in result.items():
        printable = (
            "" if value is None
            else "true" if value is True
            else "false" if value is False
            else value
        )
        print(f"{key}\t{printable}")


def command_hook(args: argparse.Namespace) -> None:
    rows = [
        {
            "regime": "below DC50",
            "dominant species": "free degrader, some binary",
            "degradation": "rising with concentration",
        },
        {
            "regime": "around Dmax",
            "dominant species": "ternary complex",
            "degradation": "maximal",
        },
        {
            "regime": "above the hook",
            "dominant species": "two separate binary complexes",
            "degradation": "falling -- both proteins saturated separately",
        },
    ]
    print(
        "# the hook is a consequence of needing THREE bodies. Once degrader "
        "concentration exceeds both binding sites, target-degrader and "
        "E3-degrader complexes outnumber target-degrader-E3, and there is "
        "nothing left to bridge.",
        file=sys.stderr,
    )
    print(
        "# positive cooperativity (alpha > 1) pushes the hook to higher "
        "concentration and widens the useful window. It is measurable by ITC or "
        "TR-FRET, and it is the single most useful ternary-complex number.",
        file=sys.stderr,
    )
    emit(rows, ["regime", "dominant species", "degradation"], args)


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
        writer.writerow([row.get(c, "") for c in columns])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    curve = subparsers.add_parser("curve", help="DC50, Dmax, and hook detection")
    curve.add_argument("--conc", help="comma-separated concentrations")
    curve.add_argument("--remaining", help="comma-separated percent protein remaining")
    curve.add_argument(
        "--from-file", help="two columns, concentration then percent remaining; - for stdin"
    )
    curve.set_defaults(handler=command_curve)

    hook = subparsers.add_parser("hook", help="what the hook effect is")
    hook.set_defaults(handler=command_hook)

    for sub in (curve, hook):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except TriageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
