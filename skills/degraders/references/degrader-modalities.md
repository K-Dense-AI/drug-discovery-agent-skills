# Degraders: event-driven pharmacology

A degrader does not inhibit a protein. It recruits an E3 ubiquitin ligase to it, the protein is
ubiquitinated and destroyed by the proteasome, and the degrader is released to do it again.

That difference has consequences that reach every part of the design.

## Occupancy versus event

| | Inhibitor | Degrader |
|---|---|---|
| Requires | continuous occupancy | a transient encounter |
| Stoichiometry | 1:1 | catalytic |
| Removes | one function | the whole protein, including scaffolding |
| Duration of effect | drug half-life | protein resynthesis rate |
| Needs | a functional pocket | any ligandable surface |

**The last row is why this matters.** An inhibitor needs a pocket whose occupancy blocks
catalysis. A degrader needs only a binding site good enough to bring the E3 close — no catalytic
site, no allosteric mechanism, no functional consequence of binding required. That is the single
largest expansion of target space in modern small-molecule discovery, and it is why
`binding-site-analysis` lists degradation as the first alternative when a target scores
undruggable.

**Removing the whole protein removes scaffolding function too.** Many proteins do things that have
nothing to do with their enzymatic activity, and an inhibitor leaves those intact. Sometimes that
is the therapeutic advantage; sometimes it is unexpected toxicity.

**Duration is set by resynthesis, not by pharmacokinetics.** A protein with a 48-hour half-life
stays depleted long after the degrader has cleared, which can decouple dosing interval from plasma
exposure entirely. It also means the relevant PK question is different from the usual one — see
`pkpd-translation` for why the standard exposure metrics do not transfer.

## Two designs

**PROTACs / bifunctional degraders.** Target ligand + linker + E3 ligand, designed deliberately.
Large (700–1100 Da) and hard to make orally available, but rationally designable: you choose the
target ligand, the E3, and the geometry.

**Molecular glues.** Small molecules that induce a protein-protein interaction between an E3 and a
neosubstrate without being bifunctional. Lenalidomide and CRBN degrading IKZF1/3 is the canonical
case. **Drug-like in size and properties** — which is their great advantage — but historically
discovered by accident rather than designed. Rational glue discovery is an active field and not
yet routine.

If a glue can be found for your target it is the better molecule. Finding one is the problem.

## The E3 ligases

Roughly 600 human E3 ligases exist. **Fewer than ten have usable chemical matter**, and two
dominate:

| E3 | Ligand | Ligand MW | Notes |
|---|---|---|---|
| **CRBN** | thalidomide / pomalidomide / lenalidomide analogues | ~250–300 Da | small and comparatively permeable; leaves the most property budget |
| **VHL** | VH032 and analogues | ~450–500 Da | large and polar; spends most of the budget itself. Extensively characterised structurally |
| IAP | LCL161 / SMAC mimetics | ~450–550 Da | E3 auto-degradation is a recurring problem |
| MDM2 | nutlin analogues | ~500–600 Da | p53 engagement confounds the phenotype |
| DCAF15 | indisulam-type | ~350 Da | molecular glue rather than bifunctional |
| DCAF1 | recent | ~400 Da | newer; different tissue expression profile |

The E3 choice is made before the linker is drawn and it fixes much of the property budget. It also
fixes the biology:

- **Tissue expression.** CRBN and VHL are broadly expressed, which is convenient and also means no
  tissue selectivity. An E3 restricted to one tissue would give targeting for free, and that is a
  major motivation for expanding the ligase toolbox.
- **CRBN's own neosubstrates.** IMiD scaffolds degrade IKZF1/IKZF3 whether or not you asked. In
  haematology that is a therapeutic bonus; elsewhere it is an off-target effect built into the
  scaffold.
- **Resistance.** Loss of the E3 is a straightforward resistance mechanism, observed in the clinic
  for CRBN-dependent agents.

## Reading a degradation experiment

**DC50** — concentration for 50% degradation. **Dmax** — maximum degradation achieved. They are
independent, and **Dmax usually matters more**: DC50 1 nM with Dmax 40% leaves most of the
protein, while DC50 100 nM with Dmax 95% removes it. Below about 50% degradation a phenotype is
unlikely whatever the DC50.

**Degradation potency need not track binary affinity.** Because the mechanism is catalytic and
depends on ternary complex formation, a weaker target binder that forms a better ternary complex
frequently degrades better. Ranking a degrader series by target Kd is a common and expensive
mistake.

**The hook effect** makes the dose-response non-monotonic — see
[ternary-complex.md](ternary-complex.md).

**Washout and recovery** matter as much as depth. How fast does the protein come back? That sets
the dosing interval, and it is measured, not predicted.

## Where the modality stands

Approved: none as of this writing. In the clinic: ARV-471 (vepdegestrant, ER), ARV-110
(bavdegalutamide, AR), and a substantial pipeline behind them, mostly oncology, mostly CRBN or VHL.

The open problems are oral bioavailability, expanding beyond two E3 ligases, tissue selectivity,
and rational molecular glue discovery.
