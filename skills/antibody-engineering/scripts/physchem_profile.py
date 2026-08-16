#!/usr/bin/env python3
"""Sequence-derived physicochemical properties for antibody developability.

Molecular weight, isoelectric point, net charge at a given pH, molar extinction
coefficient, GRAVY hydrophobicity, and aliphatic index — the numbers you need
for formulation, purification, and a first developability read, none of which
require a structure.

Why they matter here:

* **pI** drives purification and formulation. A variable-domain pI far from the
  typical 7–9 range changes the chromatography, and a pI within ~1 unit of the
  formulation pH means low net charge, low colloidal stability, and aggregation.
* **Net charge at pH 7.4** correlates with clearance and off-target binding.
  Strongly positive Fvs (roughly > +6) are associated with fast clearance and
  polyspecificity in the published developability sets.
* **Extinction coefficient** is what turns an A280 reading into a concentration.
  Getting it wrong scales every downstream measurement.
* **GRAVY** flags hydrophobic sequences; combined with a structure it becomes the
  hydrophobic-patch analysis that actually predicts aggregation.

Examples:

    python physchem_profile.py antibody.fasta
    python physchem_profile.py antibody.fasta --ph 6.0 --format tsv
    python physchem_profile.py --sequence EVQLVESGG... --charge-curve
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

#: Average residue masses (Da), monoisotopic-free averages as used for
#: protein MW, with water added once for the chain.
RESIDUE_MASS = {
    "A": 71.0788, "R": 156.1875, "N": 114.1038, "D": 115.0886, "C": 103.1388,
    "E": 129.1155, "Q": 128.1307, "G": 57.0519, "H": 137.1411, "I": 113.1594,
    "L": 113.1594, "K": 128.1741, "M": 131.1926, "F": 147.1766, "P": 97.1167,
    "S": 87.0782, "T": 101.1051, "W": 186.2132, "Y": 163.1760, "V": 99.1326,
    "U": 150.0388, "O": 237.3018,
}
WATER_MASS = 18.0153

#: EMBOSS pKa set. Different sets (Bjellqvist, IPC, DTASelect) give pI values
#: differing by a few tenths of a unit; state which you used when reporting.
PKA_NTERM = 8.6
PKA_CTERM = 3.6
PKA_SIDE_CHAIN = {"C": 8.5, "D": 3.9, "E": 4.1, "H": 6.5, "K": 10.8, "R": 12.5, "Y": 10.1}
POSITIVE = frozenset("KRH")
NEGATIVE = frozenset("DECY")

#: Kyte-Doolittle hydropathy.
HYDROPATHY = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5,
    "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8,
    "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}

#: Pace et al. (1995) molar extinction coefficients at 280 nm, M^-1 cm^-1.
EXTINCTION_TRP = 5500
EXTINCTION_TYR = 1490
EXTINCTION_CYSTINE = 125

#: Thresholds from the published developability guidelines. Treat as flags for
#: attention, not as pass/fail criteria.
HIGH_POSITIVE_CHARGE = 6.0
LOW_PI_MARGIN = 1.0


def read_sequences(args) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    for index, sequence in enumerate(args.sequence or [], start=1):
        records.append((f"sequence{index}", sequence.strip().upper()))
    for item in args.paths or []:
        path = Path(item)
        if not path.is_file():
            print(f"# warning: no such file: {path}", file=sys.stderr)
            continue
        name = ""
        chunks: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(">"):
                if chunks:
                    records.append((name, "".join(chunks).upper()))
                name = line[1:].strip().split()[0] if line[1:].strip() else "unnamed"
                chunks = []
            elif line.strip():
                chunks.append(line.strip())
        if chunks:
            records.append((name, "".join(chunks).upper()))
    return records


def molecular_weight(sequence: str) -> float:
    return sum(RESIDUE_MASS.get(residue, 0.0) for residue in sequence) + WATER_MASS


def net_charge(sequence: str, ph: float) -> float:
    """Henderson-Hasselbalch summed over ionisable groups and the termini."""
    charge = 1.0 / (1.0 + 10 ** (ph - PKA_NTERM))
    charge -= 1.0 / (1.0 + 10 ** (PKA_CTERM - ph))
    for residue in sequence:
        pka = PKA_SIDE_CHAIN.get(residue)
        if pka is None:
            continue
        if residue in POSITIVE:
            charge += 1.0 / (1.0 + 10 ** (ph - pka))
        else:
            charge -= 1.0 / (1.0 + 10 ** (pka - ph))
    return charge


def isoelectric_point(sequence: str) -> float:
    """Bisection on the net-charge curve."""
    low, high = 0.0, 14.0
    for _ in range(100):
        middle = (low + high) / 2
        if net_charge(sequence, middle) > 0:
            low = middle
        else:
            high = middle
    return round((low + high) / 2, 2)


def extinction_coefficient(sequence: str) -> tuple[int, int]:
    """(reduced, all-cystine) molar extinction at 280 nm."""
    tryptophan = sequence.count("W")
    tyrosine = sequence.count("Y")
    cysteine = sequence.count("C")
    reduced = tryptophan * EXTINCTION_TRP + tyrosine * EXTINCTION_TYR
    oxidised = reduced + (cysteine // 2) * EXTINCTION_CYSTINE
    return reduced, oxidised


def gravy(sequence: str) -> float:
    scored = [HYDROPATHY[residue] for residue in sequence if residue in HYDROPATHY]
    return sum(scored) / len(scored) if scored else 0.0


def aliphatic_index(sequence: str) -> float:
    """Ikai (1980): relative volume occupied by aliphatic side chains."""
    length = len(sequence)
    if not length:
        return 0.0
    fraction = {residue: sequence.count(residue) / length * 100 for residue in "AVIL"}
    return fraction["A"] + 2.9 * fraction["V"] + 3.9 * (fraction["I"] + fraction["L"])


def profile(name: str, sequence: str, ph: float) -> dict:
    reduced, oxidised = extinction_coefficient(sequence)
    weight = molecular_weight(sequence)
    pi = isoelectric_point(sequence)
    charge = net_charge(sequence, ph)
    return {
        "name": name,
        "length": len(sequence),
        "molecularWeight": round(weight, 1),
        "pI": pi,
        f"netCharge_pH{ph:g}": round(charge, 2),
        "extinction280_reduced": reduced,
        "extinction280_cystine": oxidised,
        # A 0.1 % (1 mg/mL) solution absorbance, which is what a
        # spectrophotometer reading is usually converted through.
        "A280_1mg_per_mL": round(oxidised / weight, 3) if weight else 0.0,
        "gravy": round(gravy(sequence), 3),
        "aliphaticIndex": round(aliphatic_index(sequence), 1),
        "cysteines": sequence.count("C"),
        "methionines": sequence.count("M"),
        "tryptophans": sequence.count("W"),
        "positiveResidues": sum(sequence.count(residue) for residue in "KR"),
        "negativeResidues": sum(sequence.count(residue) for residue in "DE"),
    }


COLUMNS = (
    "name",
    "length",
    "molecularWeight",
    "pI",
    "extinction280_cystine",
    "A280_1mg_per_mL",
    "gravy",
    "aliphaticIndex",
    "cysteines",
    "methionines",
    "tryptophans",
    "positiveResidues",
    "negativeResidues",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("paths", nargs="*", help="FASTA file(s)")
    parser.add_argument("--sequence", action="append", help="an inline sequence, repeatable")
    parser.add_argument(
        "--ph", type=float, default=7.4, help="pH for the net-charge calculation (default: 7.4)"
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        help="also report the concatenated chains as one Fv-like species",
    )
    parser.add_argument(
        "--charge-curve",
        action="store_true",
        help="print net charge from pH 3 to 11",
    )
    parser.add_argument(
        "--format", dest="output_format", choices=("text", "tsv", "csv"), default="text"
    )
    parser.add_argument("--out", help="write here instead of stdout")
    args = parser.parse_args(argv)

    records = read_sequences(args)
    if not records:
        print("error: no sequences given", file=sys.stderr)
        return 1

    if args.combine and len(records) > 1:
        combined = "".join(sequence for _, sequence in records)
        records = records + [("combined", combined)]

    charge_column = f"netCharge_pH{args.ph:g}"
    rows = [profile(name, sequence, args.ph) for name, sequence in records]
    columns = (*COLUMNS[:4], charge_column, *COLUMNS[4:])

    stream = open(args.out, "w", encoding="utf-8", newline="") if args.out else sys.stdout
    try:
        if args.output_format in ("tsv", "csv"):
            writer = csv.writer(
                stream, delimiter="," if args.output_format == "csv" else "\t",
                lineterminator="\n",
            )
            writer.writerow(columns)
            for row in rows:
                writer.writerow([row.get(column, "") for column in columns])
        else:
            for row in rows:
                stream.write(f"# {row['name']}: {row['length']} residues\n")
                stream.write(f"  molecular weight     {row['molecularWeight']} Da\n")
                stream.write(f"  isoelectric point    {row['pI']} (EMBOSS pKa set)\n")
                stream.write(f"  net charge at pH {args.ph:g}  {row[charge_column]:+.2f}\n")
                stream.write(
                    f"  extinction (280 nm)  {row['extinction280_cystine']} /M/cm "
                    f"(cystine), {row['extinction280_reduced']} reduced\n"
                )
                stream.write(
                    f"  A280 at 1 mg/mL      {row['A280_1mg_per_mL']}\n"
                )
                stream.write(f"  GRAVY                {row['gravy']:+.3f}\n")
                stream.write(f"  aliphatic index      {row['aliphaticIndex']}\n")
                stream.write(
                    f"  composition          {row['cysteines']} Cys, {row['methionines']} Met, "
                    f"{row['tryptophans']} Trp, {row['positiveResidues']} K/R, "
                    f"{row['negativeResidues']} D/E\n"
                )
                if args.charge_curve:
                    sequence = dict(records)[row["name"]]
                    stream.write("  charge curve         ")
                    stream.write(
                        "  ".join(
                            f"pH{value}:{net_charge(sequence, value):+.1f}"
                            for value in (3, 4, 5, 6, 7, 8, 9, 10, 11)
                        )
                    )
                    stream.write("\n")
                stream.write("\n")
    finally:
        if args.out:
            stream.close()
            print(f"# wrote {args.out}", file=sys.stderr)

    for row in rows:
        charge = row[charge_column]
        if charge > HIGH_POSITIVE_CHARGE:
            print(
                f"# warning: {row['name']} carries a net charge of {charge:+.1f} at pH "
                f"{args.ph:g}. Strongly positive variable domains are associated with fast "
                "clearance and polyspecificity.",
                file=sys.stderr,
            )
        if abs(row["pI"] - args.ph) < LOW_PI_MARGIN:
            print(
                f"# warning: {row['name']} has a pI of {row['pI']}, within "
                f"{LOW_PI_MARGIN} unit of pH {args.ph:g} -- near-zero net charge means "
                "poor colloidal stability. Formulate away from the pI.",
                file=sys.stderr,
            )
        if row["cysteines"] % 2 == 1:
            print(
                f"# warning: {row['name']} has an odd number of cysteines "
                f"({row['cysteines']}) -- an unpaired thiol.",
                file=sys.stderr,
            )
    print(
        "# pI and charge use the EMBOSS pKa set; other sets shift pI by a few tenths. "
        "These are sequence-only estimates -- the real pI of a folded protein differs.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
