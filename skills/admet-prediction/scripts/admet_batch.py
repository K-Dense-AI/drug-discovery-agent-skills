#!/usr/bin/env python3
"""Prepare SMILES input for ADMET-AI and split large libraries into chunks.

Standard library only. ADMET-AI does the prediction; this makes the input it
expects and keeps a large run from failing halfway through.

Four things this handles that a hand-rolled loop usually gets wrong:

* **ADMET-AI wants a CSV with a header, not a bare SMILES list.** The column
  name is passed with `--smiles_column`, and a headerless file silently loses
  its first molecule to the header row.
* **Duplicates waste the whole run.** Chemprop is deterministic, so predicting
  the same structure twice costs twice and adds nothing. Exact duplicates are
  collapsed and the mapping is kept so the output can be expanded again.
* **One bad SMILES fails the batch, not the molecule.** Splitting into chunks
  bounds the damage and makes a restart cheap.
* Predictions are per-structure with no salt or tautomer handling. Salts and
  mixtures are detected and reported, because `.` in a SMILES string usually
  means the wrong thing is being predicted on.

Commands:
    prepare   write chunked ADMET-AI input CSVs and the commands to run them
    expand    map a chunked prediction CSV back onto the original input order

Examples:
    python admet_batch.py prepare --smiles library.smi --out-dir admet_in --chunk-size 5000
    python admet_batch.py expand --input admet_in/manifest.json --predictions merged.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

DEFAULT_CHUNK = 10_000

#: A `.` in SMILES separates components: a salt, a mixture, or a counterion.
MIXTURE_MARKER = "."


class BatchError(RuntimeError):
    """Input that cannot be turned into an ADMET-AI run."""


def read_smiles(path: str, column: str | None) -> list[tuple[str, str]]:
    """Return (identifier, smiles) pairs from a .smi, .csv, or .txt file."""
    source = Path(path)
    if not source.is_file():
        raise BatchError(f"{path} does not exist")
    text = source.read_text(encoding="utf-8", errors="replace")

    rows: list[tuple[str, str]] = []
    if source.suffix.lower() == ".csv":
        reader = csv.DictReader(text.splitlines())
        if reader.fieldnames is None:
            raise BatchError(f"{path} is empty")
        name = column or next(
            (field for field in reader.fieldnames if field.lower() in ("smiles", "smi")), None
        )
        if name is None:
            raise BatchError(
                f"no SMILES column in {path}; columns are {reader.fieldnames}. "
                "Name it with --smiles-column."
            )
        for index, record in enumerate(reader):
            value = (record.get(name) or "").strip()
            if value:
                rows.append((record.get("id") or record.get("name") or f"mol{index}", value))
    else:
        for index, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            rows.append((parts[1] if len(parts) > 1 else f"mol{index}", parts[0]))

    if not rows:
        raise BatchError(f"no SMILES found in {path}")
    return rows


def command_prepare(args: argparse.Namespace) -> None:
    rows = read_smiles(args.smiles, args.smiles_column)

    mixtures = [identifier for identifier, smiles in rows if MIXTURE_MARKER in smiles]
    seen: dict[str, str] = {}
    order: list[str] = []
    duplicates = 0
    for identifier, smiles in rows:
        if smiles in seen:
            duplicates += 1
            continue
        seen[smiles] = identifier
        order.append(smiles)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    chunks = [order[i : i + args.chunk_size] for i in range(0, len(order), args.chunk_size)]
    written = []
    for index, chunk in enumerate(chunks):
        path = out_dir / f"chunk_{index:04d}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["smiles"])
            for smiles in chunk:
                writer.writerow([smiles])
        written.append({"chunk": index, "path": str(path), "molecules": len(chunk)})

    manifest = {
        "input": args.smiles,
        "total_input": len(rows),
        "unique": len(order),
        "duplicates_collapsed": duplicates,
        "mixtures": mixtures,
        "chunks": written,
        "smiles_to_id": seen,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        f"# {len(rows)} input, {len(order)} unique ({duplicates} duplicates collapsed), "
        f"{len(chunks)} chunk(s)",
        file=sys.stderr,
    )
    if mixtures:
        print(
            f"# warning: {len(mixtures)} SMILES contain `.` -- a salt, mixture, or "
            "counterion. ADMET-AI predicts on the structure as given, so desalt "
            "first or the prediction describes the wrong species.",
            file=sys.stderr,
        )
    print(f"# manifest: {manifest_path}", file=sys.stderr)

    for entry in written:
        print(
            f"admet_predict --smiles_path {entry['path']} "
            f"--save_path {entry['path'].replace('.csv', '_pred.csv')} "
            "--smiles_column smiles"
        )


def command_expand(args: argparse.Namespace) -> None:
    manifest = json.loads(Path(args.input).read_text(encoding="utf-8"))
    mapping = manifest.get("smiles_to_id") or {}

    with open(args.predictions, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise BatchError(f"{args.predictions} has no rows")

    column = next(
        (field for field in rows[0] if field.lower() in ("smiles", "smi")), None
    )
    if column is None:
        raise BatchError(f"no SMILES column in {args.predictions}")

    fieldnames = ["id"] + list(rows[0])
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    missing = 0
    for row in rows:
        identifier = mapping.get(row[column])
        if identifier is None:
            missing += 1
        writer.writerow({"id": identifier or "", **row})

    print(f"# {len(rows)} predictions expanded", file=sys.stderr)
    if missing:
        print(
            f"# warning: {missing} predicted SMILES are not in the manifest -- "
            "ADMET-AI canonicalises input, so these may be the same molecules "
            "written differently",
            file=sys.stderr,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="chunk a library into ADMET-AI inputs")
    prepare.add_argument("--smiles", required=True, help=".smi, .txt, or .csv input")
    prepare.add_argument("--smiles-column", help="column name when the input is CSV")
    prepare.add_argument("--out-dir", default="admet_in", help="default: admet_in")
    prepare.add_argument(
        "--chunk-size", type=int, default=DEFAULT_CHUNK, help=f"default: {DEFAULT_CHUNK}"
    )
    prepare.set_defaults(handler=command_prepare)

    expand = subparsers.add_parser("expand", help="restore identifiers onto predictions")
    expand.add_argument("--input", required=True, help="manifest.json from prepare")
    expand.add_argument("--predictions", required=True, help="ADMET-AI prediction CSV")
    expand.set_defaults(handler=command_expand)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except BatchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
