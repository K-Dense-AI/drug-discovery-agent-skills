#!/usr/bin/env python3
"""Query the Precision Medicine Knowledge Graph (PrimeKG) edge list.

Importable as a library (`search_nodes`, `get_neighbors`, `find_paths`,
`get_disease_context`) and runnable as a CLI:

    python query_primekg.py search Alzheimer --node-type disease
    python query_primekg.py neighbors EFO_0000249 --relation disease_protein
    python query_primekg.py context "Alzheimer's disease"
    python query_primekg.py paths CHEMBL1 D001 --max-depth 2

Reads `kg.csv` from $PRIMEKG_DATA (default `data/PrimeKG/kg.csv`). Output is
TSV by default, or JSON with --format json.
"""

import argparse
import json
import os
import sys
from typing import List, Dict, Optional, Union

import pandas as pd

# Where kg.csv lives. Override with the PRIMEKG_DATA environment variable, or
# by assigning to DATA_PATH before calling any query function.
DATA_PATH = os.environ.get("PRIMEKG_DATA", "data/PrimeKG/kg.csv")

# PrimeKG is ~4 million edges, so a re-read costs seconds and hundreds of MB.
# Every query function needs the whole edge list, and get_disease_context calls
# two of them, so the frame is cached and keyed on the file's identity: a
# caller that repoints DATA_PATH (or replaces the CSV) gets a fresh read, and
# repeated queries against one graph pay for the parse once.
_KG_CACHE: Dict[tuple, pd.DataFrame] = {}


def _load_kg() -> pd.DataFrame:
    """Load the knowledge graph, reusing the parsed frame across calls."""
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"PrimeKG data not found at {DATA_PATH}. Download kg.csv from "
            "https://dataverse.harvard.edu/dataverse/primekg and set "
            "PRIMEKG_DATA to its path."
        )
    stat = os.stat(DATA_PATH)
    key = (os.path.abspath(DATA_PATH), stat.st_mtime_ns, stat.st_size)
    cached = _KG_CACHE.get(key)
    if cached is None:
        cached = pd.read_csv(DATA_PATH, low_memory=True)
        # One graph at a time: holding several 4M-row frames would exhaust
        # memory long before the cache earned anything.
        _KG_CACHE.clear()
        _KG_CACHE[key] = cached
    return cached


def _ids_as_str(kg: pd.DataFrame, column: str) -> pd.Series:
    """PrimeKG mixes numeric gene ids with string disease ids in one column, so
    pandas reads it as object dtype. Compare as strings, always."""
    return kg[column].astype(str)


def search_nodes(name_query: str, node_type: Optional[str] = None) -> List[Dict]:
    """
    Search for nodes in PrimeKG by name and optionally type.

    Args:
        name_query: Substring to search for in node names, matched literally
            and case-insensitively (not a regular expression).
        node_type: Optional type of node (e.g., 'gene/protein', 'drug', 'disease').

    Returns:
        List of matching nodes with their metadata (at most 20).
    """
    kg = _load_kg()

    # Check both x and y columns for unique nodes
    x_nodes = kg[['x_id', 'x_type', 'x_name', 'x_source']].drop_duplicates()
    x_nodes.columns = ['id', 'type', 'name', 'source']

    y_nodes = kg[['y_id', 'y_type', 'y_name', 'y_source']].drop_duplicates()
    y_nodes.columns = ['id', 'type', 'name', 'source']

    nodes = pd.concat([x_nodes, y_nodes]).drop_duplicates()

    # regex=False: gene and drug names contain regex metacharacters ('BRCA1(2)',
    # 'PGE2 alpha'), which would otherwise either raise or silently match too much.
    mask = nodes['name'].str.contains(name_query, case=False, na=False, regex=False)
    if node_type:
        mask &= (nodes['type'] == node_type)

    results = nodes[mask].head(20).to_dict(orient='records')
    return results


def get_neighbors(node_id: Union[str, int], relation_type: Optional[str] = None) -> List[Dict]:
    """
    Get all direct neighbors of a specific node.

    Args:
        node_id: The ID of the node (e.g., NCBI Gene ID or ChEMBL ID).
        relation_type: Optional filter for specific relationship types.

    Returns:
        List of neighbors and the relationship metadata.
    """
    kg = _load_kg()
    node_id = str(node_id)

    mask_x = (_ids_as_str(kg, 'x_id') == node_id)
    mask_y = (_ids_as_str(kg, 'y_id') == node_id)

    if relation_type:
        mask_x &= (kg['relation'] == relation_type)
        mask_y &= (kg['relation'] == relation_type)

    neighbors_x = kg[mask_x][['relation', 'display_relation', 'y_id', 'y_type', 'y_name', 'y_source']]
    neighbors_x.columns = ['relation', 'display_relation', 'neighbor_id', 'neighbor_type', 'neighbor_name', 'neighbor_source']

    neighbors_y = kg[mask_y][['relation', 'display_relation', 'x_id', 'x_type', 'x_name', 'x_source']]
    neighbors_y.columns = ['relation', 'display_relation', 'neighbor_id', 'neighbor_type', 'neighbor_name', 'neighbor_source']

    results = pd.concat([neighbors_x, neighbors_y]).to_dict(orient='records')
    return results


def _incident_edges(kg: pd.DataFrame, node_id: str) -> pd.DataFrame:
    """Every edge with `node_id` on either side, plus the id of the other end.

    PrimeKG is undirected for query purposes -- a drug-protein edge is stored
    once, with the drug on whichever side the source database happened to use
    -- so a one-sided lookup silently misses half the graph.
    """
    x_ids = _ids_as_str(kg, 'x_id')
    y_ids = _ids_as_str(kg, 'y_id')
    incident = kg[(x_ids == node_id) | (y_ids == node_id)].copy()
    if incident.empty:
        incident['other_id'] = pd.Series(dtype=object)
        return incident
    incident['other_id'] = _ids_as_str(incident, 'y_id').where(
        _ids_as_str(incident, 'x_id') == node_id, _ids_as_str(incident, 'x_id')
    )
    return incident


def find_paths(start_node_id: str, end_node_id: str, max_depth: int = 2) -> List[List[Dict]]:
    """
    Find paths between two nodes (e.g., Drug to Disease) up to `max_depth` hops.

    Edges are traversed as undirected. Only depths 1 and 2 are supported --
    PrimeKG's ~4 million edges make an unbounded pandas BFS impractical, and
    three-hop paths through hub nodes are rarely interpretable anyway.

    Args:
        start_node_id: Id of the node to start from.
        end_node_id: Id of the node to reach.
        max_depth: 1 for direct edges only, 2 (default) to also return
            two-hop paths through a single intermediate node.

    Returns:
        A list of paths. Each path is a list of edge dicts, one per hop, in
        order from `start_node_id` to `end_node_id`. Direct edges are returned
        first; a pair connected directly also yields any two-hop paths.

    Raises:
        ValueError: if `max_depth` is not 1 or 2.
    """
    if max_depth not in (1, 2):
        raise ValueError(f"max_depth must be 1 or 2, got {max_depth}")

    kg = _load_kg()
    start_node_id = str(start_node_id)
    end_node_id = str(end_node_id)

    from_start = _incident_edges(kg, start_node_id)
    paths: List[List[Dict]] = []

    # Depth 1: a single edge joining the two nodes.
    direct = from_start[from_start['other_id'] == end_node_id]
    for _, row in direct.iterrows():
        paths.append([row.drop(labels='other_id').to_dict()])

    if max_depth < 2 or start_node_id == end_node_id:
        return paths

    # Depth 2: join the two frontiers on their shared intermediate node. Doing
    # it as a merge keeps the whole search to two passes over the edge list,
    # rather than one lookup per candidate intermediate.
    to_end = _incident_edges(kg, end_node_id)
    first_hops = from_start[
        (from_start['other_id'] != end_node_id)
        & (from_start['other_id'] != start_node_id)
    ]
    second_hops = to_end[
        (to_end['other_id'] != start_node_id) & (to_end['other_id'] != end_node_id)
    ]
    intermediates = set(first_hops['other_id']) & set(second_hops['other_id'])

    for intermediate in sorted(intermediates):
        for _, first in first_hops[first_hops['other_id'] == intermediate].iterrows():
            for _, second in second_hops[
                second_hops['other_id'] == intermediate
            ].iterrows():
                paths.append(
                    [
                        first.drop(labels='other_id').to_dict(),
                        second.drop(labels='other_id').to_dict(),
                    ]
                )

    return paths


def get_disease_context(disease_name: str) -> Dict:
    """
    Analyze the local graph around a disease: associated genes, drugs, and phenotypes.
    """
    results = search_nodes(disease_name, node_type='disease')
    if not results:
        return {"error": "Disease not found"}

    disease_id = results[0]['id']
    neighbors = get_neighbors(disease_id)

    summary = {
        "disease_info": results[0],
        "associated_genes": [n for n in neighbors if n['neighbor_type'] == 'gene/protein'],
        "associated_drugs": [n for n in neighbors if n['neighbor_type'] == 'drug'],
        "phenotypes": [n for n in neighbors if n['neighbor_type'] == 'phenotype'],
        "related_diseases": [n for n in neighbors if n['neighbor_type'] == 'disease']
    }
    return summary


# --- CLI -------------------------------------------------------------------
#
# The library functions above return dicts; everything below is presentation.
# Kept deliberately thin so importing this module costs nothing extra.


def _emit(rows: Union[List[Dict], Dict], fmt: str, columns: Optional[List[str]] = None) -> None:
    """Print records as TSV (default) or JSON."""
    if fmt == "json":
        print(json.dumps(rows, indent=2, default=str))
        return
    if isinstance(rows, dict):
        for key, value in rows.items():
            if isinstance(value, list):
                print(f"# {key}: {len(value)}")
            else:
                print(f"{key}\t{value}")
        return
    if not rows:
        print("# no rows", file=sys.stderr)
        return
    columns = columns or list(rows[0].keys())
    print("\t".join(columns))
    for row in rows:
        print("\t".join(str(row.get(c, "")) for c in columns))


def command_search(args: argparse.Namespace) -> None:
    _emit(search_nodes(args.query, node_type=args.node_type), args.format)


def command_neighbors(args: argparse.Namespace) -> None:
    _emit(get_neighbors(args.node_id, relation_type=args.relation), args.format)


def command_context(args: argparse.Namespace) -> None:
    context = get_disease_context(args.disease)
    if args.format == "json":
        print(json.dumps(context, indent=2, default=str))
        return
    if "error" in context:
        print(f"error: {context['error']}", file=sys.stderr)
        raise SystemExit(1)
    info = context["disease_info"]
    print(f"# {info.get('name')} ({info.get('id')})")
    for bucket in ("associated_genes", "associated_drugs", "phenotypes", "related_diseases"):
        entries = context[bucket]
        print(f"\n## {bucket} ({len(entries)})")
        for entry in entries[: args.limit]:
            print(f"{entry.get('neighbor_name')}\t{entry.get('display_relation', entry.get('relation'))}")


def command_paths(args: argparse.Namespace) -> None:
    paths = find_paths(args.start, args.end, max_depth=args.max_depth)
    if args.format == "json":
        print(json.dumps(paths, indent=2, default=str))
        return
    if not paths:
        print("# no paths found", file=sys.stderr)
        return
    print(f"# {len(paths)} path(s)")
    for hops in paths:
        print(" -> ".join(hop.get("display_relation", hop.get("relation", "?")) for hop in hops))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--format", choices=("tsv", "json"), default="tsv", help="output format (default: tsv)"
    )
    parser.add_argument(
        "--data",
        help="path to kg.csv; overrides $PRIMEKG_DATA for this run",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="find nodes by name substring")
    search.add_argument("query")
    search.add_argument("--node-type", help="restrict to one node type, e.g. disease, drug, gene/protein")
    search.set_defaults(handler=command_search)

    neighbors = subparsers.add_parser("neighbors", help="direct neighbours of a node id")
    neighbors.add_argument("node_id")
    neighbors.add_argument("--relation", help="restrict to one relation type, e.g. drug_protein")
    neighbors.set_defaults(handler=command_neighbors)

    context = subparsers.add_parser("context", help="genes, drugs and phenotypes around a disease")
    context.add_argument("disease")
    context.add_argument("--limit", type=int, default=25, help="rows per bucket (default: 25)")
    context.set_defaults(handler=command_context)

    paths = subparsers.add_parser("paths", help="direct or two-hop paths between two nodes")
    paths.add_argument("start")
    paths.add_argument("end")
    paths.add_argument("--max-depth", type=int, default=2, choices=(1, 2))
    paths.set_defaults(handler=command_paths)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.data:
        # Assigning the module global is the documented way to repoint the data
        # file; the read cache is keyed on the file's identity, so this is safe.
        global DATA_PATH
        DATA_PATH = args.data
    try:
        args.handler(args)
    except FileNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
