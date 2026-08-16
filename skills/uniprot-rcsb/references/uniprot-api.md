# UniProt REST API

Base: `https://rest.uniprot.org`. No key. Docs: <https://www.uniprot.org/help/api>,
return fields at <https://www.uniprot.org/help/return_fields>, query fields at
<https://www.uniprot.org/help/query-fields>.

## Endpoints

| Path | Purpose |
|---|---|
| `/uniprotkb/{accession}.json` | One entry, complete |
| `/uniprotkb/{accession}.fasta` | Sequence; add `?includeIsoform=true` for isoforms |
| `/uniprotkb/search?query=…` | Paged search, up to 500 per page |
| `/uniprotkb/stream?query=…` | The whole result set in one response, no paging |
| `/idmapping/run` (POST) | Start a cross-database mapping job |
| `/uniref/…`, `/uniparc/…`, `/proteomes/…` | Clusters, archive, proteomes |

Use `search` for up to a few thousand rows and `stream` beyond that — `stream` has no cursor
but is rate-limited more tightly and can time out on very large sets.

## Query syntax

Field-scoped terms joined with `AND` / `OR` / `NOT`, parenthesised freely:

```
gene:EGFR AND organism_id:9606 AND reviewed:true
(gene:EGFR OR gene:ERBB2) AND reviewed:true
family:"protein kinase superfamily" AND organism_id:9606 AND length:[300 TO 600]
accession:P00533
ec:2.7.10.1 AND reviewed:true
go:0004713 AND reviewed:true               # GO term by id, no "GO:" prefix
xref:pdb-1IEP
keyword:KW-0418                            # Kinase
cc_scl_term:SL-0039                        # Membrane
ft_binding:* AND reviewed:true
database:(type:pdb)                        # has at least one PDB structure
existence:1                                # evidence at protein level
fragment:false
```

**`reviewed:true` is the flag that matters most.** UniProtKB is about 0.5 % Swiss-Prot (manually
curated) and 99.5 % TrEMBL (automatic). A gene-name search without it returns fragments,
predicted isoforms, and assorted non-model organisms above the entry you wanted.

Ranges use `[low TO high]`, and `*` works as "has any value".

## Return fields

`fields=` takes a comma-separated list; the response only carries what you ask for.

| Field | Gives |
|---|---|
| `accession`, `id` | Accession (`P00533`) and entry name (`EGFR_HUMAN`) |
| `protein_name`, `gene_names`, `organism_name`, `organism_id` | Identity |
| `length`, `sequence`, `mass` | Sequence |
| `reviewed` | Swiss-Prot vs TrEMBL |
| `cc_function`, `cc_subcellular_location`, `cc_subunit`, `cc_ptm`, `cc_disease` | Comment blocks |
| `ft_binding`, `ft_act_site`, `ft_domain`, `ft_mutagen`, `ft_carbohyd`, `ft_disulfid`, `ft_var_seq`, `ft_transmem`, `ft_signal` | Positional features |
| `xref_pdb`, `xref_chembl`, `xref_alphafolddb`, `xref_ensembl`, `xref_refseq`, `xref_drugbank` | Cross-references |
| `go_f`, `go_p`, `go_c` | Gene Ontology by aspect |
| `ec`, `keyword`, `protein_families`, `cc_catalytic_activity` | Classification |

`format=` accepts `json`, `tsv`, `fasta`, `xml`, `list`, `gff`, `txt`. TSV is the easiest to
join with anything else; the column headers are human-readable labels, not the field names you
requested.

## Pagination lives in a header

`search` returns at most `size` results (max 500) and puts the next page in an **HTTP `Link`
header**:

```
link: <https://rest.uniprot.org/uniprotkb/search?...&cursor=88d67348niepj...&size=2>; rel="next"
```

There is no `next` key in the JSON body. A client that reads only the body silently stops at
the first page — the single most common way to under-count a UniProt search.
`scripts/_common.py:uniprot_pages` follows the header.

## Responses may be doubly gzipped

Send `Accept-Encoding: gzip` and some UniProt payloads come back gzip-wrapped **twice**: the
stored file is already gzip, and transport encoding is applied on top. `urllib` does not
decompress at all, so one round of `gzip.decompress` leaves bytes that still start with the
gzip magic, and the failure surfaces much later as `UnicodeDecodeError: invalid start byte` at
position 1. Loop on the magic bytes (bounded), or do not request gzip. `requests` handles the
outer layer for you but not the inner one.

## Feature records

`entry["features"]` is a flat list. Each item:

```json
{"type": "Binding site", "location": {"start": {"value": 745}, "end": {"value": 745}},
 "description": "", "ligand": {"name": "ATP", "id": "ChEBI:CHEBI:30616"},
 "evidences": [{"evidenceCode": "ECO:0000269", "source": "PubMed", "id": "12297049"}]}
```

`type` is a human-readable string (`Binding site`, `Active site`, `Mutagenesis`, `Natural
variant`, `Glycosylation`, `Disulfide bond`, `Domain`, `Transmembrane`, `Alternative
sequence`), not a code. Evidence codes repeat once per supporting publication — take the
distinct set. `ECO:0000269` is experimental, `ECO:0000255` is a sequence-analysis inference,
`ECO:0007744` is combinatorial evidence; the difference matters when a "binding site" turns out
to be a prediction.

**Numbering is 1-based over the canonical isoform.** A PDB structure's residue numbering usually
agrees for a single-domain construct and often does not for anything else — verify before
transferring positions.

## ID mapping

Asynchronous, three steps:

```bash
curl -X POST https://rest.uniprot.org/idmapping/run \
     -d "from=UniProtKB_AC-ID" -d "to=PDB" -d "ids=P00533,P04637"
# -> {"jobId": "uLqZrkqhmj"}
curl https://rest.uniprot.org/idmapping/status/uLqZrkqhmj
curl "https://rest.uniprot.org/idmapping/results/uLqZrkqhmj?size=500"
```

**The results path depends on the target database.** A UniProtKB target uses
`/idmapping/uniprotkb/results/{job}` and returns full entries; anything else uses
`/idmapping/results/{job}` and returns `{"from": …, "to": …}` pairs. Poll the wrong one and you
get rows containing only a `from` key — technically a success, semantically nothing.

Common database names: `UniProtKB_AC-ID`, `UniProtKB`, `UniProtKB-Swiss-Prot`, `PDB`,
`Ensembl`, `Ensembl_Protein`, `RefSeq_Protein`, `Gene_Name`, `GeneID` (Entrez), `ChEMBL`,
`DrugBank`, `PDB`, `AlphaFoldDB`, `STRING`, `KEGG`. The full list is at
<https://rest.uniprot.org/configure/idmapping/fields>.

Results paginate through the same `Link` header. Unmapped inputs come back under `failedIds`,
and inputs that mapped to nothing at all simply do not appear — check both.

## Isoforms

`P00533-1`, `P00533-2`, … are isoform accessions. The bare accession means the canonical
sequence. `?includeIsoform=true` on the FASTA endpoint returns all of them. Feature positions
are given against the canonical isoform, so an isoform sequence and the canonical feature table
do not line up.

## Related services

- **UniRef** (`/uniref/search?query=…`) — sequence clusters at 100/90/50 % identity. The right
  way to deduplicate a set of homologues before an alignment.
- **UniParc** (`/uniparc/…`) — the sequence archive, including obsolete records. Where to look
  when an accession disappeared.
- **Proteomes** (`/proteomes/search?query=…`) — per-organism reference proteomes.
