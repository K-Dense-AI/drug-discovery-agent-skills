#!/usr/bin/env python3
"""Collect Boltz predictions into one table, with the units converted.

Boltz writes one directory per input, each holding a structure per diffusion
sample, a confidence JSON per sample, and (if requested) one affinity JSON per
input. Reading a screen means walking all of that and joining it.

The affinity conversion is the part worth automating. `affinity_pred_value` is
**log10 of an IC50 expressed in micromolar** -- not pIC50, not kcal/mol, and
signed the opposite way round from everything else in this field:

    pIC50   = 6 - affinity_pred_value
    IC50    = 10 ** affinity_pred_value  micromolar
    dG      = -1.364 * pIC50             kcal/mol at 298 K

So -3 is a nanomolar binder and +2 is a decoy. Report pIC50 or IC50, never the
raw value, or half your readers will read the sign backwards.

Examples:

    python collect_results.py predictions/
    python collect_results.py predictions/ --all-samples --format csv
    python collect_results.py predictions/ --min-iptm 0.6 --out hits.tsv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

#: kcal/mol per log unit: R*T*ln(10) at 298 K.
RT_LN10 = 1.364

#: Boltz's own guidance on the binary head, and the community's on ipTM.
BINDER_PROBABILITY_THRESHOLD = 0.5
GOOD_IPTM = 0.8
POOR_IPTM = 0.6

CONFIDENCE_FILE = re.compile(r"^confidence_(?P<name>.+)_model_(?P<sample>\d+)\.json$")
AFFINITY_FILE = re.compile(r"^affinity_(?P<name>.+)\.json$")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"# warning: cannot read {path}: {error}", file=sys.stderr)
        return {}


def find_prediction_dirs(root: Path) -> list[Path]:
    """Accept the run directory, its `predictions/` child, or one input's dir."""
    if (root / "predictions").is_dir():
        root = root / "predictions"
    if any(root.glob("confidence_*.json")):
        return [root]
    return sorted(path for path in root.iterdir() if path.is_dir())


def affinity_row(value: float | None) -> dict:
    if value is None:
        return {"pIC50": None, "IC50_uM": None, "dG_kcal_mol": None}
    pic50 = 6.0 - value
    return {
        "pIC50": round(pic50, 2),
        "IC50_uM": round(10.0**value, 4) if -12 < value < 12 else None,
        "dG_kcal_mol": round(-RT_LN10 * pic50, 2),
    }


def collect(directory: Path, all_samples: bool) -> list[dict]:
    rows: list[dict] = []

    affinity: dict = {}
    for path in directory.glob("affinity_*.json"):
        affinity = load_json(path)
        break

    confidences: list[tuple[int, dict]] = []
    for path in sorted(directory.glob("confidence_*.json")):
        match = CONFIDENCE_FILE.match(path.name)
        sample = int(match.group("sample")) if match else 0
        confidences.append((sample, load_json(path)))
    if not confidences:
        return rows

    # Boltz orders samples by confidence, so sample 0 is the top-ranked pose.
    confidences.sort(key=lambda item: item[0])
    selected = confidences if all_samples else confidences[:1]

    for sample, confidence in selected:
        structures = sorted(directory.glob(f"*_model_{sample}.*"))
        structure = next(
            (path for path in structures if path.suffix in (".cif", ".pdb")), None
        )
        row = {
            "name": directory.name,
            "sample": sample,
            "confidence_score": _round(confidence.get("confidence_score")),
            "ptm": _round(confidence.get("ptm")),
            "iptm": _round(confidence.get("iptm")),
            "ligand_iptm": _round(confidence.get("ligand_iptm")),
            "protein_iptm": _round(confidence.get("protein_iptm")),
            "complex_plddt": _round(confidence.get("complex_plddt")),
            "complex_iplddt": _round(confidence.get("complex_iplddt")),
            "complex_pde": _round(confidence.get("complex_pde")),
            "complex_ipde": _round(confidence.get("complex_ipde")),
            "structure": str(structure) if structure else "",
        }

        value = affinity.get("affinity_pred_value")
        row["affinity_pred_value"] = _round(value, 4)
        row.update(affinity_row(value))
        row["binder_probability"] = _round(affinity.get("affinity_probability_binary"), 4)
        # The ensemble members disagree more often than the averaged value
        # suggests; their spread is the cheapest uncertainty estimate here.
        members = [
            affinity.get("affinity_pred_value1"),
            affinity.get("affinity_pred_value2"),
        ]
        present = [item for item in members if isinstance(item, (int, float))]
        row["ensemble_spread"] = (
            round(max(present) - min(present), 3) if len(present) == 2 else None
        )
        rows.append(row)
    return rows


def _round(value, digits: int = 4):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(float(value), digits)
    return None


COLUMNS = (
    "name",
    "sample",
    "confidence_score",
    "iptm",
    "ligand_iptm",
    "complex_plddt",
    "ptm",
    "protein_iptm",
    "complex_iplddt",
    "complex_pde",
    "binder_probability",
    "pIC50",
    "IC50_uM",
    "dG_kcal_mol",
    "affinity_pred_value",
    "ensemble_spread",
    "structure",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("out_dir", help="a Boltz --out_dir, its predictions/ child, or one input dir")
    parser.add_argument(
        "--all-samples",
        action="store_true",
        help="one row per diffusion sample instead of only the top-ranked one",
    )
    parser.add_argument("--min-iptm", type=float, help="drop rows below this ipTM")
    parser.add_argument(
        "--min-binder-probability", type=float, help="drop rows below this binder probability"
    )
    parser.add_argument("--sort", default="pIC50", help="column to sort by (default: pIC50)")
    parser.add_argument("--out", help="write here instead of stdout")
    parser.add_argument("--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv")
    args = parser.parse_args(argv)

    root = Path(args.out_dir)
    if not root.is_dir():
        print(f"error: no such directory: {root}", file=sys.stderr)
        return 1

    directories = find_prediction_dirs(root)
    if not directories:
        print(
            f"error: no prediction directories under {root}. Boltz writes to "
            "<out_dir>/predictions/<input_name>/ -- point at the run directory.",
            file=sys.stderr,
        )
        return 1

    rows: list[dict] = []
    for directory in directories:
        rows.extend(collect(directory, args.all_samples))

    if not rows:
        print(f"error: no confidence_*.json files found under {root}", file=sys.stderr)
        return 1

    before = len(rows)
    if args.min_iptm is not None:
        rows = [row for row in rows if (row.get("iptm") or 0) >= args.min_iptm]
    if args.min_binder_probability is not None:
        rows = [
            row
            for row in rows
            if (row.get("binder_probability") or 0) >= args.min_binder_probability
        ]

    def sort_key(row):
        value = row.get(args.sort)
        # Sorting by pIC50/ipTM means best first, so descending, with missing
        # values last rather than sorting as zero.
        return (value is None, -(value if isinstance(value, (int, float)) else 0))

    rows.sort(key=sort_key)

    if args.output_format == "json":
        stream = open(args.out, "w", encoding="utf-8") if args.out else sys.stdout
        try:
            json.dump(rows, stream, indent=2)
            stream.write("\n")
        finally:
            if args.out:
                stream.close()
    else:
        delimiter = "," if args.output_format == "csv" else "\t"
        stream = open(args.out, "w", encoding="utf-8", newline="") if args.out else sys.stdout
        try:
            writer = csv.writer(stream, delimiter=delimiter, lineterminator="\n")
            writer.writerow(COLUMNS)
            for row in rows:
                writer.writerow(
                    ["" if row.get(column) is None else row.get(column) for column in COLUMNS]
                )
        finally:
            if args.out:
                stream.close()

    print(f"# {len(rows)}/{before} rows from {len(directories)} prediction(s)", file=sys.stderr)

    weak = [row for row in rows if (row.get("iptm") or 1) < POOR_IPTM]
    if weak:
        print(
            f"# warning: {len(weak)} prediction(s) have ipTM < {POOR_IPTM} -- the "
            "interface is not confidently predicted, so any affinity for them is "
            "computed on a pose the model itself does not believe",
            file=sys.stderr,
        )
    disagreeing = [row for row in rows if (row.get("ensemble_spread") or 0) > 1.0]
    if disagreeing:
        print(
            f"# warning: {len(disagreeing)} prediction(s) have the two affinity ensemble "
            "members disagreeing by more than one log unit",
            file=sys.stderr,
        )
    if any(row.get("pIC50") is not None for row in rows):
        print(
            "# affinity_pred_value is log10(IC50 in uM): pIC50 = 6 - value, so a "
            "negative value is a strong binder. Use binder_probability for hit-finding "
            "and pIC50 only to compare active analogues.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
