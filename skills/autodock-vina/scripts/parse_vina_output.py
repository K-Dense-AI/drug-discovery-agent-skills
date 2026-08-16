#!/usr/bin/env python3
"""Read Vina output PDBQT files into a table, with the sanity checks.

A Vina result is a stack of poses, each with an "affinity" in kcal/mol. Three
things are worth checking every time and are easy to skip:

* **Is the best pose against a wall?** If any pose atom sits within ~1 A of the
  box boundary, the search was clipped: the true minimum may be outside the box
  and the reported score is an artefact of where you drew it. Pass `--config`
  and this is checked for you.
* **Did the search converge?** If the top poses span a wide energy range, or
  the best is barely better than the second, the run is under-sampled. Raise
  exhaustiveness rather than believing the ranking.
* **Is the score just size?** Vina's function scales with heavy-atom count, so
  bigger molecules score better almost regardless of fit. Ligand efficiency
  (affinity per heavy atom) is the comparable quantity across a library, and
  is reported here.

Examples:

    python parse_vina_output.py out.pdbqt
    python parse_vina_output.py out.pdbqt --config box.txt --top 5
    python parse_vina_output.py results/*.pdbqt --summary --out scores.tsv
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from pathlib import Path

VINA_RESULT = re.compile(
    r"^REMARK\s+VINA\s+RESULT:\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)"
)
SMILES_REMARK = re.compile(r"^REMARK\s+SMILES\s+(\S+)")

#: A pose atom this close to the wall means the box constrained the search.
EDGE_TOLERANCE = 1.0

#: Below this gap between the best and second pose, the ranking is not a
#: meaningful discrimination -- Vina's own error is around 2-3 kcal/mol.
CLOSE_POSE_GAP = 0.5


class Pose:
    __slots__ = ("model", "affinity", "rmsd_lb", "rmsd_ub", "atoms", "heavy_atoms")

    def __init__(self, model, affinity, rmsd_lb, rmsd_ub):
        self.model = model
        self.affinity = affinity
        self.rmsd_lb = rmsd_lb
        self.rmsd_ub = rmsd_ub
        self.atoms: list[tuple[float, float, float, str]] = []
        self.heavy_atoms = 0


def parse_pdbqt(path: Path) -> tuple[list[Pose], str | None]:
    poses: list[Pose] = []
    smiles: str | None = None
    current: Pose | None = None
    model = 0

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("MODEL"):
            model = int(line.split()[1]) if len(line.split()) > 1 else model + 1
            continue
        if line.startswith("ENDMDL"):
            current = None
            continue
        match = VINA_RESULT.match(line)
        if match:
            current = Pose(
                model or len(poses) + 1,
                float(match.group(1)),
                float(match.group(2)),
                float(match.group(3)),
            )
            poses.append(current)
            continue
        if smiles is None and line.startswith("REMARK"):
            smiles_match = SMILES_REMARK.match(line)
            if smiles_match:
                smiles = smiles_match.group(1)
            continue
        if line.startswith(("ATOM", "HETATM")) and current is not None:
            try:
                x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
            except ValueError:
                continue
            # PDBQT puts the AutoDock atom type in columns 78-79. `HD` is a
            # polar hydrogen and `H` a nonpolar one; everything else is heavy.
            atom_type = line[77:79].strip() if len(line) >= 78 else ""
            current.atoms.append((x, y, z, atom_type))
            if atom_type not in ("H", "HD"):
                current.heavy_atoms += 1

    return poses, smiles


def read_config(path: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        try:
            values[key.strip()] = float(value.strip())
        except ValueError:
            continue
    return values


def box_bounds(config: dict[str, float]) -> tuple[tuple[float, float], ...] | None:
    try:
        return tuple(
            (config[f"center_{axis}"] - config[f"size_{axis}"] / 2,
             config[f"center_{axis}"] + config[f"size_{axis}"] / 2)
            for axis in ("x", "y", "z")
        )
    except KeyError:
        return None


def pose_row(path: Path, pose: Pose, rank: int, bounds, smiles: str | None) -> dict:
    xs = [atom[0] for atom in pose.atoms]
    ys = [atom[1] for atom in pose.atoms]
    zs = [atom[2] for atom in pose.atoms]
    row = {
        "file": path.name,
        "ligand": path.stem,
        "rank": rank,
        "model": pose.model,
        "affinity_kcal_mol": pose.affinity,
        "rmsd_lb": pose.rmsd_lb,
        "rmsd_ub": pose.rmsd_ub,
        "heavyAtoms": pose.heavy_atoms or None,
        "ligandEfficiency": (
            round(pose.affinity / pose.heavy_atoms, 4) if pose.heavy_atoms else None
        ),
        "centerX": round(sum(xs) / len(xs), 3) if xs else None,
        "centerY": round(sum(ys) / len(ys), 3) if ys else None,
        "centerZ": round(sum(zs) / len(zs), 3) if zs else None,
        "atEdge": "",
        "smiles": smiles or "",
    }
    if bounds and pose.atoms:
        touching = []
        for axis, (low, high) in zip("xyz", bounds):
            coordinates = {"x": xs, "y": ys, "z": zs}[axis]
            if min(coordinates) - low < EDGE_TOLERANCE:
                touching.append(f"-{axis}")
            if high - max(coordinates) < EDGE_TOLERANCE:
                touching.append(f"+{axis}")
        row["atEdge"] = ",".join(touching)
    return row


COLUMNS = (
    "ligand",
    "rank",
    "affinity_kcal_mol",
    "ligandEfficiency",
    "heavyAtoms",
    "rmsd_lb",
    "rmsd_ub",
    "centerX",
    "centerY",
    "centerZ",
    "atEdge",
    "file",
)

SUMMARY_COLUMNS = (
    "ligand",
    "bestAffinity",
    "ligandEfficiency",
    "heavyAtoms",
    "poses",
    "gapToSecond",
    "spread",
    "posesWithin1kcal",
    "atEdge",
    "file",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("paths", nargs="+", help="Vina output PDBQT file(s)")
    parser.add_argument("--config", help="the docking config, to check for box-edge clipping")
    parser.add_argument("--top", type=int, default=None, help="keep only the N best poses per file")
    parser.add_argument(
        "--summary", action="store_true", help="one row per ligand instead of one per pose"
    )
    parser.add_argument("--out", help="write TSV here instead of stdout")
    parser.add_argument("--format", dest="output_format", choices=("tsv", "csv"), default="tsv")
    args = parser.parse_args(argv)

    bounds = None
    if args.config:
        config_path = Path(args.config)
        if not config_path.is_file():
            print(f"error: no such config: {config_path}", file=sys.stderr)
            return 1
        bounds = box_bounds(read_config(config_path))
        if bounds is None:
            print(
                f"# warning: {config_path} has no center_*/size_* keys; skipping the "
                "box-edge check",
                file=sys.stderr,
            )

    rows: list[dict] = []
    summaries: list[dict] = []
    warnings: list[str] = []

    for raw in args.paths:
        path = Path(raw)
        if not path.is_file():
            warnings.append(f"{raw}: no such file")
            continue
        poses, smiles = parse_pdbqt(path)
        if not poses:
            warnings.append(
                f"{path.name}: no `REMARK VINA RESULT` lines -- an empty or failed run, "
                "or a file from a different docking program"
            )
            continue
        poses.sort(key=lambda pose: pose.affinity)
        kept = poses[: args.top] if args.top else poses
        file_rows = [
            pose_row(path, pose, rank, bounds, smiles)
            for rank, pose in enumerate(kept, start=1)
        ]
        rows.extend(file_rows)

        best = poses[0]
        gap = poses[1].affinity - best.affinity if len(poses) > 1 else None
        spread = poses[-1].affinity - best.affinity if len(poses) > 1 else 0.0
        edges = sorted({edge for row in file_rows for edge in row["atEdge"].split(",") if edge})
        summaries.append(
            {
                "ligand": path.stem,
                "bestAffinity": best.affinity,
                "ligandEfficiency": (
                    round(best.affinity / best.heavy_atoms, 4) if best.heavy_atoms else None
                ),
                "heavyAtoms": best.heavy_atoms or None,
                "poses": len(poses),
                "gapToSecond": round(gap, 3) if gap is not None else None,
                "spread": round(spread, 3),
                "posesWithin1kcal": sum(
                    1 for pose in poses if pose.affinity - best.affinity <= 1.0
                ),
                "atEdge": ",".join(edges),
                "file": path.name,
            }
        )

        if edges:
            warnings.append(
                f"{path.name}: pose atoms within {EDGE_TOLERANCE:.0f} A of the box wall "
                f"({', '.join(edges)}) -- the search was clipped, so this score is not "
                "trustworthy. Enlarge or recentre the box and re-dock."
            )
        if gap is not None and gap < CLOSE_POSE_GAP and len(poses) > 1:
            warnings.append(
                f"{path.name}: best and second pose differ by only {gap:.2f} kcal/mol -- "
                "the top-ranked pose is not meaningfully distinguished from the runner-up"
            )

    output = summaries if args.summary else rows
    columns = SUMMARY_COLUMNS if args.summary else COLUMNS
    if args.summary:
        output.sort(key=lambda row: row["bestAffinity"])

    delimiter = "," if args.output_format == "csv" else "\t"
    stream = open(args.out, "w", encoding="utf-8", newline="") if args.out else sys.stdout
    try:
        writer = csv.writer(stream, delimiter=delimiter, lineterminator="\n")
        writer.writerow(columns)
        for row in output:
            writer.writerow(["" if row.get(column) is None else row.get(column) for column in columns])
    finally:
        if args.out:
            stream.close()
            print(f"# wrote {len(output)} rows to {args.out}", file=sys.stderr)

    for warning in warnings:
        print(f"# warning: {warning}", file=sys.stderr)
    if output:
        print(
            "# reminder: Vina affinity is a scoring-function estimate with roughly "
            "2-3 kcal/mol error, not a measured binding free energy. Rank with it; "
            "do not quote it as a Kd.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
