#!/usr/bin/env python3
"""Pull GWAS Catalog associations for a gene and separate signal from noise.

Four things this handles that a hand-written query usually gets wrong:

* **An unrecognised filter is ignored, not rejected.** `?gene=LRRK2` returns
  1142122 associations -- the entire catalogue -- with HTTP 200. The correct
  parameter is `mappedGene`, which returns 93. Nothing in the response says
  the filter was dropped, so the only defence is validating locally.
* **`mapped_genes` is positional, not causal.** A variant is mapped to the
  nearest gene, so an association listed under a gene often acts through a
  neighbour. LRRK2 associations carry `LINC02471` and `MUC19` alongside it.
* Genome-wide significance is 5e-8. The catalogue contains weaker entries, and
  reporting them beside real hits inflates the apparent evidence.
* The same locus is rediscovered by many studies, so a raw association count
  measures how often a region has been genotyped, not how strong it is.

Commands:
    gene      associations mapped to a gene, strongest first
    traits    the distinct traits a gene is associated with

Examples:
    python gwas_evidence.py gene LRRK2
    python gwas_evidence.py gene PCSK9 --limit 40
    python gwas_evidence.py traits LRRK2
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    GWAS_ASSOCIATION_PARAMS,
    GWAS_SIGNIFICANCE,
    TargetSafetyError,
    add_common_arguments,
    emit,
    gwas_get,
    gwas_paged,
)


def _associations(symbol: str, *, limit: int, base_url: str) -> list[dict]:
    return list(
        gwas_paged(
            "associations",
            {"mappedGene": symbol.upper()},
            "associations",
            limit=limit,
            base_url=base_url,
            known_params=GWAS_ASSOCIATION_PARAMS,
        )
    )


def _total(symbol: str, base_url: str) -> int:
    document = gwas_get(
        "associations",
        {"mappedGene": symbol.upper(), "size": 1},
        base_url=base_url,
        known_params=GWAS_ASSOCIATION_PARAMS,
    )
    return int((document.get("page") or {}).get("totalElements", 0))


def _traits(record: dict) -> list[str]:
    return [item.get("efo_trait") for item in record.get("efo_traits") or [] if item.get("efo_trait")]


def command_gene(args: argparse.Namespace) -> None:
    symbol = args.symbol.upper()
    total = _total(symbol, args.gwas_url)
    print(f"# {total} associations mapped to {symbol}", file=sys.stderr)
    if total == 0:
        print(
            "# no associations. Check the HGNC symbol -- the catalogue maps to "
            "current symbols only, and many genes genuinely have none.",
            file=sys.stderr,
        )
        return

    records = _associations(symbol, limit=args.limit, base_url=args.gwas_url)
    rows = []
    for record in records:
        p_value = record.get("p_value")
        if args.significant_only and (p_value is None or p_value > GWAS_SIGNIFICANCE):
            continue
        mapped = record.get("mapped_genes") or []
        rows.append(
            {
                "p_value": p_value,
                "genome_wide": p_value is not None and p_value <= GWAS_SIGNIFICANCE,
                "traits": _traits(record),
                "mapped_genes": mapped,
                "gene_is_sole_mapping": mapped == [symbol],
                "location": "|".join(record.get("locations") or []),
                "accession": record.get("accession_id"),
                "pubmed": record.get("pubmed_id"),
                "first_author": record.get("first_author"),
            }
        )
    rows.sort(key=lambda row: (row["p_value"] is None, row["p_value"] or 1.0))

    sole = sum(1 for row in rows if row["gene_is_sole_mapping"])
    print(
        f"# {len(rows)} shown; {sole} map to {symbol} alone -- the rest also map "
        "to a neighbour, so the causal gene is not established by this alone",
        file=sys.stderr,
    )
    emit(
        rows,
        [
            "p_value", "genome_wide", "traits", "mapped_genes", "gene_is_sole_mapping",
            "location", "accession", "pubmed", "first_author",
        ],
        args.output_format,
    )


def command_traits(args: argparse.Namespace) -> None:
    symbol = args.symbol.upper()
    records = _associations(symbol, limit=args.limit, base_url=args.gwas_url)
    if not records:
        print(f"# no associations mapped to {symbol}", file=sys.stderr)
        return

    grouped: dict[str, dict] = defaultdict(
        lambda: {"associations": 0, "studies": set(), "best_p": None, "sole": 0}
    )
    for record in records:
        p_value = record.get("p_value")
        mapped = record.get("mapped_genes") or []
        for trait in _traits(record):
            entry = grouped[trait]
            entry["associations"] += 1
            if record.get("accession_id"):
                entry["studies"].add(record["accession_id"])
            if p_value is not None and (entry["best_p"] is None or p_value < entry["best_p"]):
                entry["best_p"] = p_value
            entry["sole"] += 1 if mapped == [symbol] else 0

    rows = [
        {
            "trait": trait,
            "best_p": entry["best_p"],
            "genome_wide": entry["best_p"] is not None and entry["best_p"] <= GWAS_SIGNIFICANCE,
            "associations": entry["associations"],
            "studies": len(entry["studies"]),
            "sole_mapping": entry["sole"],
        }
        for trait, entry in grouped.items()
    ]
    rows.sort(key=lambda row: (row["best_p"] is None, row["best_p"] or 1.0))
    print(
        "# ranked by strongest association, not by count -- the same locus is "
        "rediscovered often, so counts measure genotyping effort",
        file=sys.stderr,
    )
    emit(
        rows[: args.top],
        ["trait", "best_p", "genome_wide", "associations", "studies", "sole_mapping"],
        args.output_format,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gene = subparsers.add_parser("gene", help="associations mapped to a gene")
    gene.add_argument("symbol", help="HGNC gene symbol, e.g. LRRK2")
    gene.add_argument("--limit", type=int, default=100, help="associations to fetch (default: 100)")
    gene.add_argument(
        "--significant-only",
        action="store_true",
        help=f"drop associations weaker than {GWAS_SIGNIFICANCE:g}",
    )
    add_common_arguments(gene)
    gene.set_defaults(handler=command_gene)

    traits = subparsers.add_parser("traits", help="distinct traits for a gene")
    traits.add_argument("symbol", help="HGNC gene symbol")
    traits.add_argument("--limit", type=int, default=200, help="associations to walk (default: 200)")
    traits.add_argument("--top", type=int, default=30, help="traits to show (default: 30)")
    add_common_arguments(traits)
    traits.set_defaults(handler=command_traits)

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
