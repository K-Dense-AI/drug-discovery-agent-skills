---
name: immunogenicity
description: Estimate how likely a protein therapeutic is to provoke an anti-drug antibody response, and locate the sequence regions responsible. Use this skill to tile a sequence into peptides, predict class II MHC presentation across a population-representative allele panel, aggregate predicted binders into a per-region and whole-molecule risk score, compare a candidate against its closest human germline, and decide which liabilities are worth deimmunising. Also trigger on immunogenicity, anti-drug antibody, ADA, T-cell epitope, MHC class II, HLA-DRB1, NetMHCIIpan, NetMHCpan, deimmunisation, tregitope, or population coverage.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+. The bundled scripts tile sequences, parse NetMHCpan/NetMHCIIpan output, and aggregate epitope burden using only the standard library. Running the predictor itself needs NetMHCIIpan or NetMHCpan from DTU Health Tech, which is free for academic use but requires a signed licence and is not redistributable.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🛡️"
    homepage: https://services.healthtech.dtu.dk/services/NetMHCIIpan-4.3/
  hermes:
    category: research
---

# Immunogenicity Risk

A protein therapeutic can provoke antibodies against itself, and when it does the drug stops
working — or worse, cross-reacts with an endogenous counterpart. This skill locates the sequence
regions responsible and puts them in proportion against the factors that usually matter more.

**No installation, no network, no key** for the bundled scripts. Running the predictor needs
**NetMHCIIpan** from DTU Health Tech, free for academic use under a signed licence and not
redistributable — which is why these scripts prepare its input and parse its output rather than
wrapping it.

Read [references/running-netmhciipan.md](references/running-netmhciipan.md) before your first
scan, [references/deimmunisation.md](references/deimmunisation.md) before changing a sequence, and
[references/what-drives-ada.md](references/what-drives-ada.md) before drawing a conclusion —
**that one is judgement, not syntax, and it is mostly about what the scan cannot see.**

## The two scripts

| Script | Answers |
|---|---|
| `epitope_scan.py` | Which regions present peptides, on how many alleles? |
| `ada_risk.py` | What does that add up to, and what else should I be worried about? |

## Class II, and %Rank

Two things to get right before anything else.

**Anti-drug antibodies need CD4 T-cell help, which is class II restricted.** Scanning a biologic
against MHC-I answers a question about cytotoxic T cells that is rarely the one being asked. Use
NetMHCIIpan.

**Use %Rank, not affinity.** Predicted IC50 is not comparable between alleles — each has its own
affinity distribution — so nM cannot be thresholded uniformly. %Rank normalises against a
background of random peptides and can. Conventionally ≤2% is a strong binder, ≤10% weak.

## Collapse peptides to cores, then count alleles

```bash
python skills/immunogenicity/scripts/epitope_scan.py peptides --sequence-file mab.fa > peptides.txt
# netMHCIIpan -f peptides.txt -inptype 1 -a DRB1_0101,... -xls -xlsfile out.txt
python skills/immunogenicity/scripts/epitope_scan.py parse --output out.txt
```

```
core       example_peptide  alleles_bound  allele_coverage_pct  best_rank  promiscuous
LVESGGGLV  EVQLVESGGGLVQPG  3              75.0                 0.85       true
```

Consecutive 15-mers overlap by 14 residues and share a 9-mer core, so **peptide hits overcount
epitopes by up to sevenfold**. Three predictions here collapse to one epitope.

**Promiscuity matters more than potency.** A core binding one rare allele affects few patients; one
binding eight common alleles affects most of them. The scripts sort by alleles bound, not by rank.

## Germline identity dominates the epitope count

```bash
python skills/immunogenicity/scripts/ada_risk.py score --cores cores.tsv --length 120 --humanness 0.92
```

A fully human sequence contains **plenty** of predicted class II binders — human proteins are full
of them. What makes it low-risk is central tolerance: T cells recognising self-peptides were
deleted in the thymus.

So the location of an epitope matters far more than the count. Peptides in germline framework are
largely noise; peptides in CDRs, engineered junctions, and non-human segments are the signal.
`ada_risk.py` changes its interpretation based on `--humanness`, and says so when you omit it.

## Aggregation probably matters more than your sequence

The single largest non-sequence factor. Aggregates present repetitive epitope arrays that
cross-link B-cell receptors and are taken up by antigen-presenting cells far more efficiently than
monomer.

A low-epitope sequence that aggregates in the vial will be more immunogenic than a higher-epitope
one that does not. Behind it: route (subcutaneous > IV), dosing frequency, patient population,
concomitant immunosuppression, impurities, and non-human glycans — which are epitopes in their own
right and invisible to any sequence scan.

## Nothing here predicts an ADA rate

```bash
python skills/immunogenicity/scripts/ada_risk.py context
```

| Molecule | Observed ADA |
|---|---|
| trastuzumab (humanised) | <1% |
| pembrolizumab (humanised) | <2% |
| natalizumab (humanised) | ~6–9% |
| adalimumab (**fully human**) | up to ~26% |
| infliximab (chimeric) | ~10–60% |
| muromonab-CD3 (murine) | ~50–100% |

Humanisation helps and does not decide it — fully human adalimumab reaches 26%. Clinical ADA spans
under 1% to over 60%, and no in-silico method resolves that range. Anything claiming to predict a
percentage is overselling.

## Deimmunising without breaking the molecule

The highest-leverage change is usually a substitution at **P1** of the 9-mer core, replacing a
large hydrophobic with something charged or small polar. But **a substitution that breaks one core
routinely creates a new one shifted a few residues along** — the class II groove is open-ended, so
suppressing the best register promotes the next.

Re-scan the **whole molecule** after every change, not just the mutated peptide. And rescreen for
what you may have introduced: N-X-S/T sequons (`glycoengineering`), NG or DG hotspots
(`antibody-engineering`), and aggregation propensity.

## Composing with the rest of the bundle

- `antibody-engineering` → before: germline identity, CDR boundaries, and Vernier residues, which
  is the context every epitope needs.
- `glycoengineering` → alongside: non-human glycans are immunogenic epitopes no sequence scan
  finds, and deimmunising substitutions can create new sequons.
- `protein-binder-design` → here: de novo binders are entirely non-germline, so this scan is not
  optional for them.
- `esm` → alongside: sequence likelihood as a rough humanness proxy when no germline reference fits.
- `adaptyv` → after: get the variants made and tested.

## Reporting results honestly

Say **where** the promiscuous epitopes are, not just how many. Give germline identity alongside.
Name the alleles scanned and note that DP and DQ were not. State that aggregation and route are
likely larger contributors than sequence. Call the output a triage aid, and recommend MAPPs or a
T-cell proliferation assay before any decision that matters. Never report a predicted ADA rate.
