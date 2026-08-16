---
name: chemical-space
description: Navigate make-on-demand catalogues — ZINC-22 through CartBlanche and Enamine REAL Space — to find compounds that can actually be ordered. Use this skill to look substances up by ZINC identifier or structure, understand tranche partitioning by heavy-atom count and logP, and choose between screening an enumerated subset and searching a combinatorial synthon space with a fragment-growing method such as V-SYNTHES. Also trigger on ZINC22, CartBlanche, Enamine REAL, make-on-demand, tangible library, synthon, tranche, giga-scale enumeration, or ultra-large virtual screening.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+ and outbound HTTPS access to cartblanche.docking.org. The bundled client uses only the Python standard library and needs no API key or account. Enamine REAL Space itself is a commercial catalogue — identifiers are public but bulk synthon files require a licence from Enamine.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🌌"
    homepage: https://cartblanche.docking.org
  hermes:
    category: research
---

# Purchasable Chemical Space

Make-on-demand catalogues turned virtual screening from "the million compounds we own" into
"the tens of billions a vendor will synthesise". ZINC-22 holds about 54.9 billion 2D structures
drawn from Enamine, WuXi, and Mcule; Enamine REAL Space defines around 94 billion combinatorially.
This skill is about finding compounds in that space that can actually be ordered — and knowing
when the space is too large to enumerate at all.

**Services:** `https://cartblanche.docking.org` (per-substance JSON) ·
`https://files.docking.org/zinc22` (bulk tranche tree). Both unauthenticated.
**Checked against:** the live services, August 2026.

Read [references/zinc22-and-cartblanche.md](references/zinc22-and-cartblanche.md) before calling
the API or downloading a tranche,
[references/combinatorial-spaces.md](references/combinatorial-spaces.md) before assuming a space
can be enumerated, and
[references/screening-strategy.md](references/screening-strategy.md) before designing a cascade —
**that one is judgement, not syntax.**

## The two scripts

| Script | Answers |
|---|---|
| `cartblanche_lookup.py` | What is this ZINC id, and can I buy it? |
| `space_plan.py` | Which tranches do I need, and what will the screen cost? |

## The API lies about its own responses

This is the thing to get right. CartBlanche answers **unknown routes with HTTP 200, a
`Content-Type: application/json` header, and its React app's HTML**:

| Route | Status | Content-Type | Body |
|---|---|---|---|
| `/substance/ZINC000000000053.json` | 200 | application/json | **JSON** |
| `/substance.json?zinc_id=…` | 200 | application/json | HTML shell |
| `/tranches.json` | 200 | application/json | HTML shell |

Neither the status code nor the header can be trusted; only the body can. `get_json()` raises a
named error when a response begins with `<`. **The one reliable JSON route is
`/substance/<ZINC id>.json`** — treat CartBlanche as per-identifier lookup and use the file tree
for anything bulk.

Identifiers are zero-padded to twelve digits: `ZINC53` does not resolve, `ZINC000000000053` does.
The scripts accept either.

## Can I buy it?

```bash
python skills/chemical-space/scripts/cartblanche_lookup.py substance ZINC19632618
```

```
zinc_id           smiles                              mwt      logp  heavy_atoms  purchasable  catalogs  min_price
ZINC000019632618  Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)...  493.615  4.59  37           true         281       240
```

That is imatinib, offered by 281 catalogues from 240 up. `catalogs` shows supplier, quantity, and
lead time per entry.

**Existing in ZINC is not the same as being purchasable.** An empty `catalogs` block is a compound
that was enumerated but that nobody offers. And a catalogue entry is an *order*, not a vial:
make-on-demand synthesis fails roughly one time in five, with lead times of several weeks.

## Which tranches, and what will it cost?

The bulk tree is addressed by **heavy-atom count and logP, not molecular weight** — `H25P200` is
25 heavy atoms and logP 2.0, `H25M100` is logP −1.0. A target profile expressed in MW cannot
address the directories:

```bash
python skills/chemical-space/scripts/space_plan.py tranches --hac-min 18 --hac-max 26 \
    --logp-min 1 --logp-max 4
```

Then make the funnel explicit before committing compute:

```bash
python skills/chemical-space/scripts/space_plan.py cascade --library-size 1e9
```

```
stage              input          keep  survivors    core_hours  wall_days_at_cores
property filter    1000000000     0.3   300000000    138.9       0.01
fast dock          300000000      0.01  3000000      250000      10.42
standard dock      3000000        0.1   300000       25000       1.04
rescore / MM-GBSA  300000         0.1   30000        25000       1.04
visual triage      30000          0.2   6000         500         0.02

# 1,000,000,000 in, 6,000 out
# 300,639 core-hours total; 12.5 days on 1000 cores
```

The property filter is free and removes 70% — always first. Fast docking is 83% of the compute, so
that is the only stage where a speedup matters. And 6000 survivors is still far more than anyone
buys, so a real campaign ends with diversity selection and a budget cut.

## Above 10⁸ compounds, stop enumerating

`strategy` reports the boundary, and the arithmetic behind it is unforgiving: 94 billion SMILES at
100 bytes is about 9 TB before conformers, and docking each for three seconds is roughly 78 000
core-years.

A combinatorial space is reagents plus reaction rules, not a list — so search it without
enumerating it. Dock a minimal fragment library covering every scaffold and synthon, keep the
best, and enumerate only those. V-SYNTHES2 reports this over 36 billion REAL Space compounds.

## Four ways this misleads

1. **Bigger is sublinearly better.** A thousandfold larger library buys closer to one log of
   affinity, and it does not improve enrichment — false positives scale with N too.
2. **Giga-scale finds your scoring function's blind spots reliably.** High molecular weight,
   over-buried hydrophobics, and strained conformers presented as favourable are systematic
   artefacts, and a thorough search finds them precisely because it is thorough.
3. **Receptor quality does not scale away.** A wrong protonation state costs the same fraction of
   the answer at any N. Preparing the structure beats enlarging the library.
4. **REAL Space is narrower than its size suggests.** It is a product over amide couplings,
   Suzukis, and reductive aminations; unusual scaffolds are systematically absent.

## When to stop using these tools

For similarity and substructure search across REAL Space without enumeration, use SmallWorld
(<https://sw.docking.org>) and Arthor (<https://arthor.docking.org>). For the full synthon
definition of REAL Space you need an agreement with Enamine — identifiers are public, the reagent
and reaction files are not.

## Composing with the rest of the bundle

- `binding-site-analysis` → before: is the pocket worth a billion compounds at all?
- `medchem` / `rdkit` → before: property filters and PAINS removal, at the top of the funnel.
- `autodock-vina` → alongside: the docking engine the cascade is costed for.
- `retrosynthesis` → alongside: for anything not in a catalogue, can it be made?
- `chembl` → after: is a hit series already known against this target?

## Reporting results honestly

Give the library actually screened, the keep-fraction at every stage, and whether a redocking
control reproduced a known pose. A docking score is not an affinity and a rank is not a potency
prediction. Report compounds ordered *and* compounds received — a hit rate computed against
orders rather than deliveries is wrong by about a fifth.
