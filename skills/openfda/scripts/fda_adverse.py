#!/usr/bin/env python3
"""Query FAERS adverse-event reports and score drug-event pairs for disproportionality.

Four things this handles that a hand-written query usually gets wrong:

* A drug with no reports comes back as HTTP 404, not an empty list. Treated as
  a real zero here, so "no signal" and "request failed" stay distinguishable.
* Ranking reactions by paging through reports is both slow and wrong -- the
  skip ceiling truncates at 25000. `reactions` uses a server-side `count=`
  aggregation, which is computed over the whole matching set.
* PRR and ROR need a 2x2 table built from four separate totals, not from one
  search. `signal` issues those four queries and shows the table it built.
* FAERS has no denominator: it counts reports, not patients, and never
  exposure. A high PRR is a hypothesis about reporting, not a risk estimate.

Commands:
    reports     count and sample reports for a drug
    reactions   rank reported reactions for a drug (server-side aggregation)
    signal      PRR, ROR, and chi-squared for one drug-event pair

Examples:
    python fda_adverse.py reports --drug atorvastatin
    python fda_adverse.py reactions --drug atorvastatin --top 25
    python fda_adverse.py reactions --drug atorvastatin --serious
    python fda_adverse.py signal --drug atorvastatin --reaction RHABDOMYOLYSIS
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    OpenFdaError,
    add_common_arguments,
    clamp_limit,
    count_terms,
    emit,
    get,
    last_updated,
    quote,
    total_matching,
)

ENDPOINT = "drug/event"

#: The EMA/MHRA screening rule: a pair is flagged when all three hold.
SIGNAL_MIN_REPORTS = 3
SIGNAL_MIN_PRR = 2.0
SIGNAL_MIN_CHI2 = 4.0


def drug_clause(drug: str) -> str:
    """Match a drug by brand, generic, or substance name.

    `patient.drug.medicinalproduct` alone misses reports that recorded only the
    normalised openFDA name, and vice versa, so all four fields are searched.
    """
    term = quote(drug)
    fields = (
        "patient.drug.medicinalproduct",
        "patient.drug.openfda.brand_name",
        "patient.drug.openfda.generic_name",
        "patient.drug.openfda.substance_name",
    )
    return "(" + "+OR+".join(f"{field}:{term}" for field in fields) + ")"


def reaction_clause(reaction: str) -> str:
    return f"patient.reaction.reactionmeddrapt:{quote(reaction)}"


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------


def command_reports(args: argparse.Namespace) -> None:
    search = drug_clause(args.drug)
    if args.serious:
        search += "+AND+serious:1"
    total = total_matching(ENDPOINT, search, base_url=args.base_url)
    stamp = last_updated(ENDPOINT, base_url=args.base_url)

    print(f"# drug: {args.drug}", file=sys.stderr)
    print(f"# matching reports: {total}", file=sys.stderr)
    print(f"# FAERS data current to: {stamp}", file=sys.stderr)
    if total == 0:
        print(
            "# no reports -- check the spelling, or try the generic name",
            file=sys.stderr,
        )
        return

    document = get(
        ENDPOINT,
        {"search": search, "limit": clamp_limit(args.sample)},
        base_url=args.base_url,
    )
    rows = []
    for record in document.get("results") or []:
        patient = record.get("patient") or {}
        reactions = [
            item.get("reactionmeddrapt")
            for item in (patient.get("reaction") or [])
            if item.get("reactionmeddrapt")
        ]
        rows.append(
            {
                "safetyreportid": record.get("safetyreportid"),
                "receivedate": record.get("receivedate"),
                "serious": record.get("serious"),
                "country": record.get("occurcountry"),
                "age": (patient.get("patientonsetage") or ""),
                "sex": _sex(patient.get("patientsex")),
                "reactions": reactions[:6],
            }
        )
    emit(
        rows,
        ["safetyreportid", "receivedate", "serious", "country", "age", "sex", "reactions"],
        args.output_format,
    )


def _sex(code: object) -> str:
    return {"1": "male", "2": "female"}.get(str(code), "")


# --------------------------------------------------------------------------
# reactions
# --------------------------------------------------------------------------


def command_reactions(args: argparse.Namespace) -> None:
    search = drug_clause(args.drug)
    if args.serious:
        search += "+AND+serious:1"
    total = total_matching(ENDPOINT, search, base_url=args.base_url)
    if total == 0:
        print(f"# no reports for {args.drug}", file=sys.stderr)
        return

    terms = count_terms(
        ENDPOINT,
        search,
        "patient.reaction.reactionmeddrapt.exact",
        limit=args.top,
        base_url=args.base_url,
    )
    print(f"# {total} reports, top {len(terms)} reactions", file=sys.stderr)
    print(
        "# share is of reports for this drug -- not a rate, and not comparable "
        "across drugs without a disproportionality score",
        file=sys.stderr,
    )
    rows = [
        {
            "reaction": term.get("term"),
            "reports": term.get("count"),
            "share_pct": round(100.0 * (term.get("count") or 0) / total, 2),
        }
        for term in terms
    ]
    emit(rows, ["reaction", "reports", "share_pct"], args.output_format)


# --------------------------------------------------------------------------
# signal
# --------------------------------------------------------------------------


def command_signal(args: argparse.Namespace) -> None:
    drug = drug_clause(args.drug)
    reaction = reaction_clause(args.reaction)

    a = total_matching(ENDPOINT, f"{drug}+AND+{reaction}", base_url=args.base_url)
    drug_total = total_matching(ENDPOINT, drug, base_url=args.base_url)
    reaction_total = total_matching(ENDPOINT, reaction, base_url=args.base_url)
    grand_total = total_matching(ENDPOINT, "_exists_:safetyreportid", base_url=args.base_url)

    stats = contingency(a, drug_total, reaction_total, grand_total)
    if stats is None:
        print(
            f"error: cannot build a 2x2 table from a={a}, drug={drug_total}, "
            f"reaction={reaction_total}, all={grand_total}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"# {args.drug} x {args.reaction}", file=sys.stderr)
    print(
        f"# 2x2: a={stats['a']} b={stats['b']} c={stats['c']} d={stats['d']}",
        file=sys.stderr,
    )
    print(
        "# FAERS counts reports, not patients, and has no exposure denominator; "
        "treat any signal as a hypothesis, not a risk estimate",
        file=sys.stderr,
    )
    emit(
        [stats],
        ["a", "b", "c", "d", "prr", "ror", "ror_ci_low", "ror_ci_high", "chi2", "signal"],
        args.output_format,
    )


def contingency(a: int, drug_total: int, reaction_total: int, grand_total: int) -> dict | None:
    """Build the 2x2 table and its disproportionality statistics.

    a = drug and event, b = drug without event, c = event without drug,
    d = neither. Returns None when the totals are inconsistent or a margin is
    empty, which makes every ratio undefined.
    """
    b = drug_total - a
    c = reaction_total - a
    d = grand_total - a - b - c
    if min(a, b, c, d) < 0 or a == 0 or (a + c) == 0 or (b + d) == 0:
        return None
    if b == 0 or c == 0 or d == 0:
        return None

    prr = (a / (a + b)) / (c / (c + d))
    ror = (a * d) / (b * c)
    log_se = math.sqrt(1.0 / a + 1.0 / b + 1.0 / c + 1.0 / d)
    ci_low = math.exp(math.log(ror) - 1.96 * log_se)
    ci_high = math.exp(math.log(ror) + 1.96 * log_se)

    n = a + b + c + d
    expected_a = (a + b) * (a + c) / n
    chi2 = sum(
        (observed - expected) ** 2 / expected
        for observed, expected in (
            (a, expected_a),
            (b, (a + b) * (b + d) / n),
            (c, (c + d) * (a + c) / n),
            (d, (c + d) * (b + d) / n),
        )
        if expected > 0
    )

    flagged = a >= SIGNAL_MIN_REPORTS and prr >= SIGNAL_MIN_PRR and chi2 >= SIGNAL_MIN_CHI2
    return {
        "a": a,
        "b": b,
        "c": c,
        "d": d,
        "prr": round(prr, 3),
        "ror": round(ror, 3),
        "ror_ci_low": round(ci_low, 3),
        "ror_ci_high": round(ci_high, 3),
        "chi2": round(chi2, 2),
        "signal": flagged,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    reports = subparsers.add_parser("reports", help="count and sample FAERS reports for a drug")
    reports.add_argument("--drug", required=True, help="brand, generic, or substance name")
    reports.add_argument("--serious", action="store_true", help="restrict to serious reports")
    reports.add_argument("--sample", type=int, default=10, help="reports to show (default: 10)")
    add_common_arguments(reports)
    reports.set_defaults(handler=command_reports)

    reactions = subparsers.add_parser("reactions", help="rank reported reactions for a drug")
    reactions.add_argument("--drug", required=True, help="brand, generic, or substance name")
    reactions.add_argument("--serious", action="store_true", help="restrict to serious reports")
    reactions.add_argument("--top", type=int, default=25, help="terms to return (default: 25)")
    add_common_arguments(reactions)
    reactions.set_defaults(handler=command_reactions)

    signal = subparsers.add_parser("signal", help="PRR, ROR, and chi-squared for a drug-event pair")
    signal.add_argument("--drug", required=True, help="brand, generic, or substance name")
    signal.add_argument("--reaction", required=True, help="e.g. RHABDOMYOLYSIS")
    add_common_arguments(signal)
    signal.set_defaults(handler=command_signal)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except OpenFdaError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
