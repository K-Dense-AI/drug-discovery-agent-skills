#!/usr/bin/env python3
"""Download experimental structures from the PDB, or predicted models from AlphaFold DB.

    pdb        one or more PDB ids -> mmCIF (default) or legacy PDB format
    assembly   the biological assembly rather than the asymmetric unit
    alphafold  the AlphaFold DB model for a UniProt accession, plus pLDDT bands
    ligand     the idealised coordinates and SMILES of a chemical component

Three things worth knowing before you download:

* **Legacy `.pdb` format does not exist for large entries.** Anything that
  overflows the 80-column fixed-width format -- large complexes, most recent
  cryo-EM structures -- is mmCIF only, and `files.rcsb.org/download/8ETU.pdb`
  returns 404. Default to mmCIF unless a downstream tool demands PDB.
* **The asymmetric unit is not the biological unit.** A crystal structure's
  deposited coordinates may hold half a dimer, or four copies of a monomer.
  Docking or simulating the wrong one is a silent error; use `assembly`.
* **AlphaFold pLDDT is per-residue confidence, not accuracy.** Below 70 the
  backbone is unreliable; below 50 the region is usually intrinsically
  disordered and modelled as a ribbon through space. This reports the bands
  so you know before you build a pocket around one.

Examples:

    python fetch_structure.py pdb 1IEP 3POZ --out-dir structures/
    python fetch_structure.py assembly 4HHB --assembly 1
    python fetch_structure.py alphafold P00533 --out-dir models/
    python fetch_structure.py ligand STI
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    ALPHAFOLD_API,
    RCSB_DATA,
    RCSB_FILES,
    ServiceError,
    add_common_arguments,
    download,
    get_json,
    write_table,
)

#: AlphaFold's own confidence bands. The cut-offs are from the AlphaFold DB
#: documentation, not invented here.
PLDDT_BANDS = (
    (90, 100, "very high", "backbone and side chains reliable"),
    (70, 90, "confident", "backbone reliable, side chains less so"),
    (50, 70, "low", "backbone unreliable -- do not dock into this"),
    (0, 50, "very low", "usually intrinsically disordered, treat as ribbon"),
)


def command_pdb(args) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for pdb_id in args.pdb_ids:
        pdb_id = pdb_id.upper()
        suffix = "pdb" if args.file_format == "pdb" else "cif"
        url = f"{RCSB_FILES}/{pdb_id}.{suffix}"
        destination = out_dir / f"{pdb_id}.{suffix}"
        try:
            size = download(url, destination)
        except ServiceError as error:
            if suffix == "pdb" and "HTTP 404" in str(error):
                raise ServiceError(
                    f"{pdb_id} has no legacy PDB-format file -- it is too large for the "
                    "80-column format. Re-run without `--file-format pdb` to get mmCIF."
                ) from error
            raise
        print(f"{destination}\t{size} bytes")


def command_assembly(args) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for pdb_id in args.pdb_ids:
        pdb_id = pdb_id.upper()
        suffix = "pdb" if args.file_format == "pdb" else "cif"
        url = f"{RCSB_FILES}/{pdb_id}-assembly{args.assembly}.{suffix}"
        destination = out_dir / f"{pdb_id}-assembly{args.assembly}.{suffix}"
        size = download(url, destination)
        print(f"{destination}\t{size} bytes")


def command_alphafold(args) -> None:
    predictions = get_json(f"{ALPHAFOLD_API}/{args.accession}")
    if not predictions:
        raise ServiceError(
            f"AlphaFold DB has no model for {args.accession}. It covers UniProt "
            "reference proteomes; obsolete or non-reference accessions are absent."
        )
    prediction = predictions[0]

    print(f"# {prediction.get('entryId')} ({prediction.get('uniprotDescription')})")
    print(f"# organism: {prediction.get('organismScientificName')}")
    print(f"# model version: v{prediction.get('latestVersion')}  built with {prediction.get('toolUsed')}")
    print(f"# covers UniProt residues {prediction.get('uniprotStart')}-{prediction.get('uniprotEnd')}")
    print(f"# mean pLDDT: {prediction.get('globalMetricValue')}")

    fractions = [
        ("very high (>90)", prediction.get("fractionPlddtVeryHigh")),
        ("confident (70-90)", prediction.get("fractionPlddtConfident")),
        ("low (50-70)", prediction.get("fractionPlddtLow")),
        ("very low (<50)", prediction.get("fractionPlddtVeryLow")),
    ]
    rows = [
        {"band": label, "fraction": value, "percent": None if value is None else round(value * 100, 1)}
        for label, value in fractions
    ]
    write_table(rows, ("band", "percent"))

    unreliable = (prediction.get("fractionPlddtLow") or 0) + (
        prediction.get("fractionPlddtVeryLow") or 0
    )
    if unreliable > 0.3:
        print(
            f"# warning: {unreliable * 100:.0f}% of residues are below pLDDT 70. "
            "Trim to the confident domain before docking or simulating.",
            file=sys.stderr,
        )

    if args.metadata_only:
        return

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = {
        "cif": prediction.get("cifUrl"),
        "pdb": prediction.get("pdbUrl"),
        "pae": prediction.get("paeDocUrl") if args.with_pae else None,
    }
    for kind, url in wanted.items():
        if not url or (kind != args.file_format and kind != "pae"):
            continue
        destination = out_dir / Path(url).name
        size = download(url, destination)
        print(f"{destination}\t{size} bytes")


def command_ligand(args) -> None:
    component = args.component_id.upper()
    document = get_json(f"{RCSB_DATA}/chemcomp/{component}")
    if not document:
        raise ServiceError(f"no chemical component {component}")
    chem = document.get("chem_comp") or {}
    descriptors = document.get("rcsb_chem_comp_descriptor") or {}
    print(f"# {chem.get('id')}  {chem.get('name')}")
    print(f"# formula: {chem.get('formula')}   MW: {chem.get('formula_weight')}")
    print(f"# type: {chem.get('type')}   parent: {chem.get('mon_nstd_parent_comp_id') or 'none'}")
    print(f"SMILES\t{descriptors.get('SMILES_stereo') or descriptors.get('SMILES')}")
    print(f"InChIKey\t{descriptors.get('InChIKey')}")

    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        # The idealised coordinates -- a clean starting conformer for docking,
        # free of the crystal-fitted strain of any one deposited copy.
        url = f"https://files.rcsb.org/ligands/download/{component}_ideal.sdf"
        destination = out_dir / f"{component}_ideal.sdf"
        size = download(url, destination)
        print(f"{destination}\t{size} bytes")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def with_output(sub, default_dir="."):
        sub.add_argument("--out-dir", default=default_dir, help="where to write files")
        sub.add_argument(
            "--file-format",
            choices=("cif", "pdb"),
            default="cif",
            help="mmCIF (default, always available) or legacy PDB",
        )
        add_common_arguments(sub)
        return sub

    pdb = subparsers.add_parser("pdb", help="download entries by PDB id")
    pdb.add_argument("pdb_ids", nargs="+")
    with_output(pdb).set_defaults(handler=command_pdb)

    assembly = subparsers.add_parser("assembly", help="download a biological assembly")
    assembly.add_argument("pdb_ids", nargs="+")
    assembly.add_argument("--assembly", default="1", help="assembly number (default: 1)")
    with_output(assembly).set_defaults(handler=command_assembly)

    alphafold = subparsers.add_parser("alphafold", help="AlphaFold DB model for an accession")
    alphafold.add_argument("accession", help="UniProt accession, e.g. P00533")
    alphafold.add_argument(
        "--metadata-only", action="store_true", help="report confidence without downloading"
    )
    alphafold.add_argument("--with-pae", action="store_true", help="also fetch the PAE matrix JSON")
    with_output(alphafold).set_defaults(handler=command_alphafold)

    ligand = subparsers.add_parser("ligand", help="chemical component definition")
    ligand.add_argument("component_id", help="3-character CCD id, e.g. STI")
    ligand.add_argument("--out-dir", help="also download the idealised SDF here")
    add_common_arguments(ligand)
    ligand.set_defaults(handler=command_ligand)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except ServiceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
