#!/usr/bin/env python3
"""Tile a protein into MHC class II peptides and read the predictor's output.

Standard library only. NetMHCIIpan does the prediction; this prepares its input
and turns its output into a per-region risk picture.

Four things this handles that running the predictor directly usually gets wrong:

* **Use %Rank, not affinity.** Predicted IC50 is not comparable between
  alleles, because each allele has its own affinity distribution. %Rank
  normalises against a background of random peptides and is the only value
  that can be thresholded uniformly. Ranking peptides by nM is a standard and
  serious error.
* **Class II, not class I, drives anti-drug antibodies.** ADA formation needs
  CD4 T-cell help, which is class II restricted. Scanning a biologic against
  MHC-I answers a question about cytotoxic T cells that is rarely the one
  being asked.
* **Promiscuity matters more than potency.** A peptide binding one rare allele
  is a problem for few patients; one binding eight common alleles is a problem
  for most of them. The count of alleles bound is the useful number.
* Overlapping 15-mers share a 9-mer binding core, so raw peptide hits
  massively overcount. Collapsing to distinct cores gives the real epitope
  count.

Commands:
    peptides   tile a sequence into overlapping peptides for the predictor
    parse      read NetMHCIIpan tabular output into per-peptide risk
    alleles    the reference allele panel and why these

Examples:
    python epitope_scan.py peptides --sequence-file antibody.fa --length 15 > peptides.txt
    python epitope_scan.py parse --output netmhciipan_out.txt
    python epitope_scan.py parse --output out.txt --rank-threshold 2 --format json
    python epitope_scan.py alleles
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict

#: %Rank thresholds. NetMHCpan's own convention.
STRONG_BINDER_RANK = 2.0
WEAK_BINDER_RANK = 10.0

#: Standard peptide length for class II prediction; the binding core is 9.
PEPTIDE_LENGTH = 15
CORE_LENGTH = 9

#: A reference panel of HLA-DRB1 alleles giving broad population coverage.
#: These seven cover a large majority of most populations and are the
#: conventional screening set.
REFERENCE_ALLELES = {
    "DRB1_0101": "common in European populations",
    "DRB1_0301": "common in European and African populations",
    "DRB1_0401": "common in European populations; RA-associated",
    "DRB1_0701": "broadly common",
    "DRB1_0801": "common in Native American and European populations",
    "DRB1_1101": "common in European and African populations",
    "DRB1_1501": "broadly common; MS-associated",
}

#: Amino acids the predictor accepts.
STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")


class EpitopeError(RuntimeError):
    """Input that cannot be scanned or parsed."""


def clean_sequence(text: str) -> str:
    lines = [line for line in text.splitlines() if not line.startswith(">")]
    sequence = re.sub(r"\s+", "", "".join(lines)).upper()
    if not sequence:
        raise EpitopeError("no sequence found")
    unknown = set(sequence) - STANDARD_AA
    if unknown:
        raise EpitopeError(
            f"non-standard residues in the sequence: {', '.join(sorted(unknown))}. "
            "NetMHCIIpan accepts the twenty standard amino acids only."
        )
    return sequence


def read_sequence(args: argparse.Namespace) -> str:
    if args.sequence:
        return clean_sequence(args.sequence)
    if args.sequence_file:
        stream = sys.stdin if args.sequence_file == "-" else open(args.sequence_file, encoding="utf-8")
        with stream as handle:
            return clean_sequence(handle.read())
    raise EpitopeError("give --sequence or --sequence-file")


def command_peptides(args: argparse.Namespace) -> None:
    sequence = read_sequence(args)
    length = args.length
    if len(sequence) < length:
        raise EpitopeError(f"sequence is {len(sequence)} residues, shorter than the {length}-mer window")

    peptides = [
        sequence[start : start + length] for start in range(len(sequence) - length + 1)
    ]
    for peptide in peptides:
        print(peptide)

    print(
        f"# {len(peptides)} overlapping {length}-mers from {len(sequence)} residues",
        file=sys.stderr,
    )
    print(
        f"# run: netMHCIIpan -f peptides.txt -inptype 1 -a "
        f"{','.join(sorted(REFERENCE_ALLELES))} -xls -xlsfile out.txt",
        file=sys.stderr,
    )
    print(
        f"# consecutive {length}-mers share a {CORE_LENGTH}-mer binding core, so "
        "peptide hits overcount epitopes. `parse` collapses them.",
        file=sys.stderr,
    )


def parse_output(path: str) -> list[dict]:
    """Read NetMHCIIpan tabular output.

    The format has varied between versions, so columns are located by header
    name rather than by position, and rows that do not parse are skipped.
    """
    stream = sys.stdin if path == "-" else open(path, encoding="utf-8", errors="replace")
    with stream as handle:
        lines = [line.rstrip("\n") for line in handle]

    header_index = None
    for index, line in enumerate(lines):
        lowered = line.lower()
        if "peptide" in lowered and ("rank" in lowered or "%rank" in lowered):
            header_index = index
            break
    if header_index is None:
        raise EpitopeError(
            f"no header row with `Peptide` and `Rank` in {path}. Pass NetMHCIIpan "
            "output produced with -xls, or its default tabular stdout."
        )

    headers = lines[header_index].split()
    lowered_headers = [name.lower().lstrip("%") for name in headers]

    def find(*candidates) -> int | None:
        for candidate in candidates:
            if candidate in lowered_headers:
                return lowered_headers.index(candidate)
        return None

    peptide_at = find("peptide")
    rank_at = find("rank_el", "rank", "rank_ba")
    allele_at = find("mhc", "allele", "hla")
    core_at = find("core")
    pos_at = find("pos")

    if peptide_at is None or rank_at is None:
        raise EpitopeError(f"could not locate Peptide and Rank columns in {path}")

    records = []
    for line in lines[header_index + 1 :]:
        if not line.strip() or line.startswith("#") or line.startswith("-"):
            continue
        fields = line.split()
        if len(fields) <= max(peptide_at, rank_at):
            continue
        try:
            rank = float(fields[rank_at])
        except ValueError:
            continue
        records.append(
            {
                "peptide": fields[peptide_at],
                "rank": rank,
                "allele": fields[allele_at] if allele_at is not None and len(fields) > allele_at else "",
                "core": fields[core_at] if core_at is not None and len(fields) > core_at else "",
                "position": fields[pos_at] if pos_at is not None and len(fields) > pos_at else "",
            }
        )

    if not records:
        raise EpitopeError(f"no data rows parsed from {path}")
    return records


def command_parse(args: argparse.Namespace) -> None:
    records = parse_output(args.output)
    threshold = args.rank_threshold

    binders = [record for record in records if record["rank"] <= threshold]
    alleles = {record["allele"] for record in records if record["allele"]}

    # Promiscuity: how many distinct alleles each binding core hits.
    by_core: dict[str, set[str]] = defaultdict(set)
    best_rank: dict[str, float] = {}
    example: dict[str, str] = {}
    for record in binders:
        key = record["core"] or record["peptide"]
        if record["allele"]:
            by_core[key].add(record["allele"])
        if key not in best_rank or record["rank"] < best_rank[key]:
            best_rank[key] = record["rank"]
            example[key] = record["peptide"]

    rows = [
        {
            "core": core,
            "example_peptide": example.get(core, ""),
            "alleles_bound": len(allele_set),
            "allele_coverage_pct": round(100.0 * len(allele_set) / len(alleles), 1) if alleles else None,
            "best_rank": round(best_rank.get(core, 0.0), 3),
            "promiscuous": len(allele_set) >= args.promiscuity,
        }
        for core, allele_set in by_core.items()
    ]
    rows.sort(key=lambda row: (-row["alleles_bound"], row["best_rank"]))

    promiscuous = sum(1 for row in rows if row["promiscuous"])
    print(
        f"# {len(records)} predictions across {len(alleles)} allele(s); "
        f"{len(binders)} at %Rank <= {threshold:g}",
        file=sys.stderr,
    )
    print(
        f"# {len(rows)} distinct binding cores, {promiscuous} binding "
        f"{args.promiscuity}+ alleles",
        file=sys.stderr,
    )
    print(
        "# %Rank, not affinity. Predicted IC50 is not comparable between alleles "
        "-- each has its own affinity distribution -- so nM cannot be thresholded "
        "uniformly.",
        file=sys.stderr,
    )
    print(
        "# promiscuity matters more than potency: one rare allele affects few "
        "patients, eight common ones affect most.",
        file=sys.stderr,
    )
    emit(
        rows[: args.top],
        ["core", "example_peptide", "alleles_bound", "allele_coverage_pct", "best_rank", "promiscuous"],
        args,
    )


def command_alleles(args: argparse.Namespace) -> None:
    rows = [
        {"allele": name, "note": note} for name, note in sorted(REFERENCE_ALLELES.items())
    ]
    print(
        "# a conventional HLA-DRB1 screening panel. Class II, because anti-drug "
        "antibody formation needs CD4 T-cell help -- scanning against MHC-I "
        "answers a different question.",
        file=sys.stderr,
    )
    print(
        "# DP and DQ also present peptides and are less well predicted; a clean "
        "DRB1 scan is necessary rather than sufficient.",
        file=sys.stderr,
    )
    emit(rows, ["allele", "note"], args)


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
                "" if row.get(c) is None
                else "true" if row[c] is True
                else "false" if row[c] is False
                else row[c]
                for c in columns
            ]
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    peptides = subparsers.add_parser("peptides", help="tile a sequence for the predictor")
    peptides.add_argument("--sequence", help="protein sequence")
    peptides.add_argument("--sequence-file", help="FASTA or plain text, or - for stdin")
    peptides.add_argument(
        "--length", type=int, default=PEPTIDE_LENGTH, help=f"default: {PEPTIDE_LENGTH}"
    )
    peptides.set_defaults(handler=command_peptides)

    parse = subparsers.add_parser("parse", help="read NetMHCIIpan output")
    parse.add_argument("--output", required=True, help="NetMHCIIpan output, or - for stdin")
    parse.add_argument(
        "--rank-threshold",
        type=float,
        default=STRONG_BINDER_RANK,
        help=f"%%Rank at or below this is a binder (default: {STRONG_BINDER_RANK:g})",
    )
    parse.add_argument(
        "--promiscuity", type=int, default=3, help="alleles bound to call a core promiscuous"
    )
    parse.add_argument("--top", type=int, default=30, help="default: 30")
    parse.set_defaults(handler=command_parse)

    alleles = subparsers.add_parser("alleles", help="the reference allele panel")
    alleles.set_defaults(handler=command_alleles)

    for sub in (peptides, parse, alleles):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except EpitopeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
