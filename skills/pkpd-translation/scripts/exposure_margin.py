#!/usr/bin/env python3
"""Check whether a projected human exposure covers the target and clears toxicology.

Standard library only. This is the arithmetic that decides whether a compound
can reach its target concentration at a dose that is safe -- the question
behind most candidate-selection meetings.

Four things this handles that a hand-rolled comparison usually gets wrong:

* **A cell IC50 is a free-drug number; a plasma concentration is not.** Only
  unbound drug crosses membranes and engages the target, so the comparison
  must be free-versus-free. At 99% protein binding, total Cmax overstates the
  driver a hundredfold, and this is the single most common translation error.
* **Which exposure metric matters depends on the target.** Time above a
  threshold drives time-dependent pharmacology; Cmax drives rapidly reversible
  targets and most tolerability ceilings; AUC drives cytotoxics. Reporting one
  and calling it coverage is a choice that should be explicit.
* Safety margin is computed on the same metric as efficacy, and on the same
  binding basis. Mixing a total-drug NOAEL Cmax against a free-drug efficacy
  target inflates the margin by the binding factor.
* A margin below about 10 on a first-in-human candidate is generally
  uncomfortable; the number to report is the margin, not a verdict.

Commands:
    coverage   time above a target concentration across a dosing interval
    margin     safety margin between a toxicology exposure and an efficacious one

Examples:
    python exposure_margin.py coverage --dose 100 --cl 5 --v 50 --tau 24 \\
        --target-conc 0.05 --fu 0.02
    python exposure_margin.py margin --tox-cmax 12000 --tox-auc 180000 \\
        --eff-cmax 400 --eff-auc 6000
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pk_compartmental import PkError, concentration, elimination_rate, superpose  # noqa: E402

#: Below this, a first-in-human safety margin is generally considered thin.
COMFORTABLE_MARGIN = 10.0


def command_coverage(args: argparse.Namespace) -> None:
    k = elimination_rate(args.cl, args.v)
    half_life = math.log(2.0) / k
    tau = args.tau

    kwargs = dict(
        dose=args.dose,
        clearance=args.cl,
        volume=args.v,
        route=args.route,
        ka=args.ka,
        bioavailability=args.f,
        infusion_hours=args.infusion_hours,
    )
    doses = max(int(math.ceil(5 * half_life / tau)) + 5, 10)
    start = (doses - 1) * tau

    samples = 4000
    step = tau / samples
    total_values = [
        superpose(start + index * step, tau=tau, doses=doses, **kwargs)
        for index in range(samples + 1)
    ]
    free_values = [value * args.fu for value in total_values]

    above = sum(1 for value in free_values if value >= args.target_conc)
    fraction = above / (samples + 1)

    result = {
        "fu": args.fu,
        "target_free_conc": args.target_conc,
        "css_max_total": max(total_values),
        "css_min_total": min(total_values),
        "css_max_free": max(free_values),
        "css_min_free": min(free_values),
        "hours_above_target": fraction * tau,
        "pct_interval_above_target": 100.0 * fraction,
        "trough_covers_target": min(free_values) >= args.target_conc,
        "peak_over_target": max(free_values) / args.target_conc if args.target_conc else None,
        "half_life_h": half_life,
    }

    print(
        f"# free fraction {args.fu:g}: total Cmax {result['css_max_total']:.4g} -> "
        f"free {result['css_max_free']:.4g}",
        file=sys.stderr,
    )
    if args.fu >= 1.0:
        print(
            "# fu = 1 assumes no protein binding. If you have not measured it, "
            "this comparison is total-versus-free and will overstate coverage.",
            file=sys.stderr,
        )
    print(
        f"# free concentration exceeds the target for "
        f"{result['pct_interval_above_target']:.1f}% of the interval "
        f"({result['hours_above_target']:.2g} of {tau:g} h)",
        file=sys.stderr,
    )
    if not result["trough_covers_target"]:
        print(
            "# the trough falls below target -- acceptable for time-independent "
            "pharmacology, not for a target needing continuous suppression",
            file=sys.stderr,
        )
    emit([result], list(result), args)


def command_margin(args: argparse.Namespace) -> None:
    rows = []
    for label, tox, eff in (
        ("Cmax", args.tox_cmax, args.eff_cmax),
        ("AUC", args.tox_auc, args.eff_auc),
    ):
        if tox is None or eff is None:
            continue
        if eff <= 0:
            raise PkError(f"efficacious {label} must be positive")
        rows.append(
            {
                "metric": label,
                "tox_exposure": tox,
                "efficacious_exposure": eff,
                "margin": tox / eff,
                "comfortable": tox / eff >= COMFORTABLE_MARGIN,
            }
        )
    if not rows:
        raise PkError("give at least one matched pair: --tox-cmax/--eff-cmax or --tox-auc/--eff-auc")

    smallest = min(row["margin"] for row in rows)
    print(f"# limiting margin: {smallest:.3g}x", file=sys.stderr)
    if smallest < COMFORTABLE_MARGIN:
        print(
            f"# below {COMFORTABLE_MARGIN:g}x. Thin for a first-in-human candidate, "
            "though acceptable in oncology and where the toxicity is monitorable "
            "and reversible.",
            file=sys.stderr,
        )
    print(
        "# both numbers must be on the same binding basis. A total-drug tox Cmax "
        "against a free-drug efficacy target inflates the margin by 1/fu.",
        file=sys.stderr,
    )
    emit(rows, ["metric", "tox_exposure", "efficacious_exposure", "margin", "comfortable"], args)


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
                "" if row.get(column) is None
                else "true" if row[column] is True
                else "false" if row[column] is False
                else f"{row[column]:.6g}" if isinstance(row[column], float)
                else row[column]
                for column in columns
            ]
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    coverage = subparsers.add_parser("coverage", help="time above a target concentration")
    coverage.add_argument("--dose", type=float, required=True)
    coverage.add_argument("--cl", type=float, required=True, help="clearance, volume per hour")
    coverage.add_argument("--v", type=float, required=True, help="volume of distribution")
    coverage.add_argument("--tau", type=float, required=True, help="dosing interval, hours")
    coverage.add_argument(
        "--target-conc", type=float, required=True, help="free concentration to exceed"
    )
    coverage.add_argument(
        "--fu", type=float, default=1.0, help="unbound fraction in plasma (default: 1.0)"
    )
    coverage.add_argument("--route", choices=("iv", "oral", "infusion"), default="iv")
    coverage.add_argument("--ka", type=float, help="absorption rate per hour (oral)")
    coverage.add_argument("--f", type=float, default=1.0, help="bioavailability")
    coverage.add_argument("--infusion-hours", type=float, default=1.0)
    coverage.set_defaults(handler=command_coverage)

    margin = subparsers.add_parser("margin", help="toxicology versus efficacious exposure")
    margin.add_argument("--tox-cmax", type=float, help="Cmax at the NOAEL")
    margin.add_argument("--eff-cmax", type=float, help="Cmax at the efficacious dose")
    margin.add_argument("--tox-auc", type=float, help="AUC at the NOAEL")
    margin.add_argument("--eff-auc", type=float, help="AUC at the efficacious dose")
    margin.set_defaults(handler=command_margin)

    for sub in (coverage, margin):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except PkError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
