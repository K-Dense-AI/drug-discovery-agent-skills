#!/usr/bin/env python3
"""Lay out the chemical modification pattern for an oligonucleotide.

Standard library only. An unmodified oligonucleotide is degraded by nucleases
within minutes and does not reach a cell, so the modification pattern is not a
finishing touch -- it is most of the molecule's drug-likeness.

Four things this handles that a hand-drawn pattern usually gets wrong:

* **A gapmer needs a DNA gap.** RNase H only cleaves an RNA/DNA heteroduplex,
  so 2'-modified wings must flank an unmodified DNA core of at least about
  eight residues. Modify the whole thing and the molecule binds its target and
  does nothing -- a silent, complete loss of mechanism.
* **siRNA and gapmers need opposite chemistry.** siRNA works through RISC and
  must stay RNA-like; a DNA gap in an siRNA breaks Argonaute loading. Applying
  gapmer patterning to an siRNA is a category error.
* **Phosphorothioate is a dose-limiting trade-off.** It confers nuclease
  resistance and protein binding that drives hepatic uptake, and the same
  protein binding causes complement activation, thrombocytopenia, and
  injection-site reactions. Full PS is standard for gapmers; reducing it is a
  real tolerability lever.
* **5-methylcytosine is not optional at CpG sites.** Unmethylated CpG is a
  TLR9 agonist and provokes an innate immune response.

Commands:
    gapmer    a wing-gap-wing pattern for an RNase H ASO
    sirna     a modification pattern for a duplex siRNA
    chemistry the modifications available and what each buys

Examples:
    python chemistry_plan.py gapmer --sequence GCTAGCTAGCTAGCTAGCTA --wing moe --wing-length 5
    python chemistry_plan.py gapmer --sequence ... --wing lna --wing-length 3
    python chemistry_plan.py sirna --sense ... --antisense ... --galnac
    python chemistry_plan.py chemistry
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _shared import OligoError, clean_sequence  # noqa: E402

#: RNase H needs a heteroduplex; below this many DNA residues it stops cleaving.
MIN_GAP = 8

#: Backbone and sugar modifications, and what each is for.
CHEMISTRY = {
    "ps": {
        "name": "phosphorothioate backbone",
        "buys": "nuclease resistance and plasma protein binding, which drives hepatic uptake",
        "costs": "complement activation, thrombocytopenia, injection-site reactions",
    },
    "moe": {
        "name": "2'-O-methoxyethyl",
        "buys": "high binding affinity, strong nuclease resistance, well-precedented",
        "costs": "blocks RNase H, so wings only",
    },
    "ome": {
        "name": "2'-O-methyl",
        "buys": "nuclease resistance, reduced immunostimulation; standard in siRNA",
        "costs": "blocks RNase H; lower affinity than MOE",
    },
    "lna": {
        "name": "locked nucleic acid",
        "buys": "very high affinity, so shorter oligos work",
        "costs": "blocks RNase H; associated hepatotoxicity, and shorter oligos are less specific",
    },
    "cet": {
        "name": "constrained ethyl",
        "buys": "LNA-like affinity with a better tolerability record",
        "costs": "blocks RNase H",
    },
    "f": {
        "name": "2'-fluoro",
        "buys": "affinity and nuclease resistance; common in siRNA",
        "costs": "blocks RNase H; some concern about incorporation by polymerases",
    },
    "5mc": {
        "name": "5-methylcytosine",
        "buys": "removes TLR9 agonism at CpG sites",
        "costs": "essentially none; treat as mandatory wherever C precedes G",
    },
    "galnac": {
        "name": "triantennary GalNAc conjugate",
        "buys": "ASGPR-mediated hepatocyte uptake; 10-30x potency and subcutaneous dosing",
        "costs": "restricts delivery to the liver",
    },
}

WING_CHEMISTRIES = ("moe", "ome", "lna", "cet", "f")


def command_gapmer(args: argparse.Namespace) -> None:
    sequence = clean_sequence(args.sequence)
    wing = args.wing_length
    gap = len(sequence) - 2 * wing

    if args.wing not in WING_CHEMISTRIES:
        raise OligoError(f"`{args.wing}` is not a wing chemistry; use one of {', '.join(WING_CHEMISTRIES)}")
    if gap < MIN_GAP:
        raise OligoError(
            f"a {len(sequence)} nt oligo with {wing} nt wings leaves a {gap} nt gap. "
            f"RNase H needs at least about {MIN_GAP} DNA residues -- shorten the "
            "wings or lengthen the oligo. With no DNA gap the molecule binds its "
            "target and does nothing."
        )

    positions = []
    for index, base in enumerate(sequence):
        in_wing = index < wing or index >= len(sequence) - wing
        sugar = args.wing if in_wing else "DNA"
        methylated = base == "C" and index + 1 < len(sequence) and sequence[index + 1] == "G"
        positions.append(
            {
                "position": index + 1,
                "base": base,
                "region": "5'wing" if index < wing else ("3'wing" if in_wing else "gap"),
                "sugar": sugar,
                "backbone": "PS" if args.full_ps else ("PS" if in_wing else "PO"),
                "5mc": methylated,
            }
        )

    cpg = sum(1 for item in positions if item["5mc"])
    pattern = "".join(
        "W" if item["region"].endswith("wing") else "d" for item in positions
    )

    print(f"# {wing}-{gap}-{wing} gapmer, {args.wing.upper()} wings", file=sys.stderr)
    print(f"# pattern: {pattern}", file=sys.stderr)
    print(
        f"# {gap} nt DNA gap -- RNase H needs at least ~{MIN_GAP} to cleave the "
        "heteroduplex",
        file=sys.stderr,
    )
    if cpg:
        print(
            f"# {cpg} CpG site(s) marked for 5-methylcytosine. Unmethylated CpG is "
            "a TLR9 agonist; this is not optional.",
            file=sys.stderr,
        )
    if args.wing == "lna":
        print(
            "# LNA wings give very high affinity and allow shorter oligos, at the "
            "cost of a documented hepatotoxicity association -- and a shorter oligo "
            "is inherently less specific. Consider cEt.",
            file=sys.stderr,
        )
    if args.full_ps:
        print(
            "# full phosphorothioate is standard for gapmers. It drives hepatic "
            "uptake and also the class tolerability profile -- complement "
            "activation, thrombocytopenia, injection-site reactions.",
            file=sys.stderr,
        )
    emit(positions, ["position", "base", "region", "sugar", "backbone", "5mc"], args)


def command_sirna(args: argparse.Namespace) -> None:
    sense = clean_sequence(args.sense)
    antisense = clean_sequence(args.antisense)

    rows = []
    for label, strand in (("sense", sense), ("antisense", antisense)):
        for index, base in enumerate(strand):
            terminal = index < 2 or index >= len(strand) - 2
            rows.append(
                {
                    "strand": label,
                    "position": index + 1,
                    "base": base,
                    # Alternating 2'-OMe/2'-F is the standard siRNA pattern;
                    # no DNA anywhere, because RISC needs an RNA-like duplex.
                    "sugar": "2'-OMe" if index % 2 == 0 else "2'-F",
                    "backbone": "PS" if terminal else "PO",
                }
            )

    print(
        "# alternating 2'-OMe / 2'-F, PS at both termini of each strand. "
        "No DNA anywhere: RISC needs an RNA-like duplex, so a gapmer pattern "
        "would abolish activity.",
        file=sys.stderr,
    )
    print(
        "# terminal PS only, unlike a gapmer -- full PS is not needed because "
        "the duplex is already nuclease-resistant and RISC-loaded",
        file=sys.stderr,
    )
    if args.galnac:
        print(
            "# GalNAc conjugated to the sense 3' end: ASGPR-mediated hepatocyte "
            "uptake, 10-30x potency, subcutaneous dosing. Restricts delivery to "
            "the liver -- which is why every approved siRNA so far is hepatic.",
            file=sys.stderr,
        )
        rows.append(
            {
                "strand": "sense",
                "position": len(sense) + 1,
                "base": "-",
                "sugar": "GalNAc conjugate",
                "backbone": "-",
            }
        )
    emit(rows, ["strand", "position", "base", "sugar", "backbone"], args)


def command_chemistry(args: argparse.Namespace) -> None:
    rows = [
        {"code": code, "modification": spec["name"], "buys": spec["buys"], "costs": spec["costs"]}
        for code, spec in CHEMISTRY.items()
    ]
    print(
        "# every 2' modification blocks RNase H. That is why a gapmer has an "
        "unmodified DNA core, and why applying full modification to an ASO "
        "silently removes its mechanism.",
        file=sys.stderr,
    )
    emit(rows, ["code", "modification", "buys", "costs"], args)


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

    gapmer = subparsers.add_parser("gapmer", help="wing-gap-wing pattern for an RNase H ASO")
    gapmer.add_argument("--sequence", required=True, help="the ASO sequence")
    gapmer.add_argument(
        "--wing", choices=WING_CHEMISTRIES, default="moe", help="wing chemistry (default: moe)"
    )
    gapmer.add_argument("--wing-length", type=int, default=5, help="nt per wing (default: 5)")
    gapmer.add_argument(
        "--full-ps",
        action="store_true",
        default=True,
        help="phosphorothioate throughout (the gapmer default)",
    )
    gapmer.set_defaults(handler=command_gapmer)

    sirna = subparsers.add_parser("sirna", help="modification pattern for a duplex siRNA")
    sirna.add_argument("--sense", required=True)
    sirna.add_argument("--antisense", required=True)
    sirna.add_argument("--galnac", action="store_true", help="conjugate GalNAc for liver delivery")
    sirna.set_defaults(handler=command_sirna)

    chemistry = subparsers.add_parser("chemistry", help="modifications and their trade-offs")
    chemistry.set_defaults(handler=command_chemistry)

    for sub in (gapmer, sirna, chemistry):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
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
