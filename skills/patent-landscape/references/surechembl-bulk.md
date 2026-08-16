# The SureChEMBL bulk tree

SureChEMBL extracts chemical structures from patent full text, images, and attachments by an
automated pipeline, and holds **over 31 million patent-derived compounds** from the major patent
offices. CC BY-SA 3.0, with attribution required.

## There is no public REST API

Checked live in August 2026: `https://www.surechembl.org/api/` and every plausible variant return
404. The website is interactive-only. **Everything programmatic goes through the EBI bulk tree:**

```
https://ftp.ebi.ac.uk/pub/databases/chembl/SureChEMBL/
├── bulk_data/          SureChEMBL 2.0 -- Parquet, released fortnightly
│   ├── 2026-08-04/
│   ├── 2026-07-17/
│   └── ... (31 dated releases)
└── data/               legacy quarterly txt + SDF dump, README dated 2016
```

**The two directories are different data.** `data/` is the old minimally-filtered dump (release 8,
last README April 2016) in `SureChEMBL_YYYYMMDD_N.txt.gz` / `.sdf.gz` files. `bulk_data/` is the
current 2.0 rebuild. Confusing them is easy and the older one is much less useful.

## A 2.0 release

Live sizes from release 2026-08-04:

| File | Size | Holds |
|---|---|---|
| `patents.parquet` | 5.9 GB | one row per document: id, title, dates, classifications |
| `patent_compound_map.parquet` | 5.0 GB | the join, **with the document field each compound came from** |
| `compounds.parquet` | 4.2 GB | one row per compound: id, SMILES, InChI, InChIKey |
| `fpsim2_fingerprints.h5` | 1.4 GB | an FPSim2 index for local similarity search |
| `biomedical_entities.parquet` | 30 MB | recognised genes, proteins, diseases |
| `biomedical_locations.parquet` | — | where in the document each entity occurred |
| `biomedical_types.parquet` | — | the entity type vocabulary |
| `fields.parquet` | small | the document-field vocabulary |

About 15 GB for the three main tables. `surechembl_bulk.py plan` reports which ones a given
question needs, so you do not pull all of it to answer one lookup.

**Pin a release.** Taking "latest" makes an analysis irreproducible, because the corpus changes
fortnightly.

## `patent_compound_map` is the interesting table

`compounds` and `patents` are just entities. The mapping carries **which field of the document a
compound was extracted from** — and that distinction is the whole legal signal:

| Field | What it usually means |
|---|---|
| `claims` | the compound is claimed. This is the one that matters |
| `title` / `abstract` | a headline compound of the filing |
| `description` | disclosed — possibly as prior art, a comparator, or a reagent |
| `image` | extracted from a structure drawing by OCSR |
| `attachment` | from supplementary material |

A compound appearing only in the description may be a competitor's molecule cited as prior art, a
solvent, or a starting material. Treating every extracted compound as "claimed by this patent" is
the most common misreading of this dataset.

## Querying it

The tables are far too large for pandas on a laptop, and exactly the right size for DuckDB, which
reads Parquet directly without loading it:

```sql
-- documents disclosing a given InChIKey, and where in the document
SELECT p.patent_id, p.title, m.field
FROM 'patent_compound_map.parquet' m
JOIN 'compounds.parquet'  c ON c.compound_id = m.compound_id
JOIN 'patents.parquet'    p ON p.patent_id   = m.patent_id
WHERE c.inchikey = 'BSYNRYMUTXBXSQ-UHFFFAOYSA-N';
```

DuckDB will push the filter into the Parquet scan and read only the relevant row groups, so this
is fast even against 5 GB files.

For **similarity search**, use the shipped FPSim2 index rather than computing fingerprints:

```python
from FPSim2 import FPSim2Engine
engine = FPSim2Engine("fpsim2_fingerprints.h5")
results = engine.similarity("CC(=O)Oc1ccccc1C(=O)O", 0.7, n_workers=4)
```

That is the intended route from "here is my structure" to "here are the patents", and it is why
the index ships with the release.

## Identifiers

SureChEMBL compound ids look like `SCHEMBL12345`. They cross-reference into ChEMBL and PubChem
through **UniChem**, which is the bridge from a patent compound back to bioactivity data — and
therefore the join between this skill and `chembl`.

Patent identifiers follow the office convention: `US-9999999-B2`, `EP-1234567-A1`,
`WO-2020123456-A1`. The kind code matters — `A` is an application, `B` a grant.

## Coverage and its limits

Structures come from an **automated pipeline**, with the consequences you would expect:

- **OCSR errors.** Structures extracted from images are wrong some of the time, particularly for
  poor scans and complex stereochemistry.
- **Markush structures are not enumerated.** A patent claiming a generic scaffold with variable
  substituents may yield only the specific examples. **This is the single biggest gap for
  freedom-to-operate work**, because the Markush claim is usually what has legal force.
- **Text-mining noise.** Reagents, solvents, and prior-art compounds are extracted alongside the
  subject matter.
- **Lag.** Extraction follows publication, which itself follows filing by 18 months.

So SureChEMBL answers "has this structure been disclosed in a patent" reasonably well, and
"is this structure covered by a claim" not at all.

## Licence

CC BY-SA 3.0. Attribution must name <https://www.surechembl.org/> and be visible in any resource
that integrates the data. Note the ShareAlike term if you redistribute derivatives.
