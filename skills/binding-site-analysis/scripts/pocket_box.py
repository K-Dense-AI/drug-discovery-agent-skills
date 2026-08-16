#!/usr/bin/env python3
"""Turn a cavity into the docking box a search engine needs.

Standard library only. Reads coordinates from an fpocket pocket file, a
reference ligand, or a residue selection, and writes a box in the exact form
AutoDock Vina consumes.

Four things this handles that eyeballing a box usually gets wrong:

* **A box sized to the cavity is too small.** The ligand must be able to
  translate and rotate inside it, so the box needs padding beyond the pocket
  extent -- 4 to 5 A per side is the usual choice, and the default here is 4.
* **A box much larger than the site wastes the search.** Vina's exhaustiveness
  is spread over the whole volume, so doubling the edge length eightfold
  dilutes sampling. The volume is reported, with a warning past 27000 A^3.
* **fpocket alpha-sphere centres and pocket atoms give different extents.**
  The `_vert.pqr` alpha-sphere centres describe the cavity itself; the
  `_atm.pdb` atoms describe the protein lining it, which is systematically
  larger. This reads the vertices when present.
* A box centred on a reference ligand is almost always better than a box
  centred on a predicted cavity, when a holo structure exists at all.

Commands:
    from-pocket   box around an fpocket cavity
    from-ligand   box around a reference ligand in a PDB file
    from-residues box around a set of residues

Examples:
    python pocket_box.py from-pocket --out-dir 4EY7_out --pocket 1
    python pocket_box.py from-ligand --pdb 4EY7.pdb --resname E20
    python pocket_box.py from-residues --pdb receptor.pdb --residues A:279,A:286,A:337
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

#: Padding added on every side, in angstrom. Enough for the ligand to move.
DEFAULT_PADDING = 4.0

#: Past this volume the search is spread too thin for a fixed exhaustiveness.
LARGE_BOX_VOLUME = 27000.0

#: Solvent, ions, and buffer components that are not the ligand of interest.
NON_LIGAND = frozenset(
    {
        "HOH", "WAT", "DOD", "SO4", "PO4", "GOL", "EDO", "PEG", "MPD", "TRS",
        "ACT", "CL", "NA", "K", "MG", "CA", "ZN", "MN", "FE", "NI", "CD",
        "IOD", "BR", "FMT", "ACE", "NH2", "DMS", "IMD", "EPE", "MES",
    }
)


class BoxError(RuntimeError):
    """Input that does not describe a site."""


def read_coordinates(path: Path, keep) -> list[tuple[float, float, float]]:
    """Pull xyz from PDB or PQR lines that `keep` accepts."""
    if not path.is_file():
        raise BoxError(f"{path} does not exist")
    points = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        if not keep(line):
            continue
        try:
            points.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
        except ValueError:
            continue
    return points


def box_from_points(
    points: list[tuple[float, float, float]], padding: float
) -> dict:
    if not points:
        raise BoxError("no atoms matched, so there is nothing to build a box around")
    lows = [min(point[axis] for point in points) for axis in range(3)]
    highs = [max(point[axis] for point in points) for axis in range(3)]
    centre = [(low + high) / 2.0 for low, high in zip(lows, highs)]
    size = [(high - low) + 2 * padding for low, high in zip(lows, highs)]
    volume = size[0] * size[1] * size[2]
    return {
        "center_x": round(centre[0], 3),
        "center_y": round(centre[1], 3),
        "center_z": round(centre[2], 3),
        "size_x": round(size[0], 3),
        "size_y": round(size[1], 3),
        "size_z": round(size[2], 3),
        "volume_A3": round(volume, 1),
        "atoms_used": len(points),
        "padding": padding,
    }


def command_from_pocket(args: argparse.Namespace) -> None:
    directory = Path(args.out_dir)
    vertices = directory / "pockets" / f"pocket{args.pocket}_vert.pqr"
    atoms = directory / "pockets" / f"pocket{args.pocket}_atm.pdb"

    if vertices.is_file():
        source = vertices
        points = read_coordinates(vertices, lambda line: True)
        note = "alpha-sphere centres (the cavity itself)"
    elif atoms.is_file():
        source = atoms
        points = read_coordinates(atoms, lambda line: True)
        note = "lining atoms -- systematically larger than the cavity"
    else:
        raise BoxError(
            f"neither pocket{args.pocket}_vert.pqr nor pocket{args.pocket}_atm.pdb "
            f"found under {directory}/pockets"
        )

    box = box_from_points(points, args.padding)
    print(f"# from {source.name}: {note}", file=sys.stderr)
    report(box, args)


def command_from_ligand(args: argparse.Namespace) -> None:
    path = Path(args.pdb)
    resname = args.resname.upper()

    def keep(line: str) -> bool:
        if not line.startswith("HETATM"):
            return False
        if line[17:20].strip().upper() != resname:
            return False
        return not args.chain or line[21:22].strip() == args.chain

    points = read_coordinates(path, keep)
    if not points:
        present = sorted(
            {
                line[17:20].strip()
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.startswith("HETATM") and line[17:20].strip() not in NON_LIGAND
            }
        )
        raise BoxError(
            f"no HETATM records for `{resname}` in {path}. Candidate ligands "
            f"present: {', '.join(present) if present else 'none'}"
        )
    box = box_from_points(points, args.padding)
    print(
        f"# centred on {resname}, {box['atoms_used']} atoms. A box from a bound "
        "ligand beats a box from a predicted cavity whenever one exists.",
        file=sys.stderr,
    )
    report(box, args)


def command_from_residues(args: argparse.Namespace) -> None:
    wanted = set()
    for item in args.residues.split(","):
        item = item.strip()
        if not item:
            continue
        chain, _, number = item.partition(":")
        if not number:
            chain, number = "", chain
        try:
            wanted.add((chain.strip(), int(number)))
        except ValueError as error:
            raise BoxError(f"`{item}` is not chain:resseq, e.g. A:279") from error
    if not wanted:
        raise BoxError("no residues given")

    def keep(line: str) -> bool:
        chain = line[21:22].strip()
        try:
            resseq = int(line[22:26])
        except ValueError:
            return False
        return (chain, resseq) in wanted or ("", resseq) in wanted

    points = read_coordinates(Path(args.pdb), keep)
    box = box_from_points(points, args.padding)
    print(f"# {len(wanted)} residues requested, {box['atoms_used']} atoms matched", file=sys.stderr)
    report(box, args)


def report(box: dict, args: argparse.Namespace) -> None:
    if box["volume_A3"] > LARGE_BOX_VOLUME:
        print(
            f"# warning: {box['volume_A3']:.0f} A^3 is a large box. Vina spreads a "
            "fixed exhaustiveness over the whole volume, so raise --exhaustiveness "
            "or tighten the site.",
            file=sys.stderr,
        )
    if args.output_format == "json":
        json.dump(box, sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif args.output_format == "vina":
        for key in ("center_x", "center_y", "center_z", "size_x", "size_y", "size_z"):
            print(f"{key} = {box[key]}")
    else:
        for key, value in box.items():
            print(f"{key}\t{value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    pocket = subparsers.add_parser("from-pocket", help="box around an fpocket cavity")
    pocket.add_argument("--out-dir", required=True, help="the <name>_out directory")
    pocket.add_argument("--pocket", type=int, required=True, help="pocket number")
    pocket.set_defaults(handler=command_from_pocket)

    ligand = subparsers.add_parser("from-ligand", help="box around a reference ligand")
    ligand.add_argument("--pdb", required=True, help="receptor PDB containing the ligand")
    ligand.add_argument("--resname", required=True, help="ligand residue name, e.g. E20")
    ligand.add_argument("--chain", help="restrict to one chain")
    ligand.set_defaults(handler=command_from_ligand)

    residues = subparsers.add_parser("from-residues", help="box around chosen residues")
    residues.add_argument("--pdb", required=True)
    residues.add_argument("--residues", required=True, help="e.g. A:279,A:286,A:337")
    residues.set_defaults(handler=command_from_residues)

    for sub in (pocket, ligand, residues):
        sub.add_argument(
            "--padding", type=float, default=DEFAULT_PADDING, help="angstrom per side (default: 4)"
        )
        sub.add_argument(
            "--format",
            dest="output_format",
            choices=("tsv", "json", "vina"),
            default="tsv",
            help="vina emits a Vina config fragment",
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except BoxError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
