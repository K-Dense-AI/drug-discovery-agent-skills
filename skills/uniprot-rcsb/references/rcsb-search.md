# RCSB PDB — search and data APIs

Two different services, and every practical question needs both:

| Service | URL | Returns |
|---|---|---|
| Search | `https://search.rcsb.org/rcsbsearch/v2/query` (POST) | **Identifiers and scores only** |
| Data (REST) | `https://data.rcsb.org/rest/v1/core/...` | One record per request |
| Data (GraphQL) | `https://data.rcsb.org/graphql` (POST) | Many records, batched |
| Files | `https://files.rcsb.org/download/...` | Coordinates |

The search API does not return resolution, method, ligands, or organism. "Find EGFR structures
below 2.5 Å with an inhibitor bound" is therefore a search for ids followed by a data request
to describe them — which is what `scripts/rcsb_search.py` does.

## Search request

```json
{
  "query": { … },
  "return_type": "entry",
  "request_options": {
    "paginate": {"start": 0, "rows": 25},
    "results_content_type": ["experimental"],
    "scoring_strategy": "combined",
    "sort": [{"sort_by": "rcsb_entry_info.resolution_combined", "direction": "asc"}]
  }
}
```

- `return_type`: `entry`, `polymer_entity`, `non_polymer_entity`, `polymer_instance` (a chain),
  `assembly`, `mol_definition`. Identifiers take the shape of the return type — `1IEP`,
  `1IEP_1`, `1IEP.A`.
- `results_content_type`: `["experimental"]` for the PDB, `["computational"]` for
  AlphaFold/ESMFold models mirrored into RCSB, or both. **The default includes computational
  models**, so an unqualified search mixes predicted structures into what looks like a list of
  crystal structures. Always state it.
- `paginate.rows` maxes at 10,000 per request.

**No hits is `HTTP 204` with an empty body**, not a JSON document with an empty array.
`json.loads("")` raises, so a naive client reports a parse error where the answer is simply
"nothing matched".

## Query nodes

```json
{"type": "terminal", "service": "text",
 "parameters": {"attribute": "rcsb_entry_info.resolution_combined",
                "operator": "less_or_equal", "value": 2.5}}
```

```json
{"type": "group", "logical_operator": "and", "nodes": [ … ]}
```

Services: `text` (attribute queries), `full_text` (free text over the whole record),
`sequence` (MMseqs2), `seqmotif` (PROSITE/regex patterns), `structure` (shape similarity),
`chemical` (SMILES substructure/similarity over ligands), `strucmotif` (3D residue motifs).

Operators: `exact_match`, `in`, `contains_words`, `contains_phrase`, `exists`, `greater`,
`less`, `greater_or_equal`, `less_or_equal`, `range`, `equals`.

Not every attribute is searchable. `chem_comp.id` returns
`search is not enabled on [chem_comp.id] attribute` — use
`rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id` to find entries containing a
ligand. The searchable set is at <https://search.rcsb.org/structure-search-attributes.html>.

## Attributes worth memorising

| Attribute | Use |
|---|---|
| `rcsb_entry_info.resolution_combined` | Resolution, any method |
| `exptl.method` | `X-RAY DIFFRACTION`, `ELECTRON MICROSCOPY`, `SOLUTION NMR` |
| `rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession` | UniProt accession |
| `rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_name` | Pair with the above, value `UniProt` |
| `rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id` | Bound ligand by CCD id |
| `rcsb_entity_source_organism.taxonomy_lineage.name` | Source organism |
| `rcsb_entry_info.polymer_entity_count_protein` | Complex size |
| `rcsb_accession_info.initial_release_date` | Release date, for time-split benchmarks |
| `rcsb_polymer_entity.pdbx_mutation` | Engineered mutations |
| `refine.ls_R_factor_R_free` | R-free |
| `rcsb_binding_affinity.value` / `.type` | Deposited affinity (Kd/Ki/IC50) where available |

## Sequence search

```json
{"type": "terminal", "service": "sequence",
 "parameters": {"sequence_type": "protein", "value": "MTEYKLVVVGAGGVGKS…",
                "identity_cutoff": 0.9, "evalue_cutoff": 1}}
```

MMseqs2-backed. Minimum 20 residues (25 for nucleotides). `identity_cutoff` is a fraction, not
a percentage. Return `polymer_entity` — an `entry` return type collapses several matching
chains into one hit and loses which chain matched.

## Chemical search

```json
{"type": "terminal", "service": "chemical",
 "parameters": {"value": "CC(=O)Oc1ccccc1C(=O)O", "type": "descriptor",
                "descriptor_type": "SMILES", "match_type": "graph-relaxed"}}
```

`match_type`: `graph-exact`, `graph-relaxed`, `graph-relaxed-stereo`, `fingerprint-similarity`.
This searches the chemical component dictionary, so it finds *ligands in structures*, not
compounds in general.

## Data API

REST, one record per request:

```
/rest/v1/core/entry/{id}
/rest/v1/core/polymer_entity/{id}/{entity}
/rest/v1/core/nonpolymer_entity/{id}/{entity}
/rest/v1/core/polymer_entity_instance/{id}/{asym}
/rest/v1/core/assembly/{id}/{assembly}
/rest/v1/core/chemcomp/{comp_id}
/rest/v1/core/uniprot/{id}/{entity}
```

GraphQL, many records per request — this is the one to use when describing search results:

```graphql
query Describe($ids: [String!]!) {
  entries(entry_ids: $ids) {
    rcsb_id
    struct { title }
    exptl { method }
    refine { ls_R_factor_R_free }
    rcsb_entry_info {
      resolution_combined
      polymer_entity_count
      deposited_polymer_monomer_count
      deposited_unmodeled_polymer_monomer_count
    }
    polymer_entities {
      rcsb_polymer_entity { pdbx_description pdbx_mutation }
      rcsb_polymer_entity_container_identifiers { uniprot_ids auth_asym_ids }
    }
    nonpolymer_entities {
      nonpolymer_comp { chem_comp { id name formula_weight } }
    }
  }
}
```

Describing 25 hits is one request this way and roughly 60 through REST, because ligand
identities live on the non-polymer entities rather than on the entry.

Two useful fields hide in `rcsb_entry_info`: `deposited_unmodeled_polymer_monomer_count` is how
many construct residues were never resolved, and `deposited_polymer_monomer_count` is how many
were. Their ratio is a better usability signal than resolution alone.

There is **no `nonpolymer_bound_components`** field on the entry record; ligand codes come from
the non-polymer entities.

## File downloads

```
https://files.rcsb.org/download/1IEP.cif           mmCIF, always available
https://files.rcsb.org/download/1IEP.pdb           legacy PDB -- 404 for large entries
https://files.rcsb.org/download/1IEP-assembly1.cif biological assembly
https://files.rcsb.org/ligands/download/STI_ideal.sdf   idealised ligand conformer
https://files.rcsb.org/ligands/download/STI_model.sdf   as-deposited coordinates
```

Anything that overflows the 80-column fixed-width format — large complexes, most recent cryo-EM
entries, more than 62 chains or 99,999 atoms — exists **only** as mmCIF. Defaulting a pipeline
to `.pdb` works until it meets one of those and then 404s.

## Chemical component identifiers

Three-character (older) or five-character (since 2023) CCD codes: `STI` is imatinib, `ATP` is
ATP, `HOH` is water. The chemical component dictionary is at
`https://files.rcsb.org/ligands/download/{ID}_ideal.sdf` and through
`/rest/v1/core/chemcomp/{ID}`, which carries `SMILES`, `SMILES_stereo`, `InChI`, `InChIKey`,
formula, and formula weight.

Beware the additives: `SO4`, `GOL`, `EDO`, `PEG`, `MPD`, `DMS`, `ACT`, `MES`, `TRS`, and the
monatomic ions are crystallisation components, not ligands. Counting them as ligands makes
almost every crystal structure look holo.
