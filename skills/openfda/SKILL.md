---
name: openfda
description: Query the FDA's public openFDA APIs for post-market drug data — FAERS adverse-event reports, Drugs@FDA approval and submission history, Structured Product Labels including boxed warnings, the National Drug Code directory, recall enforcement reports, and drug shortages. Use this skill to check what a regulator has already concluded about a molecule or its class, to date an approval and count its efficacy supplements, to read an approved indication or boxed warning, and to score a drug-event pair for disproportionate reporting with PRR, ROR, and chi-squared. Also trigger on openFDA, api.fda.gov, FAERS, Drugs@FDA, SPL, NDC, pharmacovigilance, boxed warning, adverse event report, drug recall, or safety signal.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+ and outbound HTTPS access to api.fda.gov. The bundled scripts use only the Python standard library. No key is needed, but the anonymous quota is 1000 requests/day; set OPENFDA_API_KEY (free, from open.fda.gov) to raise it to 120000/day. Data is public domain (CC0). FAERS publishes quarterly and lags by three months or more.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🏛️"
    homepage: https://open.fda.gov
    envVars:
      - name: OPENFDA_API_KEY
        required: false
        description: Free openFDA key; raises the daily quota from 1000 to 120000 requests.
  hermes:
    category: research
---

# openFDA

The FDA's own post-market record, served as a public REST API: 20.6 M adverse-event reports,
every drug application since 1939, and the full text of approved labels. It answers the question
that comes after the biology — *what has already happened to this molecule, or to its class, in
people* — and it is the cheapest safety evidence available anywhere.

**Base URL:** `https://api.fda.gov` — REST, no key required.
**Docs:** [open.fda.gov/apis](https://open.fda.gov/apis/) ·
[field reference](https://open.fda.gov/apis/drug/event/searchable-fields/)
**Checked against:** the live API, August 2026; FAERS data current to 2026-07-30.

Read [references/api-reference.md](references/api-reference.md) before writing a query by hand,
[references/endpoint-fields.md](references/endpoint-fields.md) before trusting a field name, and
[references/disproportionality.md](references/disproportionality.md) before reporting any signal
— **that one is judgement, not syntax.**

## The three scripts

| Script | Answers |
|---|---|
| `fda_adverse.py` | What has been reported against this drug, and is any of it disproportionate? |
| `fda_approvals.py` | When was it approved, by whom, and how many indications has it gained? |
| `fda_labels.py` | What does the approved label actually say? |

## Zero results arrive as HTTP 404

This is the single thing to get right. A search that matches nothing returns:

```
HTTP 404  {"error": {"code": "NOT_FOUND", "message": "No matches found!"}}
```

That is a *successful query with an empty result set*. Any client that treats non-200 as failure
turns "this drug has no reports" into a crash, and — worse — makes a typo indistinguishable from
a real zero, because **a misspelled field name also returns 404**. `get()` in
`scripts/_common.py` converts `NOT_FOUND` into an empty payload; when a count comes back empty,
check the field name against `references/endpoint-fields.md` before believing it.

The other two surprises: `limit` above 1000 returns **403 `API_KEY_MISSING`** (a key raises the
daily quota, not the per-request cap — lower `limit` instead), and `skip` is hard-capped at
**25000**, so a search matching 500 000 reports has 25 000 reachable records. Partition by
`receivedate` to go deeper.

## Adverse events

Rank what is reported, using a server-side aggregation rather than paging:

```bash
python skills/openfda/scripts/fda_adverse.py reactions --drug atorvastatin --top 6
```

```
# 518912 reports, top 6 reactions
reaction         reports  share_pct
FATIGUE          29506    5.69
NAUSEA           25700    4.95
DIARRHOEA        25358    4.89
DYSPNOEA         24427    4.71
DRUG INEFFECTIVE 24372    4.7
DIZZINESS        20872    4.02
```

Those are the generic complaints of a widely prescribed drug — the list is dominated by how many
people take it, not by what it does. To get pharmacology out of FAERS you need a comparator.

## Disproportionality

`signal` builds a 2x2 table from four separate totals and scores the pair:

```bash
python skills/openfda/scripts/fda_adverse.py signal --drug atorvastatin --reaction RHABDOMYOLYSIS
```

```
# 2x2: a=5713 b=513199 c=35397 d=20138381
a     b       c      d         prr    ror    ror_ci_low  ror_ci_high  chi2      signal
5713  513199  35397  20138381  6.275  6.333  6.158       6.514        21854.8   true
```

Statin-associated rhabdomyolysis — the toxicity that withdrew cerivastatin in 2001. Compare the
same drug against a background event:

```
# atorvastatin x ALOPECIA
5344  513568  193048  19980730  1.076  1.077  1.048  1.107  28.33  false
```

**This pair is why the rule is a conjunction of three tests** (`a ≥ 3`, `PRR ≥ 2`, `chi² ≥ 4`).
Alopecia's chi-squared is 28 — seven times the threshold — and on that statistic alone it would
be flagged. Its PRR of 1.08 says atorvastatin reports mention alopecia at the background rate.
The chi-squared is large only because N is 20 million.

Each `signal` run costs four requests against a 1000/day anonymous quota.

## Approvals

```bash
python skills/openfda/scripts/fda_approvals.py application --ingredient pembrolizumab
```

```
application_number  sponsor             brand_names    original_approval  submissions  efficacy_supplements
BLA125514           MERCK SHARP DOHME   KEYTRUDA       20140904           127          108
BLA761467           MERCK SHARP DOHME   KEYTRUDA QLEX  20250919           11           7
```

`efficacy_supplements` counts approved `SUPPL` submissions with class `EFFICACY` — roughly, how
many times the label gained an indication. It is the cheapest available measure of how far a drug
travelled beyond its first approval. `timeline --appno BLA125514 --type ORIG` shows that first
approval was a PRIORITY review of a Type 1 New Molecular Entity.

Only `submission_status: AP` is an approval; `CR` is a complete response letter — a rejection.

## Labels

```bash
python skills/openfda/scripts/fda_labels.py boxed --drug metformin --limit 5
python skills/openfda/scripts/fda_labels.py section --drug atorvastatin --section mechanism_of_action
python skills/openfda/scripts/fda_labels.py classes --drug apixaban
```

`classes` returns the Established Pharmacologic Class and mechanism annotations
(`Factor Xa Inhibitor [EPC]` / `Factor Xa Inhibitors [MoA]` for apixaban).

**Two traps.** Every manufacturer files its own SPL, so a generic drug has hundreds of
near-identical records and the scripts de-duplicate before showing text. And `openfda.*`
annotations are frequently missing entirely — checked live, every atorvastatin label examined
carried no `pharm_class_epc` at all, while pembrolizumab and apixaban carry them. Absence is a
property of that SPL, not of the drug. The same applies to `boxed_warning`: its absence from a
generic label is not evidence the drug has no boxed warning.

## Four ways this API misleads quietly

1. **A report is not a patient, and never an exposure.** FAERS counts submissions. A report
   naming five drugs appears under all five. Nothing here is an incidence or a risk.
2. **A drug search matches concomitant medications.** `drugcharacterization` is `1` suspect,
   `2` concomitant, `3` interacting. Without filtering, you are counting reports where the drug
   was merely present in the patient.
3. **Data lags by a quarter or more.** `meta.last_updated` was 2026-07-30 here. A drug approved
   in the last two quarters has essentially no FAERS data, so absence of signal means nothing.
4. **Notoriety drives reporting.** Publicity, litigation, and safety communications raise report
   counts with no change in biology. Disproportionality measures reporting behaviour.

## When to stop using the API

For anything beyond triage — shrinkage estimators (BCPNN, MGPS/EBGM), stratification by age and
sex, or multi-drug adjustment — download the quarterly FAERS extract instead. Those methods
estimate a prior across the whole contingency space at once and cannot be built from per-pair
queries. See [references/disproportionality.md](references/disproportionality.md).

## Composing with the rest of the bundle

- `chembl` → here: mechanisms and indications for an approved drug, then its real-world safety.
- `clinicaltrials` → alongside: what is being tested now, against what has already been approved.
- `open-targets` → here: the known drugs for a target, checked against their post-market record.
- `target-safety` → alongside: human genetic evidence for the same liability, before it is a drug.
- `pkpd-translation` → after: an approved label's dose and exposure as a translation anchor.

## Reporting results honestly

Quote `a` beside every ratio and give the ROR with its confidence interval — a PRR of 12 built on
four reports is noise. Name the data cut. Say "reports mention this event disproportionately",
never "the drug causes" or "the risk is". Nothing here is validated for clinical use, and the
API's own disclaimer says so.
