---
name: antibody-engineering
description: Number antibody variable domains, annotate CDRs, and assess developability from sequence. Use this skill to apply IMGT, Kabat, Chothia, Martin, or AHo numbering with ANARCI, delimit CDRs and framework regions, scan for chemical liabilities (N-glycosylation sequons, deamidation NG, isomerisation DG, oxidation, unpaired cysteine, fragmentation), compute pI, net charge, extinction coefficient and hydrophobicity, and plan humanisation by CDR grafting. Also trigger on antibody, nanobody, VHH, scFv, Fab, CDR, framework, ANARCI, abnumber, IgBLAST, OAS, SAbDab, humanization, Vernier residues, or developability.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: scan_liabilities.py and physchem_profile.py need only Python 3.10+ and the standard library. number_antibody.py additionally needs anarci (pip install anarci) and HMMER with hmmscan on PATH (conda install -c bioconda hmmer, or brew install hmmer). No GPU, no network, no API key.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🅨"
    homepage: https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/
  hermes:
    category: research
---

# Antibody engineering

Sequence-level analysis for antibodies, nanobodies, and other variable-domain formats: numbering,
CDR annotation, chemical liabilities, and physicochemical properties. All of it runs in seconds
and rules out a surprising fraction of problems before a model or a wet-lab week is spent.

Read [references/numbering-schemes.md](references/numbering-schemes.md) before quoting any
residue position, [references/developability.md](references/developability.md) before acting on a
liability, [references/humanization-and-design.md](references/humanization-and-design.md) for
grafting and humanness, and [references/tools.md](references/tools.md) for the wider ecosystem.

## A residue number means nothing without its scheme

"Residue 52" is a different residue in IMGT, Kabat, and Chothia numbering, and the CDRs they
define overlap only partially. The same trastuzumab heavy chain:

```
IMGT    CDRH1 GFNIKDTY (8)   CDRH2 IYPTNGYT (8)            CDRH3 SRWGGDGFYAMDY (13)
Kabat   CDRH1 DTYIH    (5)   CDRH2 RIYPTNGYTRYADSVKG (17)  CDRH3 WGGDGFYAMDY   (11)
```

Neither is wrong. **Use IMGT by default** — one definition for both chains, structurally
principled gaps, and the germline database is IMGT-numbered — and convert to Kabat when matching
legacy literature. State the scheme every time.

```bash
python skills/antibody-engineering/scripts/number_antibody.py antibody.fasta
python skills/antibody-engineering/scripts/number_antibody.py antibody.fasta --scheme kabat
python skills/antibody-engineering/scripts/number_antibody.py antibody.fasta \
    --format regions --out regions.tsv
```

```
# trastuzumab_VH: chain H, closest germline human_H (human), E=3e-60
#   variable domain spans input residues 1-120
  CDRH1	8	GFNIKDTY
  CDRH2	8	IYPTNGYT
  CDRH3	13	SRWGGDGFYAMDY
```

Needs `pip install anarci` plus HMMER (`hmmscan` on PATH). Note that ANARCI's species call is
the closest germline, not an annotation — a humanised antibody reports `human` because its
frameworks are human, which says nothing about its CDRs.

## Liabilities, weighted by region

```bash
python skills/antibody-engineering/scripts/scan_liabilities.py antibody.fasta \
    --regions regions.tsv --min-severity high
```

```
# trastuzumab_VH: 120 residues, 3 finding(s)
  [critical] deamidation (NG) 'NG' at 55 (CDRH2)
             the fastest-deamidating motif; Asn -> iso-Asp/Asp changes charge and can
             abolish binding, and it is the usual cause of potency loss on storage
  [critical] isomerisation (DG) 'DG' at 102 (CDRH3)
             Asp-Gly isomerises to iso-Asp through a succinimide intermediate
```

Those are trastuzumab's two documented hotspots, found from sequence alone.

**Pass `--regions`.** The same `NG` in framework 3 is usually buried and tolerated; in CDR-H2 it
is a redesign candidate. Without region information every finding is reported at the framework
baseline, and the script says so.

Motifs covered: N-glycosylation sequons (`N-X-[ST]`, X≠P), deamidation (`NG` ≫ `NS`/`NT`/`NN`/…),
isomerisation (`DG` ≫ `DS`/`DT`/…), acid-labile `DP` fragmentation, Met and Trp oxidation,
unpaired and extra cysteines, N-terminal pyroglutamate, and the `RGD`/`RYD` integrin motifs.

A liability is a question, not a veto. Many approved antibodies carry known liabilities and
manage them with formulation and release specifications. What settles it is a force-degradation
study, not a prediction.

## Physicochemical profile

```bash
python skills/antibody-engineering/scripts/physchem_profile.py antibody.fasta --combine
```

```
# trastuzumab_VH: 120 residues
  molecular weight     13164.7 Da
  isoelectric point    8.17 (EMBOSS pKa set)
  net charge at pH 7.4  +0.89
  extinction (280 nm)  35535 /M/cm (cystine)
  A280 at 1 mg/mL      2.699
  GRAVY                -0.305
```

- **pI** drives purification and formulation. Formulate at least a unit away from it — near-zero
  net charge means poor colloidal stability, and the script warns when the two are close.
- **Net charge at pH 7.4** above roughly +6 associates with fast clearance and polyspecificity in
  the published developability sets.
- **Extinction coefficient** is what turns A280 into a concentration; getting it wrong scales
  every downstream number including your affinities.
- Different pKa sets shift pI by a few tenths. The script uses EMBOSS and says so; quote the set.

## The order that saves time

1. `number_antibody.py --format regions` — everything downstream needs regions.
2. `scan_liabilities.py --regions` — seconds, catches the classics.
3. `physchem_profile.py` — pI, charge, extinction coefficient.
4. Model the Fv (ABodyBuilder3, IgFold, or `boltz`) — needed for anything conformational.
5. Structure-based properties: TAP metrics, hydrophobic and charged patches.
6. Humanness, if the molecule is not already human.
7. Test: force degradation, SEC, DSF, HIC, AC-SINS, PSR.

Steps 1–3 cost seconds. Do them before spending a GPU hour.

## What sequence cannot tell you

Aggregation, viscosity, polyspecificity, and thermal stability are **conformational**, and none
of them follow from motifs. They need a structure — hydrophobic patch area across the VH/VL
interface predicts aggregation and HIC retention far better than GRAVY does — or an experiment.
Reporting a clean liability scan as "developable" is the mistake this skill is meant to prevent;
say "no sequence liabilities detected, structure-based properties not assessed".

Antibody–antigen complex prediction is also still genuinely hard for every current method,
because the interface is a rearranged loop rather than a conserved surface. Check ipTM before
believing a predicted complex.

## Composing with the rest of the bundle

- `glycoengineering` — the sequons this skill flags, in depth: occupancy, glycoform engineering,
  effector-function consequences.
- `esm` — language-model scoring for affinity maturation and humanness.
- `boltz` — antibody–antigen cofolding when you need the complex.
- `uniprot-rcsb` — antigen sequence and structure; SAbDab entries are PDB entries.
- `adaptyv` — submit designs and get measured binding and thermostability back.
- `open-targets` — whether the antigen is validated and accessible to a biologic; its `AB`
  tractability buckets answer exactly that.
