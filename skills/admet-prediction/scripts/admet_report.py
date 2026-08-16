#!/usr/bin/env python3
"""Turn ADMET-AI output into a developability verdict rather than a table of numbers.

Standard library only. ADMET-AI produces the predictions; this reads its CSV
and applies the thresholds that decide whether a series is worth making.

Four things this handles that reading the CSV directly usually gets wrong:

* **The percentile columns matter more than the raw values.** ADMET-AI reports
  each prediction against the distribution of approved drugs in DrugBank. A
  predicted clearance of 12 mL/min/kg means nothing on its own; the 80th
  percentile against approved drugs means something.
* **Direction differs per endpoint.** High solubility is good, high clearance
  is bad, and high hERG inhibition is very bad. A single "score" over the
  columns is meaningless, so each is flagged against its own direction.
* **Classification endpoints are probabilities, not classes.** hERG at 0.55 is
  not "a blocker" -- it is a coin flip from a model with real error, and
  treating it as a call discards that.
* **Predictions on molecules unlike the training data are unreliable and do
  not say so.** Applicability domain is not part of the output, so molecular
  weight and logP well outside drug-like space are flagged separately.

Commands:
    report     flag liabilities for each molecule
    summary    endpoint-level view across a set
    endpoints  the registry of endpoints and thresholds this script applies

Examples:
    python admet_report.py report --csv admet_predictions.csv
    python admet_report.py report --csv out.csv --only hERG,DILI,CYP3A4_Veith
    python admet_report.py summary --csv out.csv
    python admet_report.py endpoints
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

#: Endpoint registry. `bad_high` says which direction is the liability;
#: `concern` is the value at which it is worth acting on.
#: Names match ADMET-AI's TDC-derived column names.
ENDPOINTS = {
    # --- toxicity: the endpoints that kill programmes ---
    "hERG": {
        "kind": "classification", "bad_high": True, "concern": 0.5,
        "label": "hERG blockade", "why": "QT prolongation; a hard stop in most indications",
    },
    "AMES": {
        "kind": "classification", "bad_high": True, "concern": 0.5,
        "label": "Ames mutagenicity", "why": "genotoxicity; usually disqualifying",
    },
    "DILI": {
        "kind": "classification", "bad_high": True, "concern": 0.5,
        "label": "drug-induced liver injury", "why": "the commonest cause of post-market withdrawal",
    },
    "Carcinogens_Lagunin": {
        "kind": "classification", "bad_high": True, "concern": 0.5,
        "label": "carcinogenicity", "why": "disqualifying outside oncology",
    },
    "ClinTox": {
        "kind": "classification", "bad_high": True, "concern": 0.5,
        "label": "clinical toxicity", "why": "failed clinical trials for toxicity",
    },
    "LD50_Zhu": {
        "kind": "regression", "bad_high": False, "concern": 2.0,
        "label": "acute toxicity LD50 (log mol/kg)", "why": "lower is more acutely toxic",
    },
    # --- absorption ---
    "Caco2_Wang": {
        "kind": "regression", "bad_high": False, "concern": -5.15,
        "label": "Caco-2 permeability (log cm/s)", "why": "below -5.15 is low permeability",
    },
    "HIA_Hou": {
        "kind": "classification", "bad_high": False, "concern": 0.5,
        "label": "human intestinal absorption", "why": "low absorption limits oral dosing",
    },
    "Bioavailability_Ma": {
        "kind": "classification", "bad_high": False, "concern": 0.5,
        "label": "oral bioavailability", "why": "the summary absorption endpoint",
    },
    "Pgp_Broccatelli": {
        "kind": "classification", "bad_high": True, "concern": 0.5,
        "label": "P-glycoprotein substrate", "why": "efflux limits absorption and brain exposure",
    },
    "Solubility_AqSolDB": {
        "kind": "regression", "bad_high": False, "concern": -5.0,
        "label": "aqueous solubility (log mol/L)", "why": "below -5 is poorly soluble",
    },
    "Lipophilicity_AstraZeneca": {
        "kind": "regression", "bad_high": True, "concern": 4.0,
        "label": "lipophilicity (logD)", "why": "above 4 drives promiscuity and clearance",
    },
    # --- distribution ---
    "BBB_Martins": {
        "kind": "classification", "bad_high": None, "concern": 0.5,
        "label": "blood-brain barrier penetration",
        "why": "wanted for CNS targets, unwanted otherwise -- direction depends on the programme",
    },
    "PPBR_AZ": {
        "kind": "regression", "bad_high": True, "concern": 99.0,
        "label": "plasma protein binding (%)", "why": "above 99% leaves little free drug",
    },
    "VDss_Lombardo": {
        "kind": "regression", "bad_high": None, "concern": None,
        "label": "steady-state volume of distribution (L/kg)", "why": "context dependent",
    },
    # --- metabolism ---
    "CYP3A4_Veith": {
        "kind": "classification", "bad_high": True, "concern": 0.5,
        "label": "CYP3A4 inhibition", "why": "drug-drug interactions; 3A4 handles most drugs",
    },
    "CYP2D6_Veith": {
        "kind": "classification", "bad_high": True, "concern": 0.5,
        "label": "CYP2D6 inhibition", "why": "drug-drug interactions; polymorphic enzyme",
    },
    "CYP2C9_Veith": {
        "kind": "classification", "bad_high": True, "concern": 0.5,
        "label": "CYP2C9 inhibition", "why": "drug-drug interactions",
    },
    "CYP2C19_Veith": {
        "kind": "classification", "bad_high": True, "concern": 0.5,
        "label": "CYP2C19 inhibition", "why": "drug-drug interactions",
    },
    "CYP1A2_Veith": {
        "kind": "classification", "bad_high": True, "concern": 0.5,
        "label": "CYP1A2 inhibition", "why": "drug-drug interactions",
    },
    # --- excretion ---
    "Clearance_Hepatocyte_AZ": {
        "kind": "regression", "bad_high": True, "concern": 20.0,
        "label": "hepatocyte clearance (uL/min/1e6 cells)", "why": "high clearance shortens exposure",
    },
    "Clearance_Microsome_AZ": {
        "kind": "regression", "bad_high": True, "concern": 30.0,
        "label": "microsomal clearance (uL/min/mg)", "why": "high clearance shortens exposure",
    },
    "Half_Life_Obach": {
        "kind": "regression", "bad_high": False, "concern": 3.0,
        "label": "half-life (h)", "why": "below ~3 h makes once-daily dosing hard",
    },
}

#: Applicability-domain guardrails. Outside these, predictions are extrapolation.
PHYSCHEM_BOUNDS = {
    "molecular_weight": (150.0, 700.0),
    "logP": (-2.0, 6.0),
    "hydrogen_bond_donors": (0.0, 6.0),
    "hydrogen_bond_acceptors": (0.0, 12.0),
    "tpsa": (0.0, 180.0),
}

#: DrugBank percentile beyond which a value is unusual among approved drugs.
EXTREME_PERCENTILE = 90.0

PERCENTILE_SUFFIX = "_drugbank_approved_percentile"


class AdmetError(RuntimeError):
    """Input that is not ADMET-AI output, or is missing what is needed."""


def read_predictions(path: str) -> list[dict]:
    stream = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8")
    with stream as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise AdmetError(f"{path} has no rows")
    known = set(rows[0]) & set(ENDPOINTS)
    if not known:
        raise AdmetError(
            f"{path} has none of the expected ADMET-AI columns. Got "
            f"{sorted(rows[0])[:8]}... -- run `admet_predict --smiles_path in.csv "
            "--save_path out.csv` and pass that file."
        )
    return rows


def as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def flag(name: str, value: float | None) -> tuple[bool, str]:
    """Is this value a liability, given the endpoint's direction?"""
    spec = ENDPOINTS[name]
    if value is None or spec["concern"] is None or spec["bad_high"] is None:
        return (False, "")
    if spec["bad_high"]:
        return (value >= spec["concern"], f">= {spec['concern']:g}")
    return (value <= spec["concern"], f"<= {spec['concern']:g}")


def domain_warnings(row: dict) -> list[str]:
    """Physicochemistry outside the range the models were trained on."""
    warnings = []
    for key, (low, high) in PHYSCHEM_BOUNDS.items():
        value = as_float(row.get(key))
        if value is None:
            continue
        if value < low or value > high:
            warnings.append(f"{key}={value:.4g} outside [{low:g}, {high:g}]")
    return warnings


def command_report(args: argparse.Namespace) -> None:
    rows = read_predictions(args.csv)
    wanted = (
        [name.strip() for name in args.only.split(",")] if args.only else list(ENDPOINTS)
    )
    unknown = [name for name in wanted if name not in ENDPOINTS]
    if unknown:
        raise AdmetError(
            f"unknown endpoint(s): {', '.join(unknown)}. Run `endpoints` for the list."
        )

    out = []
    for index, row in enumerate(rows):
        smiles = row.get("smiles") or row.get("SMILES") or f"row{index}"
        liabilities = []
        for name in wanted:
            if name not in row:
                continue
            value = as_float(row[name])
            is_flagged, rule = flag(name, value)
            if not is_flagged:
                continue
            percentile = as_float(row.get(f"{name}{PERCENTILE_SUFFIX}"))
            liabilities.append(
                {
                    "endpoint": name,
                    "label": ENDPOINTS[name]["label"],
                    "value": value,
                    "rule": rule,
                    "drugbank_percentile": percentile,
                    "why": ENDPOINTS[name]["why"],
                }
            )
        warnings = domain_warnings(row)
        out.append(
            {
                "smiles": smiles,
                "liabilities": len(liabilities),
                "flagged": [item["endpoint"] for item in liabilities],
                "out_of_domain": warnings,
                "detail": liabilities,
            }
        )

    out.sort(key=lambda item: -item["liabilities"])
    clean = sum(1 for item in out if item["liabilities"] == 0)
    print(f"# {len(out)} molecules, {clean} with no flagged liability", file=sys.stderr)
    print(
        "# classification endpoints are probabilities. A hERG value of 0.55 is a "
        "coin flip from a model with real error, not a verdict.",
        file=sys.stderr,
    )
    if any(item["out_of_domain"] for item in out):
        print(
            "# some molecules fall outside drug-like physicochemical space; "
            "ADMET-AI does not report applicability domain, so those predictions "
            "are extrapolation",
            file=sys.stderr,
        )

    if args.output_format == "json":
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    writer = csv.writer(
        sys.stdout, delimiter="," if args.output_format == "csv" else "\t", lineterminator="\n"
    )
    writer.writerow(["smiles", "liabilities", "flagged", "out_of_domain"])
    for item in out:
        writer.writerow(
            [
                item["smiles"],
                item["liabilities"],
                "|".join(item["flagged"]),
                "|".join(item["out_of_domain"]),
            ]
        )


def command_summary(args: argparse.Namespace) -> None:
    rows = read_predictions(args.csv)
    out = []
    for name, spec in ENDPOINTS.items():
        values = [as_float(row.get(name)) for row in rows if row.get(name) not in (None, "")]
        values = [value for value in values if value is not None]
        if not values:
            continue
        flagged = sum(1 for value in values if flag(name, value)[0])
        ordered = sorted(values)
        middle = len(ordered) // 2
        median = (
            ordered[middle]
            if len(ordered) % 2
            else (ordered[middle - 1] + ordered[middle]) / 2.0
        )
        out.append(
            {
                "endpoint": name,
                "label": spec["label"],
                "kind": spec["kind"],
                "n": len(values),
                "median": median,
                "min": ordered[0],
                "max": ordered[-1],
                "flagged": flagged,
                "flagged_pct": round(100.0 * flagged / len(values), 1),
            }
        )
    out.sort(key=lambda item: -item["flagged_pct"])
    print(f"# {len(rows)} molecules across {len(out)} endpoints", file=sys.stderr)
    emit(out, ["endpoint", "label", "kind", "n", "median", "min", "max", "flagged", "flagged_pct"], args)


def command_endpoints(args: argparse.Namespace) -> None:
    out = [
        {
            "endpoint": name,
            "label": spec["label"],
            "kind": spec["kind"],
            "liability_direction": (
                "" if spec["bad_high"] is None else "high" if spec["bad_high"] else "low"
            ),
            "concern_at": spec["concern"],
            "why": spec["why"],
        }
        for name, spec in ENDPOINTS.items()
    ]
    print(
        "# thresholds are this skill's conventions, not ADMET-AI's -- they are "
        "here to be argued with, and BBB has no direction because it depends on "
        "whether the target is in the brain",
        file=sys.stderr,
    )
    emit(out, ["endpoint", "label", "kind", "liability_direction", "concern_at", "why"], args)


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
                else f"{row[column]:.4g}" if isinstance(row[column], float)
                else row[column]
                for column in columns
            ]
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser("report", help="flag liabilities per molecule")
    report.add_argument("--csv", required=True, help="ADMET-AI output CSV, or - for stdin")
    report.add_argument("--only", help="comma-separated endpoint names to consider")
    report.set_defaults(handler=command_report)

    summary = subparsers.add_parser("summary", help="endpoint-level view across a set")
    summary.add_argument("--csv", required=True, help="ADMET-AI output CSV, or - for stdin")
    summary.set_defaults(handler=command_summary)

    endpoints = subparsers.add_parser("endpoints", help="the endpoint registry")
    endpoints.set_defaults(handler=command_endpoints)

    for sub in (report, summary, endpoints):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except AdmetError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
