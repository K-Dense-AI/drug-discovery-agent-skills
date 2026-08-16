#!/usr/bin/env python3
"""Combine constraint and genetic association into one target safety readout.

This is the question that decides whether a target is worth a programme:
*what happens to people who naturally have less of this protein?* Constraint
answers whether such people exist; GWAS answers what else changes when they do.

Four things this handles that a hand-written summary usually gets wrong:

* **Tolerance and association are the two halves, and they mean opposite
  things.** A tolerant gene with a disease association is the ideal target --
  human knockouts exist, and losing the protein moves the disease. A
  constrained gene with the same association is a warning.
* The verdict is a heuristic over two axes and is reported as such, with the
  inputs beside it, never as a score on its own.
* A gene absent from gnomAD constraint is `unknown`, not safe.
* Every association is positional. The dossier reports how many map to the
  gene alone, because that is the difference between evidence and adjacency.

Commands:
    gene   the combined readout for one or more genes

Examples:
    python safety_dossier.py gene PCSK9
    python safety_dossier.py gene PCSK9 LRRK2 HTT --format json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    GWAS_ASSOCIATION_PARAMS,
    GWAS_SIGNIFICANCE,
    TargetSafetyError,
    add_common_arguments,
    emit,
    gwas_paged,
    loeuf_band,
)
from gnomad_constraint import fetch as fetch_gene  # noqa: E402
from gnomad_constraint import row_for  # noqa: E402

#: LOEUF above this is read as "human knockouts are tolerated".
TOLERANT_LOEUF = 0.6


def verdict(loeuf: float | None, significant_traits: int) -> tuple[str, str]:
    """A two-axis heuristic, never a score on its own.

    The axes are independent: constraint says whether losing the protein is
    survivable, association says whether losing it does anything useful.
    """
    if loeuf is None:
        return (
            "unknown",
            "no constraint estimate -- absence of data, not evidence of tolerance",
        )
    tolerant = loeuf >= TOLERANT_LOEUF
    if tolerant and significant_traits:
        return (
            "genetically supported",
            "loss of function is tolerated in humans and moves a measured trait -- "
            "the pattern that most improves the odds of clinical success",
        )
    if tolerant:
        return (
            "tolerated, unvalidated",
            "inhibition looks survivable but no genome-wide association ties this "
            "gene to a phenotype worth treating",
        )
    if significant_traits:
        return (
            "associated but constrained",
            "the biology is implicated, but loss of function is depleted in humans -- "
            "expect mechanism-based toxicity from systemic inhibition",
        )
    return (
        "constrained, unvalidated",
        "loss of function is depleted and nothing is associated; the weakest of the four",
    )


def dossier(symbol: str, args: argparse.Namespace) -> dict:
    gene = fetch_gene(symbol, genome=args.genome, api_url=args.gnomad_url)
    constraint = row_for(gene)

    records = list(
        gwas_paged(
            "associations",
            {"mappedGene": symbol.upper()},
            "associations",
            limit=args.limit,
            base_url=args.gwas_url,
            known_params=GWAS_ASSOCIATION_PARAMS,
        )
    )

    traits: dict[str, float] = {}
    sole = 0
    for record in records:
        p_value = record.get("p_value")
        if p_value is None or p_value > GWAS_SIGNIFICANCE:
            continue
        if (record.get("mapped_genes") or []) == [symbol.upper()]:
            sole += 1
        for item in record.get("efo_traits") or []:
            trait = item.get("efo_trait")
            if not trait:
                continue
            if trait not in traits or p_value < traits[trait]:
                traits[trait] = p_value

    ranked = sorted(traits.items(), key=lambda pair: pair[1])
    label, reasoning = verdict(constraint["loeuf"], len(ranked))
    band, _ = loeuf_band(constraint["loeuf"])

    return {
        "symbol": constraint["symbol"],
        "gene_id": constraint["gene_id"],
        "loeuf": constraint["loeuf"],
        "band": band,
        "pLI": constraint["pLI"],
        "obs_lof": constraint["obs_lof"],
        "exp_lof": constraint["exp_lof"],
        "associations_walked": len(records),
        "genome_wide_traits": len(ranked),
        "sole_mapped_hits": sole,
        "top_traits": [trait for trait, _ in ranked[:5]],
        "verdict": label,
        "reasoning": reasoning,
    }


COLUMNS = (
    "symbol", "loeuf", "band", "pLI", "obs_lof", "exp_lof",
    "genome_wide_traits", "sole_mapped_hits", "top_traits", "verdict",
)


def command_gene(args: argparse.Namespace) -> None:
    rows = []
    for symbol in args.symbols:
        try:
            rows.append(dossier(symbol, args))
        except TargetSafetyError as error:
            print(f"# skipping {symbol}: {error}", file=sys.stderr)
    if not rows:
        raise TargetSafetyError("no genes resolved")

    for row in rows:
        print(f"# {row['symbol']}: {row['verdict']} -- {row['reasoning']}", file=sys.stderr)
    print(
        "# a heuristic over two axes, reported with its inputs. Constraint says "
        "whether losing the protein is survivable; association says whether it "
        "does anything. Neither is a substitute for a tox study.",
        file=sys.stderr,
    )
    emit(rows, COLUMNS if args.output_format != "json" else list(rows[0]), args.output_format)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gene = subparsers.add_parser("gene", help="combined constraint and association readout")
    gene.add_argument("symbols", nargs="+", help="HGNC gene symbols")
    gene.add_argument(
        "--genome", choices=("GRCh38", "GRCh37"), default="GRCh38", help="reference genome"
    )
    gene.add_argument(
        "--limit", type=int, default=200, help="associations to walk per gene (default: 200)"
    )
    add_common_arguments(gene)
    gene.set_defaults(handler=command_gene)

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
