# The ternary complex

Everything distinctive about degrader pharmacology follows from needing **three** bodies —
target, degrader, and E3 — rather than two.

## Cooperativity

The degrader binds each protein separately, but the complex that matters is all three together.
Cooperativity measures whether the two proteins help or hinder each other:

```
α = Kd(binary) / Kd(ternary)
```

- **α > 1** — positive cooperativity. Protein-protein contacts stabilise the complex, so the
  ternary complex forms more readily than either binary interaction predicts.
- **α ≈ 1** — no cooperativity. The complex is just the two binary events happening at once.
- **α < 1** — negative cooperativity. The proteins clash, and the complex forms worse than
  expected.

Positive cooperativity is the single most useful ternary-complex number, and it is measurable —
by ITC, TR-FRET, or SPR — rather than merely predictable. It explains why weak binders can be
excellent degraders, and it is the main lever a linker has.

## The hook effect

The characteristic non-monotonic dose-response. At low concentration, degradation rises as
expected. Past an optimum it **falls**, because the degrader now saturates both proteins
separately:

| Regime | Dominant species | Degradation |
|---|---|---|
| below DC50 | free degrader, some binary | rising |
| around Dmax | ternary complex | maximal |
| above the hook | two separate binary complexes | falling |

Once degrader concentration exceeds both binding sites, target-degrader and E3-degrader
complexes outnumber target-degrader-E3, and there is nothing left to bridge.

Three practical consequences:

1. **A sigmoid fit through a hooked curve returns a confident, meaningless DC50.**
   `degrader_triage.py curve` fits the descending limb only, and says when it detected a hook.
2. **You must test high enough to see it.** No hook within the tested range may mean there is
   none, or that you stopped two logs too early.
3. **Positive cooperativity pushes the hook to higher concentration** and widens the useful
   window, which is another reason α matters.

The hook is also a dosing problem in vivo: more drug is not always more effect, and the
therapeutic window has a ceiling that is not a toxicity ceiling.

## Predicting the structure

The complex is a protein-protein interface induced by a flexible small molecule, which makes it
harder than either docking or protein-protein prediction alone.

| Tool | Approach | Note |
|---|---|---|
| **PRosettaC** | Rosetta PPI docking constrained by both anchored ligands | outperforms AlphaFold3 on curated PROTAC benchmarks |
| **DeepTernary** | SE(3)-equivariant encoder, query-based decoder, trained on TernaryDB | state of the art on PROTAC benchmarks, and fast |
| **AlphaFold3** | end-to-end with ligands | see the caveat below |
| **SILCS-xTAC** | ensemble-based, from SILCS maps | models the complex as an ensemble rather than one pose |
| **PROTAC-Model** | FRODOCK + RosettaDock | open and scriptable |

**The AlphaFold3 caveat is important.** Benchmarking against curated crystallographic ternary
complexes found its apparent performance inflated by accessory proteins — Elongin B/C for VHL,
DDB1 for CRBN — contributing large interface areas that have nothing to do with the degrader. The
model gets credit for assembling a complex it partly memorised, while the degrader-specific
interface is predicted less well.

Which leads to the setup rule below.

## Model the right construct

**VHL does not fold without Elongin B and Elongin C.** **CRBN functions as part of a complex with
DDB1.** Predicting against the isolated domain produces a complex that cannot exist, and including
the accessory subunits is not optional.

`ternary_setup.py manifest` records which subunits each E3 needs, with a reference PDB
(VHL: 5T35 with Elongin B/C; CRBN: 4TZ4 with DDB1).

## Exit vectors and linker geometry

**The attachment atom is not the same as an exit vector.** A linker must leave each ligand from an
atom that is solvent-exposed *and* points toward the partner protein. An atom buried in the
binding pocket cannot be linked from, however well the docking pose scores.

Getting the vectors right is done by inspecting the two co-crystal structures, and it is the
step that most often makes a linker series fail before it starts.

**Linker length has a pair-specific window**, typically 4–20 heavy atoms:

- **Too short** — the proteins clash, and no productive complex forms.
- **Too long** — the entropic cost of ordering a floppy complex swamps the enthalpy of the
  interface, and cooperativity falls toward or below 1.

There is no way to predict the optimum reliably, which is why **scanning a length series is the
standard first experiment**. `ternary_setup.py linkers` generates one.

## Linker chemistry

| Chemistry | Trade-off |
|---|---|
| **PEG** | flexible and soluble; the default first series. Costs rotatable bonds and entropy |
| **Alkyl** | flexible and lipophilic; better permeability, worse solubility |
| **Rigid** (piperazine, piperidine, spiro, alkyne) | fewer rotatable bonds, better exposure — but the geometry must already be right |
| **Triazole** | click chemistry, so a series is fast to make; adds polarity and rigidity |

The usual progression is a flexible PEG or alkyl series to find the length window, then
rigidification at the optimum to recover the rotatable bonds — which is where oral exposure comes
from. Rigidifying before the geometry is known simply locks in the wrong conformation.

## What to measure

Structure prediction is a hypothesis generator here, not an answer. The measurements that decide:

- **Cooperativity (α)** by ITC or TR-FRET.
- **Ternary complex formation** by TR-FRET, AlphaScreen, or SPR.
- **Ubiquitination** in vitro, which confirms the complex is productive rather than merely formed.
- **Degradation** in cells: DC50, Dmax, and a washout time course.

A complex that forms but does not ubiquitinate is a real and common outcome — the lysines must be
presented to the E2 in the right geometry, and forming the interface does not guarantee it.
