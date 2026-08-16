#!/usr/bin/env python3
"""Search the PDB and report the metadata you need to pick a structure.

The RCSB search API returns *only identifiers and scores* -- no resolution, no
ligands, no method. Every practical question ("the best EGFR structure with an
inhibitor bound") therefore takes two services: search for the ids, then fetch
each entry from the data API. This script does both and merges them.

Commands:

    uniprot     structures for a UniProt accession, resolution-filtered
    sequence    MMseqs2 sequence similarity search
    text        full-text search over titles, abstracts, and annotations
    attribute   raw attribute query for anything the above do not cover
    ligand      entries containing a given chemical component (by CCD id)

Examples:

    python rcsb_search.py uniprot P00533 --max-resolution 2.5 --has-ligand
    python rcsb_search.py sequence --fasta target.fasta --identity 0.9
    python rcsb_search.py text "SARS-CoV-2 main protease" --max-resolution 2.0
    python rcsb_search.py ligand STI
    python rcsb_search.py attribute rcsb_entry_info.deposited_polymer_entity_instance_count \\
        greater 20 --return-type entry
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    RCSB_GRAPHQL,
    RCSB_SEARCH,
    ServiceError,
    add_common_arguments,
    emit,
    post_json,
)

#: Chemical components that are crystallisation additives, buffers, ions, or
#: cryoprotectants rather than ligands of interest. Judging "does this
#: structure have a ligand?" without excluding these calls every entry a hit.
COMMON_ADDITIVES = frozenset(
    {
        "HOH", "DOD", "SO4", "PO4", "GOL", "EDO", "PEG", "PGE", "PG4", "1PE", "MPD",
        "DMS", "ACT", "FMT", "MES", "TRS", "EPE", "CIT", "TLA", "MLI", "IMD", "BME",
        "NA", "K", "MG", "CA", "ZN", "MN", "FE", "FE2", "NI", "CO", "CU", "CD", "HG",
        "CL", "BR", "IOD", "F", "NO3", "AZI", "CO3", "NH4", "OXY", "PER",
        "ACY", "ACE", "NAG", "BGC", "MAN", "GLC", "FUC", "GAL", "NDG", "BMA",
        "UNX", "UNL", "PGO", "BU3", "P6G", "12P", "15P", "2PE", "XPE",
    }
)

ENTRY_COLUMNS = (
    "pdbId",
    "method",
    "resolution",
    "rFree",
    "ligands",
    "uniprotIds",
    "mutations",
    "unmodelledResidues",
    "modelledResidues",
    "polymerEntities",
    "releaseYear",
    "title",
    "score",
)


def run_search(query: dict, *, return_type: str = "entry", rows: int = 25, start: int = 0,
               content: tuple[str, ...] = ("experimental",)) -> tuple[int, list[dict]]:
    """POST one search request. Returns (total_count, result_set).

    A search with no hits answers **204 with an empty body**, not an empty
    JSON document -- so `post_json` returning None means zero results, not a
    failure.
    """
    payload = {
        "query": query,
        "return_type": return_type,
        "request_options": {
            "paginate": {"start": start, "rows": rows},
            "results_content_type": list(content),
        },
    }
    document = post_json(RCSB_SEARCH, payload)
    if document is None:
        return 0, []
    return document.get("total_count", 0), document.get("result_set") or []


def terminal(service: str, parameters: dict) -> dict:
    return {"type": "terminal", "service": service, "parameters": parameters}


def group(nodes: list[dict], operator: str = "and") -> dict:
    if len(nodes) == 1:
        return nodes[0]
    return {"type": "group", "logical_operator": operator, "nodes": nodes}


def attribute_node(attribute: str, operator: str, value) -> dict:
    return terminal("text", {"attribute": attribute, "operator": operator, "value": value})


DESCRIBE_QUERY = """
query Describe($ids: [String!]!) {
  entries(entry_ids: $ids) {
    rcsb_id
    struct { title }
    exptl { method }
    refine { ls_R_factor_R_free }
    rcsb_accession_info { initial_release_date }
    rcsb_entry_info {
      resolution_combined
      polymer_entity_count
      deposited_polymer_monomer_count
      deposited_unmodeled_polymer_monomer_count
    }
    polymer_entities {
      rcsb_id
      rcsb_polymer_entity { pdbx_description pdbx_mutation }
      rcsb_polymer_entity_container_identifiers { uniprot_ids auth_asym_ids }
      entity_poly { rcsb_sample_sequence_length }
    }
    nonpolymer_entities {
      rcsb_id
      nonpolymer_comp { chem_comp { id name formula_weight } }
    }
  }
}
"""


def describe_entries(pdb_ids: list[str], *, batch_size: int = 50) -> dict[str, dict]:
    """One GraphQL request per batch of entries, instead of N REST calls.

    The REST data API needs a separate request per entry *and* per
    non-polymer entity to find out which ligands are bound, which is dozens
    of round trips for a 25-hit search. The GraphQL endpoint returns entries,
    polymer entities, and ligands together.
    """
    described: dict[str, dict] = {}
    for start in range(0, len(pdb_ids), batch_size):
        batch = pdb_ids[start : start + batch_size]
        document = post_json(
            RCSB_GRAPHQL, {"query": DESCRIBE_QUERY, "variables": {"ids": batch}}
        )
        if not document:
            continue
        if document.get("errors"):
            raise ServiceError(
                "RCSB GraphQL error: "
                + "; ".join(str(item.get("message")) for item in document["errors"][:3])
            )
        for entry in (document.get("data") or {}).get("entries") or []:
            described[entry["rcsb_id"]] = _flatten_entry(entry)
    return described


def _flatten_entry(entry: dict) -> dict:
    info = entry.get("rcsb_entry_info") or {}
    resolutions = info.get("resolution_combined") or []
    refine = (entry.get("refine") or [{}]) or [{}]
    ligands = []
    for nonpolymer in entry.get("nonpolymer_entities") or []:
        component = ((nonpolymer.get("nonpolymer_comp") or {}).get("chem_comp") or {})
        code = component.get("id")
        if code and code not in COMMON_ADDITIVES:
            ligands.append(code)

    entities = entry.get("polymer_entities") or []
    uniprot_ids: list[str] = []
    mutations: list[str] = []
    for entity in entities:
        identifiers = entity.get("rcsb_polymer_entity_container_identifiers") or {}
        uniprot_ids.extend(identifiers.get("uniprot_ids") or [])
        mutation = (entity.get("rcsb_polymer_entity") or {}).get("pdbx_mutation")
        if mutation:
            mutations.append(mutation)

    modelled = info.get("deposited_polymer_monomer_count")
    unmodelled = info.get("deposited_unmodeled_polymer_monomer_count")
    return {
        "pdbId": entry.get("rcsb_id"),
        "method": "|".join(item.get("method", "") for item in entry.get("exptl") or []),
        "resolution": resolutions[0] if resolutions else None,
        "rFree": (refine[0] or {}).get("ls_R_factor_R_free"),
        "title": ((entry.get("struct") or {}).get("title") or "")[:110],
        "releaseYear": ((entry.get("rcsb_accession_info") or {}).get("initial_release_date") or "")[:4],
        "polymerEntities": info.get("polymer_entity_count"),
        "ligands": "|".join(sorted(dict.fromkeys(ligands))),
        "ligandCount": len(set(ligands)),
        "uniprotIds": "|".join(dict.fromkeys(uniprot_ids)),
        "mutations": "; ".join(mutations),
        # Residues in the construct that were never resolved: loops, termini,
        # and disordered regions. A high count is the usual reason a "2.0 A
        # structure" turns out to have a hole through the binding site.
        "unmodelledResidues": unmodelled,
        "modelledResidues": modelled,
    }


def report(args, total: int, results: list[dict], return_type: str) -> None:
    ids = [item["identifier"] for item in results]
    scores = {item["identifier"]: item.get("score") for item in results}

    entry_ids = [identifier.split("_")[0] for identifier in ids]
    print(f"# {total} hits; describing {len(ids)}", file=sys.stderr)
    entries = describe_entries(list(dict.fromkeys(entry_ids)))

    rows = []
    for identifier, entry_id in zip(ids, entry_ids):
        row = dict(entries.get(entry_id) or {"pdbId": entry_id})
        row["score"] = scores.get(identifier)
        if return_type == "polymer_entity":
            row["entityId"] = identifier
        rows.append(row)

    if args.max_resolution is not None:
        rows = [
            row
            for row in rows
            if row.get("resolution") is not None and row["resolution"] <= args.max_resolution
        ]
    if getattr(args, "has_ligand", False):
        rows = [row for row in rows if row.get("ligandCount")]
    if getattr(args, "exclude_mutants", False):
        rows = [row for row in rows if not (row.get("mutations") or "").strip()]

    rows.sort(key=lambda row: (row.get("resolution") is None, row.get("resolution") or 0))
    columns = (("entityId",) if return_type == "polymer_entity" else ()) + ENTRY_COLUMNS
    emit(rows, columns, args.output_format)


def command_uniprot(args) -> None:
    nodes = [
        attribute_node(
            "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers"
            ".database_accession",
            "exact_match",
            args.accession,
        ),
        attribute_node(
            "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers"
            ".database_name",
            "exact_match",
            "UniProt",
        ),
    ]
    if args.max_resolution is not None:
        nodes.append(
            attribute_node("rcsb_entry_info.resolution_combined", "less_or_equal", args.max_resolution)
        )
    total, results = run_search(group(nodes), return_type="polymer_entity", rows=args.limit)
    report(args, total, results, "polymer_entity")


def command_sequence(args) -> None:
    sequence = args.sequence
    if args.fasta:
        lines = Path(args.fasta).read_text(encoding="utf-8").splitlines()
        sequence = "".join(line.strip() for line in lines if not line.startswith(">"))
    if not sequence:
        raise ServiceError("sequence search needs a SEQUENCE argument or --fasta")
    if len(sequence) < 20:
        raise ServiceError("the sequence service requires at least 20 residues")

    query = terminal(
        "sequence",
        {
            "sequence_type": args.sequence_type,
            "value": sequence,
            "identity_cutoff": args.identity,
            "evalue_cutoff": args.evalue,
        },
    )
    total, results = run_search(query, return_type="polymer_entity", rows=args.limit)
    report(args, total, results, "polymer_entity")


def command_text(args) -> None:
    nodes = [terminal("full_text", {"value": args.query})]
    if args.max_resolution is not None:
        nodes.append(
            attribute_node("rcsb_entry_info.resolution_combined", "less_or_equal", args.max_resolution)
        )
    total, results = run_search(group(nodes), return_type="entry", rows=args.limit)
    report(args, total, results, "entry")


def command_ligand(args) -> None:
    # `chem_comp.id` is not searchable from the text service; the
    # nonpolymer-entity container identifier is the attribute that works.
    query = attribute_node(
        "rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id",
        "exact_match",
        args.component_id.upper(),
    )
    total, results = run_search(query, return_type="entry", rows=args.limit)
    report(args, total, results, "entry")


def command_attribute(args) -> None:
    value: object = args.value
    try:
        value = json.loads(args.value)
    except json.JSONDecodeError:
        pass
    query = attribute_node(args.attribute, args.operator, value)
    total, results = run_search(query, return_type=args.return_type, rows=args.limit)
    report(args, total, results, args.return_type)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def shared(sub, *, resolution=True, ligand=True):
        sub.add_argument("--limit", type=int, default=25, help="hits to describe (default: 25)")
        if resolution:
            sub.add_argument("--max-resolution", type=float, help="keep entries at or below this")
        else:
            sub.set_defaults(max_resolution=None)
        if ligand:
            sub.add_argument(
                "--has-ligand",
                action="store_true",
                help="keep only entries with a bound component that is not a buffer or ion",
            )
            sub.add_argument(
                "--exclude-mutants",
                action="store_true",
                help="drop entities with an engineered mutation",
            )
        add_common_arguments(sub)
        return sub

    uniprot = subparsers.add_parser("uniprot", help="structures for a UniProt accession")
    uniprot.add_argument("accession")
    shared(uniprot).set_defaults(handler=command_uniprot)

    sequence = subparsers.add_parser("sequence", help="MMseqs2 sequence similarity search")
    sequence.add_argument("sequence", nargs="?", help="raw sequence; or use --fasta")
    sequence.add_argument("--fasta", help="read the sequence from this FASTA file")
    sequence.add_argument(
        "--identity", type=float, default=0.9, help="identity cutoff 0-1 (default: 0.9)"
    )
    sequence.add_argument("--evalue", type=float, default=1.0, help="E-value cutoff (default: 1.0)")
    sequence.add_argument(
        "--sequence-type", choices=("protein", "dna", "rna"), default="protein"
    )
    shared(sequence).set_defaults(handler=command_sequence)

    text = subparsers.add_parser("text", help="full-text search")
    text.add_argument("query")
    shared(text).set_defaults(handler=command_text)

    ligand = subparsers.add_parser("ligand", help="entries containing a chemical component")
    ligand.add_argument("component_id", help="3-character CCD id, e.g. STI")
    shared(ligand).set_defaults(handler=command_ligand)

    attribute = subparsers.add_parser("attribute", help="raw attribute query")
    attribute.add_argument("attribute", help="e.g. rcsb_entry_info.resolution_combined")
    attribute.add_argument(
        "operator",
        help="exact_match, contains_phrase, greater, less, greater_or_equal, "
        "less_or_equal, range, exists, in",
    )
    attribute.add_argument("value", help="parsed as JSON when possible")
    attribute.add_argument(
        "--return-type",
        default="entry",
        choices=("entry", "polymer_entity", "assembly", "polymer_instance", "non_polymer_entity"),
    )
    shared(attribute).set_defaults(handler=command_attribute)

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
