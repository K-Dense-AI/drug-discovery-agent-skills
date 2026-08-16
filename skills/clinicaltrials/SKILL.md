---
name: clinicaltrials
description: Search the ClinicalTrials.gov registry through its version 2 REST API for interventional and observational studies, their phases, enrolment, endpoints, sponsors, and posted results. Use this skill to survey who is developing what against an indication, date a competitor's programme, read primary and secondary outcome measures, find eligibility criteria, and distinguish a study that completed from one that was terminated or withdrawn. Also trigger on ClinicalTrials.gov, NCT number, trial registry, study phase, enrolment, primary outcome measure, recruiting status, trial sponsor, or competitive landscape.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+ and outbound HTTPS access to clinicaltrials.gov. The bundled client uses only the Python standard library and needs no API key or account. The version 2 API replaced the retired classic API in June 2024. Registry entries are sponsor-submitted and are not independently verified.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🧾"
    homepage: https://clinicaltrials.gov/data-api/api
  hermes:
    category: research
---

# ClinicalTrials.gov

The world's largest trial registry: roughly 560 000 studies, sponsor-submitted, going back to
2000. It answers the question that no bench assay can — *has anyone already tried this in
people, and what happened to them when they did.* For a target or an indication it is the
cheapest competitive and feasibility intelligence available.

**Base URL:** `https://clinicaltrials.gov/api/v2` — REST, no key.
**Docs:** [data-api](https://clinicaltrials.gov/data-api/api) ·
[search areas](https://clinicaltrials.gov/data-api/about-api/search-areas)
**Checked against:** the live v2 API, August 2026. The classic API was retired in June 2024.

Read [references/api-reference.md](references/api-reference.md) before writing a query by hand,
[references/study-structure.md](references/study-structure.md) before reaching for a field, and
[references/reading-a-registry.md](references/reading-a-registry.md) before drawing a conclusion
from anything you find — **that one is judgement, not syntax.**

## The three scripts

| Script | Answers |
|---|---|
| `ct_search.py` | What is registered against this condition or drug, and how much of it? |
| `ct_study.py` | What exactly did this one study set out to do? |
| `ct_landscape.py` | Who else is in this indication, and what stops trials here? |

## COMPLETED does not mean it worked

This is the single thing to get right. `overallStatus: COMPLETED` means the study finished
running. It says nothing about whether the intervention succeeded — a trial that comprehensively
missed its primary endpoint completes normally.

Three separate facts, routinely conflated:

| | Means |
|---|---|
| `overallStatus: COMPLETED` | the study finished |
| `hasResults: true` | results were posted to the registry |
| whether the endpoint was met | **not recorded in the registry at all** |

`hasResults` is a top-level sibling of `protocolSection`, not part of the status module, and it is
the easiest useful field to miss. `ct_study.py show` prints a warning when a study completed
without posting results.

## Searching

```bash
python skills/clinicaltrials/scripts/ct_search.py search \
    --condition "non-small cell lung cancer" --phase PHASE3 --limit 3
```

```
# 1019 studies match
nct_id       status      phase   enrollment  sponsor                    start       has_results
NCT06357533  RECRUITING  PHASE3  675         AstraZeneca                2024-04-11  false
NCT05278052  RECRUITING  PHASE3  190         Tata Memorial Hospital     2020-04-20  false
NCT00268684  UNKNOWN     PHASE3  381         Tel-Aviv Sourasky          2005-05     false
```

`UNKNOWN` is not an error: it is what the registry assigns when the sponsor has stopped verifying
the record. On a 2005 study, read it as "probably abandoned".

`count --by phase` and `count --by status` give the shape of a field without walking it. Note that
**phase counts overlap** — a phase 2/3 study carries `["PHASE2","PHASE3"]` and is returned by a
filter for either — so they do not sum to the total.

## One study in detail

```bash
python skills/clinicaltrials/scripts/ct_study.py show NCT02142738
python skills/clinicaltrials/scripts/ct_study.py outcomes NCT02142738
```

```
nct_id             NCT02142738
status             COMPLETED
phase              PHASE3
allocation         RANDOMIZED
enrollment         305 (ACTUAL)
sponsor            Merck Sharp & Dohme LLC
start              2014-08-25
has_results        True
```

`outcomes` separates the primary endpoint — what the study was *powered for* — from the
secondaries. A positive secondary in a study that missed its primary is hypothesis-generating,
not evidence, and the registry will not make that distinction for you.

`eligibility` splits the criteria blob back into inclusion and exclusion. There is no structured
form in the registry; it is one newline-delimited string with headings inside it.

## Landscape and attrition

```bash
python skills/clinicaltrials/scripts/ct_landscape.py attrition \
    --condition "pancreatic cancer" --phase PHASE3 --limit 120
```

```
phase   studies  completed  recruiting  terminated  withdrawn  stopped_pct
PHASE3  120      43         25          16          5          18.3

# 21 stated reasons for stopping
  - Preliminary data showed no survival benefit in the GV1001 group compared to gemcitabine.
  - recruitment prematurely stopped due to a lack of eligible patients.
```

**`whyStopped` is the richest field in the registry** and the reason `attrition` prints reasons
rather than counting them. Those two examples are completely different facts: the first is a real
negative result about the biology, often the only public record of it; the second says nothing
about the drug and everything about whether you can recruit for your own trial.

`sponsors` reports total enrolment and highest phase alongside the study count, because counting
registrations measures activity, not investment — twenty investigator-initiated phase 1s are not
two 800-patient phase 3s.

## Four ways this registry misleads quietly

1. **Nobody verifies any of it.** Sponsors submit and update at their own pace. A record is
   evidence of stated intent, not of what happened.
2. **Drug names are free text with no identifier.** `MK-3475`, `pembrolizumab`, and `Keytruda`
   do not group together. Resolve names with `chembl` first and search each synonym.
3. **Missing results usually mean nothing.** FDAAA compliance is well below 100% and does not
   reach phase 1, most non-US studies, or products never filed with the FDA.
4. **`ESTIMATED` enrolment is a plan.** Everything is estimated at registration; the gap between
   it and the final `ACTUAL` is itself a feasibility finding.

## When to stop using this API

The registry has no aggregation endpoint, so every breakdown here walks studies one page at a
time. For corpus-wide analysis, use the bulk download rather than the API. For European trials,
many of which never appear here, use the EU CTR; the WHO ICTRP federates the national registries.

## Composing with the rest of the bundle

- `open-targets` → here: is anyone already running trials against this target?
- `chembl` → here: resolve a compound's synonyms before searching free-text intervention names.
- `openfda` → alongside: the registry is what was attempted, openFDA is what was approved.
- `depmap` → here: a genetic dependency, checked against whether the clinic has tried it.
- `pkpd-translation` → after: a registered dose and schedule as a translation anchor.

## Reporting results honestly

Give the query, the number of studies actually walked rather than the number matched, and the
date. Say "N studies are registered", never "N studies show". Quote `whyStopped` verbatim instead
of paraphrasing it into a cause. If asked whether a trial succeeded, say the registry does not
record that.
