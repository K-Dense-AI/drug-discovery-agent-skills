# What an FEP number is worth

Judgement, not syntax. FEP is the most rigorous affinity prediction available in routine practice,
and it is still wrong by a factor of five to ten.

## The accuracy ceiling

Across well-behaved congeneric series, published RMSE against experiment clusters around
**1–1.5 kcal/mol**, for OpenFE, FEP+, and everything else. That is not an implementation gap; it
is the force fields.

What 1 kcal/mol means in practice, at 298 K:

| Error | Affinity factor |
|---|---|
| 0.5 kcal/mol | 2.3× |
| 1.0 kcal/mol | 5.4× |
| 1.4 kcal/mol | 10× |
| 2.0 kcal/mol | 29× |

So FEP can reliably separate a 10 nM compound from a 1 µM one. It cannot reliably separate 10 nM
from 30 nM, and reporting a rank order within that gap is over-reading the method.

This is still transformative relative to docking, whose scores correlate with affinity so weakly
that rank-ordering a congeneric series is barely better than chance.

## The three error estimates, and what each misses

**Per-edge uncertainty** (from repeats, or from MBAR). Measures how well the sampling converged.
Says nothing about whether the force field is right, so a tight uncertainty on a wrong number is
entirely normal. Necessary, not sufficient.

**Cycle closure.** Measures self-consistency without any experimental data or assumption. Catches
sampling problems and bad mappings that per-edge uncertainty hides. A network without cycles has
none of this.

**Error against experiment.** The real test, available only where you have measurements — which
is, by definition, not the compounds you are trying to predict.

A run that passes all three is trustworthy. A run reporting only the first is reporting the least
informative one.

## Comparing to experiment

Relative FEP gives differences, so there is no absolute anchor. Comparison requires an **offset
correction**: shift the predicted values so the means match, then compute MUE and RMSE.
`fep_report.py rank --experimental` does exactly this and says so.

Two conversions to be careful about:

**IC50 to free energy.** `ΔG = RT·ln(IC50)` assumes IC50 tracks Kd, which requires the assay to be
at equilibrium and the substrate concentration to be well below Km (Cheng-Prusoff). Neither always
holds. Ki or Kd is preferable where available.

**Assay data mixed across sources.** Combining IC50 values from different labs, formats, and
substrate concentrations introduces spread that will be attributed to your calculation. Use one
assay, or say plainly that you did not.

Metrics worth reporting together: **MUE** (interpretable, in kcal/mol), **RMSE** (penalises the
large misses that matter), and **Kendall tau or Spearman** (rank correlation, which is often what
the decision actually needs).

## When FEP fails, and how it looks

The failures are not random noise — they are systematic and they produce confident numbers:

**Different binding mode.** FEP assumes both ligands bind the same way. If B flips, the answer is
meaningless and nothing in the output signals it. The most dangerous failure available.

**Protonation state changes.** If A and B have different dominant ionisation states at pH 7.4, the
transformation is not the one you think. Check pKa first — `rowan` in this bundle predicts it.

**Slow conformational change.** If the protein must rearrange to accommodate B, and that
rearrangement is slower than the simulation, the calculation samples the wrong ensemble.
Buried water networks are a common instance: an ordered water that leaves on binding may not leave
within the simulation.

**Net charge changes.** Finite-size electrostatic artefacts requiring explicit correction. The
least reliable class of edge in any network.

**Force field gaps.** Halogen bonds, metal coordination, unusual heterocycles, and strong
polarisation are all approximated by fixed-charge force fields.

## Where FEP belongs in a programme

Cost places it precisely. GPU-days for tens of compounds, where docking is seconds for millions:

```
chemical-space  →  10^9 compounds, docking score, seconds each
autodock-vina   →  10^4 compounds, poses, minutes each
FEP             →  10^1 compounds, ΔΔG, GPU-days each
synthesis       →  10^1 compounds, real data, weeks each
```

FEP sits immediately before synthesis, deciding which of twenty analogues to make. That is where
a 5× accuracy on relative potency changes a decision, and where GPU-days are cheaper than
chemist-weeks.

Using FEP earlier is a category error; using docking to choose between twenty close analogues
wastes the opportunity.

## Prerequisites often skipped

- **A crystal structure**, ideally with a ligand from the series. FEP inherits the binding mode
  it is given; a docked pose propagates its error into every edge.
- **A congeneric series.** Ligands must be similar enough to map. Scaffold hops need SepTop or
  ABFE.
- **Some experimental data** in the set, to validate against.
- **Correct protonation and tautomers** for every ligand.

`uniprot-rcsb` for the structure and its quality, `binding-site-analysis` to confirm the pocket.

## Reporting

Give ΔΔG with its uncertainty, the number of repeats, and the cycle closure RMS. State the
reference ligand and that values are relative to it. When comparing to experiment, say the
comparison is offset-corrected, give MUE and a rank correlation, and name the assay. Say which
edges changed net charge.

And frame the precision honestly: "predicted 0.8 kcal/mol more potent, which is roughly fourfold,
against a method RMSE of about 1 kcal/mol" is a true statement. "Predicted 4-fold more potent" is
not.
