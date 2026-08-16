#!/usr/bin/env python3
"""Scale doses and clearance between species, and project a first-in-human dose.

Standard library only. The Km factors and reference body weights are from the
FDA's 2005 guidance, *Estimating the Maximum Safe Starting Dose in Initial
Clinical Trials for Therapeutics in Adult Healthy Volunteers*.

Four things this handles that a hand-rolled conversion usually gets wrong:

* **Do not scale mg/kg directly between species.** A rat mg/kg dose is not a
  human mg/kg dose. The conversion is by body surface area, which the Km
  factors encode: HED = animal dose x (Km_animal / Km_human). For the rat that
  is a factor of about 6.2, and skipping it overdoses the first human cohort
  by that factor.
* **Clearance scales with body weight to roughly the 0.75 power, not to the
  first power.** Volume scales near 1.0 and half-life near 0.25. Using the
  wrong exponent is a systematic error that grows with the weight ratio.
* The most-sensitive species sets the starting dose, not the average. `fih`
  takes the minimum HED across species.
* A default safety factor of 10 applies to a NOAEL-derived dose. It is not a
  law -- steep dose-response, irreversible toxicity, or a novel target argue
  for more, and the guidance says so.

Commands:
    hed     human equivalent dose from an animal dose
    scale   allometric scaling of a parameter across species
    fih     maximum recommended starting dose from NOAEL values

Examples:
    python allometry.py hed --species rat --dose 50
    python allometry.py scale --parameter clearance --data mouse:0.5,rat:1.8,dog:12
    python allometry.py fih --noael rat:50 --noael dog:12 --safety-factor 10
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys

#: FDA 2005 guidance, Table 1. Km = body weight (kg) / body surface area (m2).
#: HED (mg/kg) = animal dose (mg/kg) x Km_animal / Km_human.
SPECIES = {
    "human": {"km": 37, "weight_kg": 60.0},
    "child": {"km": 25, "weight_kg": 20.0},
    "mouse": {"km": 3, "weight_kg": 0.020},
    "hamster": {"km": 5, "weight_kg": 0.080},
    "rat": {"km": 6, "weight_kg": 0.150},
    "ferret": {"km": 7, "weight_kg": 0.300},
    "guinea-pig": {"km": 8, "weight_kg": 0.400},
    "rabbit": {"km": 12, "weight_kg": 1.8},
    "dog": {"km": 20, "weight_kg": 10.0},
    "monkey": {"km": 12, "weight_kg": 3.0},
    "marmoset": {"km": 6, "weight_kg": 0.350},
    "squirrel-monkey": {"km": 12, "weight_kg": 0.600},
    "baboon": {"km": 20, "weight_kg": 12.0},
    "micro-pig": {"km": 27, "weight_kg": 20.0},
    "mini-pig": {"km": 35, "weight_kg": 40.0},
}

HUMAN_KM = SPECIES["human"]["km"]

#: Conventional allometric exponents. Clearance is the important one.
EXPONENTS = {"clearance": 0.75, "volume": 1.0, "half_life": 0.25}

#: FDA default when converting a NOAEL-derived HED into a starting dose.
DEFAULT_SAFETY_FACTOR = 10.0


class AllometryError(RuntimeError):
    """Input that cannot support the calculation being asked for."""


def resolve(name: str) -> dict:
    key = name.strip().lower()
    if key not in SPECIES:
        raise AllometryError(
            f"`{name}` is not a known species. Known: {', '.join(sorted(SPECIES))}"
        )
    return SPECIES[key]


def human_equivalent_dose(species: str, dose_mg_kg: float) -> float:
    """Convert an animal mg/kg dose to the human equivalent by surface area."""
    return dose_mg_kg * resolve(species)["km"] / HUMAN_KM


def command_hed(args: argparse.Namespace) -> None:
    rows = []
    for species in args.species:
        entry = resolve(species)
        hed = human_equivalent_dose(species, args.dose)
        rows.append(
            {
                "species": species.lower(),
                "animal_dose_mg_kg": args.dose,
                "km": entry["km"],
                "divide_by": round(HUMAN_KM / entry["km"], 3),
                "hed_mg_kg": hed,
                "hed_total_mg_60kg": hed * 60.0,
            }
        )
    print(
        "# HED = animal mg/kg x Km_animal / Km_human. Body-surface-area scaling, "
        "not a direct mg/kg transfer.",
        file=sys.stderr,
    )
    emit(rows, ["species", "animal_dose_mg_kg", "km", "divide_by", "hed_mg_kg", "hed_total_mg_60kg"], args)


def parse_pairs(values: list[str], label: str) -> list[tuple[str, float]]:
    pairs = []
    for chunk in values:
        for item in chunk.split(","):
            item = item.strip()
            if not item:
                continue
            if ":" not in item:
                raise AllometryError(f"`{item}` is not {label}; use species:value")
            name, _, number = item.partition(":")
            try:
                pairs.append((name.strip().lower(), float(number)))
            except ValueError as error:
                raise AllometryError(f"`{item}` has a non-numeric value") from error
    if not pairs:
        raise AllometryError(f"no {label} given")
    return pairs


def fit_allometry(points: list[tuple[float, float]]) -> dict:
    """Least-squares fit of log(parameter) against log(weight)."""
    if len(points) < 2:
        raise AllometryError("at least two species are needed to fit an exponent")
    xs = [math.log(weight) for weight, _ in points]
    ys = [math.log(value) for _, value in points]
    n = len(points)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0:
        raise AllometryError("all species have the same body weight")
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sxx
    intercept = mean_y - slope * mean_x
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    return {
        "exponent": slope,
        "coefficient": math.exp(intercept),
        "r2": 1.0 - ss_res / ss_tot if ss_tot else 1.0,
        "n_species": n,
    }


def command_scale(args: argparse.Namespace) -> None:
    pairs = parse_pairs(args.data, "a species:value pair")
    points = [(resolve(name)["weight_kg"], value) for name, value in pairs]
    fit = fit_allometry(points)

    human_weight = args.human_weight
    predicted = fit["coefficient"] * human_weight ** fit["exponent"]
    conventional = EXPONENTS[args.parameter]
    single = pairs[0]
    single_weight = resolve(single[0])["weight_kg"]
    fixed_exponent = single[1] * (human_weight / single_weight) ** conventional

    print(
        f"# fitted exponent {fit['exponent']:.3f} (R2 {fit['r2']:.3f}) over "
        f"{fit['n_species']} species; conventional for {args.parameter} is {conventional}",
        file=sys.stderr,
    )
    if abs(fit["exponent"] - conventional) > 0.25:
        print(
            "# the fitted exponent is far from the conventional value -- with few "
            "species this is usually noise, not biology",
            file=sys.stderr,
        )
    emit(
        [
            {
                "parameter": args.parameter,
                "species_used": len(pairs),
                "fitted_exponent": fit["exponent"],
                "fitted_r2": fit["r2"],
                "human_prediction_fitted": predicted,
                "conventional_exponent": conventional,
                "human_prediction_conventional": fixed_exponent,
                "human_weight_kg": human_weight,
            }
        ],
        [
            "parameter", "species_used", "fitted_exponent", "fitted_r2",
            "human_prediction_fitted", "conventional_exponent",
            "human_prediction_conventional", "human_weight_kg",
        ],
        args,
    )


def command_fih(args: argparse.Namespace) -> None:
    pairs = parse_pairs(args.noael, "a species:NOAEL pair")
    rows = []
    for name, noael in pairs:
        hed = human_equivalent_dose(name, noael)
        rows.append(
            {
                "species": name,
                "noael_mg_kg": noael,
                "hed_mg_kg": hed,
                "hed_total_mg": hed * args.human_weight,
            }
        )
    rows.sort(key=lambda row: row["hed_mg_kg"])

    most_sensitive = rows[0]
    mrsd = most_sensitive["hed_mg_kg"] / args.safety_factor
    print(
        f"# most sensitive species: {most_sensitive['species']} "
        f"(HED {most_sensitive['hed_mg_kg']:.4g} mg/kg)",
        file=sys.stderr,
    )
    print(
        f"# MRSD = {mrsd:.4g} mg/kg = {mrsd * args.human_weight:.4g} mg for a "
        f"{args.human_weight:g} kg adult, at a safety factor of {args.safety_factor:g}",
        file=sys.stderr,
    )
    print(
        "# the minimum HED sets the dose, not the mean. Raise the safety factor "
        "for steep dose-response, irreversible toxicity, or a novel target.",
        file=sys.stderr,
    )
    for row in rows:
        row["mrsd_mg_kg"] = mrsd if row is most_sensitive else None
    emit(rows, ["species", "noael_mg_kg", "hed_mg_kg", "hed_total_mg", "mrsd_mg_kg"], args)


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    hed = subparsers.add_parser("hed", help="human equivalent dose from an animal dose")
    hed.add_argument("--species", action="append", required=True, help="repeatable, e.g. rat")
    hed.add_argument("--dose", type=float, required=True, help="animal dose in mg/kg")
    hed.set_defaults(handler=command_hed)

    scale = subparsers.add_parser("scale", help="allometric scaling across species")
    scale.add_argument(
        "--parameter", choices=tuple(EXPONENTS), default="clearance", help="what is being scaled"
    )
    scale.add_argument(
        "--data", action="append", required=True, help="species:value pairs, e.g. rat:1.8,dog:12"
    )
    scale.add_argument("--human-weight", type=float, default=60.0, help="kg (default: 60)")
    scale.set_defaults(handler=command_scale)

    fih = subparsers.add_parser("fih", help="maximum recommended starting dose")
    fih.add_argument(
        "--noael", action="append", required=True, help="species:NOAEL mg/kg, repeatable"
    )
    fih.add_argument(
        "--safety-factor", type=float, default=DEFAULT_SAFETY_FACTOR, help="default: 10"
    )
    fih.add_argument("--human-weight", type=float, default=60.0, help="kg (default: 60)")
    fih.set_defaults(handler=command_fih)

    for sub in (hed, scale, fih):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except AllometryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
