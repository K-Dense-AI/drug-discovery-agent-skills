#!/usr/bin/env python3
"""Scan oligonucleotide candidates for off-target complementarity.

Standard library only. Needs a transcriptome FASTA that you supply -- none is
bundled.

Four things this handles that a BLAST search usually gets wrong:

* **Seed matches, not full-length alignment, drive siRNA off-targets.** Seven
  nucleotides of antisense positions 2-8 pairing with a 3' UTR is enough for
  microRNA-like repression, and a full-length aligner scores that as a
  non-hit. This is the dominant off-target mechanism and the one BLAST misses.
* **The relevant count is how many transcripts a seed hits**, which for a
  common 7-mer is hundreds. Seeds are compared against each other, because
  zero is not achievable and the useful question is which candidate is worst.
* **ASOs off-target differently.** RNase H cleaves on partial
  complementarity, so a 20-mer gapmer with a contiguous 12-14 nt match
  elsewhere is a real hepatotoxicity risk -- a different search from the seed.
* A hit in an annotated transcript is not the same as a hit in an expressed
  one. Tissue expression decides whether an off-target matters, and this
  script cannot see it.

Commands:
    seeds     seed-match counts for candidate antisense strands
    contig    longest contiguous complementarity against the transcriptome

Examples:
    python offtarget_scan.py seeds --antisense AACTTGGATCCGATCTGGACG --fasta transcripts.fa
    python offtarget_scan.py seeds --from-file candidates.txt --fasta transcripts.fa
    python offtarget_scan.py contig --antisense AACTTGG... --fasta transcripts.fa --min-match 12
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _shared import (  # noqa: E402
    SEED_END,
    SEED_START,
    OligoError,
    clean_sequence,
    read_fasta,
    reverse_complement,
)

#: A contiguous complementary stretch at or above this is an RNase H liability.
DEFAULT_MIN_CONTIG = 12


def read_candidates(args: argparse.Namespace) -> list[tuple[str, str]]:
    """(name, antisense) pairs from the command line or a file."""
    candidates: list[tuple[str, str]] = []
    if args.antisense:
        candidates.append(("candidate", clean_sequence(args.antisense)))
    if args.from_file:
        stream = sys.stdin if args.from_file == "-" else open(args.from_file, encoding="utf-8")
        with stream as handle:
            for index, line in enumerate(handle):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                name = parts[1] if len(parts) > 1 else f"cand{index}"
                candidates.append((name, clean_sequence(parts[0])))
    if not candidates:
        raise OligoError("give --antisense or --from-file")
    return candidates


def seed_of(antisense: str) -> str:
    """Antisense positions 2-8, the microRNA-like seed."""
    if len(antisense) < SEED_END:
        raise OligoError(f"antisense must be at least {SEED_END} nt to have a seed")
    return antisense[SEED_START:SEED_END]


def command_seeds(args: argparse.Namespace) -> None:
    candidates = read_candidates(args)
    transcripts = read_fasta(args.fasta)
    print(f"# {len(transcripts)} transcripts loaded from {args.fasta}", file=sys.stderr)

    rows = []
    for name, antisense in candidates:
        seed = seed_of(antisense)
        # A seed represses a transcript by pairing with it, so search the
        # transcript for the seed's reverse complement.
        target = reverse_complement(seed)
        hits = 0
        hit_names = []
        for transcript_name, sequence in transcripts.items():
            count = sequence.count(target)
            if count:
                hits += count
                if len(hit_names) < 5:
                    hit_names.append(transcript_name)
        rows.append(
            {
                "candidate": name,
                "antisense": antisense,
                "seed": seed,
                "seed_target": target,
                "transcripts_hit": sum(
                    1 for sequence in transcripts.values() if target in sequence
                ),
                "total_sites": hits,
                "examples": hit_names,
            }
        )

    rows.sort(key=lambda row: row["transcripts_hit"])
    print(
        "# a 7-mer seed matches hundreds of transcripts in any real "
        "transcriptome. Zero is not achievable -- rank candidates against each "
        "other and take the least bad.",
        file=sys.stderr,
    )
    print(
        "# an annotated transcript is not an expressed one. Whether an "
        "off-target matters depends on tissue expression, which this cannot see.",
        file=sys.stderr,
    )
    emit(
        rows,
        ["candidate", "seed", "seed_target", "transcripts_hit", "total_sites", "examples"],
        args,
    )


def longest_common_substring(needle: str, haystack: str) -> int:
    """Length of the longest contiguous run of `needle` present in `haystack`."""
    best = 0
    for start in range(len(needle)):
        # Once no window of length best+1 from here can fit, stop.
        if len(needle) - start <= best:
            break
        for end in range(len(needle), start + best, -1):
            if needle[start:end] in haystack:
                best = max(best, end - start)
                break
    return best


def command_contig(args: argparse.Namespace) -> None:
    candidates = read_candidates(args)
    transcripts = read_fasta(args.fasta)
    print(f"# {len(transcripts)} transcripts loaded", file=sys.stderr)

    rows = []
    for name, antisense in candidates:
        target = reverse_complement(antisense)
        worst = 0
        worst_transcript = ""
        liabilities = 0
        for transcript_name, sequence in transcripts.items():
            match = longest_common_substring(target, sequence)
            if match >= args.min_match:
                liabilities += 1
            if match > worst:
                worst = match
                worst_transcript = transcript_name
        rows.append(
            {
                "candidate": name,
                "length": len(antisense),
                "longest_match": worst,
                "worst_transcript": worst_transcript,
                "transcripts_at_or_above_min": liabilities,
                "acceptable": worst < args.min_match,
            }
        )

    rows.sort(key=lambda row: row["longest_match"])
    print(
        f"# a contiguous complementary stretch of {args.min_match}+ nt elsewhere "
        "is enough for RNase H to cleave the wrong transcript. This is the "
        "mechanism behind gapmer hepatotoxicity.",
        file=sys.stderr,
    )
    print(
        "# the intended target will itself show a full-length match; exclude it "
        "from the FASTA or read the worst_transcript column.",
        file=sys.stderr,
    )
    emit(
        rows,
        ["candidate", "length", "longest_match", "worst_transcript",
         "transcripts_at_or_above_min", "acceptable"],
        args,
    )


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
                else "|".join(str(item) for item in row[c]) if isinstance(row[c], list)
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

    for name, handler, help_text in (
        ("seeds", command_seeds, "seed-match counts across the transcriptome"),
        ("contig", command_contig, "longest contiguous complementarity"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--antisense", help="one antisense sequence")
        sub.add_argument("--from-file", help="one sequence per line, or - for stdin")
        sub.add_argument("--fasta", required=True, help="transcriptome FASTA you supply")
        if name == "contig":
            sub.add_argument(
                "--min-match",
                type=int,
                default=DEFAULT_MIN_CONTIG,
                help=f"contiguous nt considered a liability (default: {DEFAULT_MIN_CONTIG})",
            )
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
        sub.set_defaults(handler=handler)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except OligoError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
