---
name: primekg
description: Query the Precision Medicine Knowledge Graph (PrimeKG) for multiscale biological relationships across genes and proteins, drugs, diseases, phenotypes, pathways, biological processes, exposures and anatomy. Use this skill to search entities by name, pull direct neighbours and their evidence types, summarise the local network around a disease, and find direct or two-hop drug-disease connections for repurposing hypotheses. Also trigger on PrimeKG, kg.csv, Harvard Dataverse knowledge graph, disease_protein, drug_protein, indication and contraindication edges, or network pharmacology over a biomedical knowledge graph.
license: MIT
compatibility: Requires Python 3.10+ with pandas. Needs the PrimeKG edge list (kg.csv, roughly 4 million rows and several hundred MB) downloaded from Harvard Dataverse and pointed at with the PRIMEKG_DATA environment variable. No network access at query time; the whole graph is read into memory, so budget a few GB of RAM.
allowed-tools: Read Write Edit Bash
metadata:
  version: "1.3"
  skill-author: K-Dense Inc. (PrimeKG original from Harvard MIMS)
---

# PrimeKG Knowledge Graph Skill

## Overview

PrimeKG is a precision medicine knowledge graph that integrates 20 high-quality primary resources
into a single edge list. It describes 17,080 diseases with **4,050,249 relationships** across ten
major biological scales — drug-target, disease-gene, phenotype-disease, pathway and anatomical
associations among them — over roughly 129,000 nodes.

Its distinguishing feature is drug-disease coverage: PrimeKG carries *indication*,
*contraindication*, and *off-label use* edges that most disease knowledge graphs lack, which is
what makes repurposing questions answerable here rather than merely askable.

**Cite:** Chandak P, Huang K, Zitnik M. *Building a knowledge graph to enable precision medicine.*
Sci Data 10, 67 (2023). PMID 36732524.

**Key capabilities:**
- Search for nodes (genes, proteins, drugs, diseases, phenotypes)
- Retrieve direct neighbors (associated entities and clinical evidence)
- Analyze local disease context (related genes, drugs, phenotypes)
- Identify drug-disease paths (potential repurposing opportunities)

**Data access:** `scripts/query_primekg.py` reads `kg.csv` from the path in the `PRIMEKG_DATA`
environment variable (default `data/PrimeKG/kg.csv`). Download the CSV first — see
[Data Path](#data-path). The script works as a CLI or as an importable module:

```bash
python skills/primekg/scripts/query_primekg.py search Alzheimer --node-type disease
python skills/primekg/scripts/query_primekg.py neighbors EFO_0000249 --relation disease_protein
python skills/primekg/scripts/query_primekg.py context "Alzheimer's disease"
python skills/primekg/scripts/query_primekg.py paths CHEMBL1 D001 --max-depth 2
```

Add `--format json` for machine-readable output, or `--data /path/to/kg.csv` to override
`PRIMEKG_DATA` for one run. Every subcommand exits non-zero when the data file is missing.

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
import sys
sys.path.insert(0, "skills/primekg/scripts")   # scripts/ is not a package
from query_primekg import search_nodes

# Search for Alzheimer's disease nodes
results = search_nodes("Alzheimer", node_type="disease")
# Returns: [{"id": "EFO_0000249", "type": "disease", "name": "Alzheimer's disease", ...}]
```

### 2. Get Neighbors (Direct Associations)

Retrieve all connected nodes and relationship types.

```python
from query_primekg import get_neighbors

# Get all neighbors of a specific disease ID
neighbors = get_neighbors("EFO_0000249")
# Returns: List of neighbors like {"neighbor_name": "APOE", "relation": "disease_gene", ...}
```

### 3. Analyze Disease Context

A high-level function to summarize associations for a disease.

```python
from query_primekg import get_disease_context

# Comprehensive summary for a disease
context = get_disease_context("Alzheimer's disease")
# Access: context['associated_genes'], context['associated_drugs'], context['phenotypes']
```

### 4. Connect Two Entities (Repurposing Hypotheses)

Find how a drug and a disease are linked, either directly or through one shared
intermediate node. Edges are traversed as undirected.

```python
from query_primekg import find_paths

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
4. **Multiscale integration:** see Composing below — PrimeKG asserts that a relationship exists,
   not how strong the evidence is. Pair it with a scored source before acting.

## Composing with the rest of the bundle

- `open-targets` → alongside: PrimeKG tells you an edge *exists*; Open Targets scores how strong
  the evidence is and names the datatype behind it. A PrimeKG `disease_protein` edge and an Open
  Targets association driven only by `literature` are the same claim at different resolutions.
- `ncats-arax` → instead, when provenance matters: ARAX returns Biolink-typed relationships with
  source attribution per edge. PrimeKG gives you the graph but not the citation for each edge.
- `target-safety` → after: a `disease_protein` edge says nothing about whether inhibiting the
  protein is tolerated. gnomAD constraint does.
- `depmap` → after: whether the gene is actually required in cells, not merely associated.
- `chembl` → after: what has been made against a protein this graph implicates.
- `clinicaltrials` → after: PrimeKG's indication and off-label edges are a hypothesis generator;
  the registry says whether anyone has tested it.

**Two-hop paths are hypotheses, not evidence.** Traversal through a hub node connects almost
anything to almost anything — read the intermediate node before believing the path.

## Resources

### Scripts
- `scripts/query_primekg.py`: search, neighbours, disease context and path finding, usable as a
  CLI or as an importable module.

### Data Path
- Data: `kg.csv`, downloaded from the [PrimeKG Harvard Dataverse](https://dataverse.harvard.edu/dataverse/primekg).
- Point the scripts at it with `export PRIMEKG_DATA=/path/to/kg.csv` (default: `data/PrimeKG/kg.csv`).
- Total nodes: ~129,000
- Total edges: ~4,000,000
- Database: CSV-based, optimized for pandas querying.
