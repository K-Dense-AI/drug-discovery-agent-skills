# Designing a perturbation network

The network is the experiment design. It fixes the cost, and it decides whether the answer can be
checked at all.

## Topologies

For N ligands:

| Shape | Edges | Cycles | Trade-off |
|---|---|---|---|
| **Star** | N−1 | 0 | cheapest; **no internal validation whatsoever** |
| **Cyclic** | ~2N−1 | ~N | roughly double the cost, every ligand checkable |
| **Complete** | N(N−1)/2 | many | maximal redundancy, affordable only for tiny sets |

The number of independent cycles is the **circuit rank**: `edges − nodes + components`. For a
5-ligand cyclic network that is 8 − 5 + 1 = **4** independent checks; a star gives 4 − 5 + 1 = **0**.

`fep_network.py plan` reports this, and warns when it is zero.

## Why cycles are not optional

Free energy is a **state function**: the change around any closed loop must be exactly zero. It
never is, and the deviation — the hysteresis — is a direct measure of the calculation's error that
depends on **no assumptions at all**. It needs no experimental data, no reference, and no model of
what the error should be.

That makes it the single most valuable diagnostic FEP has, and a star map forfeits it entirely.

Worked, from `fep_report.py cycles`:

```
cycle             length  closure_kcal  acceptable
a -> b -> c -> a  3       0.5           true
```

Edges of +1.0, +1.0, and −1.5 sum to +0.5 rather than zero. That 0.5 kcal/mol is real error in
those three edges, visible without any experimental measurement.

Consequence for interpretation: **a per-ligand ΔG depends on which path you take from the
reference**, and different paths disagree by exactly the closure error. `fep_report.py rank`
follows one path and says so; cinnabar computes a maximum-likelihood estimate over all paths.

## Choosing edges: similarity beats topology

Topology decides how many checks you get. **Chemical similarity decides whether each edge
converges at all.**

A perturbation between two closely related ligands — one methyl added — converges quickly and
reliably. A perturbation between distant ligands may not converge in any affordable amount of
sampling, and will return a confident wrong number rather than an error.

This is why OpenFE's planners (LOMAP scorer, minimal spanning network, Konnektor) select edges by
mapping quality rather than by graph shape. Use them. The topologies in `fep_network.py` are for
reasoning about cost and validation structure, not for overriding a similarity-based planner.

Practical rule: an edge should change **fewer than about ten heavy atoms**, and should not change
the ring system.

## The reference ligand carries a star map

In a star, every result is relative to one compound, so the reference must be:

- **well posed** — ideally with a crystal structure, since the whole network inherits its binding
  mode;
- **chemically central** — similar to everything else, so all mappings are good;
- **experimentally solid** — a well-measured affinity, since the absolute anchor comes from it;
- **not an outlier** — unusual chemistry propagates its problems everywhere.

Getting this wrong corrupts the entire map, and cycle closure cannot detect it because there are
no cycles.

## Perturbations to treat with suspicion

**Net charge changes.** Adding or removing a formal charge introduces finite-size electrostatic
artefacts requiring explicit correction. These edges are consistently the least reliable in any
network. Where possible, route around them: connect two neutral ligands directly rather than
through a charged intermediate.

**Ring opening, closing, or resizing.** The mapping has nowhere sensible to put the atoms.

**Large fragment growth.** Beyond roughly ten heavy atoms, use SepTop or split into two edges
through an intermediate — even a hypothetical one you have no data for, since it cancels out.

**Anything with a different binding mode.** FEP assumes both ligands occupy the same pose. If B
flips relative to A, the calculation is meaningless, and nothing in the output will say so. This is
the failure mode that most often produces a confident wrong answer.

## Budgeting

```bash
python fep_network.py cost --edges 24 --gpus 4
```

At roughly 24 GPU-hours per edge per repeat and three repeats, a 20-ligand cyclic network is
around 2,800 GPU-hours — several weeks on four GPUs.

That cost is the whole reason FEP sits where it does in a programme: it is for the twenty
compounds you are choosing between, after docking has narrowed millions to hundreds. Using it
earlier is a category error.

**Three repeats minimum.** A single replicate reports only within-run sampling error and
systematically understates the real spread.

## A practical recipe

1. Start from a **crystal structure** with a bound ligand, and use that ligand as the reference.
2. Let LOMAP or Konnektor plan the edges by similarity.
3. **Add cycles** if the planner produced a tree — the extra edges buy your only error check.
4. **Look at the atom mappings** before committing GPU time.
5. Run **three repeats** per edge.
6. Check **cycle closure** before looking at any result.
7. Compare against experiment on the subset you have data for, offset-corrected.
8. Only then use the ranking to choose what to make.
