#!/usr/bin/env python3
"""Look compounds up in ChEMBL by id, name, structure, or similarity.

Commands:

    id           one or more ChEMBL molecule ids -> full records
    name         free-text name search (brand, generic, research code)
    smiles       exact structure match, salt/parent aware (flexmatch)
    inchikey     lookup by standard InChIKey, full or skeleton
    similar      Tanimoto similarity search over ECFP4-style fingerprints
    substructure substructure search from a SMILES or SMARTS-like query
    mechanism    approved/clinical mechanisms of action for a molecule or target

Structure searches put the query *in the URL path*, so a SMILES containing
`#`, `+`, `/`, or `\\` must be percent-encoded -- unencoded, `#` truncates the
URL at the fragment marker and you get a 404 or, worse, the wrong molecule.
This script encodes for you.

Examples:

    python compound_lookup.py id CHEMBL941 CHEMBL939
    python compound_lookup.py name imatinib
    python compound_lookup.py smiles "CC(=O)Oc1ccccc1C(=O)O"
    python compound_lookup.py similar "CC(=O)Oc1ccccc1C(=O)O" --threshold 70
    python compound_lookup.py mechanism --target CHEMBL203
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    ChemblError,
    add_common_arguments,
    as_float,
    emit,
    get,
    paged,
)

MOLECULE_COLUMNS = (
    "molecule_chembl_id",
    "pref_name",
    "molecule_type",
    "max_phase",
    "first_approval",
    "canonical_smiles",
    "standard_inchi_key",
    "full_mwt",
    "alogp",
    "hba",
    "hbd",
    "psa",
    "rtb",
    "aromatic_rings",
    "num_ro5_violations",
    "qed_weighted",
    "structure_type",
    "withdrawn_flag",
    "black_box_warning",
    "oral",
    "parenteral",
    "topical",
    "natural_product",
    "prodrug",
    "chirality",
)

#: Only meaningful on a similarity search; carried through so the score is not
#: silently lost when the same formatter handles both search kinds.
SIMILARITY_COLUMNS = ("similarity", *MOLECULE_COLUMNS)


def flatten(molecule: dict) -> dict:
    """Lift `molecule_properties` and `molecule_structures` to the top level.

    Every numeric property arrives as a string; the caller wants numbers.
    """
    properties = molecule.get("molecule_properties") or {}
    structures = molecule.get("molecule_structures") or {}
    flat = {
        "molecule_chembl_id": molecule.get("molecule_chembl_id"),
        "pref_name": molecule.get("pref_name"),
        "molecule_type": molecule.get("molecule_type"),
        "max_phase": as_float(molecule.get("max_phase")),
        "first_approval": molecule.get("first_approval"),
        "canonical_smiles": structures.get("canonical_smiles"),
        "standard_inchi_key": structures.get("standard_inchi_key"),
        "structure_type": molecule.get("structure_type"),
        "withdrawn_flag": molecule.get("withdrawn_flag"),
        "black_box_warning": molecule.get("black_box_warning"),
        "oral": molecule.get("oral"),
        "parenteral": molecule.get("parenteral"),
        "topical": molecule.get("topical"),
        "natural_product": molecule.get("natural_product"),
        "prodrug": molecule.get("prodrug"),
        "chirality": molecule.get("chirality"),
        "similarity": as_float(molecule.get("similarity")),
    }
    for field in ("full_mwt", "alogp", "psa", "qed_weighted"):
        flat[field] = as_float(properties.get(field))
    for field in ("hba", "hbd", "rtb", "aromatic_rings", "num_ro5_violations", "heavy_atoms"):
        flat[field] = properties.get(field)
    return flat


def _emit_molecules(records, args, columns=MOLECULE_COLUMNS) -> None:
    rows = [flatten(record) for record in records]
    if args.output_format == "json":
        emit(rows, columns, "json")
        return
    emit(rows, columns, args.output_format)


def command_id(args) -> None:
    records = list(
        paged(
            "molecule",
            {"molecule_chembl_id__in": ",".join(args.chembl_ids)},
            limit=len(args.chembl_ids),
            base_url=args.base_url,
        )
    )
    found = {record.get("molecule_chembl_id") for record in records}
    missing = [identifier for identifier in args.chembl_ids if identifier not in found]
    if missing:
        print(f"# not found: {', '.join(missing)}", file=sys.stderr)
    _emit_molecules(records, args)


def command_name(args) -> None:
    document = get(
        "molecule/search",
        {"q": args.query, "limit": args.limit},
        base_url=args.base_url,
    )
    records = document.get("molecules") or []
    print(
        f"# {(document.get('page_meta') or {}).get('total_count', 0)} matches "
        "(full-text, ranked by relevance)",
        file=sys.stderr,
    )
    _emit_molecules(records, args)


def command_smiles(args) -> None:
    """Exact-structure lookup.

    `flexmatch` is the right operator here: it matches the compound regardless
    of salt form, tautomer representation, or charge state, which is what
    "is this molecule in ChEMBL?" almost always means. `__exact` on the
    canonical SMILES matches only a byte-identical string and will miss the
    parent of a hydrochloride salt.
    """
    field = "molecule_structures__canonical_smiles__exact" if args.exact else (
        "molecule_structures__canonical_smiles__flexmatch"
    )
    records = list(paged("molecule", {field: args.smiles}, limit=args.limit, base_url=args.base_url))
    if not records:
        print(
            "# no match. flexmatch normalises salts and tautomers; if you passed "
            "--exact, retry without it",
            file=sys.stderr,
        )
    _emit_molecules(records, args)


def command_inchikey(args) -> None:
    key = args.inchikey.strip().upper()
    if len(key) == 14:
        # The skeleton block alone: same connectivity, any stereochemistry or
        # protonation state.
        params = {"molecule_structures__standard_inchi_key__startswith": key}
    else:
        params = {"molecule_structures__standard_inchi_key": key}
    records = list(paged("molecule", params, limit=args.limit, base_url=args.base_url))
    _emit_molecules(records, args)


def command_similar(args) -> None:
    if not 40 <= args.threshold <= 100:
        raise ChemblError("--threshold must be between 40 and 100 (the API rejects lower)")
    quoted = urllib.parse.quote(args.smiles, safe="")
    records = list(
        paged(
            f"similarity/{quoted}/{args.threshold}",
            limit=args.limit,
            base_url=args.base_url,
        )
    )
    records.sort(key=lambda record: -(as_float(record.get("similarity")) or 0))
    print(f"# {len(records)} molecules at >= {args.threshold}% similarity", file=sys.stderr)
    _emit_molecules(records, args, SIMILARITY_COLUMNS)


def command_substructure(args) -> None:
    quoted = urllib.parse.quote(args.query, safe="")
    records = list(paged(f"substructure/{quoted}", limit=args.limit, base_url=args.base_url))
    print(f"# {len(records)} molecules contain the query substructure", file=sys.stderr)
    _emit_molecules(records, args)


MECHANISM_COLUMNS = (
    "molecule_chembl_id",
    "target_chembl_id",
    "action_type",
    "mechanism_of_action",
    "max_phase",
    "direct_interaction",
    "molecular_mechanism",
    "disease_efficacy",
    "mechanism_comment",
    "selectivity_comment",
)


def command_mechanism(args) -> None:
    if not (args.molecule or args.target):
        raise ChemblError("mechanism needs --molecule or --target")
    params = {}
    if args.molecule:
        params["molecule_chembl_id"] = args.molecule
    if args.target:
        params["target_chembl_id"] = args.target
    records = list(paged("mechanism", params, limit=args.limit, base_url=args.base_url))
    rows = [
        {column: record.get(column) for column in MECHANISM_COLUMNS} for record in records
    ]
    print(f"# {len(rows)} curated mechanism records", file=sys.stderr)
    emit(rows, MECHANISM_COLUMNS, args.output_format)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def with_common(sub, limit_default=25):
        sub.add_argument("--limit", type=int, default=limit_default, help="maximum rows")
        add_common_arguments(sub)
        return sub

    by_id = subparsers.add_parser("id", help="fetch molecules by ChEMBL id")
    by_id.add_argument("chembl_ids", nargs="+")
    with_common(by_id, 100).set_defaults(handler=command_id)

    by_name = subparsers.add_parser("name", help="full-text name search")
    by_name.add_argument("query")
    with_common(by_name).set_defaults(handler=command_name)

    by_smiles = subparsers.add_parser("smiles", help="exact structure lookup")
    by_smiles.add_argument("smiles")
    by_smiles.add_argument(
        "--exact",
        action="store_true",
        help="byte-identical canonical SMILES instead of salt/tautomer-aware flexmatch",
    )
    with_common(by_smiles).set_defaults(handler=command_smiles)

    by_key = subparsers.add_parser("inchikey", help="lookup by standard InChIKey")
    by_key.add_argument("inchikey", help="full 27-character key, or the 14-character skeleton")
    with_common(by_key).set_defaults(handler=command_inchikey)

    similar = subparsers.add_parser("similar", help="Tanimoto similarity search")
    similar.add_argument("smiles")
    similar.add_argument(
        "--threshold", type=int, default=70, help="percent similarity, 40-100 (default: 70)"
    )
    with_common(similar, 100).set_defaults(handler=command_similar)

    substructure = subparsers.add_parser("substructure", help="substructure search")
    substructure.add_argument("query", help="SMILES or SMARTS")
    with_common(substructure, 100).set_defaults(handler=command_substructure)

    mechanism = subparsers.add_parser("mechanism", help="curated mechanisms of action")
    mechanism.add_argument("--molecule", help="ChEMBL molecule id")
    mechanism.add_argument("--target", help="ChEMBL target id")
    with_common(mechanism, 200).set_defaults(handler=command_mechanism)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except ChemblError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
