#!/usr/bin/env python3
"""Non-compartmental analysis of a concentration-time profile.

Standard library only. NCA is deliberately assumption-light: it reads the
observed curve rather than fitting a model to it, which is why it is the first
thing done to any new profile.

Four things this handles that a hand-rolled trapezoid usually gets wrong:

* **Linear-up / log-down is the default, not plain linear.** Concentrations
  fall exponentially, so a straight line between two descending points always
  overestimates the area beneath them. Plain linear trapezoid inflates AUC and
  therefore deflates clearance.
* **The terminal slope decides everything downstream.** t-half, AUC-infinity,
  Vz, and MRT all inherit lambda-z, so the fit is reported with its R-squared
  and the number of points used, and refuses to guess from fewer than three.
* **Extrapolated area must be small to be trusted.** If more than 20% of
  AUC-infinity comes from extrapolation past the last measured point, the
  sampling was too short and the number is a guess. That is flagged.
* Clearance and volume differ by route. `--route iv` gives true CL and Vz;
  after oral dosing you only ever get CL/F and Vz/F, and calling them CL and V
  silently assumes complete bioavailability.

Examples:
    python nca.py --times 0,0.25,0.5,1,2,4,8,12,24 \\
                  --conc 0,820,1200,980,610,290,95,38,6 --dose 100 --route iv
    python nca.py --from-file profile.tsv --dose 50 --route oral --format json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys

#: Above this fraction, AUC-infinity is mostly extrapolation and not evidence.
MAX_TRUSTED_EXTRAPOLATION = 0.20

#: Fewer terminal points than this cannot define a slope worth reporting.
MIN_TERMINAL_POINTS = 3


class NcaError(RuntimeError):
    """Input that cannot support the calculation being asked for."""


def read_profile(args: argparse.Namespace) -> tuple[list[float], list[float]]:
    if args.from_file:
        times, concentrations = [], []
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
                    times.append(float(parts[0]))
                    concentrations.append(float(parts[1]))
                except ValueError:
                    continue  # a header row
    else:
        if not args.times or not args.conc:
            raise NcaError("give --times and --conc, or --from-file")
        times = [float(value) for value in args.times.split(",")]
        concentrations = [float(value) for value in args.conc.split(",")]

    if len(times) != len(concentrations):
        raise NcaError(f"{len(times)} times but {len(concentrations)} concentrations")
    if len(times) < 3:
        raise NcaError("at least three points are needed")
    if any(second <= first for first, second in zip(times, times[1:])):
        raise NcaError("times must be strictly increasing")
    if any(value < 0 for value in concentrations):
        raise NcaError("concentrations must not be negative")
    return times, concentrations


def auc_linear_log(times: list[float], concentrations: list[float]) -> tuple[float, float]:
    """AUC and AUMC by linear-up / log-down trapezoid.

    Ascending or equal segments use the linear rule; descending segments use
    the logarithmic rule, which follows the exponential decay instead of
    cutting the corner above it.
    """
    auc = 0.0
    aumc = 0.0
    for (t1, c1), (t2, c2) in zip(zip(times, concentrations), zip(times[1:], concentrations[1:])):
        dt = t2 - t1
        if c1 > 0 and c2 > 0 and c2 < c1:
            ratio = math.log(c1 / c2)
            auc += dt * (c1 - c2) / ratio
            aumc += dt * (t1 * c1 - t2 * c2) / ratio - dt * dt * (c2 - c1) / (ratio * ratio)
        else:
            auc += dt * (c1 + c2) / 2.0
            aumc += dt * (t1 * c1 + t2 * c2) / 2.0
    return auc, aumc


def auc_linear(times: list[float], concentrations: list[float]) -> tuple[float, float]:
    """Plain linear trapezoid, for comparison."""
    auc = 0.0
    aumc = 0.0
    for (t1, c1), (t2, c2) in zip(zip(times, concentrations), zip(times[1:], concentrations[1:])):
        dt = t2 - t1
        auc += dt * (c1 + c2) / 2.0
        aumc += dt * (t1 * c1 + t2 * c2) / 2.0
    return auc, aumc


def terminal_slope(
    times: list[float], concentrations: list[float], *, min_points: int = MIN_TERMINAL_POINTS
) -> dict:
    """Fit lambda-z on the terminal log-linear phase.

    Points from Tmax onward are candidates. The window maximising adjusted
    R-squared is chosen, which is the conventional automatic rule.
    """
    peak_index = max(range(len(concentrations)), key=lambda i: concentrations[i])
    candidates = [
        (t, c) for t, c in zip(times[peak_index + 1 :], concentrations[peak_index + 1 :]) if c > 0
    ]
    if len(candidates) < min_points:
        raise NcaError(
            f"only {len(candidates)} positive points after Tmax; at least "
            f"{min_points} are needed to define a terminal slope"
        )

    best = None
    for start in range(len(candidates) - min_points + 1):
        window = candidates[start:]
        fit = _loglinear_fit(window)
        if fit["slope"] >= 0:
            continue
        if best is None or fit["adj_r2"] > best["adj_r2"]:
            best = fit
    if best is None:
        raise NcaError(
            "no descending terminal phase found -- concentrations never fall "
            "log-linearly, so t-half cannot be estimated"
        )
    return best


def _loglinear_fit(points: list[tuple[float, float]]) -> dict:
    n = len(points)
    xs = [t for t, _ in points]
    ys = [math.log(c) for _, c in points]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx if sxx else 0.0
    intercept = mean_y - slope * mean_x

    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot else 1.0
    adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / (n - 2) if n > 2 else r2
    return {
        "slope": slope,
        "intercept": intercept,
        "r2": r2,
        "adj_r2": adj_r2,
        "n_points": n,
        "first_time": xs[0],
    }


def back_extrapolate_c0(times: list[float], concentrations: list[float]) -> float | None:
    """Estimate C0 for an IV bolus by log-linear back-extrapolation.

    Sampling never starts at t=0, so the area between dosing and the first
    sample is missing from the trapezoid. For a bolus that area is real and
    often several percent of AUC; ignoring it inflates clearance by the same
    fraction. Convention is to fit the first two positive descending points.
    """
    positive = [(t, c) for t, c in zip(times, concentrations) if c > 0]
    if len(positive) < 2 or positive[0][0] <= 0:
        return None
    (t1, c1), (t2, c2) = positive[0], positive[1]
    if c2 >= c1:
        return None  # still absorbing or still distributing; not a bolus peak
    slope = (math.log(c2) - math.log(c1)) / (t2 - t1)
    return math.exp(math.log(c1) - slope * t1)


def analyse(times: list[float], concentrations: list[float], *, dose: float, route: str) -> dict:
    c0 = back_extrapolate_c0(times, concentrations) if route == "iv" else None
    if c0 is not None:
        times = [0.0] + list(times)
        concentrations = [c0] + list(concentrations)

    auc_t, aumc_t = auc_linear_log(times, concentrations)
    auc_linear_only, _ = auc_linear(times, concentrations)

    peak_index = max(range(len(concentrations)), key=lambda i: concentrations[i])
    fit = terminal_slope(times, concentrations)
    lambda_z = -fit["slope"]
    half_life = math.log(2.0) / lambda_z

    last_time = times[-1]
    last_conc = concentrations[-1]
    auc_extrap = last_conc / lambda_z
    auc_inf = auc_t + auc_extrap
    aumc_inf = aumc_t + last_time * last_conc / lambda_z + last_conc / (lambda_z ** 2)
    extrap_fraction = auc_extrap / auc_inf if auc_inf else 0.0

    clearance = dose / auc_inf if auc_inf else None
    vz = dose / (lambda_z * auc_inf) if auc_inf else None
    mrt = aumc_inf / auc_inf if auc_inf else None
    vss = clearance * mrt if (clearance is not None and mrt is not None) else None

    oral = route == "oral"
    return {
        "c0_back_extrapolated": c0,
        "cmax": concentrations[peak_index],
        "tmax": times[peak_index],
        "clast": last_conc,
        "tlast": last_time,
        "auc_0_t": auc_t,
        "auc_0_inf": auc_inf,
        "auc_extrap_pct": 100.0 * extrap_fraction,
        "auc_linear_only": auc_linear_only,
        "lambda_z": lambda_z,
        "half_life": half_life,
        "terminal_points": fit["n_points"],
        "terminal_r2": fit["r2"],
        "clearance_label": "CL/F" if oral else "CL",
        "clearance": clearance,
        "volume_label": "Vz/F" if oral else "Vz",
        "vz": vz,
        "mrt": mrt,
        "vss": None if oral else vss,
    }


COLUMNS = (
    "c0_back_extrapolated", "cmax", "tmax", "clast", "tlast", "auc_0_t", "auc_0_inf", "auc_extrap_pct",
    "lambda_z", "half_life", "terminal_points", "terminal_r2",
    "clearance_label", "clearance", "volume_label", "vz", "mrt", "vss",
)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        times, concentrations = read_profile(args)
        result = analyse(times, concentrations, dose=args.dose, route=args.route)
    except NcaError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if result["auc_extrap_pct"] > 100 * MAX_TRUSTED_EXTRAPOLATION:
        print(
            f"# warning: {result['auc_extrap_pct']:.1f}% of AUC-infinity is "
            "extrapolated past the last sample. Above 20% the sampling was too "
            "short and AUC-infinity, CL, and Vz are guesses.",
            file=sys.stderr,
        )
    if result["terminal_r2"] < 0.9:
        print(
            f"# warning: terminal fit R2 is {result['terminal_r2']:.3f} over "
            f"{result['terminal_points']} points -- t-half is poorly determined",
            file=sys.stderr,
        )
    if args.route == "oral":
        print(
            "# oral dosing: clearance and volume are CL/F and Vz/F. Calling them "
            "CL and V assumes F = 1, which is almost never true.",
            file=sys.stderr,
        )
    difference = 100.0 * (result["auc_linear_only"] - result["auc_0_t"]) / result["auc_0_t"]
    print(
        f"# linear-only trapezoid would give AUC(0-t) {difference:+.1f}% vs "
        "linear-up/log-down (used here)",
        file=sys.stderr,
    )

    if args.output_format == "json":
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        writer = csv.writer(
            sys.stdout, delimiter="," if args.output_format == "csv" else "\t", lineterminator="\n"
        )
        writer.writerow(["metric", "value"])
        for key in COLUMNS:
            value = result[key]
            writer.writerow([key, f"{value:.6g}" if isinstance(value, float) else value])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--times", help="comma-separated sample times")
    parser.add_argument("--conc", help="comma-separated concentrations")
    parser.add_argument(
        "--from-file", help="two columns, time then concentration; - for stdin"
    )
    parser.add_argument("--dose", type=float, required=True, help="dose in mass units")
    parser.add_argument(
        "--route",
        choices=("iv", "oral"),
        default="iv",
        help="iv gives CL and Vz; oral gives CL/F and Vz/F (default: iv)",
    )
    parser.add_argument(
        "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
