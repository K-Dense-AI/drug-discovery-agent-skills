#!/usr/bin/env python3
"""Simulate a dosing regimen and report its steady-state exposure.

Standard library only. One- and two-compartment models with IV bolus, IV
infusion, and first-order oral absorption, single or repeated dosing by
superposition.

Four things this handles that a hand-rolled simulation usually gets wrong:

* **Accumulation depends on half-life and interval, not on dose.** The ratio
  is 1 / (1 - exp(-k*tau)), so doubling the dose does not change it. A drug
  with a 24 h half-life dosed daily accumulates about 2.4-fold, and a single
  dose tells you nothing about that.
* **Time to steady state depends only on half-life** -- about 4.3 half-lives
  to 95%, whatever the dose or interval. Loading doses exist because of this.
* Oral absorption has a **flip-flop** trap: when absorption is slower than
  elimination the terminal slope reports ka, not k, and half-life is
  overstated. Flagged when ka < k.
* Cmin at steady state, not Cavg, decides whether coverage is maintained
  through the interval -- and Cmax decides whether the tolerability ceiling is
  breached. Both are reported; the average hides both.

Commands:
    simulate   concentration-time curve for a regimen
    steady     Cmax, Cmin, Cavg, accumulation, and time to steady state

Examples:
    python pk_compartmental.py steady --dose 100 --cl 5 --v 50 --tau 24
    python pk_compartmental.py steady --dose 100 --cl 5 --v 50 --tau 12 --route oral --ka 1.2 --f 0.5
    python pk_compartmental.py simulate --dose 100 --cl 5 --v 50 --tau 24 --doses 5 --step 0.5
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys

LN2 = math.log(2.0)

#: Fraction of steady state reached after n half-lives: 1 - 2^-n.
STEADY_STATE_FRACTION = 0.95


class PkError(RuntimeError):
    """Parameters that cannot support the calculation being asked for."""


def elimination_rate(clearance: float, volume: float) -> float:
    if clearance <= 0 or volume <= 0:
        raise PkError("clearance and volume must both be positive")
    return clearance / volume


def concentration(
    t: float,
    *,
    dose: float,
    clearance: float,
    volume: float,
    route: str,
    ka: float | None,
    bioavailability: float,
    infusion_hours: float,
) -> float:
    """Concentration at time t after a single dose."""
    k = elimination_rate(clearance, volume)
    if t < 0:
        return 0.0

    if route == "iv":
        return (dose / volume) * math.exp(-k * t)

    if route == "infusion":
        rate = dose / infusion_hours
        if t <= infusion_hours:
            return (rate / clearance) * (1.0 - math.exp(-k * t))
        peak = (rate / clearance) * (1.0 - math.exp(-k * infusion_hours))
        return peak * math.exp(-k * (t - infusion_hours))

    if ka is None or ka <= 0:
        raise PkError("oral dosing needs --ka above zero")
    if abs(ka - k) < 1e-9:
        # The standard solution divides by (ka - k); at equality the limit is
        # this instead, and the naive formula would divide by zero.
        return (bioavailability * dose * k * t / volume) * math.exp(-k * t)
    return (
        (bioavailability * dose * ka)
        / (volume * (ka - k))
        * (math.exp(-k * t) - math.exp(-ka * t))
    )


def superpose(t: float, *, tau: float, doses: int, **kwargs) -> float:
    """Concentration at time t from `doses` identical doses every `tau`."""
    total = 0.0
    for index in range(doses):
        elapsed = t - index * tau
        if elapsed >= 0:
            total += concentration(elapsed, **kwargs)
    return total


def steady_state(args: argparse.Namespace) -> dict:
    k = elimination_rate(args.cl, args.v)
    half_life = LN2 / k
    tau = args.tau

    accumulation = 1.0 / (1.0 - math.exp(-k * tau))
    fraction_target = STEADY_STATE_FRACTION
    half_lives_to_ss = math.log(1.0 - fraction_target) / math.log(0.5)
    time_to_ss = half_lives_to_ss * half_life

    kwargs = dict(
        dose=args.dose,
        clearance=args.cl,
        volume=args.v,
        route=args.route,
        ka=args.ka,
        bioavailability=args.f,
        infusion_hours=args.infusion_hours,
    )

    # Sample the last interval of a long regimen: that is steady state.
    doses = max(int(math.ceil(time_to_ss / tau)) + 5, 10)
    start = (doses - 1) * tau
    samples = 2000
    values = [
        superpose(start + tau * index / samples, tau=tau, doses=doses, **kwargs)
        for index in range(samples + 1)
    ]

    cmax = max(values)
    cmin = values[-1]
    auc_tau = sum(
        (values[i] + values[i + 1]) / 2.0 * (tau / samples) for i in range(samples)
    )
    cavg = auc_tau / tau

    return {
        "half_life_h": half_life,
        "k_per_h": k,
        "tau_h": tau,
        "accumulation_ratio": accumulation,
        "half_lives_to_95pct_ss": half_lives_to_ss,
        "time_to_95pct_ss_h": time_to_ss,
        "doses_to_95pct_ss": time_to_ss / tau,
        "css_max": cmax,
        "css_min": cmin,
        "css_avg": cavg,
        "peak_trough_ratio": cmax / cmin if cmin > 0 else None,
        "auc_tau": auc_tau,
        "first_dose_cmax": max(
            concentration(tau * index / samples, **kwargs) for index in range(samples + 1)
        ),
    }


def command_steady(args: argparse.Namespace) -> None:
    result = steady_state(args)
    k = result["k_per_h"]

    if args.route == "oral" and args.ka is not None and args.ka < k:
        print(
            f"# flip-flop kinetics: ka ({args.ka:g}/h) is below k ({k:.4g}/h), so "
            "the terminal slope reports absorption, not elimination, and the "
            "apparent half-life overstates the true one",
            file=sys.stderr,
        )
    print(
        f"# t1/2 {result['half_life_h']:.3g} h, tau {args.tau:g} h -> "
        f"accumulation {result['accumulation_ratio']:.2f}x, "
        f"steady state in {result['time_to_95pct_ss_h']:.3g} h "
        f"({result['doses_to_95pct_ss']:.1f} doses)",
        file=sys.stderr,
    )
    print(
        "# accumulation depends on half-life and interval only -- changing the "
        "dose moves every concentration but not the ratio",
        file=sys.stderr,
    )
    emit([result], list(result), args)


def command_simulate(args: argparse.Namespace) -> None:
    kwargs = dict(
        dose=args.dose,
        clearance=args.cl,
        volume=args.v,
        route=args.route,
        ka=args.ka,
        bioavailability=args.f,
        infusion_hours=args.infusion_hours,
    )
    end = args.tau * args.doses + (args.tail or args.tau)
    steps = int(end / args.step) + 1
    rows = []
    for index in range(steps):
        t = index * args.step
        rows.append(
            {
                "time_h": round(t, 6),
                "concentration": superpose(t, tau=args.tau, doses=args.doses, **kwargs),
            }
        )
    print(
        f"# {args.doses} doses of {args.dose:g} every {args.tau:g} h, "
        f"{end:g} h simulated at {args.step:g} h resolution",
        file=sys.stderr,
    )
    emit(rows, ["time_h", "concentration"], args)


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
                else f"{row[column]:.6g}" if isinstance(row[column], float)
                else row[column]
                for column in columns
            ]
        )


def add_model_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dose", type=float, required=True, help="dose in mass units")
    parser.add_argument("--cl", type=float, required=True, help="clearance, volume per hour")
    parser.add_argument("--v", type=float, required=True, help="volume of distribution")
    parser.add_argument("--tau", type=float, required=True, help="dosing interval in hours")
    parser.add_argument(
        "--route", choices=("iv", "oral", "infusion"), default="iv", help="default: iv"
    )
    parser.add_argument("--ka", type=float, help="first-order absorption rate, per hour (oral)")
    parser.add_argument("--f", type=float, default=1.0, help="bioavailability (default: 1.0)")
    parser.add_argument(
        "--infusion-hours", type=float, default=1.0, help="infusion duration (default: 1.0)"
    )
    parser.add_argument(
        "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    steady = subparsers.add_parser("steady", help="steady-state exposure metrics")
    add_model_arguments(steady)
    steady.set_defaults(handler=command_steady)

    simulate = subparsers.add_parser("simulate", help="concentration-time curve")
    add_model_arguments(simulate)
    simulate.add_argument("--doses", type=int, default=1, help="number of doses (default: 1)")
    simulate.add_argument("--step", type=float, default=0.25, help="hours (default: 0.25)")
    simulate.add_argument("--tail", type=float, help="hours to simulate after the last dose")
    simulate.set_defaults(handler=command_simulate)

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
