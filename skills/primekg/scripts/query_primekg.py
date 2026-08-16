import pandas as pd
import os
from typing import List, Dict, Optional, Union

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
