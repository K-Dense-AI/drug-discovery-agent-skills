#!/usr/bin/env python3
"""Write a valid Boltz input YAML from the command line.

Boltz's YAML is small but unforgiving: chain ids must be unique and are
referenced by later blocks, `smiles` and `ccd` are mutually exclusive, the
affinity binder must be a ligand chain, and a protein without `msa` fails
unless `--use_msa_server` is passed to `boltz predict`. Getting one of those
wrong costs a GPU-minutes-long run that dies at parse time.

Emitted by hand rather than through a YAML library, so the script has no
dependencies and the output stays readable.

Examples:

    # protein + ligand cofolding, with affinity
    python make_boltz_yaml.py --protein-fasta target.fasta \\
        --ligand-smiles "Cc1ccc(cc1Nc1nccc(n1)c1cccnc1)NC(=O)c1ccc(CN2CCN(C)CC2)cc1" \\
        --affinity --out complex.yaml

    # a known cofactor by CCD code, plus a pocket constraint
    python make_boltz_yaml.py --protein-sequence MVTPEG... --ligand-ccd SAH \\
        --pocket A:790,A:797,A:855 --out cofactor.yaml

    # a homodimer, single-sequence mode (fast, less accurate)
    python make_boltz_yaml.py --protein-sequence MVTPEG... --copies 2 \\
        --no-msa --out dimer.yaml
"""

from __future__ import annotations

import argparse
import string
import sys
from pathlib import Path

#: Boltz-2's affinity module was trained on ligands up to this size (heavy
#: atoms plus retained hydrogens). It will run past it and return a number
#: that means nothing.
AFFINITY_ATOM_LIMIT = 128
AFFINITY_RECOMMENDED_LIMIT = 56

CHAIN_IDS = list(string.ascii_uppercase)

AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWYXBZUO")


def read_fasta(path: Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    name = ""
    chunks: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            if chunks:
                records.append((name, "".join(chunks)))
            name = line[1:].strip()
            chunks = []
        elif line.strip():
            chunks.append(line.strip())
    if chunks:
        records.append((name, "".join(chunks)))
    return records


def estimate_heavy_atoms(smiles: str) -> int:
    """Crude heavy-atom count from a SMILES string, for the affinity warning.

    Deliberately approximate -- this exists to catch "you passed a peptide to
    the affinity module", not to be a cheminformatics toolkit. Bracket atoms
    count as one; two-letter organic subset symbols are handled; hydrogens
    inside brackets are ignored.
    """
    count = 0
    index = 0
    two_letter = {"Cl", "Br", "Si", "Se", "As", "Te"}
    while index < len(smiles):
        character = smiles[index]
        if character == "[":
            end = smiles.find("]", index)
            if end == -1:
                break
            token = smiles[index + 1 : end]
            symbol = "".join(c for c in token if c.isalpha())
            if symbol and not symbol.startswith("H"):
                count += 1
            index = end + 1
            continue
        if smiles[index : index + 2] in two_letter:
            count += 1
            index += 2
            continue
        if character.isalpha():
            if character.upper() in "BCNOPSFI":
                count += 1
            index += 1
            continue
        index += 1
    return count


def quote(value: str) -> str:
    """SMILES routinely contain `#`, `\\`, and `[`; always quote them."""
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def parse_contacts(specification: str) -> list[tuple[str, str]]:
    contacts: list[tuple[str, str]] = []
    for item in specification.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise SystemExit(
                f"error: contact `{item}` must be CHAIN:RESIDUE, e.g. A:790"
            )
        chain, _, residue = item.partition(":")
        contacts.append((chain.strip(), residue.strip()))
    return contacts


def build_yaml(args) -> str:
    proteins: list[tuple[str, str]] = []
    if args.protein_fasta:
        for name, sequence in read_fasta(Path(args.protein_fasta)):
            proteins.append((name, sequence.upper()))
    for sequence in args.protein_sequence or []:
        proteins.append(("", sequence.strip().upper()))

    if not proteins and not (args.ligand_smiles or args.ligand_ccd):
        raise SystemExit("error: give at least one protein or ligand")

    for name, sequence in proteins:
        unknown = set(sequence) - AMINO_ACIDS
        if unknown:
            raise SystemExit(
                f"error: sequence {name or '(inline)'} contains non-amino-acid "
                f"characters: {''.join(sorted(unknown))}"
            )

    lines = ["version: 1", "sequences:"]
    chain_index = 0
    ligand_chains: list[str] = []
    protein_chains: list[str] = []

    for name, sequence in proteins:
        if chain_index >= len(CHAIN_IDS):
            raise SystemExit("error: more chains than single-letter ids available")
        if args.copies > 1:
            ids = CHAIN_IDS[chain_index : chain_index + args.copies]
            if len(ids) < args.copies:
                raise SystemExit("error: not enough chain ids for the requested copies")
            chain_index += args.copies
            identifier = "[" + ", ".join(ids) + "]"
            protein_chains.extend(ids)
        else:
            identifier = CHAIN_IDS[chain_index]
            protein_chains.append(identifier)
            chain_index += 1
        lines.append("  - protein:")
        lines.append(f"      id: {identifier}")
        lines.append(f"      sequence: {sequence}")
        if args.msa_path:
            lines.append(f"      msa: {args.msa_path}")
        elif args.no_msa:
            # `empty` is Boltz's explicit single-sequence mode. Omitting the
            # key entirely is an error unless --use_msa_server is passed to
            # the CLI, which is a different failure and a confusing one.
            lines.append("      msa: empty")
        if args.cyclic:
            lines.append("      cyclic: true")
        if name:
            lines.insert(len(lines) - 1, f"      # {name}")

    for smiles in args.ligand_smiles or []:
        identifier = CHAIN_IDS[chain_index]
        chain_index += 1
        ligand_chains.append(identifier)
        lines.append("  - ligand:")
        lines.append(f"      id: {identifier}")
        lines.append(f"      smiles: {quote(smiles)}")

    for code in args.ligand_ccd or []:
        identifier = CHAIN_IDS[chain_index]
        chain_index += 1
        ligand_chains.append(identifier)
        lines.append("  - ligand:")
        lines.append(f"      id: {identifier}")
        lines.append(f"      ccd: {code.upper()}")

    if args.pocket:
        if not ligand_chains:
            raise SystemExit("error: --pocket needs a ligand to bind")
        binder = args.pocket_binder or ligand_chains[0]
        contacts = parse_contacts(args.pocket)
        lines.append("constraints:")
        lines.append("  - pocket:")
        lines.append(f"      binder: {binder}")
        rendered = ", ".join(f"[{chain}, {residue}]" for chain, residue in contacts)
        lines.append(f"      contacts: [{rendered}]")
        lines.append(f"      max_distance: {args.pocket_distance}")
        if args.pocket_force:
            lines.append("      force: true")

    if args.affinity:
        if not ligand_chains:
            raise SystemExit("error: --affinity needs a ligand chain")
        binder = args.affinity_binder or ligand_chains[0]
        if binder not in ligand_chains:
            raise SystemExit(
                f"error: affinity binder `{binder}` is not a ligand chain "
                f"(ligands: {', '.join(ligand_chains) or 'none'})"
            )
        if len(ligand_chains) > 1 and not args.affinity_binder:
            print(
                f"# note: {len(ligand_chains)} ligands present; affinity is computed for "
                f"chain {binder} only. Use --affinity-binder to choose.",
                file=sys.stderr,
            )
        lines.append("properties:")
        lines.append("  - affinity:")
        lines.append(f"      binder: {binder}")

    return "\n".join(lines) + "\n"


def warn(args) -> None:
    if args.affinity:
        for smiles in args.ligand_smiles or []:
            atoms = estimate_heavy_atoms(smiles)
            if atoms > AFFINITY_ATOM_LIMIT:
                print(
                    f"# warning: ligand of ~{atoms} heavy atoms exceeds the affinity "
                    f"module's {AFFINITY_ATOM_LIMIT}-atom limit; the value will be "
                    "returned but is meaningless",
                    file=sys.stderr,
                )
            elif atoms > AFFINITY_RECOMMENDED_LIMIT:
                print(
                    f"# note: ligand of ~{atoms} heavy atoms is above the ~"
                    f"{AFFINITY_RECOMMENDED_LIMIT} atoms the affinity head was trained "
                    "on; treat the number with extra caution",
                    file=sys.stderr,
                )
    if args.no_msa:
        print(
            "# note: msa: empty is single-sequence mode. It is much faster and "
            "noticeably less accurate -- use it for a smoke test, not a result.",
            file=sys.stderr,
        )
    if not args.no_msa and not args.msa_path:
        print(
            "# reminder: no MSA path given, so `boltz predict` must be run with "
            "--use_msa_server (which sends your sequence to the public ColabFold "
            "server -- do not use it for confidential sequences).",
            file=sys.stderr,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--protein-fasta", help="FASTA file; one chain per record")
    parser.add_argument(
        "--protein-sequence", action="append", help="inline sequence, repeatable"
    )
    parser.add_argument(
        "--copies", type=int, default=1, help="identical copies of each protein chain"
    )
    parser.add_argument("--ligand-smiles", action="append", help="ligand SMILES, repeatable")
    parser.add_argument("--ligand-ccd", action="append", help="ligand CCD code, repeatable")
    parser.add_argument("--msa-path", help="precomputed .a3m (single chain) or .csv (paired)")
    parser.add_argument(
        "--no-msa",
        action="store_true",
        help="single-sequence mode (`msa: empty`); faster and less accurate",
    )
    parser.add_argument("--cyclic", action="store_true", help="mark protein chains cyclic")
    parser.add_argument(
        "--pocket", help="comma-separated CHAIN:RESIDUE contacts defining the binding site"
    )
    parser.add_argument("--pocket-binder", help="which chain binds the pocket (default: first ligand)")
    parser.add_argument(
        "--pocket-distance", type=float, default=6.0, help="max_distance in Angstrom, 4-20"
    )
    parser.add_argument(
        "--pocket-force", action="store_true", help="enforce the pocket with a potential"
    )
    parser.add_argument("--affinity", action="store_true", help="predict binding affinity")
    parser.add_argument("--affinity-binder", help="ligand chain for affinity (default: first)")
    parser.add_argument("--out", help="write here instead of stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.pocket_distance is not None and not 4.0 <= args.pocket_distance <= 20.0:
        print("error: --pocket-distance must be between 4 and 20 Angstrom", file=sys.stderr)
        return 1
    document = build_yaml(args)
    warn(args)
    if args.out:
        Path(args.out).write_text(document, encoding="utf-8")
        print(f"# wrote {args.out}", file=sys.stderr)
        print(
            f"# next: boltz predict {args.out} --out_dir predictions/ "
            + ("--use_msa_server " if not (args.no_msa or args.msa_path) else "")
            + "--use_potentials --diffusion_samples 5",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
