---
name: primekg
description: Query the Precision Medicine Knowledge Graph (PrimeKG) for multiscale biological data including genes, drugs, diseases, phenotypes, and more.
license: Unknown
metadata:
  version: "1.2"
  skill-author: K-Dense Inc. (PrimeKG original from Harvard MIMS)
---

# PrimeKG Knowledge Graph Skill

## Overview

PrimeKG is a precision medicine knowledge graph that integrates over 20 primary databases and high-quality scientific literature into a single resource. It contains over 100,000 nodes and 4 million edges across 29 relationship types, including drug-target, disease-gene, and phenotype-disease associations.

**Key capabilities:**
- Search for nodes (genes, proteins, drugs, diseases, phenotypes)
- Retrieve direct neighbors (associated entities and clinical evidence)
- Analyze local disease context (related genes, drugs, phenotypes)
- Identify drug-disease paths (potential repurposing opportunities)

**Data access:** Programmatic access via `scripts/query_primekg.py`, which reads `kg.csv` from the
path in the `PRIMEKG_DATA` environment variable (default `data/PrimeKG/kg.csv`). Download the CSV
first — see [Data Path](#data-path).

## When to Use This Skill

This skill should be used when:

- **Knowledge-based drug discovery:** Identifying targets and mechanisms for diseases.
- **Drug repurposing:** Finding existing drugs that might have evidence for new indications.
- **Phenotype analysis:** Understanding how symptoms/phenotypes relate to diseases and genes.
- **Multiscale biology:** Bridging the gap between molecular targets (genes) and clinical outcomes (diseases).
- **Network pharmacology:** Investigating the broader network effects of drug-target interactions.

## Core Workflow

### 1. Search for Entities

Find identifiers for genes, drugs, or diseases.

```python
from scripts.query_primekg import search_nodes

# Search for Alzheimer's disease nodes
results = search_nodes("Alzheimer", node_type="disease")
# Returns: [{"id": "EFO_0000249", "type": "disease", "name": "Alzheimer's disease", ...}]
```

### 2. Get Neighbors (Direct Associations)

Retrieve all connected nodes and relationship types.

```python
from scripts.query_primekg import get_neighbors

# Get all neighbors of a specific disease ID
neighbors = get_neighbors("EFO_0000249")
# Returns: List of neighbors like {"neighbor_name": "APOE", "relation": "disease_gene", ...}
```

### 3. Analyze Disease Context

A high-level function to summarize associations for a disease.

```python
from scripts.query_primekg import get_disease_context

# Comprehensive summary for a disease
context = get_disease_context("Alzheimer's disease")
# Access: context['associated_genes'], context['associated_drugs'], context['phenotypes']
```

### 4. Connect Two Entities (Repurposing Hypotheses)

Find how a drug and a disease are linked, either directly or through one shared
intermediate node. Edges are traversed as undirected.

```python
from scripts.query_primekg import find_paths

# Direct edges first, then two-hop paths through a shared neighbour
paths = find_paths("CHEMBL1", "D001")            # max_depth=2 by default
paths = find_paths("CHEMBL1", "D001", max_depth=1)  # direct edges only

# Each path is a list of edge dicts, ordered start -> end:
# [{'relation': 'drug_protein', ...}, {'relation': 'disease_protein', ...}]
for hops in paths:
    print(" -> ".join(hop["display_relation"] for hop in hops))
```

Only depths 1 and 2 are supported; any other `max_depth` raises `ValueError`.
Three or more hops through a 4-million-edge graph run through hub nodes and are
rarely interpretable.

## Relationship Types in PrimeKG

The graph contains several key relationship types including:
- `protein_protein`: Physical PPIs
- `drug_protein`: Drug target/mechanism associations
- `disease_gene`: Genetic associations
- `drug_disease`: Indications and contraindications
- `disease_phenotype`: Clinical signs and symptoms
- `gwas`: Genome-wide association studies evidence

## Best Practices

1. **Use specific IDs:** When using `get_neighbors`, ensure you have the correct ID from `search_nodes`.
2. **Context first:** Use `get_disease_context` for a broad overview before diving into specific genes or drugs.
3. **Filter relationships:** Use the `relation_type` filter in `get_neighbors` to focus on specific evidence (e.g., only `drug_protein`).
4. **Multiscale integration:** Combine with `OpenTargets` for deeper genetic evidence or `Semantic Scholar` for the latest literature context.

## Resources

### Scripts
- `scripts/query_primekg.py`: Core functions for searching and querying the knowledge graph.

### Data Path
- Data: `kg.csv`, downloaded from the [PrimeKG Harvard Dataverse](https://dataverse.harvard.edu/dataverse/primekg).
- Point the scripts at it with `export PRIMEKG_DATA=/path/to/kg.csv` (default: `data/PrimeKG/kg.csv`).
- Total nodes: ~129,000
- Total edges: ~4,000,000
- Database: CSV-based, optimized for pandas querying.
