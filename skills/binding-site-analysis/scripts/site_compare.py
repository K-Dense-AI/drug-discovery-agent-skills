#!/usr/bin/env python3
"""Compare cavities between structures to find induced fit and cryptic sites.

Standard library only. Takes two or more fpocket runs and reports which
cavities exist in which -- the comparison that reveals a pocket that only
opens when something is bound, and the reason docking into an apo structure so
often fails.

Four things this handles that eyeballing two runs usually gets wrong:

* **Pocket numbering is not stable between structures.** fpocket numbers by
  Score, so pocket 1 in the apo form and pocket 1 in the holo form are usually
  different cavities. Matching must be spatial, which is what this does.
* **A cryptic site is defined by its absence.** A cavity that scores well in
  the holo structure and is missing or poor in the apo one is the interesting
  case, and it is invisible if you only ever look at one structure.
* Coordinates must be in the same frame. If the two structures were not
  superposed first, every centre differs and nothing matches; a total absence
  of matches is reported as a likely alignment problem rather than as biology.
* Druggability differences below about 0.1 are noise. The threshold is
  explicit rather than implied.

Commands:
    match   pair cavities between two fpocket runs and report what changed

Examples:
    python site_compare.py match --apo 1ake_out --holo 4ake_out
    python site_compare.py match --apo apo_out --holo holo_out --distance 6 --format json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pocket_report import PocketError, parse_info, resolve_info  # noqa: E402

#: Centres closer than this are treated as the same cavity.
DEFAULT_MATCH_DISTANCE = 5.0

#: Druggability changes smaller than this are not worth reporting as a change.
MEANINGFUL_DELTA = 0.1


class CompareArgs:
    """Minimal stand-in so `resolve_info` can be reused for a directory."""

    def __init__(self, out_dir: str) -> None:
        self.info = None
        self.out_dir = out_dir


def pocket_centre(out_dir: Path, number: int) -> tuple[float, float, float] | None:
    """Centroid of a pocket's alpha-sphere centres."""
    for name in (f"pocket{number}_vert.pqr", f"pocket{number}_atm.pdb"):
        path = out_dir / "pockets" / name
        if not path.is_file():
            continue
        points = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.startswith(("ATOM", "HETATM")):
                continue
            try:
                points.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
            except ValueError:
                continue
        if points:
            return tuple(sum(p[axis] for p in points) / len(points) for axis in range(3))
    return None


def load(out_dir: str) -> list[dict]:
    directory = Path(out_dir)
    pockets = parse_info(resolve_info(CompareArgs(out_dir)))
    for pocket in pockets:
        pocket["centre"] = pocket_centre(directory, pocket["pocket"])
    return pockets


def distance(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def command_match(args: argparse.Namespace) -> None:
    apo = load(args.apo)
    holo = load(args.holo)

    if not any(p["centre"] for p in apo) or not any(p["centre"] for p in holo):
        raise PocketError(
            "no pocket coordinates found -- this needs the full fpocket _out "
            "directory including its pockets/ subdirectory, not just _info.txt"
        )

    rows = []
    matched_apo: set[int] = set()
    for holo_pocket in holo:
        if not holo_pocket["centre"]:
            continue
        best = None
        for apo_pocket in apo:
            if not apo_pocket["centre"]:
                continue
            separation = distance(holo_pocket["centre"], apo_pocket["centre"])
            if separation <= args.distance and (best is None or separation < best[1]):
                best = (apo_pocket, separation)

        holo_drug = holo_pocket.get("druggability") or 0.0
        if best is None:
            rows.append(
                {
                    "holo_pocket": holo_pocket["pocket"],
                    "apo_pocket": None,
                    "separation": None,
                    "holo_druggability": holo_drug,
                    "apo_druggability": None,
                    "delta": None,
                    "classification": "cryptic",
                    "note": "present in holo, absent in apo -- opens on binding",
                }
            )
            continue

        apo_pocket, separation = best
        matched_apo.add(apo_pocket["pocket"])
        apo_drug = apo_pocket.get("druggability") or 0.0
        delta = holo_drug - apo_drug
        if abs(delta) < MEANINGFUL_DELTA:
            classification, note = "stable", "present and comparable in both"
        elif delta > 0:
            classification, note = (
                "induced fit",
                "scores materially better in holo -- the apo conformation understates it",
            )
        else:
            classification, note = (
                "closes on binding",
                "scores worse in holo; often an allosteric site that shuts",
            )
        rows.append(
            {
                "holo_pocket": holo_pocket["pocket"],
                "apo_pocket": apo_pocket["pocket"],
                "separation": round(separation, 2),
                "holo_druggability": holo_drug,
                "apo_druggability": apo_drug,
                "delta": round(delta, 3),
                "classification": classification,
                "note": note,
            }
        )

    for apo_pocket in apo:
        if apo_pocket["pocket"] in matched_apo or not apo_pocket["centre"]:
            continue
        rows.append(
            {
                "holo_pocket": None,
                "apo_pocket": apo_pocket["pocket"],
                "separation": None,
                "holo_druggability": None,
                "apo_druggability": apo_pocket.get("druggability") or 0.0,
                "delta": None,
                "classification": "apo only",
                "note": "present in apo, gone in holo",
            }
        )

    if not any(row["separation"] is not None for row in rows):
        print(
            "# nothing matched at any distance. The two structures are almost "
            "certainly not superposed -- align them before comparing, or every "
            "cavity will look cryptic.",
            file=sys.stderr,
        )

    cryptic = [row for row in rows if row["classification"] == "cryptic"]
    if cryptic:
        best = max(cryptic, key=lambda row: row["holo_druggability"])
        print(
            f"# {len(cryptic)} cavity(ies) present only in holo; the best scores "
            f"{best['holo_druggability']:.2f}. Docking into the apo structure "
            "cannot find these.",
            file=sys.stderr,
        )

    rows.sort(key=lambda row: -(row["holo_druggability"] or 0.0))
    columns = [
        "holo_pocket", "apo_pocket", "separation", "holo_druggability",
        "apo_druggability", "delta", "classification", "note",
    ]
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

    match = subparsers.add_parser("match", help="pair cavities between two runs")
    match.add_argument("--apo", required=True, help="fpocket _out directory for the apo form")
    match.add_argument("--holo", required=True, help="fpocket _out directory for the holo form")
    match.add_argument(
        "--distance",
        type=float,
        default=DEFAULT_MATCH_DISTANCE,
        help=f"centres within this are the same cavity (default: {DEFAULT_MATCH_DISTANCE})",
    )
    match.add_argument(
        "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
    )
    match.set_defaults(handler=command_match)
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
