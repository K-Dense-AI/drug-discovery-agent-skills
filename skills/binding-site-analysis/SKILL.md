---
name: binding-site-analysis
description: Decide whether a protein has a pocket worth targeting, and where it is, before committing to a docking or design campaign. Use this skill to run fpocket cavity detection, rank cavities by druggability and volume, compare apo and holo conformations to spot induced fit, identify allosteric and cryptic cavities that only open in simulation, and convert a chosen cavity into the search box coordinates a docking run needs. Also trigger on fpocket, cavity detection, druggability score, alpha sphere, cryptic pocket, allosteric site, pocket volume, hotspot mapping, or undruggable target assessment.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+. The bundled scripts parse fpocket output and emit box coordinates using only the standard library. Detecting cavities needs the fpocket binary (conda-forge or apt, MIT) on PATH. Cryptic-cavity workflows additionally need a molecular dynamics engine; no GPU is required for static detection.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🕳️"
    homepage: https://github.com/Discngine/fpocket
  hermes:
    category: research
---

# Binding Site Analysis

The step before docking. Every docking skill in this bundle assumes you already know where the
ligand goes and that the site is worth the compute — this is where those two assumptions get
checked. fpocket runs in seconds and can save a month of screening against a pocket that was never
going to bind anything.

**Tool:** [fpocket](https://github.com/Discngine/fpocket), MIT, `conda install -c conda-forge fpocket`.
Alpha-sphere cavity detection by Voronoi tessellation.
**Checked against:** fpocket 4.x output format.

Read [references/fpocket-output.md](references/fpocket-output.md) before parsing a run,
[references/druggability.md](references/druggability.md) before calling a site druggable or not,
and [references/cryptic-and-allosteric.md](references/cryptic-and-allosteric.md) when the answer
is "no pocket" — **that one is judgement, not syntax.**

## The three scripts

| Script | Answers |
|---|---|
| `pocket_report.py` | Which cavities are there, and is any of them worth targeting? |
| `pocket_box.py` | Where exactly does the docking box go? |
| `site_compare.py` | Does a pocket appear only when something is bound? |

## Score and Druggability Score are different, and pocket1 is not the answer

This is the thing to get right. fpocket reports two numbers per cavity and they measure different
things. **Score** ranks cavities geometrically, and pocket *numbering follows it*. **Druggability
Score** is a logistic model trained to separate sites with known drug-like ligands from sites
without — it is the one that answers "worth a campaign".

They disagree often:

```bash
python skills/binding-site-analysis/scripts/pocket_report.py rank --out-dir receptor_out
```

```
# fpocket ranks pocket 1 first by Score, but pocket 2 is the most druggable.
pocket  druggability  score  volume  apolar_fraction  verdict     reason
2       0.871         0.31   720.5   0.7143           druggable   resembles sites with known drug-like ligands
1       0.183         0.412  980.4   0.3172           poor        does not resemble a small-molecule binding site
```

Pocket 1 is larger and scores higher. It is also 68% polar surface, which is a groove rather than
a pocket. **Volume alone is misleading** — the apolar fraction is what distinguishes a site that
will bind a small molecule, and this script derives it because fpocket does not.

Thresholds applied: druggability ≥ 0.5 is druggable, 0.2–0.5 marginal; volume < 200 Å³ is too
small whatever the score; apolar fraction < 0.35 flags a polar groove. The 0.5 cut is fpocket's
own; the others are this skill's conventions, stated so you can argue with them.

## Strip the structure first

fpocket contours around whatever is in the file. Waters and ligands left in place get reported as
protein surface, and the cavity they occupy disappears:

```bash
grep -v HOH input.pdb | grep -v HETATM > receptor.pdb && fpocket -f receptor.pdb
```

A structural metal or covalent prosthetic group should stay; a substrate analogue should go.

## Producing the box

```bash
python skills/binding-site-analysis/scripts/pocket_box.py from-pocket --out-dir receptor_out \
    --pocket 2 --format vina
```

```
center_x = 12.0
center_y = 22.0
center_z = 33.0
size_x = 12.0
size_y = 12.0
size_z = 14.0
```

That output pastes directly into an AutoDock Vina config. Two sizing rules are built in: **4 Å of
padding per side**, so the ligand can translate and rotate rather than being pinned; and a warning
past 27 000 Å³, because Vina spreads a fixed exhaustiveness over the whole volume and a box twice
as wide samples eight times as thinly.

`from-ligand` centres on a crystallographic ligand instead, and **that is the better option
whenever a holo structure exists** — a real bound pose beats a predicted cavity. It lists the
candidate HETATM residues when the one you named is not present.

## Cryptic sites, or why the apo structure lied

```bash
python skills/binding-site-analysis/scripts/site_compare.py match --apo apo_out --holo holo_out
```

Classifies each cavity as `cryptic` (in holo, absent in apo), `induced fit`, `stable`,
`closes on binding`, or `apo only`. **Superpose the structures first** — matching is spatial, and
unaligned inputs make every cavity look cryptic. The script says so when nothing matches.

This is not a corner case. The KRAS G12C switch II pocket does not exist in unliganded KRAS;
thirty years of "undruggable" rested on structures that could not show it.

## Four ways this misleads

1. **A low druggability score means "unlike sites we have drugged before"**, not "impossible". The
   training set predates degraders, covalent inhibitors, and most protein–protein interface drugs.
2. **You scored one conformation.** Apo structures under-report pockets systematically.
3. **Structure quality propagates.** Missing loops, uncertain rotamers above ~2.5 Å, and
   AlphaFold's tendency toward closed apo-like states all change the answer. Check with
   `uniprot-rcsb` first.
4. **A detector that cannot recover a known site should not be trusted on an unknown one.** If a
   holo structure exists, verify the top cavity contains the crystallographic ligand.

## When the answer is "no druggable pocket"

That is a conclusion about conventional reversible small molecules, not about the target. In
rough order of how often they work: covalent inhibition (how KRAS G12C fell), targeted degradation
(`degraders` — a degrader needs a binding site, not an inhibitory pocket), molecular glues,
cryptic sites found by mixed-solvent MD, biologics if the target is extracellular, and
`oligonucleotides` to sidestep the protein entirely.

## Composing with the rest of the bundle

- `uniprot-rcsb` → before: check resolution, missing residues, and whether a holo structure exists.
- This skill → `autodock-vina`: `pocket_box.py --format vina` writes its config directly.
- This skill → `diffdock` / `boltz`: which site to focus on before posing.
- `molecular-dynamics` → alongside: mixed-solvent simulation to find cryptic pockets.
- `chemical-space` → after: only worth a giga-scale library once the site is worth it.

## Reporting results honestly

Give the druggability score, the volume, and the apolar fraction together — one number is not an
assessment. Say which structure and which conformation was analysed, and whether waters and
ligands were stripped. If a known ligand exists, say whether the detector recovered its site. Call
a predicted cryptic pocket a hypothesis until a fragment soak or thermal shift confirms it.
