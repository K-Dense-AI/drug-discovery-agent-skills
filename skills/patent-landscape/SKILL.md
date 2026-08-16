---
name: patent-landscape
description: Find out whether a chemical series is already claimed, using SureChEMBL's patent-extracted compound corpus and, where a key is available, PatentsView for legal status and assignee history. Use this skill to trace a structure to the patent documents that disclose it, survey an assignee's filings around a target, and understand what the freedom-to-operate question requires that a structure search cannot answer. Also trigger on SureChEMBL, patent chemistry, Markush structure, freedom to operate, composition of matter, assignee, priority date, patent family, or PatentsView.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+ and outbound HTTPS access to ftp.ebi.ac.uk. SureChEMBL has no public REST API — the bundled scripts navigate its bulk FTP tree, which is large, so plan for disk. PatentsView lookup is optional and needs a free PATENTSVIEW_API_KEY. Nothing here is legal advice; a freedom-to-operate opinion requires a qualified attorney.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "📜"
    homepage: https://www.surechembl.org
    envVars:
      - name: PATENTSVIEW_API_KEY
        required: false
        description: Optional free PatentsView key for legal-status and assignee lookup.

  hermes:
    category: research
---

# Chemical Patent Landscape

Whether a series is already claimed decides whether it is worth pursuing, and the question comes
up long before anyone talks to an attorney. SureChEMBL extracts structures from patent full text,
images, and attachments — over 31 million compounds from the major offices — and it is the only
open, structure-searchable patent chemistry resource.

**Services:** `https://ftp.ebi.ac.uk/pub/databases/chembl/SureChEMBL` (bulk, no key) ·
`https://search.patentsview.org/api/v1` (optional, free key).
**Checked against:** the live bulk tree, August 2026 — 31 releases, newest 2026-08-04.

Read [references/surechembl-bulk.md](references/surechembl-bulk.md) before downloading anything,
[references/patent-data-sources.md](references/patent-data-sources.md) to know which source is
silent about what, and [references/reading-patents.md](references/reading-patents.md) before
drawing any conclusion — **that one is judgement, not syntax, and the gap it describes is wide.**

## The two scripts

| Script | Answers |
|---|---|
| `surechembl_bulk.py` | Which release, which tables, and how much disk? |
| `patent_search.py` | Who is filing in this space, in the US? |

## SureChEMBL has no REST API

Checked live: `surechembl.org/api/` and every plausible variant return 404. The website is
interactive-only, and everything programmatic goes through the EBI bulk tree.

```bash
python skills/patent-landscape/scripts/surechembl_bulk.py releases --limit 3
```

```
# 31 releases, newest 2026-08-04. Updated fortnightly.
release     url
2026-08-04  https://ftp.ebi.ac.uk/.../bulk_data/2026-08-04/
2026-07-17  ...
```

**Two directories hold different data.** `bulk_data/` is SureChEMBL 2.0 — Parquet plus an FPSim2
similarity index, fortnightly. `data/` is the legacy quarterly txt/SDF dump whose README is dated
2016. They are easily confused and the old one is much less useful.

**Pin a release.** Taking "latest" makes an analysis irreproducible against a corpus that changes
every two weeks.

## Plan the download; it is 15 GB

```bash
python skills/patent-landscape/scripts/surechembl_bulk.py plan --question structure-to-patent
```

```
# structure-to-patent: match a structure to compound ids, then to the documents disclosing it
# 3 table(s), 14.1 GB for release 2026-08-04
curl -O https://ftp.ebi.ac.uk/.../compounds.parquet           # 4.2 GB
curl -O https://ftp.ebi.ac.uk/.../patent_compound_map.parquet # 5.0 GB
curl -O https://ftp.ebi.ac.uk/.../patents.parquet             # 5.9 GB
```

A similarity search needs only `fpsim2_fingerprints.h5` (1.4 GB) and `compounds.parquet`. Query
the Parquet with DuckDB rather than pandas — it reads them in place without loading them.

## Where the compound was found is the legal signal

`patent_compound_map.parquet` records **which document field** each compound came from, and that
column carries almost all the meaning:

| Field | What it usually means |
|---|---|
| `claims` | the compound is claimed — the one that matters |
| `title` / `abstract` | a headline compound of the filing |
| `description` | disclosed: possibly prior art, a comparator, or a reagent |
| `image` | extracted from a drawing by OCSR, and sometimes wrong |

**Treating every extracted compound as "claimed by this patent" is the commonest misreading of
this dataset.** Only the claims define a monopoly.

## Markush claims are not enumerated

This is the limitation that matters most. Chemical patents claim a **genus** — a scaffold with
variable positions — and a single Markush claim can cover billions of compounds. SureChEMBL
extracts the specific examples, not the genus.

So no structure hit means *this exact structure was not disclosed as an example*. It does not mean
the structure falls outside every claim, and for a novel analogue of a known series the opposite
is usually true. Markush search is a specialist capability that Reaxys, SciFinder, and Derwent
implement and no free source does.

## Novelty and freedom to operate are different questions

**Novelty** — has this been disclosed before? — determines whether *you* can patent it. A
structure search genuinely helps.

**Freedom to operate** — can I sell this without infringing? — requires reading the claims of
every in-force patent in every jurisdiction you will sell in, construed against your product. A
structure search does not answer this and cannot.

They are independent: a compound can be novel and infringing, or old and non-infringing.

## The US-only half

```bash
python skills/patent-landscape/scripts/patent_search.py assignees --title "PROTAC"
```

Needs a free `PATENTSVIEW_API_KEY`. Note that **a missing key surfaces as a connection failure
rather than a 401**, so the obvious diagnosis is a network problem; the script checks explicitly.

Two coverage facts to carry: PatentsView is **US grants and pre-grant publications only** — no
EPO, WIPO, CNIPA, or JPO — and **assignee names are not normalised**, so "Merck", "Merck Sharp &
Dohme", and "Merck & Co., Inc." count as three companies.

## The 18-month blind spot

Applications publish 18 months after priority. **Everything filed in the last 18 months is
invisible in every source**, without exception. An empty landscape may mean nobody is working on
the target, or that everybody filed last year — and the second is common precisely for the targets
worth working on.

## Composing with the rest of the bundle

- `chembl` → here: SureChEMBL ids cross-reference through UniChem, joining patent chemistry to
  measured bioactivity.
- `chemical-space` → alongside: purchasable is a different question from unclaimed.
- `generative-design` → after: novelty of generated structures is a real use for this.
- `clinicaltrials` / `openfda` → alongside: filings, trials, and approvals are three views of the
  same competitive picture.

## Reporting results honestly

Name the source, its coverage, and the pinned release. Say which document field a compound was
found in. State that Markush claims are not enumerated and that the search under-reports coverage
for that reason. Note the 18-month lag. Give family counts rather than document counts where you
can.

Never write "this compound is free to use". Write "no exact structure match in SureChEMBL release
2026-08-04; this does not address Markush claims, unpublished applications, or claim construction,
and is not a freedom-to-operate assessment." Any decision with money attached needs a patent
attorney — this skill exists to tell you whether to go and ask one.
