# Scoring, search settings, and what a Vina number means

## The number

Vina reports an "affinity" in kcal/mol. It is an **empirical scoring function fitted to a
training set of complexes**, not a computed free energy. Published error against experimental
binding data is roughly 2–3 kcal/mol RMSE — about two orders of magnitude in Kd. A −9.5 and a
−8.2 are not distinguishable.

What it is good for:

- **Enriching a library.** Ranking thousands of compounds so the top few hundred are worth
  looking at. This works, modestly, and is the main legitimate use.
- **Pose prediction.** With a well-prepared receptor and a defined pocket, Vina reproduces
  crystal poses within 2 Å a good fraction of the time.

What it is not good for:

- Quoting a predicted Kd or ΔG.
- Comparing across targets, or across receptor preparations of the same target.
- Distinguishing compounds within 1–2 kcal/mol of each other.
- Ranking compounds of very different size, without normalising.

## Size bias and ligand efficiency

The function scales with heavy-atom count: add atoms, gain score, almost regardless of fit. In a
library ranked by raw affinity, the top is dominated by the largest molecules.

Report **ligand efficiency** alongside:

```
LE = affinity / heavy atoms          (more negative is better; ~ -0.3 is a useful fragment)
```

`parse_vina_output.py` computes it. For fragments (< 20 heavy atoms) LE is the only sensible
ranking; for a lead-like library, look at both and be suspicious of anything that ranks first on
raw score alone.

## Scoring functions

| `--scoring` | Needs | Notes |
|---|---|---|
| `vina` (default) | Receptor PDBQT | Maps computed internally; the general-purpose choice |
| `vinardo` | Receptor PDBQT | Reparameterised; often better pose prediction, different score scale |
| `ad4` | Precomputed `autogrid4` maps, `--maps` instead of `--receptor` | The AutoDock4 force field |

**Scores from different functions are not comparable with each other.** A −14 from `ad4` and a
−12 from `vina` say nothing about which pose is better. Pick one function for a campaign and
stay on it.

Vinardo is worth trying when Vina's poses look wrong; it changes the balance of the
hydrophobic and hydrogen-bond terms.

## Exhaustiveness and reproducibility

`--exhaustiveness` is the search effort. The default of **8 is too low for anything but a small
rigid ligand** — the AutoDock documentation says so itself for the imatinib tutorial, and
recommends 32.

- Cost is roughly linear in exhaustiveness.
- Larger boxes need more of it: the same effort spread over eight times the volume samples each
  region one eighth as densely.
- More rotatable bonds need more of it.

**The search is stochastic.** Two runs with the same inputs give different results unless you
pass `--seed`. Any docking result you intend to report should have a fixed seed recorded with
it, and any ranking that changes between seeds is not a ranking.

A practical convergence check: run the same ligand three times with different seeds. If the top
pose moves by more than 2 Å or the score by more than 1 kcal/mol, raise exhaustiveness.

## Reading the pose list

```
ligand  rank  affinity  ligandEfficiency  rmsd_lb  rmsd_ub  atEdge
lig1    1     -12.5     -0.34             0.000    0.000
lig1    2     -12.2     -0.33             1.234    2.345    +x
lig1    3     -9.1      -0.25             3.456    5.678
```

- `rmsd_lb` / `rmsd_ub` are that pose's RMSD from the **best** pose, so mode 1 is always 0.
  A large spread means several distinct binding modes were found; a small one means the search
  kept landing in the same place, which is a good sign.
- **`atEdge` is a failure flag.** Pose atoms touching the box wall mean the search was clipped —
  the real optimum may lie outside the box, and the reported score is an artefact of where you
  drew it. Enlarge or recentre and re-dock.
- A tiny gap between poses 1 and 2 (< 0.5 kcal/mol) means the top-ranked pose is not
  meaningfully distinguished from the runner-up. Inspect both.

## Validating a setup before trusting it

1. **Redock the native ligand.** Take a holo structure, remove the ligand, dock it back. RMSD to
   the crystal pose under 2 Å means the setup works. This is the single most informative hour in
   any docking project.
2. **Cross-dock** ligands from other structures of the same target into your receptor. Success
   here predicts screening performance far better than self-docking does.
3. **Decoy enrichment.** Mix known actives with property-matched decoys (DUD-E, DEKOIS) and check
   that actives enrich in the top ranks. Report enrichment factor or AUC — not "we found the
   actives".

Skipping all three and reporting scores is how docking gets its reputation.

## After docking

Vina's score is a filter, not an answer. Reasonable next steps, in increasing cost:

- **Rescoring** with a different function (Vinardo, RF-Score, or an ML scoring function) and
  keeping compounds that survive both.
- **Cofolding with affinity prediction** — the `boltz` skill's Boltz-2 affinity head is trained
  on measured data and answers a different question from a physics-style score.
- **Short MD of the top poses** — the `molecular-dynamics` skill. A pose that drifts out of the
  site in 10 ns was not a pose.
- **MM/GBSA rescoring** on MD snapshots: better than docking scores, far from free energy.
- **Alchemical free energy** for a congeneric series, when the series is worth it.

## Reporting

State: PDB id and preparation steps, box centre and size, scoring function, exhaustiveness,
seed, and the redocking RMSD that validated the setup. Give affinities with ligand efficiency,
and say explicitly that they are scoring-function estimates. A docking result without its box
and its seed is not reproducible.
