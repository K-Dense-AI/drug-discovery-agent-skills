# Installing and running OpenFE

The Open Free Energy toolkit, an open-source ecosystem for alchemical binding free energy
calculations. MIT, <https://openfree.energy>. Version 1.12 (June 2026).

## `pip install openfe` gets the wrong package

**Checked live: PyPI `openfe` is a 0.0.12 placeholder, unrelated to this toolkit.** Install from
conda-forge, docker, or singularity:

```bash
mamba create -n openfe -c conda-forge openfe
conda activate openfe
openfe --version
```

An NVIDIA GPU is effectively mandatory. A single edge is hours of molecular dynamics; on CPU it is
not worth attempting.

## What it computes

Alchemical free energy calculations transform one ligand into another inside the protein, and
separately in solvent, through a series of unphysical intermediate states indexed by λ. The
difference between the two legs gives the **relative binding free energy** ΔΔG:

```
ΔΔG_bind = ΔG_complex(A→B) − ΔG_solvent(A→B)
```

Because it is a thermodynamic cycle, the unphysical path does not matter — only the endpoints do.
That is what makes the method rigorous where a docking score is not: it computes a real
thermodynamic quantity from statistical mechanics, including entropy and explicit water.

## Protocols

| Protocol | Computes |
|---|---|
| `RelativeHybridTopologyProtocol` | RBFE between two similar ligands — the workhorse |
| **SepTop** | separated topologies; handles more dissimilar ligands |
| **ABFE** | absolute binding free energy; no partner ligand needed, more expensive and less precise |

RBFE is the default choice for a congeneric series. ABFE matters when there is nothing to
perturb *to* — a single ligand, or scaffolds too different to map.

## The workflow

```bash
# 1. plan a network over a ligand set
openfe plan-rbfe-network -M ligands.sdf -p protein.pdb -o network/

# 2. run each transformation (this is the expensive part)
openfe quickrun network/transformations/easy_rbfe_lig1_lig2.json -o results/lig1_lig2.json

# 3. collect the edges
openfe gather results/ -o ddg.tsv
```

Step 2 is embarrassingly parallel across edges and is what a cluster is for. `ddg.tsv` from step 3
is what `fep_report.py` reads.

## Atom mapping is where runs fail

A perturbation needs a correspondence between the atoms of A and B. OpenFE uses **LOMAP** or
**Kartograf** to generate mappings and score them.

A poor mapping — transforming too many atoms, or mapping across a ring — makes the alchemical path
long and the sampling poor, and the result will be wrong rather than merely imprecise. **Look at
the mappings before running.** OpenFE can render them, and it is the highest-value ten minutes in
the whole workflow.

Two perturbation classes to treat with suspicion:

- **Net charge changes.** Adding or removing a formal charge introduces finite-size artefacts that
  need explicit corrections. OpenFE 1.12 added net-charge support for membrane-bound systems, but
  these edges remain the least reliable in any network.
- **Large fragment transformations.** Growing a phenyl into a naphthyl is fine; swapping a whole
  scaffold is not. That is what SepTop exists for.

## The ecosystem

OpenFE pairs with a set of companion packages, all versioned together in a release:

| Package | Job |
|---|---|
| **LOMAP** | atom mapping and network planning by similarity |
| **Kartograf** | geometry-based atom mapping |
| **Konnektor** | network planning algorithms |
| **cinnabar** | analysis — maximum-likelihood ΔG estimation and plots |
| **openfe-analysis** | trajectory and convergence analysis |

**cinnabar matters for analysis.** It computes per-ligand free energies by maximum likelihood over
*all* paths, weighted by uncertainty, rather than following one path from a reference. The
`rank` command in `fep_report.py` follows a single path — enough to see the ordering, and it says
so — but cinnabar is the right tool for a final number.

## Settings that drive cost

| Setting | Typical | Effect |
|---|---|---|
| λ windows | 11–12 | more windows, better overlap, linear cost |
| sampling per window | 5 ns | the dominant cost |
| repeats | 3 | the only honest per-edge uncertainty |
| legs | 2 (complex, solvent) | both required for ΔΔG |

Roughly 24 GPU-hours per edge per repeat at these settings. `fep_network.py cost` does the
arithmetic; a 20-ligand cyclic network at three repeats is on the order of 2,800 GPU-hours.

**Do not run one repeat.** A single replicate gives an uncertainty from within-run sampling only,
which systematically understates the real spread.

## Alternatives

| Tool | Notes |
|---|---|
| **OpenFE** | open source, actively developed, the default open choice |
| **FEP+** (Schrödinger) | commercial, the industry benchmark, extensively validated |
| **BioSimSpace / FESetup** | open, wraps GROMACS/AMBER/SOMD |
| **PMX** | open, GROMACS-based, strong for non-equilibrium approaches |
| **Amber TI / GROMACS FEP** | run it yourself; maximal control, maximal setup burden |

Published accuracy for well-behaved congeneric series clusters around 1–1.5 kcal/mol RMSE across
all of these — which is roughly a five- to tenfold error in affinity, and is a genuine ceiling
imposed by force fields rather than by any one implementation.
