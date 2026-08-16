#!/usr/bin/env python3
"""Aggregate epitope burden into a whole-molecule anti-drug antibody risk picture.

Standard library only.

Four things this handles that summing epitope hits usually gets wrong:

* **Epitope count alone is a poor predictor.** Clinical ADA incidence tracks
  the number of *distinct sequence regions* presenting peptides more closely
  than the raw hit count, because overlapping peptides from one region are one
  epitope. Regions are collapsed here.
* **Germline identity dominates everything.** A fully human sequence has the
  lowest risk not because it lacks predicted epitopes -- it has plenty -- but
  because those peptides are subject to central tolerance. Predicted epitopes
  in germline framework are largely noise; epitopes in engineered regions are
  the signal.
* **Sequence risk is one input among several.** Route, dose, frequency,
  aggregation, patient immune status, and concomitant immunosuppression all
  move ADA incidence by more than sequence usually does.
* A risk category is a triage aid. Clinical ADA rates for approved antibodies
  span under 1% to over 60%, and no in-silico method resolves that range.

Commands:
    score     whole-molecule risk from a parsed epitope table
    factors   the non-sequence determinants, and their rough weight
    context   observed ADA rates for reference molecules

Examples:
    python ada_risk.py score --cores cores.tsv --length 450
    python ada_risk.py score --cores cores.tsv --length 120 --humanness 0.95
    python ada_risk.py factors
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

#: Promiscuous cores per 100 residues. Bands are triage conventions, not
#: calibrated predictors -- see `context` for why no such calibration exists.
DENSITY_BANDS = (
    (1.0, "low", "few promiscuous epitopes for a molecule this size"),
    (2.5, "moderate", "typical for a humanised or human sequence"),
    (5.0, "elevated", "worth deimmunising the worst regions before the clinic"),
    (float("inf"), "high", "characteristic of chimeric or non-human sequence"),
)

#: Germline identity below this is the dominant risk factor by a wide margin.
HUMANNESS_CONCERN = 0.85

#: Non-sequence determinants of ADA, roughly ordered by how much they move it.
FACTORS = {
    "aggregation": "the single largest non-sequence factor; aggregates are potent immunogens",
    "route": "subcutaneous > intramuscular > intravenous for ADA incidence",
    "frequency": "chronic frequent dosing raises risk; single doses rarely sensitise",
    "dose": "non-monotonic -- very high doses can induce tolerance",
    "patient_status": "autoimmune populations respond more; immunosuppressed less",
    "concomitant_immunosuppression": "methotrexate materially reduces ADA against TNF blockers",
    "product_impurities": "host cell protein and leachables act as adjuvants",
    "glycosylation": "non-human glycans (alpha-gal, NGNA) are immunogenic epitopes in themselves",
}

#: Observed clinical ADA incidence, to calibrate expectations about what any
#: prediction could possibly resolve.
REFERENCE_RATES = {
    "adalimumab (fully human)": "up to ~26%, and higher without methotrexate",
    "infliximab (chimeric)": "~10-60% depending on regimen and comedication",
    "trastuzumab (humanised)": "<1%",
    "natalizumab (humanised)": "~6-9%",
    "muromonab-CD3 (murine)": "~50-100%; withdrawn",
    "pembrolizumab (humanised)": "<2%",
}


class RiskError(RuntimeError):
    """Input that cannot support a risk estimate."""


def read_cores(path: str) -> list[dict]:
    """Read the output of `epitope_scan.py parse`."""
    stream = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8")
    with stream as handle:
        text = handle.read()
    delimiter = "," if text.count(",") > text.count("\t") else "\t"
    rows = list(csv.DictReader(text.splitlines(), delimiter=delimiter))
    if not rows:
        raise RiskError(f"{path} has no rows")

    fields = {name.lower().strip(): name for name in rows[0]}
    if "core" not in fields:
        raise RiskError(
            f"{path} has no `core` column. Pass the output of "
            "`epitope_scan.py parse`."
        )

    records = []
    for row in rows:
        try:
            alleles = int(float(row.get(fields.get("alleles_bound", ""), 0) or 0))
        except (TypeError, ValueError):
            alleles = 0
        records.append(
            {
                "core": row[fields["core"]],
                "alleles_bound": alleles,
                "promiscuous": str(row.get(fields.get("promiscuous", ""), "")).lower() == "true",
            }
        )
    return records


def band_for(density: float) -> tuple[str, str]:
    for ceiling, label, meaning in DENSITY_BANDS:
        if density < ceiling:
            return (label, meaning)
    return ("high", "")  # pragma: no cover - the last band is unbounded


def command_score(args: argparse.Namespace) -> None:
    cores = read_cores(args.cores)
    promiscuous = [core for core in cores if core["promiscuous"] or core["alleles_bound"] >= 3]

    if args.length <= 0:
        raise RiskError("--length must be positive")
    density = 100.0 * len(promiscuous) / args.length
    band, meaning = band_for(density)

    result = {
        "distinct_cores": len(cores),
        "promiscuous_cores": len(promiscuous),
        "sequence_length": args.length,
        "promiscuous_per_100aa": round(density, 2),
        "band": band,
        "interpretation": meaning,
        "humanness": args.humanness,
    }

    print(
        f"# {len(promiscuous)} promiscuous cores over {args.length} residues = "
        f"{density:.2f} per 100 aa -- {band}",
        file=sys.stderr,
    )
    if args.humanness is not None:
        if args.humanness < HUMANNESS_CONCERN:
            result["dominant_risk"] = "germline divergence"
            print(
                f"# germline identity {args.humanness:.0%} is below "
                f"{HUMANNESS_CONCERN:.0%}. This dominates the epitope count: "
                "peptides in germline framework are subject to central tolerance "
                "and are largely noise, while peptides in divergent regions are "
                "the real signal.",
                file=sys.stderr,
            )
        else:
            result["dominant_risk"] = "engineered regions and CDRs"
            print(
                f"# germline identity {args.humanness:.0%}. At this level the risk "
                "concentrates in the CDRs and any engineered positions, not the "
                "framework.",
                file=sys.stderr,
            )
    else:
        print(
            "# no --humanness given. Germline identity is the dominant sequence "
            "determinant, so this score is incomplete without it -- compute it "
            "with the `antibody-engineering` skill.",
            file=sys.stderr,
        )

    print(
        "# a triage aid, not a prediction. Clinical ADA for approved antibodies "
        "spans <1% to >60%, and no in-silico method resolves that range.",
        file=sys.stderr,
    )

    if args.output_format == "json":
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    for key, value in result.items():
        print(f"{key}\t{'' if value is None else value}")


def command_factors(args: argparse.Namespace) -> None:
    rows = [{"factor": name, "effect": note} for name, note in FACTORS.items()]
    print(
        "# these move ADA incidence more than sequence usually does. Aggregation "
        "in particular can dominate everything a sequence scan reports.",
        file=sys.stderr,
    )
    emit(rows, ["factor", "effect"], args)


def command_context(args: argparse.Namespace) -> None:
    rows = [{"molecule": name, "observed_ada": rate} for name, rate in REFERENCE_RATES.items()]
    print(
        "# adalimumab is fully human and still reaches ~26% ADA; trastuzumab is "
        "humanised and sits below 1%. Humanness helps and does not decide it.",
        file=sys.stderr,
    )
    emit(rows, ["molecule", "observed_ada"], args)


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

    score = subparsers.add_parser("score", help="whole-molecule risk from an epitope table")
    score.add_argument("--cores", required=True, help="output of epitope_scan.py parse, or -")
    score.add_argument("--length", type=int, required=True, help="sequence length in residues")
    score.add_argument(
        "--humanness", type=float, help="germline identity 0-1, from antibody-engineering"
    )
    score.set_defaults(handler=command_score)

    factors = subparsers.add_parser("factors", help="non-sequence determinants of ADA")
    factors.set_defaults(handler=command_factors)

    context = subparsers.add_parser("context", help="observed ADA rates for reference molecules")
    context.set_defaults(handler=command_context)

    for sub in (score, factors, context):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except RiskError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
