#!/usr/bin/env python3
"""Choose the epitope and trim the target before starting a binder campaign.

Standard library only. Reads a PDB and writes the target specification the
design tools consume.

Four things this handles that setting up by hand usually gets wrong:

* **Hotspots are the whole design brief.** BindCraft and RFdiffusion are told
  where to bind by a short list of target residues. Choosing a flat, polar, or
  flexible patch produces designs that fold beautifully and bind nothing, and
  the campaign gives no signal that the site was the problem.
* **Trim the target.** Designing against a 900-residue protein wastes almost
  all of the compute on regions the binder never touches, and both AlphaFold2
  hallucination and RFdiffusion scale badly with target size. 100-200 residues
  around the epitope is the usual window.
* **Hotspot residues must be surface-exposed.** A buried residue cannot be
  contacted, and neither tool will tell you -- it will simply fail to converge.
  A per-residue neighbour count is a cheap proxy for exposure.
* Glycans and disordered termini are neither modelled nor bindable, and
  leaving them in the target biases the interface toward regions that do not
  exist in the real protein.

Commands:
    residues   list target residues with an exposure proxy
    hotspots   validate a hotspot selection
    trim       residues within a radius of the chosen epitope

Examples:
    python binder_target_spec.py residues --pdb target.pdb --chain A
    python binder_target_spec.py hotspots --pdb target.pdb --chain A --hotspots 45,47,52,89
    python binder_target_spec.py trim --pdb target.pdb --chain A --hotspots 45,47,52 --radius 20
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict

#: Neighbouring CB atoms within this radius, as an exposure proxy.
NEIGHBOUR_RADIUS = 10.0

#: Above this many neighbours a residue is buried and cannot be contacted.
BURIED_NEIGHBOURS = 22

#: Below this it is highly exposed -- often a flexible loop rather than a face.
HIGHLY_EXPOSED_NEIGHBOURS = 10

#: A workable hotspot set is small and contiguous in space.
HOTSPOT_RANGE = (3, 6)

#: Target size that keeps design tractable, in residues.
TRIM_TARGET = (100, 200)

#: Residues that make poor hotspots: no side chain, or charged and flexible.
POOR_HOTSPOT = {"GLY": "no side chain to contact", "PRO": "backbone-constrained"}

#: Not part of the protein for design purposes.
NON_PROTEIN = frozenset({"HOH", "WAT", "NAG", "MAN", "BMA", "FUC", "GAL", "SIA", "SO4", "GOL", "EDO"})


class TargetError(RuntimeError):
    """A target specification the design tools cannot use."""


def read_residues(path: str, chain: str | None) -> dict[int, dict]:
    """Per-residue CB coordinates (CA for glycine) from a PDB."""
    residues: dict[int, dict] = {}
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError as error:
        raise TargetError(f"cannot read {path}: {error}") from error

    for line in lines:
        if not line.startswith("ATOM"):
            continue
        resname = line[17:20].strip()
        if resname in NON_PROTEIN:
            continue
        line_chain = line[21:22].strip()
        if chain and line_chain != chain:
            continue
        atom = line[12:16].strip()
        if atom not in ("CB", "CA"):
            continue
        try:
            resseq = int(line[22:26])
            xyz = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        except ValueError:
            continue
        # Prefer CB; fall back to CA for glycine or where CB is absent.
        if resseq in residues and residues[resseq]["atom"] == "CB":
            continue
        residues[resseq] = {"resname": resname, "chain": line_chain, "xyz": xyz, "atom": atom}

    if not residues:
        raise TargetError(
            f"no protein residues read from {path}"
            + (f" for chain {chain}" if chain else "")
            + ". Check the chain id and that the file has ATOM records."
        )
    return residues


def neighbour_counts(residues: dict[int, dict], radius: float = NEIGHBOUR_RADIUS) -> dict[int, int]:
    """How many other residues sit within `radius`. A cheap burial proxy."""
    counts: dict[int, int] = defaultdict(int)
    items = list(residues.items())
    for index, (first_id, first) in enumerate(items):
        for second_id, second in items[index + 1 :]:
            separation = math.dist(first["xyz"], second["xyz"])
            if separation <= radius:
                counts[first_id] += 1
                counts[second_id] += 1
    return {resseq: counts.get(resseq, 0) for resseq in residues}


def exposure_label(count: int) -> str:
    if count >= BURIED_NEIGHBOURS:
        return "buried"
    if count <= HIGHLY_EXPOSED_NEIGHBOURS:
        return "highly exposed"
    return "surface"


def parse_hotspots(text: str) -> list[int]:
    values = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(int(item))
        except ValueError as error:
            raise TargetError(f"`{item}` is not a residue number") from error
    if not values:
        raise TargetError("no hotspot residues given")
    return values


def command_residues(args: argparse.Namespace) -> None:
    residues = read_residues(args.pdb, args.chain)
    counts = neighbour_counts(residues)

    rows = [
        {
            "resseq": resseq,
            "resname": data["resname"],
            "chain": data["chain"],
            "neighbours": counts[resseq],
            "exposure": exposure_label(counts[resseq]),
            "good_hotspot": (
                counts[resseq] < BURIED_NEIGHBOURS and data["resname"] not in POOR_HOTSPOT
            ),
        }
        for resseq, data in sorted(residues.items())
    ]
    exposed = sum(1 for row in rows if row["good_hotspot"])
    print(
        f"# {len(rows)} residues, {exposed} plausible as hotspots", file=sys.stderr
    )
    print(
        f"# neighbours = other residues within {NEIGHBOUR_RADIUS:g} A of CB. "
        f"Above {BURIED_NEIGHBOURS} is buried and cannot be contacted; below "
        f"{HIGHLY_EXPOSED_NEIGHBOURS} is often a flexible loop rather than a face.",
        file=sys.stderr,
    )
    emit(rows, ["resseq", "resname", "chain", "neighbours", "exposure", "good_hotspot"], args)


def command_hotspots(args: argparse.Namespace) -> None:
    residues = read_residues(args.pdb, args.chain)
    counts = neighbour_counts(residues)
    wanted = parse_hotspots(args.hotspots)

    problems = []
    rows = []
    for resseq in wanted:
        if resseq not in residues:
            problems.append(f"{resseq} is not in the structure")
            rows.append({"resseq": resseq, "resname": "", "neighbours": None,
                         "exposure": "absent", "issue": "not in the structure"})
            continue
        data = residues[resseq]
        count = counts[resseq]
        issue = ""
        if count >= BURIED_NEIGHBOURS:
            issue = "buried -- cannot be contacted"
            problems.append(f"{resseq} {data['resname']} is buried")
        elif data["resname"] in POOR_HOTSPOT:
            issue = POOR_HOTSPOT[data["resname"]]
        rows.append(
            {
                "resseq": resseq,
                "resname": data["resname"],
                "neighbours": count,
                "exposure": exposure_label(count),
                "issue": issue,
            }
        )

    present = [residues[r]["xyz"] for r in wanted if r in residues]
    spread = max(
        (math.dist(a, b) for index, a in enumerate(present) for b in present[index + 1 :]),
        default=0.0,
    )

    print(f"# {len(wanted)} hotspot residues, maximum separation {spread:.1f} A", file=sys.stderr)
    if not HOTSPOT_RANGE[0] <= len(wanted) <= HOTSPOT_RANGE[1]:
        print(
            f"# {len(wanted)} hotspots is outside the usual {HOTSPOT_RANGE[0]}-"
            f"{HOTSPOT_RANGE[1]}. Too few underdetermines the interface; too many "
            "over-constrains it and the designs will not converge.",
            file=sys.stderr,
        )
    if spread > 25.0:
        print(
            f"# {spread:.1f} A is a wide spread for one epitope -- a single binder "
            "cannot contact all of these. Split into separate campaigns.",
            file=sys.stderr,
        )
    if problems:
        print(f"# {len(problems)} problem(s): {'; '.join(problems)}", file=sys.stderr)
    print(
        "# hotspots are the whole design brief. A flat, polar, or flexible patch "
        "gives designs that fold beautifully and bind nothing, with no signal "
        "that the site was the problem.",
        file=sys.stderr,
    )
    emit(rows, ["resseq", "resname", "neighbours", "exposure", "issue"], args)


def command_trim(args: argparse.Namespace) -> None:
    residues = read_residues(args.pdb, args.chain)
    wanted = parse_hotspots(args.hotspots)
    centres = [residues[r]["xyz"] for r in wanted if r in residues]
    if not centres:
        raise TargetError("none of the hotspot residues are in the structure")

    keep = sorted(
        resseq
        for resseq, data in residues.items()
        if any(math.dist(data["xyz"], centre) <= args.radius for centre in centres)
    )

    print(
        f"# {len(keep)} of {len(residues)} residues within {args.radius:g} A of the epitope",
        file=sys.stderr,
    )
    if len(keep) < TRIM_TARGET[0]:
        print(
            f"# below {TRIM_TARGET[0]} residues the trimmed target may not fold "
            "stably on its own -- widen the radius",
            file=sys.stderr,
        )
    elif len(keep) > TRIM_TARGET[1]:
        print(
            f"# above {TRIM_TARGET[1]} residues, design gets slow and most of the "
            "compute is spent on regions the binder never touches -- narrow the radius",
            file=sys.stderr,
        )

    if args.output_format == "json":
        json.dump({"chain": args.chain, "keep": keep, "hotspots": wanted}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    print(",".join(str(resseq) for resseq in keep))
    print(
        "# pass this to your structure editor to write the trimmed target; keep "
        "the original numbering so the hotspot ids stay valid",
        file=sys.stderr,
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
        ("residues", command_residues, "list residues with an exposure proxy"),
        ("hotspots", command_hotspots, "validate a hotspot selection"),
        ("trim", command_trim, "residues near the epitope"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--pdb", required=True, help="target structure")
        sub.add_argument("--chain", help="restrict to one chain")
        if name in ("hotspots", "trim"):
            sub.add_argument("--hotspots", required=True, help="comma-separated residue numbers")
        if name == "trim":
            sub.add_argument("--radius", type=float, default=20.0, help="angstrom (default: 20)")
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
        sub.set_defaults(handler=handler)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except TargetError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
