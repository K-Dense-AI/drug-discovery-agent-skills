#!/usr/bin/env python3
"""Define a docking box, and write the Vina config and a viewable box file.

The box is the single most consequential parameter in a docking run and the
one most often set by eye. Too small and the correct pose cannot fit; too
large and the search dilutes -- Vina's default exhaustiveness explores a fixed
budget, so doubling the box volume roughly halves the sampling density and
quietly degrades every result.

Four ways to define one, in descending order of reliability:

    --reference-ligand   the bound ligand of a holo structure (best)
    --residues           a list of pocket residues, e.g. A:790,A:797,A:855
    --chain              the whole of one chain (blind docking; see the warning)
    --center/--size      explicit numbers

Reads PDB, mmCIF, SDF, MOL2, and PDBQT with no dependencies.

Examples:

    python make_box.py 1iep.cif --reference-ligand STI --out 1iep_box.txt
    python make_box.py rec.pdb --residues A:790,A:797,A:855 --padding 5
    python make_box.py rec.pdb --center 15.19 53.90 16.92 --size 20 20 20
"""

from __future__ import annotations

import argparse
import gzip
import re
import sys
from pathlib import Path

#: Waters, ions, buffers and cryoprotectants. Picking `--reference-ligand`
#: automatically has to skip these or the box lands on a sulfate.
NON_LIGANDS = frozenset(
    {
        "HOH", "DOD", "WAT", "SO4", "PO4", "GOL", "EDO", "PEG", "PGE", "PG4", "1PE",
        "2PE", "MPD", "DMS", "ACT", "ACY", "FMT", "MES", "TRS", "EPE", "CIT", "TLA",
        "MLI", "IMD", "BME", "NA", "K", "MG", "CA", "ZN", "MN", "FE", "FE2", "NI",
        "CO", "CU", "CD", "HG", "CL", "BR", "IOD", "F", "NO3", "AZI", "CO3", "NH4",
        "UNX", "UNL", "PGO", "BU3", "P6G", "SCN",
    }
)

#: Vina's own guidance is that the box should exceed the ligand's longest
#: dimension by enough room to rotate. Below this, poses get clipped at the
#: wall and the reported affinity is meaningless.
MIN_BOX_EDGE = 15.0

#: Above roughly this volume the search is spread too thin for the default
#: exhaustiveness to cover, and results become irreproducible run to run.
LARGE_VOLUME_WARNING = 27000.0  # 30 x 30 x 30


def read_text(path: Path) -> str:
    data = path.read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8", "replace")


class Point:
    __slots__ = ("x", "y", "z", "resname", "chain", "resseq", "record", "element")

    def __init__(self, x, y, z, resname="", chain="", resseq=0, record="ATOM", element=""):
        self.x, self.y, self.z = x, y, z
        self.resname = resname
        self.chain = chain
        self.resseq = resseq
        self.record = record
        self.element = element


def parse_structure(text: str) -> list[Point]:
    if "_atom_site." in text:
        return _parse_cif(text)
    if text.lstrip().startswith(("ATOM", "HETATM", "HEADER", "REMARK", "MODEL", "COMPND", "CRYST")):
        return _parse_pdb(text)
    if "V2000" in text or "V3000" in text or text.count("$$$$"):
        return _parse_sdf(text)
    if "@<TRIPOS>" in text:
        return _parse_mol2(text)
    return _parse_pdb(text)


def _parse_pdb(text: str) -> list[Point]:
    points = []
    for line in text.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        try:
            points.append(
                Point(
                    float(line[30:38]),
                    float(line[38:46]),
                    float(line[46:54]),
                    resname=line[17:20].strip(),
                    chain=line[21].strip() or "?",
                    resseq=int(line[22:26]),
                    record=line[:6].strip(),
                    element=(line[76:78].strip().upper() if len(line) >= 78 else ""),
                )
            )
        except ValueError:
            continue
    return points


def _parse_cif(text: str) -> list[Point]:
    points: list[Point] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        if lines[index].strip() != "loop_":
            index += 1
            continue
        index += 1
        headers = []
        while index < len(lines) and lines[index].strip().startswith("_"):
            headers.append(lines[index].strip())
            index += 1
        if not headers or not headers[0].startswith("_atom_site."):
            continue
        columns = {name.split(".", 1)[1]: position for position, name in enumerate(headers)}
        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped or stripped.startswith(("#", "loop_", "_", "data_")):
                break
            values = stripped.split()
            index += 1

            def field(key, default=""):
                position = columns.get(key)
                if position is None or position >= len(values):
                    return default
                return "" if values[position] in (".", "?") else values[position]

            try:
                points.append(
                    Point(
                        float(field("Cartn_x")),
                        float(field("Cartn_y")),
                        float(field("Cartn_z")),
                        resname=field("auth_comp_id") or field("label_comp_id"),
                        chain=field("auth_asym_id") or field("label_asym_id") or "?",
                        resseq=int(field("auth_seq_id") or field("label_seq_id") or 0),
                        record=field("group_PDB", "ATOM"),
                        element=field("type_symbol").upper(),
                    )
                )
            except ValueError:
                continue
        break
    return points


def _parse_sdf(text: str) -> list[Point]:
    points = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            try:
                x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
            except ValueError:
                continue
            # An SDF coordinate line is `x y z SYMBOL ...`; the symbol is
            # alphabetic and short, which rules out the counts and bond lines.
            if parts[3].isalpha() and len(parts[3]) <= 2:
                points.append(Point(x, y, z, resname="LIG", record="HETATM", element=parts[3].upper()))
    return points


def _parse_mol2(text: str) -> list[Point]:
    points = []
    in_atoms = False
    for line in text.splitlines():
        if line.startswith("@<TRIPOS>ATOM"):
            in_atoms = True
            continue
        if line.startswith("@<TRIPOS>"):
            in_atoms = False
            continue
        if not in_atoms:
            continue
        parts = line.split()
        if len(parts) >= 6:
            try:
                points.append(
                    Point(float(parts[2]), float(parts[3]), float(parts[4]),
                          resname="LIG", record="HETATM", element=parts[5].split(".")[0].upper())
                )
            except ValueError:
                continue
    return points


def list_ligands(points: list[Point]) -> dict[tuple[str, str, int], int]:
    counts: dict[tuple[str, str, int], int] = {}
    for point in points:
        if point.record != "HETATM" or point.resname in NON_LIGANDS:
            continue
        key = (point.resname, point.chain, point.resseq)
        counts[key] = counts.get(key, 0) + 1
    return counts


def select_reference(points: list[Point], code: str | None) -> list[Point]:
    ligands = list_ligands(points)
    if not ligands:
        raise SystemExit(
            "error: no non-solvent HETATM component found. Give --center/--size, "
            "--residues, or a separate ligand file as the input."
        )
    if code:
        matches = [key for key in ligands if key[0].upper() == code.upper()]
        if not matches:
            available = ", ".join(sorted({key[0] for key in ligands}))
            raise SystemExit(f"error: no component `{code}`. Present: {available}")
        # Several copies in the asymmetric unit: take the largest, and say so.
        chosen = max(matches, key=lambda key: ligands[key])
        if len(matches) > 1:
            print(
                f"# note: {len(matches)} copies of {code} present; using "
                f"{chosen[1]}:{chosen[2]} ({ligands[chosen]} atoms)",
                file=sys.stderr,
            )
    else:
        chosen = max(ligands, key=lambda key: ligands[key])
        print(
            f"# auto-selected the largest non-solvent component: {chosen[0]} "
            f"{chosen[1]}:{chosen[2]} ({ligands[chosen]} atoms)",
            file=sys.stderr,
        )
    return [
        point
        for point in points
        if point.record == "HETATM"
        and point.resname == chosen[0]
        and point.chain == chosen[1]
        and point.resseq == chosen[2]
    ]


def select_residues(points: list[Point], specification: str) -> list[Point]:
    wanted: set[tuple[str, int]] = set()
    for item in specification.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            chain, _, number = item.partition(":")
        else:
            chain, number = "", item
        try:
            wanted.add((chain.strip(), int(number)))
        except ValueError:
            raise SystemExit(f"error: cannot read residue `{item}`; use CHAIN:NUMBER") from None

    selected = [
        point
        for point in points
        if (point.chain, point.resseq) in wanted or ("", point.resseq) in wanted
    ]
    found = {(point.chain, point.resseq) for point in selected}
    missing = sorted(item for item in wanted if item not in found and ("", item[1]) not in
                     {("", number) for _, number in found})
    if missing:
        print(
            f"# warning: no atoms for {', '.join(f'{c}:{n}' for c, n in missing)} -- "
            "unresolved in this structure, or the numbering differs",
            file=sys.stderr,
        )
    if not selected:
        raise SystemExit("error: none of the requested residues have coordinates")
    return selected


def bounding_box(points: list[Point], padding: float, cubic: bool) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    xs = [point.x for point in points]
    ys = [point.y for point in points]
    zs = [point.z for point in points]
    center = (
        (min(xs) + max(xs)) / 2,
        (min(ys) + max(ys)) / 2,
        (min(zs) + max(zs)) / 2,
    )
    size = (
        max(max(xs) - min(xs) + 2 * padding, MIN_BOX_EDGE),
        max(max(ys) - min(ys) + 2 * padding, MIN_BOX_EDGE),
        max(max(zs) - min(zs) + 2 * padding, MIN_BOX_EDGE),
    )
    if cubic:
        edge = max(size)
        size = (edge, edge, edge)
    return center, size


def box_pdb(center, size) -> str:
    """Eight corners as HETATM records, for loading next to the receptor."""
    cx, cy, cz = center
    sx, sy, sz = size
    lines = ["REMARK    DOCKING BOX", "REMARK    load next to the receptor to check placement"]
    serial = 1
    for dx in (-sx / 2, sx / 2):
        for dy in (-sy / 2, sy / 2):
            for dz in (-sz / 2, sz / 2):
                lines.append(
                    "HETATM{0:5d}  C   BOX X   1    {1:8.3f}{2:8.3f}{3:8.3f}  1.00  0.00           C".format(
                        serial, cx + dx, cy + dy, cz + dz
                    )
                )
                serial += 1
    lines.append("END")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("structure", nargs="?", help="receptor or ligand file (PDB/mmCIF/SDF/MOL2/PDBQT)")
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--reference-ligand",
        nargs="?",
        const="",
        metavar="CCD",
        help="centre on this bound component; omit the code to take the largest",
    )
    source.add_argument("--residues", help="comma-separated CHAIN:NUMBER pocket residues")
    source.add_argument("--chain", help="centre on an entire chain (blind docking)")
    source.add_argument(
        "--center", nargs=3, type=float, metavar=("X", "Y", "Z"), help="explicit centre"
    )
    parser.add_argument(
        "--size", nargs=3, type=float, metavar=("X", "Y", "Z"), help="explicit box size in Angstrom"
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=5.0,
        help="Angstrom added on every side of the selection (default: 5)",
    )
    parser.add_argument("--cubic", action="store_true", help="force a cube of the longest edge")
    parser.add_argument("--out", help="write the Vina config here (default: stdout)")
    parser.add_argument("--box-pdb", help="also write the eight box corners as a PDB")
    parser.add_argument("--list-ligands", action="store_true", help="list bound components and stop")
    args = parser.parse_args(argv)

    if args.center:
        if not args.size:
            parser.error("--center also needs --size")
        center, size = tuple(args.center), tuple(args.size)
        selection_note = "explicit centre and size"
    else:
        if not args.structure:
            parser.error("a structure file is required unless --center/--size are given")
        path = Path(args.structure)
        if not path.is_file():
            print(f"error: no such file: {path}", file=sys.stderr)
            return 1
        points = parse_structure(read_text(path))
        if not points:
            print(f"error: no coordinates found in {path}", file=sys.stderr)
            return 1

        if args.list_ligands:
            ligands = list_ligands(points)
            if not ligands:
                print("(no non-solvent components)")
                return 0
            print("component\tchain\tresseq\tatoms")
            for (name, chain, resseq), count in sorted(
                ligands.items(), key=lambda item: -item[1]
            ):
                print(f"{name}\t{chain}\t{resseq}\t{count}")
            return 0

        if args.residues:
            selected = select_residues(points, args.residues)
            selection_note = f"residues {args.residues}"
        elif args.chain:
            selected = [point for point in points if point.chain == args.chain]
            if not selected:
                print(f"error: no chain {args.chain}", file=sys.stderr)
                return 1
            selection_note = f"the whole of chain {args.chain}"
        elif args.reference_ligand is not None:
            selected = select_reference(points, args.reference_ligand or None)
            selection_note = "a reference ligand"
        else:
            selected = select_reference(points, None)
            selection_note = "a reference ligand (default selection)"

        center, size = bounding_box(selected, args.padding, args.cubic)
        if args.size:
            size = tuple(args.size)

    volume = size[0] * size[1] * size[2]
    config = (
        f"# docking box from {selection_note}\n"
        f"center_x = {center[0]:.3f}\n"
        f"center_y = {center[1]:.3f}\n"
        f"center_z = {center[2]:.3f}\n"
        f"size_x = {size[0]:.3f}\n"
        f"size_y = {size[1]:.3f}\n"
        f"size_z = {size[2]:.3f}\n"
    )
    if args.out:
        Path(args.out).write_text(config, encoding="utf-8")
        print(f"# wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(config)

    print(f"# volume: {volume:.0f} A^3", file=sys.stderr)
    if volume > LARGE_VOLUME_WARNING:
        print(
            f"# warning: a box this large spreads the search thin. Vina's default "
            "exhaustiveness of 8 was tuned for a pocket-sized box; raise "
            "--exhaustiveness to 32+ or narrow the box.",
            file=sys.stderr,
        )
    if args.chain:
        print(
            "# warning: whole-chain (blind) docking rarely reproduces a known pose. "
            "Prefer a reference ligand or a pocket-detection tool.",
            file=sys.stderr,
        )
    if min(size) <= MIN_BOX_EDGE + 0.001:
        print(
            f"# note: one or more edges were raised to the {MIN_BOX_EDGE:.0f} A floor "
            "so a ligand has room to rotate",
            file=sys.stderr,
        )

    print(
        "# meeko: mk_prepare_receptor.py -i <receptor.pdb> -o receptor -p -v "
        f"--box_center {center[0]:.3f} {center[1]:.3f} {center[2]:.3f} "
        f"--box_size {size[0]:.1f} {size[1]:.1f} {size[2]:.1f}",
        file=sys.stderr,
    )

    if args.box_pdb:
        Path(args.box_pdb).write_text(box_pdb(center, size), encoding="utf-8")
        print(f"# wrote {args.box_pdb}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
