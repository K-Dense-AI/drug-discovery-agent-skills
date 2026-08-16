#!/usr/bin/env python3
"""Tile a transcript into siRNA or ASO candidates and rank them by design rules.

Standard library only. Nearest-neighbour thermodynamics use the SantaLucia
1998 unified parameters, which reproduce the published worked example exactly.

Four things this handles that a hand-rolled tiling usually gets wrong:

* **Duplex asymmetry decides which strand is loaded.** RISC keeps the strand
  whose 5' end is less thermodynamically stable. An siRNA with a stable
  antisense 5' end loads the sense strand instead, silences the wrong
  transcript, and looks simply inactive.
* **The two modalities want opposite things.** siRNA is cleaved by RISC in the
  cytoplasm and prefers mature mRNA; a gapmer ASO recruits RNase H, works in
  the nucleus, and can therefore target introns and pre-mRNA. Applying siRNA
  rules to an ASO discards its main advantage.
* **GC content has a window, not a direction.** Below about 30% the duplex is
  too weak, above about 60% it is too stable to unwind. Optimising GC upward
  is a common and silent error.
* Runs of four or more identical bases -- particularly poly-G, which forms
  quadruplexes -- cause synthesis and specificity problems that no
  thermodynamic score reflects.

Commands:
    tile     generate and rank candidates across a transcript
    tm       nearest-neighbour melting temperature for one duplex
    rules    the design rules applied, and where each comes from

Examples:
    python oligo_design.py tile --sequence-file transcript.fa --modality sirna
    python oligo_design.py tile --sequence ACGT... --modality aso --length 20 --top 10
    python oligo_design.py tm --sequence CGTTGA
    python oligo_design.py rules
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _shared import (  # noqa: E402
    SEED_END,
    SEED_START,
    OligoError,
    clean_sequence,
    reverse_complement,
)

#: SantaLucia (1998) unified nearest-neighbour parameters for DNA/DNA duplexes.
#: Keyed by the 5'->3' dinucleotide of one strand; dH in kcal/mol, dS in cal/(mol K).
NEAREST_NEIGHBOUR = {
    "AA": (-7.9, -22.2), "TT": (-7.9, -22.2),
    "AT": (-7.2, -20.4),
    "TA": (-7.2, -21.3),
    "CA": (-8.5, -22.7), "TG": (-8.5, -22.7),
    "GT": (-8.4, -22.4), "AC": (-8.4, -22.4),
    "CT": (-7.8, -21.0), "AG": (-7.8, -21.0),
    "GA": (-8.2, -22.2), "TC": (-8.2, -22.2),
    "CG": (-10.6, -27.2),
    "GC": (-9.8, -24.4),
    "GG": (-8.0, -19.9), "CC": (-8.0, -19.9),
}

#: Helix initiation, applied once per terminus according to its base pair.
INIT_GC = (0.1, -2.8)
INIT_AT = (2.3, 4.1)

GAS_CONSTANT = 1.987  # cal/(mol K)

#: Default strand concentration for a Tm calculation, molar.
DEFAULT_STRAND_CONC = 1e-6

#: Design windows. These are conventions from the siRNA/ASO literature, not
#: hard limits, and are printed by `rules` so they can be argued with.
GC_WINDOW = (0.30, 0.60)
SIRNA_LENGTH = 21
ASO_LENGTH = 20
MAX_HOMOPOLYMER = 3


def read_sequence(args: argparse.Namespace) -> str:
    if args.sequence:
        return clean_sequence(args.sequence)
    if args.sequence_file:
        stream = sys.stdin if args.sequence_file == "-" else open(args.sequence_file, encoding="utf-8")
        with stream as handle:
            return clean_sequence(handle.read())
    raise OligoError("give --sequence or --sequence-file")


def thermodynamics(sequence: str) -> tuple[float, float]:
    """Total dH (kcal/mol) and dS (cal/mol/K) for a perfectly matched duplex."""
    if len(sequence) < 2:
        raise OligoError("a duplex needs at least two bases")
    delta_h = 0.0
    delta_s = 0.0
    for index in range(len(sequence) - 1):
        pair = sequence[index : index + 2]
        if pair not in NEAREST_NEIGHBOUR:
            raise OligoError(f"no nearest-neighbour parameters for `{pair}`")
        step_h, step_s = NEAREST_NEIGHBOUR[pair]
        delta_h += step_h
        delta_s += step_s

    for terminus in (sequence[0], sequence[-1]):
        init_h, init_s = INIT_GC if terminus in "GC" else INIT_AT
        delta_h += init_h
        delta_s += init_s
    return (delta_h, delta_s)


def melting_temperature(sequence: str, strand_conc: float = DEFAULT_STRAND_CONC) -> float:
    """Tm in Celsius for a non-self-complementary duplex."""
    delta_h, delta_s = thermodynamics(sequence)
    if strand_conc <= 0:
        raise OligoError("strand concentration must be positive")
    # CT/4 for non-self-complementary strands at equal concentration.
    kelvin = (delta_h * 1000.0) / (delta_s + GAS_CONSTANT * math.log(strand_conc / 4.0))
    return kelvin - 273.15


def gc_fraction(sequence: str) -> float:
    return sum(1 for base in sequence if base in "GC") / len(sequence)


def longest_homopolymer(sequence: str) -> int:
    longest = 1
    run = 1
    for previous, current in zip(sequence, sequence[1:]):
        run = run + 1 if current == previous else 1
        longest = max(longest, run)
    return longest


def end_stability(sequence: str, window: int = 5) -> float:
    """Sum of nearest-neighbour dG-proxy (dH) over the terminal `window` bases.

    Less negative means a less stable end. RISC loads the strand whose 5' end
    is less stable, so this is what duplex asymmetry compares.
    """
    return sum(NEAREST_NEIGHBOUR[sequence[i : i + 2]][0] for i in range(window - 1))


def evaluate(antisense: str, sense: str, modality: str) -> dict:
    """Score one candidate against the design rules for its modality."""
    gc = gc_fraction(sense)
    homopolymer = longest_homopolymer(sense)
    tm = melting_temperature(sense)

    flags = []
    if not GC_WINDOW[0] <= gc <= GC_WINDOW[1]:
        flags.append(f"gc_{gc:.0%}")
    if homopolymer > MAX_HOMOPOLYMER:
        flags.append(f"run_of_{homopolymer}")
    if "GGGG" in sense:
        flags.append("poly_g_quadruplex")

    row = {
        "sense": sense,
        "antisense": antisense,
        "gc": round(gc, 3),
        "tm_c": round(tm, 1),
        "max_run": homopolymer,
    }

    if modality == "sirna":
        # RISC keeps the strand whose 5' end is less stable. Positive asymmetry
        # means the antisense 5' end is the weaker one, which is what we want.
        antisense_5 = end_stability(antisense)
        sense_5 = end_stability(sense)
        asymmetry = antisense_5 - sense_5
        row["asymmetry"] = round(asymmetry, 2)
        row["antisense_loaded"] = asymmetry > 0
        if asymmetry <= 0:
            flags.append("wrong_strand_loaded")
        # A/U at antisense position 1 favours loading; G/C at sense position 1 too.
        if antisense[0] not in "AT":
            flags.append("as_pos1_not_au")
        row["seed"] = antisense[SEED_START:SEED_END]

    row["flags"] = flags
    row["passes"] = not flags
    return row


def command_tile(args: argparse.Namespace) -> None:
    sequence = read_sequence(args)
    length = args.length or (SIRNA_LENGTH if args.modality == "sirna" else ASO_LENGTH)
    if len(sequence) < length:
        raise OligoError(f"sequence is {len(sequence)} nt, shorter than the {length} nt window")

    rows = []
    for start in range(0, len(sequence) - length + 1, args.step):
        sense = sequence[start : start + length]
        antisense = reverse_complement(sense)
        row = evaluate(antisense, sense, args.modality)
        row["position"] = start + 1
        rows.append(row)

    passing = [row for row in rows if row["passes"]]
    print(
        f"# {len(rows)} candidates across {len(sequence)} nt; {len(passing)} pass all rules",
        file=sys.stderr,
    )
    if args.modality == "sirna":
        print(
            "# asymmetry > 0 means the antisense 5' end is less stable, so RISC "
            "loads the antisense strand. Negative asymmetry silences the wrong "
            "transcript and looks like simple inactivity.",
            file=sys.stderr,
        )
    else:
        print(
            "# gapmer ASOs recruit RNase H and act in the nucleus, so intronic "
            "and pre-mRNA sites are legitimate targets -- unlike siRNA.",
            file=sys.stderr,
        )
    print(
        "# these rules are necessary, not sufficient. Accessibility of the site "
        "in the folded transcript is not modelled here, and it dominates in "
        "practice.",
        file=sys.stderr,
    )

    ordered = (passing if args.passing_only else rows)
    ordered = sorted(ordered, key=lambda row: (-row.get("asymmetry", 0.0), row["position"]))
    columns = ["position", "sense", "antisense", "gc", "tm_c", "max_run"]
    if args.modality == "sirna":
        columns += ["asymmetry", "antisense_loaded", "seed"]
    columns += ["passes", "flags"]
    emit(ordered[: args.top], columns, args)


def command_tm(args: argparse.Namespace) -> None:
    sequence = read_sequence(args)
    delta_h, delta_s = thermodynamics(sequence)
    row = {
        "sequence": sequence,
        "length": len(sequence),
        "gc": round(gc_fraction(sequence), 3),
        "delta_h_kcal": round(delta_h, 2),
        "delta_s_cal": round(delta_s, 2),
        "tm_c": round(melting_temperature(sequence, args.strand_conc), 2),
        "strand_conc_M": args.strand_conc,
    }
    print(
        "# SantaLucia 1998 unified parameters; Tm assumes a non-self-complementary "
        "duplex at equal strand concentration and 1 M Na+",
        file=sys.stderr,
    )
    emit([row], list(row), args)


def command_rules(args: argparse.Namespace) -> None:
    rows = [
        {"rule": "GC content", "window": f"{GC_WINDOW[0]:.0%}-{GC_WINDOW[1]:.0%}",
         "why": "below is too weak to hybridise, above is too stable to unwind"},
        {"rule": "homopolymer run", "window": f"<= {MAX_HOMOPOLYMER}",
         "why": "runs of 4+ cause synthesis and specificity problems"},
        {"rule": "poly-G", "window": "no GGGG",
         "why": "G-quadruplex formation; non-specific protein binding"},
        {"rule": "duplex asymmetry", "window": "> 0 (siRNA)",
         "why": "RISC loads the strand with the less stable 5' end"},
        {"rule": "antisense position 1", "window": "A or U (siRNA)",
         "why": "favours antisense loading into Argonaute"},
        {"rule": "seed region", "window": f"antisense {SEED_START + 1}-{SEED_END}",
         "why": "drives microRNA-like off-target silencing; scan it separately"},
        {"rule": "length", "window": f"{SIRNA_LENGTH} nt siRNA, {ASO_LENGTH} nt ASO",
         "why": "conventional; gapmers are typically 16-20 nt"},
    ]
    print(
        "# conventions from the siRNA and ASO literature, not hard limits. The "
        "dominant factor in practice -- accessibility of the site in the folded "
        "transcript -- is not among them and is not modelled here.",
        file=sys.stderr,
    )
    emit(rows, ["rule", "window", "why"], args)


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

    tile = subparsers.add_parser("tile", help="generate and rank candidates")
    tile.add_argument("--sequence", help="target sequence")
    tile.add_argument("--sequence-file", help="FASTA or plain text, or - for stdin")
    tile.add_argument(
        "--modality", choices=("sirna", "aso"), default="sirna", help="default: sirna"
    )
    tile.add_argument("--length", type=int, help="oligo length (default: 21 siRNA, 20 ASO)")
    tile.add_argument("--step", type=int, default=1, help="tiling step (default: 1)")
    tile.add_argument("--top", type=int, default=25, help="default: 25")
    tile.add_argument("--passing-only", action="store_true", help="drop flagged candidates")
    tile.set_defaults(handler=command_tile)

    tm = subparsers.add_parser("tm", help="nearest-neighbour melting temperature")
    tm.add_argument("--sequence", help="duplex sequence")
    tm.add_argument("--sequence-file", help="FASTA or plain text, or - for stdin")
    tm.add_argument(
        "--strand-conc", type=float, default=DEFAULT_STRAND_CONC, help="molar (default: 1e-6)"
    )
    tm.set_defaults(handler=command_tm)

    rules = subparsers.add_parser("rules", help="the design rules applied")
    rules.set_defaults(handler=command_rules)

    for sub in (tile, tm, rules):
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
