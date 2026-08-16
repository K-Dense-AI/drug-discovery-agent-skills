#!/usr/bin/env python3
"""Fan a compound library out into one Boltz YAML per ligand, plus a manifest.

Boltz predicts one complex per input file, so screening N compounds against one
target means N YAML files. Written naively that means N MSAs of the same
protein — the expensive part of the run, recomputed every time.

This writes the shared MSA path into every file, so you compute it once:

    boltz predict target_only.yaml --use_msa_server --out_dir msa_run/
    # then reuse msa_run/processed/msa/*.npz -- or supply your own .a3m

Input is a SMILES file: one molecule per line, `SMILES[<whitespace>NAME]`.
Blank lines and `#` comments are skipped.

Examples:

    python screen_library.py --protein-fasta target.fasta --smiles library.smi \\
        --out-dir screen/ --affinity --msa-path target.a3m
    python screen_library.py --protein-fasta target.fasta --smiles library.smi \\
        --out-dir screen/ --affinity --pocket A:790,A:797,A:855
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_boltz_yaml import (  # noqa: E402
    AFFINITY_ATOM_LIMIT,
    AFFINITY_RECOMMENDED_LIMIT,
    build_yaml,
    estimate_heavy_atoms,
    read_fasta,
)

SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class Options:
    """A stand-in for the argparse namespace `build_yaml` expects."""

    def __init__(self, **values):
        defaults = dict(
            protein_fasta=None,
            protein_sequence=None,
            copies=1,
            ligand_smiles=None,
            ligand_ccd=None,
            msa_path=None,
            no_msa=False,
            cyclic=False,
            pocket=None,
            pocket_binder=None,
            pocket_distance=6.0,
            pocket_force=False,
            affinity=False,
            affinity_binder=None,
        )
        defaults.update(values)
        for key, value in defaults.items():
            setattr(self, key, value)


def read_smiles(path: Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        smiles = parts[0]
        name = parts[1].strip() if len(parts) > 1 else f"mol{number:05d}"
        name = SAFE_NAME.sub("_", name)[:60] or f"mol{number:05d}"
        original = name
        suffix = 2
        while name in seen:
            name = f"{original}_{suffix}"
            suffix += 1
        seen.add(name)
        entries.append((name, smiles))
    return entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--protein-fasta", help="target FASTA (one or more chains)")
    parser.add_argument("--protein-sequence", action="append", help="inline target sequence")
    parser.add_argument("--smiles", required=True, help="library file: SMILES [name] per line")
    parser.add_argument("--out-dir", required=True, help="directory for the YAML files")
    parser.add_argument("--msa-path", help="precomputed MSA reused by every input")
    parser.add_argument("--no-msa", action="store_true", help="single-sequence mode")
    parser.add_argument("--affinity", action="store_true", help="request the affinity head")
    parser.add_argument("--pocket", help="comma-separated CHAIN:RESIDUE binding-site contacts")
    parser.add_argument("--pocket-distance", type=float, default=6.0)
    parser.add_argument("--pocket-force", action="store_true")
    parser.add_argument("--copies", type=int, default=1, help="copies of each protein chain")
    parser.add_argument("--limit", type=int, help="only the first N compounds")
    parser.add_argument(
        "--skip-oversized",
        action="store_true",
        help="omit compounds above the affinity module's size limit instead of writing them",
    )
    args = parser.parse_args(argv)

    if not (args.protein_fasta or args.protein_sequence):
        print("error: give --protein-fasta or --protein-sequence", file=sys.stderr)
        return 1
    smiles_path = Path(args.smiles)
    if not smiles_path.is_file():
        print(f"error: no such file: {smiles_path}", file=sys.stderr)
        return 1
    if args.protein_fasta and not Path(args.protein_fasta).is_file():
        print(f"error: no such file: {args.protein_fasta}", file=sys.stderr)
        return 1

    entries = read_smiles(smiles_path)
    if args.limit:
        entries = entries[: args.limit]
    if not entries:
        print(f"error: no molecules read from {smiles_path}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped: list[str] = []
    oversized: list[str] = []
    manifest_lines = ["name\tyaml\tsmiles\theavyAtomsEstimate"]

    for name, smiles in entries:
        atoms = estimate_heavy_atoms(smiles)
        if args.affinity and atoms > AFFINITY_ATOM_LIMIT:
            oversized.append(name)
            if args.skip_oversized:
                skipped.append(name)
                continue
        options = Options(
            protein_fasta=args.protein_fasta,
            protein_sequence=args.protein_sequence,
            copies=args.copies,
            ligand_smiles=[smiles],
            msa_path=args.msa_path,
            no_msa=args.no_msa,
            pocket=args.pocket,
            pocket_distance=args.pocket_distance,
            pocket_force=args.pocket_force,
            affinity=args.affinity,
        )
        try:
            document = build_yaml(options)
        except SystemExit as error:
            print(f"# skipping {name}: {error}", file=sys.stderr)
            skipped.append(name)
            continue
        path = out_dir / f"{name}.yaml"
        path.write_text(document, encoding="utf-8")
        manifest_lines.append(f"{name}\t{path}\t{smiles}\t{atoms}")
        written += 1

    manifest = out_dir / "manifest.tsv"
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    print(f"# wrote {written} YAML file(s) and {manifest}", file=sys.stderr)
    if skipped:
        print(f"# skipped {len(skipped)}: {', '.join(skipped[:10])}", file=sys.stderr)
    if oversized and not args.skip_oversized:
        print(
            f"# warning: {len(oversized)} compound(s) exceed the affinity module's "
            f"{AFFINITY_ATOM_LIMIT}-atom limit and will return meaningless affinities "
            "(pass --skip-oversized to leave them out)",
            file=sys.stderr,
        )

    if args.protein_fasta:
        chains = read_fasta(Path(args.protein_fasta))
        residues = sum(len(sequence) for _, sequence in chains) * args.copies
        print(f"# target: {len(chains)} chain(s), {residues} residues per complex", file=sys.stderr)

    if not (args.msa_path or args.no_msa):
        print(
            "# note: no --msa-path, so every one of these inputs will build its own MSA "
            "for the same protein. Compute it once and pass --msa-path; it is the "
            "single biggest saving in a screen.",
            file=sys.stderr,
        )

    msa_flag = "" if (args.msa_path or args.no_msa) else " --use_msa_server"
    print(
        f"# next: boltz predict {out_dir} --out_dir {out_dir}/predictions{msa_flag} "
        "--use_potentials --diffusion_samples 5\n"
        f"#       python collect_results.py {out_dir}/predictions --out scores.tsv",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
