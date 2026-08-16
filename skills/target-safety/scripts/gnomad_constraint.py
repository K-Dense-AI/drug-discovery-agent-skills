#!/usr/bin/env python3
"""Read gnomAD mutational constraint for a gene and say what it implies for a target.

Four things this handles that a hand-written query usually gets wrong:

* gnomAD answers a misspelled field or an unknown gene with **HTTP 200 and an
  `errors` array**. Checking the status code alone reports "no constraint" for
  a gene that was never found.
* **LOEUF, not pLI.** pLI is a posterior probability forced toward 0 or 1 and
  saturates for short genes; LOEUF is continuous with a confidence interval and
  is what gnomAD now recommends. Both are reported here, LOEUF first.
* **A high LOEUF is the reassuring direction.** Tolerance of loss of function
  means human knockouts exist and are healthy, which is evidence that
  inhibiting the target is survivable. Constraint is the warning.
* **Absent constraint is not zero constraint.** Genes with too little coverage
  carry no estimate at all, and reporting that as 0 inverts the conclusion.

Commands:
    gene       constraint for one or more genes
    compare    the same table sorted, for ranking a target list

Examples:
    python gnomad_constraint.py gene LRRK2
    python gnomad_constraint.py gene LRRK2 PCSK9 SCN2A --format json
    python gnomad_constraint.py compare LRRK2 PCSK9 SCN2A HTT KRAS
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    TargetSafetyError,
    add_common_arguments,
    emit,
    gnomad_post,
    loeuf_band,
)

GENE_QUERY = """
query GeneConstraint($symbol: String!, $genome: ReferenceGenomeId!) {
  gene(gene_symbol: $symbol, reference_genome: $genome) {
    gene_id
    symbol
    name
    chrom
    start
    stop
    canonical_transcript_id
    gnomad_constraint {
      exp_lof
      obs_lof
      oe_lof
      oe_lof_lower
      oe_lof_upper
      pLI
      oe_mis
      oe_mis_upper
      mis_z
      lof_z
      syn_z
    }
  }
}
"""

COLUMNS = (
    "symbol",
    "gene_id",
    "loeuf",
    "band",
    "oe_lof",
    "obs_lof",
    "exp_lof",
    "pLI",
    "oe_mis_upper",
    "mis_z",
    "implication",
)


def fetch(symbol: str, *, genome: str, api_url: str) -> dict:
    data = gnomad_post(
        GENE_QUERY, {"symbol": symbol.upper(), "genome": genome}, api_url=api_url
    )
    gene = data.get("gene")
    if not gene:
        raise TargetSafetyError(
            f"gnomAD has no gene called `{symbol}` on {genome}. Check the HGNC "
            "symbol -- aliases and previous symbols are not resolved here."
        )
    return gene


def row_for(gene: dict) -> dict:
    constraint = gene.get("gnomad_constraint") or {}
    loeuf = constraint.get("oe_lof_upper")
    band, implication = loeuf_band(loeuf)
    return {
        "symbol": gene.get("symbol"),
        "gene_id": gene.get("gene_id"),
        "loeuf": loeuf,
        "band": band,
        "oe_lof": constraint.get("oe_lof"),
        "obs_lof": constraint.get("obs_lof"),
        "exp_lof": constraint.get("exp_lof"),
        "pLI": constraint.get("pLI"),
        "oe_mis_upper": constraint.get("oe_mis_upper"),
        "mis_z": constraint.get("mis_z"),
        "implication": implication,
    }


def command_gene(args: argparse.Namespace) -> None:
    rows = []
    for symbol in args.symbols:
        gene = fetch(symbol, genome=args.genome, api_url=args.gnomad_url)
        row = row_for(gene)
        rows.append(row)
        if row["loeuf"] is None:
            print(
                f"# {row['symbol']}: no constraint estimate -- too little coverage "
                "to model, which is not the same as unconstrained",
                file=sys.stderr,
            )
    print(
        "# LOEUF is the upper bound of the observed/expected LoF ratio. Low means "
        "depleted (constrained); high means tolerated.",
        file=sys.stderr,
    )
    emit(rows, COLUMNS, args.output_format)


def command_compare(args: argparse.Namespace) -> None:
    rows = []
    for symbol in args.symbols:
        try:
            rows.append(row_for(fetch(symbol, genome=args.genome, api_url=args.gnomad_url)))
        except TargetSafetyError as error:
            print(f"# skipping {symbol}: {error}", file=sys.stderr)
    if not rows:
        raise TargetSafetyError("no genes resolved")

    rows.sort(key=lambda row: (row["loeuf"] is None, row["loeuf"] or 0.0))
    print(
        "# sorted most constrained first. The top of this list is where "
        "inhibition is most likely to be poorly tolerated.",
        file=sys.stderr,
    )
    emit(rows, ("symbol", "loeuf", "band", "pLI", "obs_lof", "exp_lof", "implication"), args.output_format)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler, help_text in (
        ("gene", command_gene, "constraint for one or more genes"),
        ("compare", command_compare, "rank a target list by constraint"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("symbols", nargs="+", help="HGNC gene symbols, e.g. LRRK2")
        sub.add_argument(
            "--genome",
            choices=("GRCh38", "GRCh37"),
            default="GRCh38",
            help="reference genome (default: GRCh38)",
        )
        add_common_arguments(sub)
        sub.set_defaults(handler=handler)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except TargetSafetyError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
