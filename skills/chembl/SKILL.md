---
name: chembl
description: Query the ChEMBL database web services for measured bioactivity data, compound records and calculated properties, targets, assays, mechanisms of action, drug indications and warnings. Use this skill to build curated SAR or QSAR datasets for a target, look compounds up by SMILES, InChIKey, name, or ChEMBL id, run similarity and substructure searches, and check what chemistry is already known against a protein. Also trigger when a query mentions ChEMBL ids (CHEMBL...), pChEMBL values, IC50/Ki/Kd/EC50 retrieval, assay confidence scores, or ebi.ac.uk/chembl.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+ and outbound HTTPS access to www.ebi.ac.uk. The bundled scripts use only the Python standard library and need no API key. ChEMBL data is CC BY-SA 3.0; bulk analyses beyond ~100k activities should use the FTP database dump rather than the API.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "⚗️"
    homepage: https://www.ebi.ac.uk/chembl/
  hermes:
    category: research
---

# ChEMBL

ChEMBL is the curated database of measured bioactivity from the medicinal-chemistry literature —
about 24.5 million activity values over 2.9 million compounds and 18,500 targets. It is where you
find out what has already been made against a target, how potent it was, and how much of that is
trustworthy.

**Base URL:** `https://www.ebi.ac.uk/chembl/api/data` — REST, no key.
**Docs:** [interactive schema](https://www.ebi.ac.uk/chembl/api/data/docs) ·
[ChEMBL home](https://www.ebi.ac.uk/chembl/)
**Checked against:** ChEMBL_37, released 2026-05-01.

Read [references/api-reference.md](references/api-reference.md) before writing a request by hand,
[references/data-curation.md](references/data-curation.md) before modelling anything you pull, and
[references/entity-fields.md](references/entity-fields.md) when you need to know what a field
means or what type it really is.

## The one thing to get right

Raw ChEMBL rows are not a dataset. `activity.json?target_chembl_id=CHEMBL203` returns everything
ever published against that id: censored `>` values, rows ChEMBL itself flags as wrong, assays
whose target assignment is a guess, mutant-protein assays, and the same compound measured eight
times across four papers. Modelling that directly is the most common way to produce a QSAR model
that scores well and predicts nothing.

`target_activities.py` applies the curation and prints the attrition:

```bash
python skills/chembl/scripts/target_activities.py --uniprot P00533 \
    --standard-type Ki --min-confidence 8 --out egfr_ki.tsv
```

```
# resolved P00533 -> CHEMBL203 (Epidermal growth factor receptor, SINGLE PROTEIN); 15 other ChEMBL target(s) share this component
# CHEMBL203 Ki assay_type=B: 538 activity rows
# fetching confidence scores for 78 assays
# input rows: 538
# dropped 23: potential_duplicate flag
# kept rows: 515
# warning: 78 molecule(s) have replicate pChEMBL values spanning >= 1.0 log units -- review before modelling
# wrote 321 rows to egfr_ki.tsv
```

```
molecule_chembl_id  pchembl_median  pchembl_spread  n_measurements  n_documents  inconsistent
CHEMBL4100860       10.26           0.52            2               1            false
CHEMBL3883534       9.85            0               1               1            false
CHEMBL3758502       9.22            1.00            5               1            true
```

515 measurements collapse to 321 molecules, 78 of which carry replicates that disagree by more
than a log unit. That last number is the one people skip.

The curation, and why each step exists:

| Step | Why |
|---|---|
| One `SINGLE PROTEIN` target | A UniProt accession maps to family and complex targets too; pooling them mixes "inhibits EGFR" with "inhibits something in that family" |
| One `standard_type` | IC50, Ki, Kd, EC50 are different physical quantities |
| `standard_relation = '='` | A `>` row means "inactive at the top dose", not a measurement |
| Drop `data_validity_comment` | ChEMBL's own flag for implausible or mis-converted values |
| Require `pchembl_value` | The one column where unit conversion is already done and checked |
| `confidence_score >= 8` | Below 5, the target assignment is inferred rather than stated |
| Median per molecule + spread | Replicates disagree; a compound with pIC50 5.1 and 8.9 has no median worth using |

Add `--list-targets` to see the target choices before committing, and `--raw` for one row per
measurement instead of per molecule.

## Compound lookup

```bash
python skills/chembl/scripts/compound_lookup.py id CHEMBL941 CHEMBL939
python skills/chembl/scripts/compound_lookup.py name imatinib
python skills/chembl/scripts/compound_lookup.py smiles "CC(=O)Oc1ccccc1C(=O)O"
python skills/chembl/scripts/compound_lookup.py inchikey BSYNRYMUTXBXSQ      # skeleton only
python skills/chembl/scripts/compound_lookup.py similar "CC(=O)Oc1ccccc1C(=O)O" --threshold 80
python skills/chembl/scripts/compound_lookup.py substructure "c1ccc2c(c1)ncnc2"
python skills/chembl/scripts/compound_lookup.py mechanism --target CHEMBL203
```

Structure searches put the query **in the URL path**, so a SMILES with `#`, `+`, `/`, or `\` must
be percent-encoded — unencoded, `#` truncates the URL at the fragment marker and you get a 404 or
the wrong molecule. The script encodes for you; a hand-written `curl` will not.

Exact lookup defaults to `flexmatch`, which is salt-, charge-, and tautomer-tolerant — usually
what "is this compound in ChEMBL?" means. `--exact` requires a byte-identical canonical SMILES
and will miss the parent of a hydrochloride salt.

## Anything else

```bash
python skills/chembl/scripts/chembl_query.py endpoints
python skills/chembl/scripts/chembl_query.py status
python skills/chembl/scripts/chembl_query.py count activity --filter target_chembl_id=CHEMBL203
python skills/chembl/scripts/chembl_query.py fetch drug_warning \
    --filter molecule_chembl_id=CHEMBL941
python skills/chembl/scripts/chembl_query.py fetch molecule \
    --filter molecule_properties__full_mwt__lte=300 --filter max_phase=4 \
    --limit 500 --out small_approved.tsv
```

Filters use Django-style lookups: `field__gte`, `field__in`, `field__isnull`, `field__icontains`,
`related__field`. Multiple filters AND together; there is no OR across fields.

## Four ways this API fails quietly

1. **`limit` caps at 1000 without saying so.** Ask for 2000, get 1000, with
   `page_meta.limit == 1000` and no error. Follow `page_meta.next`; the bundled `paged()` does.
2. **A lookup written with one underscore is read as a field name.** `pchembl_value_gte=8`
   filters nothing and returns the whole table. `parse_filters` rejects that spelling.
3. **Numbers are strings.** `"standard_value": "41.0"`, `"max_phase": "4.0"`. Sorting as text
   puts `"9"` above `"41"`. Convert on ingest.
4. **`molecule_structures` and `molecule_properties` are null for biologics** (`structure_type`
   `SEQ`). Guard the access or every antibody in your set crashes the loop.

Also current as of ChEMBL_37: the ChemAxon-derived properties (`cx_logp`, `cx_logd`,
`cx_most_apka`, `molecular_species`, `hba_lipinski`) **no longer exist**. Filtering on one now
returns 400. Compute logD and pKa yourself — `rowan` for macro-pKa, `rdkit` for approximations.

## When to stop using the API

Above roughly 10⁵ activities, page the FTP dump instead:
<https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/> ships Postgres, MySQL, SQLite, and
SDF. A whole-database question ("every kinase inhibitor under 400 Da with a measured Ki") is one
SQL query locally and tens of thousands of HTTP requests remotely.

The official `chembl_webresource_client` Python package is the other route. It is convenient, but
it hides paging behaviour and caches across releases; the scripts here stay standard-library only
so their behaviour is inspectable.

## Composing with the rest of the bundle

- `open-targets` — which targets are worth pulling chemistry for; its `clinical_precedence`
  evidence names the ChEMBL drugs.
- `medchem` / `rdkit` / `datamol` — standardise, deduplicate, and triage what you pulled. Do this
  before modelling: the same compound appears under several ChEMBL ids.
- `pytdc` — scaffold splits. A random split on ChEMBL data reports a fantasy R², because
  congeneric series from one paper land on both sides.
- `molfeat` / `deepchem` — featurisation and model fitting once the set is clean.
- `uniprot-rcsb` — the structure to dock the actives into.
- `chemical-space` — ChEMBL is what has been *measured*; ZINC-22 and Enamine REAL are what can
  be *bought*. Different questions, and a hit list needs both.
- `patent-landscape` — SureChEMBL ids cross-reference through UniChem, joining measured
  bioactivity to patent chemistry.
- `clinicaltrials` / `openfda` — what happened to these compounds after the assay.

For bioassay coverage far wider than ChEMBL's curated set, PubChem's PUG-REST is the
complement — many more assays, much less curation, 5 requests/second and a 30-second timeout.

## Reporting results honestly

Say the release (`ChEMBL_37`), the target id and type, the measurement type, and the filters you
applied. Report how many rows you started from and how many survived — a pipeline that loses
nothing has not filtered. Absence of data in ChEMBL means nobody published it in an indexed
journal, not that a compound is inactive.
