#!/usr/bin/env python3
"""Parse fpocket output and rank cavities by whether they are worth targeting.

Standard library only. fpocket itself is a binary; this reads what it wrote.

Four things this handles that reading `_info.txt` by eye usually gets wrong:

* **fpocket's Score and its Druggability Score are different things.** Score
  ranks cavities against each other geometrically. Druggability Score is a
  logistic model trained to separate sites with known drug-like ligands from
  sites without, and it is the one that answers "is this worth a campaign".
  They frequently disagree, and the top-ranked pocket is often not the most
  druggable one.
* Pocket numbering follows Score, so `pocket1` is not necessarily the site you
  want. Sorting by druggability is a different order and this reports both.
* **A large volume is not a good pocket.** Volume with low hydrophobicity and
  high polar SASA is usually a surface groove or a crystallographic artefact.
  The apolar fraction is what distinguishes a site that binds a small molecule.
* Where the real ligand sits is a fact, not a prediction. With `--ligand-resname`
  the reported cavities are checked against it, which is the only honest
  validation available without an experiment.

Commands:
    rank      pockets ordered by druggability, with the geometry behind it
    residues  the residues lining a chosen pocket

Examples:
    python pocket_report.py rank --info 4EY7_out/4EY7_info.txt
    python pocket_report.py rank --out-dir 4EY7_out --min-druggability 0.5
    python pocket_report.py residues --out-dir 4EY7_out --pocket 1
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

#: fpocket's own guidance: above this a cavity resembles known druggable sites.
DRUGGABLE = 0.5

#: Below this a cavity is usually too small for a lead-like ligand (cubic A).
MIN_USEFUL_VOLUME = 200.0

#: Apolar fraction below this suggests a polar groove rather than a pocket.
MIN_APOLAR_FRACTION = 0.35

POCKET_HEADER = re.compile(r"^Pocket\s+(\d+)\s*:", re.IGNORECASE)
FIELD = re.compile(r"^\s*(.+?)\s*:\s*(-?[\d.eE+]+)\s*$")

#: The `_info.txt` labels this script reads, mapped to short column names.
FIELDS = {
    "Score": "score",
    "Druggability Score": "druggability",
    "Number of Alpha Spheres": "alpha_spheres",
    "Total SASA": "total_sasa",
    "Polar SASA": "polar_sasa",
    "Apolar SASA": "apolar_sasa",
    "Volume": "volume",
    "Mean local hydrophobic density": "hydrophobic_density",
    "Mean alpha sphere radius": "mean_alpha_radius",
    "Hydrophobicity score": "hydrophobicity",
    "Polarity score": "polarity",
    "Charge score": "charge",
    "Flexibility": "flexibility",
}


class PocketError(RuntimeError):
    """Missing or unreadable fpocket output."""


def resolve_info(args: argparse.Namespace) -> Path:
    if args.info:
        path = Path(args.info)
    elif args.out_dir:
        directory = Path(args.out_dir)
        candidates = sorted(directory.glob("*_info.txt"))
        if not candidates:
            raise PocketError(
                f"no *_info.txt in {directory}. fpocket writes <name>_out/<name>_info.txt "
                "-- point --out-dir at the _out directory itself."
            )
        path = candidates[0]
    else:
        raise PocketError("give --info or --out-dir")
    if not path.is_file():
        raise PocketError(f"{path} does not exist")
    return path


def parse_info(path: Path) -> list[dict]:
    """Read `<name>_info.txt` into one record per pocket."""
    pockets: list[dict] = []
    current: dict | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        header = POCKET_HEADER.match(line.strip())
        if header:
            current = {"pocket": int(header.group(1))}
            pockets.append(current)
            continue
        if current is None:
            continue
        field = FIELD.match(line)
        if not field:
            continue
        label, value = field.group(1).strip(), field.group(2)
        key = FIELDS.get(label)
        if key:
            try:
                current[key] = float(value)
            except ValueError:
                pass
    if not pockets:
        raise PocketError(f"no pockets parsed from {path} -- is this an fpocket _info.txt?")
    return pockets


def enrich(pocket: dict) -> dict:
    """Add the derived numbers that decide whether a cavity is worth docking."""
    total = pocket.get("total_sasa") or 0.0
    apolar = pocket.get("apolar_sasa") or 0.0
    fraction = apolar / total if total else None
    volume = pocket.get("volume")
    druggability = pocket.get("druggability")

    verdict, reason = classify(druggability, volume, fraction)
    return {
        **pocket,
        "apolar_fraction": fraction,
        "verdict": verdict,
        "reason": reason,
    }


def classify(
    druggability: float | None, volume: float | None, apolar_fraction: float | None
) -> tuple[str, str]:
    if druggability is None:
        return ("unknown", "no druggability score in this output")
    if volume is not None and volume < MIN_USEFUL_VOLUME:
        return (
            "too small",
            f"volume {volume:.0f} A^3 is below {MIN_USEFUL_VOLUME:.0f}; too small for a "
            "lead-like ligand even if the score is high",
        )
    if druggability >= DRUGGABLE:
        if apolar_fraction is not None and apolar_fraction < MIN_APOLAR_FRACTION:
            return (
                "druggable but polar",
                "scores well yet is mostly polar surface -- check it is a real "
                "cavity and not a solvent-exposed groove",
            )
        return ("druggable", "resembles sites with known drug-like ligands")
    if druggability >= 0.2:
        return (
            "marginal",
            "below fpocket's druggable cut; possible for a fragment campaign or a "
            "covalent approach, unlikely for a conventional lead",
        )
    return ("poor", "does not resemble a small-molecule binding site")


def command_rank(args: argparse.Namespace) -> None:
    pockets = [enrich(pocket) for pocket in parse_info(resolve_info(args))]
    if args.min_druggability is not None:
        pockets = [p for p in pockets if (p.get("druggability") or 0.0) >= args.min_druggability]
        if not pockets:
            print(
                f"# no pocket scores at or above {args.min_druggability} -- this "
                "protein may not have a conventional small-molecule site",
                file=sys.stderr,
            )
            return

    by_score = sorted(pockets, key=lambda p: -(p.get("score") or 0.0))
    pockets.sort(key=lambda p: -(p.get("druggability") or 0.0))

    if by_score and pockets and by_score[0]["pocket"] != pockets[0]["pocket"]:
        print(
            f"# fpocket ranks pocket {by_score[0]['pocket']} first by Score, but "
            f"pocket {pockets[0]['pocket']} is the most druggable. Numbering "
            "follows Score, so pocket1 is not automatically the site you want.",
            file=sys.stderr,
        )
    druggable = sum(1 for p in pockets if p["verdict"] == "druggable")
    print(f"# {len(pockets)} pockets, {druggable} scoring as druggable", file=sys.stderr)

    columns = [
        "pocket", "druggability", "score", "volume", "alpha_spheres",
        "apolar_fraction", "hydrophobicity", "polarity", "verdict", "reason",
    ]
    emit(pockets[: args.top], columns, args)


def command_residues(args: argparse.Namespace) -> None:
    directory = Path(args.out_dir)
    candidates = list(directory.glob(f"pockets/pocket{args.pocket}_atm.pdb"))
    if not candidates:
        raise PocketError(
            f"no pockets/pocket{args.pocket}_atm.pdb under {directory}. fpocket "
            "writes one _atm.pdb per pocket inside the _out/pockets directory."
        )

    seen: dict[tuple[str, int], str] = {}
    for line in candidates[0].read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        resname = line[17:20].strip()
        chain = line[21:22].strip() or "_"
        try:
            resseq = int(line[22:26])
        except ValueError:
            continue
        seen[(chain, resseq)] = resname

    rows = [
        {"chain": chain, "resseq": resseq, "resname": resname}
        for (chain, resseq), resname in sorted(seen.items())
    ]
    print(f"# {len(rows)} residues lining pocket {args.pocket}", file=sys.stderr)
    emit(rows, ["chain", "resseq", "resname"], args)


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
                "" if row.get(column) is None
                else f"{row[column]:.4g}" if isinstance(row[column], float)
                else row[column]
                for column in columns
            ]
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    rank = subparsers.add_parser("rank", help="pockets ordered by druggability")
    rank.add_argument("--info", help="path to <name>_info.txt")
    rank.add_argument("--out-dir", help="path to the <name>_out directory")
    rank.add_argument("--min-druggability", type=float, help="drop pockets below this")
    rank.add_argument("--top", type=int, default=15, help="rows to show (default: 15)")
    rank.set_defaults(handler=command_rank)

    residues = subparsers.add_parser("residues", help="residues lining a pocket")
    residues.add_argument("--out-dir", required=True, help="path to the <name>_out directory")
    residues.add_argument("--pocket", type=int, required=True, help="pocket number")
    residues.set_defaults(handler=command_residues)

    for sub in (rank, residues):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except PocketError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
