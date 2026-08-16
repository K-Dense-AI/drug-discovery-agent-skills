# Where patent data comes from

No single source covers everything. Knowing which one is silent about what is most of the skill.

## The sources

| Source | Covers | Access | Chemistry |
|---|---|---|---|
| **SureChEMBL** | structures from major offices | bulk Parquet, no key | yes — 31M+ compounds |
| **PatentsView** | US grants and pre-grant publications | REST, **free key** | no |
| **EPO OPS** | worldwide bibliographic, EP full text | REST, OAuth key | no |
| **Espacenet** | 140M+ documents worldwide | web, limited API | no |
| **Google Patents / BigQuery** | worldwide full text | BigQuery, GCP billing | some annotations |
| **The Lens** | worldwide, links to literature | web + API, free tier | via linked data |
| **USPTO PatFT / Patent Public Search** | US full text | web, bulk downloads | no |
| **WIPO PATENTSCOPE** | PCT applications | web | no |
| **Reaxys, SciFinder, Derwent, Orbit** | curated worldwide | commercial | expert-curated |

Two things follow. **Chemical structure search and legal-status data live in different places** —
SureChEMBL has the structures and no legal status; PatentsView and EPO OPS have the metadata and
no chemistry. Joining them is manual.

And **the commercial sources are curated by people.** Derwent's abstracts and Reaxys's Markush
handling do work no automated pipeline does. If patents matter to a decision, that is what an
information professional will use.

## PatentsView specifics

Free API key from <https://patentsview.org/apis>, sent as `X-Api-Key`.

**A missing key surfaces as a connection failure, not a 401** — the request never completes a
handshake — so the obvious diagnosis is a network problem. `patent_search.py` checks for the key
explicitly and says so.

The query language is nested JSON, url-encoded into `q`:

```json
{"_and": [{"_text_any": {"patent_title": "kinase inhibitor"}},
          {"_gte": {"patent_date": "2020-01-01"}}]}
```

Operators: `_eq`, `_neq`, `_gt`, `_gte`, `_lt`, `_lte`, `_begins`, `_contains`, `_text_any`,
`_text_all`, `_text_phrase`, `_and`, `_or`, `_not`.

**Coverage is US only.** No EPO, WIPO, CNIPA, or JPO. A molecule with no US filing is invisible,
and given that CNIPA is now the largest patent office in the world by volume, that is a large
blind spot for any global landscape.

**Assignee names are not normalised.** "Merck", "Merck Sharp & Dohme", "Merck & Co., Inc.", and
"MSD" are distinct strings. A naive count by assignee splits one company's portfolio across rows,
and `patent_search.py assignees` says so rather than pretending otherwise. Normalising properly
needs a name-resolution step against something like GLEIF or a hand-built alias table.

## EPO Open Patent Services

`https://ops.epo.org/3.2/`, OAuth2, free tier with a weekly volume allowance. Returns 403 without
credentials, which is at least honest.

The best free source for **worldwide bibliographic data, patent families, and legal status** —
which is the information PatentsView lacks. Family data matters especially: one invention filed in
fifteen countries is one family, and counting the members as separate patents inflates a
landscape by an order of magnitude.

Not covered by the bundled scripts, because it needs OAuth and a registered application.

## Google Patents on BigQuery

`patents-public-data` in BigQuery. Worldwide full text, with some chemical annotations, queryable
in SQL at scale. Needs a GCP project and billing, and a broad query over the full-text tables can
be genuinely expensive — check the byte estimate before running.

The best option for large-scale text analysis if you already have GCP.

## Choosing

- **"Has this structure been disclosed?"** → SureChEMBL. Free, and the only structure-searchable
  open source.
- **"Who is filing in this space, in the US?"** → PatentsView.
- **"What is the worldwide family and legal status?"** → EPO OPS or Espacenet.
- **"Large-scale full-text mining"** → Google Patents on BigQuery.
- **"A decision with money attached"** → a patent attorney with a commercial database.

## The 18-month blind spot

Patent applications publish 18 months after their priority date. **Everything filed in the last 18
months is invisible in every source above**, without exception.

For a fast-moving target this is the dominant limitation. An empty landscape may mean nobody is
working on it, or it may mean everybody filed last year and nothing has published yet. There is no
way to tell from the data, and the second is common precisely for the targets worth working on.
