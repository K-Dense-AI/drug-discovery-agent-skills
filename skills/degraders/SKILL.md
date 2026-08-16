---
name: degraders
description: Work on bifunctional degraders and molecular glues, where potency comes from a ternary complex rather than occupancy. Use this skill to apply the property rules that govern this beyond-rule-of-five space, reason about linker length, attachment vector and E3 ligase choice, prepare inputs for ternary complex structure prediction, and interpret degradation readouts — DC50, Dmax, cooperativity, and the hook effect that makes a dose-response curve turn over. Also trigger on PROTAC, molecular glue, targeted protein degradation, E3 ligase, cereblon, VHL, ternary complex, DC50, Dmax, hook effect, cooperativity, or PROTAC-DB.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+. The bundled scripts implement degrader property rules, linker metrics, and ternary-complex input preparation using only the standard library. Predicting a ternary structure needs an external tool (PRosettaC, AlphaFold3, or DeepTernary) with its own licence and, in most cases, a GPU.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🔗"
    homepage: http://cadd.zju.edu.cn/protacdb/
  hermes:
    category: research
---

# Targeted Protein Degradation

A degrader does not inhibit a protein — it recruits an E3 ligase to it, the protein is destroyed,
and the degrader is released to do it again. That single change makes an "undruggable" target
tractable, because a degrader needs only a **binding site**, not a functional pocket. It is the
largest expansion of small-molecule target space in the last decade, and almost every
developability heuristic you know is calibrated for something else.

**No installation, no network, no key** for the bundled scripts — they implement the property
rules, linker arithmetic, and dose-response analysis. Ternary complex *prediction* needs an
external tool (PRosettaC, DeepTernary, AlphaFold3) with its own licence and usually a GPU.

Read [references/degrader-modalities.md](references/degrader-modalities.md) for how this
pharmacology differs, [references/ternary-complex.md](references/ternary-complex.md) before
modelling or designing a linker, and
[references/degrader-developability.md](references/degrader-developability.md) before judging a
molecule — **that one is judgement, not syntax.**

## The three scripts

| Script | Answers |
|---|---|
| `protac_properties.py` | Is this molecule inside the bRo5 habitable band? |
| `ternary_setup.py` | What do the prediction tools need, and what linker lengths do I make? |
| `degrader_triage.py` | What do DC50, Dmax, and the curve shape actually say? |

## Occupancy versus event

| | Inhibitor | Degrader |
|---|---|---|
| Requires | continuous occupancy | a transient encounter |
| Stoichiometry | 1:1 | **catalytic** |
| Removes | one function | the whole protein, scaffolding included |
| Duration | drug half-life | **protein resynthesis rate** |
| Needs | a functional pocket | **any ligandable surface** |

The last row is the point. No catalytic site, no allosteric mechanism, no functional consequence
of binding required — which is why `binding-site-analysis` names degradation first when a target
scores undruggable.

The duration row has a practical sting: a degrader can be fully cleared while its effect persists
for days, so the usual exposure-response framing does not transfer.

## Lipinski rejects every PROTAC

```bash
python skills/degraders/scripts/protac_properties.py windows
```

| Property | Window | Failure below | Failure above |
|---|---|---|---|
| MW | 700–1100 | not a complete bifunctional | permeability collapses |
| cLogP | 3–7 | too polar at this size | aggregation, promiscuity |
| TPSA | 150–250 | check the molecule is complete | passive permeability lost |
| Rotatable bonds | 8–20 | a degrader has a linker | entropic cost of the ternary complex |

**Every window is two-sided**, so optimising any of them in one direction is wrong. Filtering a
degrader series on Ro5 discards all of it, including the molecules that work.

**Permeability is the binding constraint and TPSA cannot see it.** Successful oral degraders are
molecular chameleons — polar in water, and in a membrane they fold to form intramolecular hydrogen
bonds that shield that polarity. Measure PAMPA or Caco-2; do not predict it.

## Model the right construct

**VHL does not fold without Elongin B/C. CRBN needs DDB1.** Predicting against the isolated domain
gives a complex that cannot exist:

```bash
python skills/degraders/scripts/ternary_setup.py manifest --target 6BOY --e3 vhl
python skills/degraders/scripts/ternary_setup.py tools
```

This is not pedantry. Benchmarking against curated crystallographic ternaries found **AlphaFold3's
apparent performance inflated by exactly those accessory proteins** contributing interface area
that has nothing to do with the degrader — while **PRosettaC outperforms it** on the
degrader-specific interface. Tool choice here disagrees with the obvious default.

The other setup trap: **the attachment atom is not the exit vector.** A linker must leave each
ligand from a solvent-exposed atom pointing at the partner. Buried atoms cannot be linked from,
whatever the docking says.

## Scan the linker; do not predict it

Length has a pair-specific window of roughly 4–20 heavy atoms. Too short and the proteins clash;
too long and the entropic cost of ordering the complex swamps the interface enthalpy.

```bash
python skills/degraders/scripts/ternary_setup.py linkers --min 4 --max 16 --chemistry peg
```

Find the window with a flexible PEG or alkyl series, **then** rigidify at the optimum — that is
where oral exposure comes from, and rotatable bonds are charged twice here, once against
permeability and once against cooperativity. Rigidifying first locks in a conformation before you
know which one you want.

## The hook effect breaks the dose-response

```bash
python skills/degraders/scripts/degrader_triage.py curve \
    --conc 0.1,1,10,100,1000,10000 --remaining 95,70,25,8,15,60
```

```
# HOOK EFFECT: degradation falls by 52.0 points above 100. At high concentration the
# degrader saturates both proteins separately, forming binary complexes that cannot
# become ternary.
dmax_pct  92.0
dc50      2.7826
```

**A sigmoid fit through a hooked curve returns a confident, meaningless DC50** — the script fits
the descending limb only. And "no hook observed" may just mean the range stopped two logs early.

**Dmax usually matters more than DC50.** DC50 1 nM at 40% leaves most of the protein; DC50 100 nM
at 95% removes it. Below ~50% degradation a phenotype is unlikely whatever the potency.

## Four things that surprise people

1. **Degradation potency need not track binary affinity.** A weaker binder forming a better
   ternary complex often degrades better. Ranking a series by target Kd is an expensive mistake.
2. **A complex that forms may not ubiquitinate.** Lysines must be presented to the E2 in the right
   geometry; forming the interface does not guarantee it.
3. **CRBN degrades IKZF1/3 whether you asked or not.** The IMiD scaffold brings its own
   neosubstrates.
4. **Off-target degradation has no inhibitor analogue.** Global proteomics is the standard
   selectivity experiment and there is no computational substitute. Run it early.

## Composing with the rest of the bundle

- `binding-site-analysis` → here: when the pocket scores undruggable, this is the first
  alternative — a degrader needs a binding site, not an inhibitory pocket.
- `rdkit` / `datamol` → before: compute the descriptors `protac_properties.py check` reads.
- `medchem` → carefully: its rule sets are calibrated for Ro5 chemistry and will reject degraders.
- `uniprot-rcsb` → before: co-crystal structures for both ligands, to read the exit vectors.
- `admet-prediction` → carefully: every public ADMET model is extrapolating on bRo5 chemistry.
- `pkpd-translation` → after, with a protein-turnover compartment added.

## Reporting results honestly

Give DC50 **and** Dmax, say whether a hook was seen and over what range, and give cooperativity if
measured. Name the E3 and the linker. Report permeability as measured, never inferred from TPSA.
Say whether global proteomics selectivity has been run. And when quoting property windows, call
them bRo5 conventions — the molecule is supposed to violate Lipinski.
