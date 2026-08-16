# GWAS Catalog REST API v2

Base URL `https://www.ebi.ac.uk/gwas/rest/api/v2`. No key. Behaviour below verified live in
August 2026.

## The failure that matters most: silently ignored filters

```
GET /associations?mappedGene=LRRK2&size=1   ->  totalElements: 93
GET /associations?gene=LRRK2&size=1         ->  totalElements: 1142122
```

Both return HTTP 200. The second is the **entire catalogue** — the `gene` parameter does not
exist, so it was dropped, and nothing in the response says so. There is no error, no warning, and
no echo of the applied filters. A script that pages this and reports "1.1 M associations for
LRRK2" looks like it worked.

The correct parameter is `mappedGene`. `gwas_get()` in `scripts/_common.py` validates parameter
names against a known set and refuses anything else, because local validation is the only defence.

Known-good association parameters: `mappedGene`, `efoTrait`, `reportedTrait`, `accessionId`,
`rsId`, `page`, `size`, `sort`.

## Endpoints

| Path | Returns |
|---|---|
| `/associations` | variant–trait associations (filterable) |
| `/associations/{id}` | one association |
| `/genes/{symbol}` | gene metadata: location, biotype, Ensembl and Entrez ids |
| `/single-nucleotide-polymorphisms/{rsId}` | variant record |
| `/studies` | studies, filterable by accession, trait, publication |
| `/efo-traits` | the EFO trait vocabulary |

Note that `/genes/{symbol}/associations` **does not exist** (404) — the gene-scoped route is a
filter on `/associations`, not a sub-resource.

## Pagination

HAL-style, offset-based, unlike ClinicalTrials.gov:

```json
{"_embedded": {"associations": [...]},
 "page": {"size": 3, "totalElements": 93, "totalPages": 31, "number": 0}}
```

Records live under `_embedded.<collection>`; the collection key is plural and matches the
endpoint. Walk with `page=0,1,2...` until `page.number >= page.totalPages`.

**The service is slow** — six to ten seconds for one page is normal. The timeout in `_common.py`
is 120 s deliberately, and broad walks should be bounded with `--limit`.

## The association record

```json
{"association_id": 218958492,
 "p_value": 3.0e-08, "pvalue_mantissa": 3, "pvalue_exponent": -8,
 "beta": "-", "range": "-", "risk_frequency": "NR",
 "efo_traits": [{"efo_id": "EFO_0010819", "efo_trait": "clonal hematopoiesis"}],
 "reported_trait": ["Passenger-approximated clonal expansion rate ..."],
 "accession_id": "GCST90841394",
 "locations": ["14:95713905"],
 "mapped_genes": ["TCL1A"],
 "pubmed_id": "38714703", "first_author": "Pershad Y"}
```

`efo_traits` is the ontology-normalised trait and is what to group on. `reported_trait` is the
author's free text and is far messier. `beta` and `risk_frequency` are frequently `"-"` or
`"NR"` — treat them as missing, not zero.

## `mapped_genes` is positional, not causal

This is the second big trap. Variants are mapped to the **nearest** gene or genes, so an
association listed under a gene may act through a neighbour, an enhancer, or a long non-coding
RNA. LRRK2 associations carry `["LRRK2", "LINC02471", "LRRK2-DT"]` and `["LRRK2", "MUC19"]`.

The scripts report `gene_is_sole_mapping` for exactly this reason. Live, for LRRK2:

```
trait                      best_p    associations  studies  sole_mapping
bone density               1e-300    1             1        0
Parkinson disease          4e-148    23            18       18
cathepsin L1 measurement   4e-39     2             2        0
```

The strongest p-value in the table — bone density at 1e-300 — has **zero** sole mappings, so the
causal gene at that locus is probably not LRRK2. Parkinson disease at 4e-148 has 18 associations
mapping to LRRK2 alone across 18 studies. That is the real signal, and ranking by p-value alone
would have picked the wrong one.

Fine-mapping, colocalisation with eQTL data, and locus-to-gene scoring exist to resolve this.
None of them are in this API; `open-targets` carries an L2G score that does some of the work.

## Significance and counting

Genome-wide significance is **5 × 10⁻⁸** (Bonferroni over roughly a million independent common
variants). The catalogue includes weaker entries, so filter deliberately — `--significant-only`
on `gwas_evidence.py gene`.

**Do not rank by association count.** The same locus is rediscovered by every new cohort, so a
count measures how often a region has been genotyped, not how strong the effect is. Rank by best
p-value and report the number of independent studies alongside.

Also note that p-value magnitude scales with sample size, so a 1e-300 in a million-person
biobank and a 1e-9 in a 5000-person study are not comparable as effect sizes. If you need effect
size, use `beta` or the odds ratio, when present.

## Ancestry

The catalogue is overwhelmingly European-ancestry. An association absent for a gene may be absent
because nobody has powered a study in the relevant population, and effect sizes do not always
transfer. `/studies` carries ancestry metadata when this matters.

## Licence

EMBL-EBI, freely available. Cite the catalogue and the underlying publication (`pubmed_id`).
