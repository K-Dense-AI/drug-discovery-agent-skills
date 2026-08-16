---
name: autodock-vina
description: Structure-based docking with AutoDock Vina, Vinardo, and AutoDock4 through the Meeko toolchain. Use this skill to define a docking box, prepare receptors and ligands as PDBQT, run single or batch docking, rescore, and interpret affinities, poses, and ligand efficiency. Covers box definition from a reference ligand or pocket residues, protonation and tautomer decisions, flexible side chains, exhaustiveness and seeds, redocking validation, and virtual screening over compound libraries. Also trigger on vina, smina, gnina, mk_prepare_ligand, mk_prepare_receptor, mk_export, scrub.py, PDBQT, autogrid4, docking box, or binding-pose prediction.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: The bundled scripts need only Python 3.10+ and the standard library. Running a docking calculation additionally needs the AutoDock Vina binary (conda install -c conda-forge vina, or pip install vina 1.2.7) and Meeko 0.7+ (pip install meeko) on PATH; SMILES input also needs molscrub. CPU only; no GPU or API key required.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🔬"
    homepage: https://autodock-vina.readthedocs.io
  hermes:
    category: research
---

# AutoDock Vina

Classical, CPU-only, physics-style docking: put a ligand in a defined box and search for the pose
that minimises an empirical scoring function. Unlike `diffdock`, it returns a score you can rank
with; unlike `boltz`, it needs a receptor structure and a defined site, and runs on a laptop.

**Docs:** [autodock-vina.readthedocs.io](https://autodock-vina.readthedocs.io) ·
[meeko.readthedocs.io](https://meeko.readthedocs.io)
**Checked against:** Vina 1.2.7, Meeko 0.7.1.

Read [references/receptor-preparation.md](references/receptor-preparation.md) and
[references/ligand-preparation.md](references/ligand-preparation.md) before running anything —
that is where accuracy is won. Read
[references/scoring-and-interpretation.md](references/scoring-and-interpretation.md) before
reporting a number, and [references/troubleshooting.md](references/troubleshooting.md) when
something fails.

## Before anything else: what the score is

Vina's "affinity" in kcal/mol is an empirical scoring function with roughly **2–3 kcal/mol
error** — about two orders of magnitude in Kd. It is useful for enriching a library and for
predicting a pose. It is not a predicted binding free energy, it is not comparable across targets
or across scoring functions, and a −9.5 and a −8.2 are not distinguishable. Report it as what it
is.

It also **scales with heavy-atom count**, so a library ranked by raw score puts the biggest
molecules on top. Rank with ligand efficiency alongside; the parser computes it.

## The workflow

```bash
# 1. box, from the co-crystal ligand of a holo structure
python skills/autodock-vina/scripts/make_box.py 1iep.cif \
    --reference-ligand STI --out box.txt --box-pdb box.pdb

# 2. receptor and ligand PDBQT (Meeko, external)
mk_prepare_receptor.py -i receptor_H.pdb -o receptor -p -v \
    --box_center 15.190 53.903 16.917 --box_size 20 20 20
scrub.py ligands.smi -o ligands_3d.sdf --ph 7.4

# 3. dock
python skills/autodock-vina/scripts/dock_batch.py run \
    --receptor receptor.pdbqt --config box.txt --ligands ligands_3d.sdf \
    --exhaustiveness 32 --seed 42 --workers 8 --out-dir docking/

# 4. read the results, with the sanity checks
python skills/autodock-vina/scripts/parse_vina_output.py docking/*_out.pdbqt \
    --config box.txt --summary
```

`dock_batch.py check` verifies the toolchain first; `--dry-run` prints every command without
running it.

## The box is the parameter that matters

Too small and the correct pose cannot fit. Too large and the search dilutes — the exhaustiveness
budget is fixed, so doubling the volume halves the sampling density and quietly degrades every
result.

```bash
# see what is bound before choosing
python skills/autodock-vina/scripts/make_box.py 1iep.cif --list-ligands
# component  chain  resseq  atoms
# STI        A      201     37

python skills/autodock-vina/scripts/make_box.py 1iep.cif --reference-ligand STI
# center_x = 15.190   size_x = 18.664
# center_y = 53.903   size_y = 26.739
# center_z = 16.917   size_z = 23.526
```

Four ways to define it, in descending order of reliability: `--reference-ligand` (a bound ligand
in a holo structure), `--residues A:790,A:797,A:855` (known pocket residues), `--center/--size`
(explicit), and `--chain` (blind docking, which rarely reproduces a known pose — the script warns).

Ligand auto-selection skips waters, ions, buffers, and cryoprotectants, so the box does not land
on a sulfate. Write `--box-pdb` and load it next to the receptor in PyMOL; looking at the box
takes ten seconds and catches the coordinate mix-ups that produce a whole campaign of nonsense.

## Reading results, including the failure flags

```bash
python skills/autodock-vina/scripts/parse_vina_output.py out.pdbqt --config box.txt
```

```
ligand  rank  affinity_kcal_mol  ligandEfficiency  heavyAtoms  rmsd_lb  atEdge
lig1    1     -12.5              -0.34             37          0.000
lig1    2     -12.2              -0.33             37          1.234    +x
lig1    3     -9.1               -0.25             37          3.456

# warning: pose atoms within 1 A of the box wall (+x) -- the search was clipped
# warning: best and second pose differ by only 0.30 kcal/mol
```

- **`atEdge` invalidates a score.** A pose touching the wall means the optimum may lie outside
  the box. Enlarge or recentre and re-dock. Passing `--config` is what enables this check, and it
  is the reason to pass it.
- **A sub-0.5 kcal/mol gap** between the top two poses means the ranking is not a discrimination.
- `rmsd_lb`/`rmsd_ub` are measured from the best pose, so a large spread means several distinct
  binding modes and a small one means the search kept converging — that is a good sign.

## Settings that are not the defaults

- **`--exhaustiveness 32`, not 8.** The AutoDock documentation says so itself for the imatinib
  tutorial. The default was tuned for small rigid ligands in a tight box.
- **`--seed`.** The search is stochastic; without a fixed seed the run is not reproducible, and a
  ranking that changes between seeds is not a ranking.
- **`--scoring vinardo`** is worth trying when Vina's poses look wrong. Scores from different
  functions are *not comparable with each other*.

## Validate before you trust

Redock the co-crystal ligand into its own structure and measure RMSD to the crystal pose. Under
2 Å means the box, the protonation, and the receptor preparation can reproduce a known answer.
Above that, fix the setup before docking anything unknown. Then cross-dock ligands from other
structures of the same target — that predicts screening performance far better than self-docking.

One run, one hour, and it is the only calibration the method offers.

## Where this fails

Metalloenzymes, highly charged pockets, water-mediated binding, induced fit needing backbone
movement, covalent inhibitors, ligands with more than ~15 rotatable bonds, and fragments. In
those cases say the method does not apply rather than reporting a score anyway.
[references/troubleshooting.md](references/troubleshooting.md) covers each and names the
alternatives (smina, gnina, AutoDock-GPU, covalent protocols).

## Composing with the rest of the bundle

- `uniprot-rcsb` → here: find and check the structure, confirm the site residues are actually
  resolved, and download the coordinates.
- `binding-site-analysis` → before: is the pocket worth docking into at all, and where exactly
  is it? `pocket_box.py --format vina` writes this skill's box config directly.
- `chemical-space` → before: purchasable compounds to dock, and a costed screening cascade.
- `free-energy-perturbation` → after: rigorous ΔΔG on the tens of compounds worth it.
- `medchem` / `rdkit` / `datamol` → here: triage and standardise the library first. Docking
  20,000 PAINS wastes the compute and pollutes the hit list.
- `molecular-dynamics` → after: run the top poses; a pose that leaves the site in 10 ns was not a
  pose.
- `boltz` → alongside: a trained affinity head answers a different question from a physics-style
  score, and agreement between the two is worth more than either alone.
- `diffdock` → alternative: diffusion-based pose generation with no box, but no affinity.
- `chembl` → validation: known actives against your target, for decoy enrichment.
