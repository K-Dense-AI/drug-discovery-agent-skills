# Chemical modification

An unmodified oligonucleotide is degraded by serum nucleases within minutes and does not enter
cells. The modification pattern is not a finishing touch — it is most of what makes the molecule a
drug.

## The modifications

| Code | Modification | Buys | Costs |
|---|---|---|---|
| **PS** | phosphorothioate backbone | nuclease resistance; protein binding that drives hepatic uptake | complement activation, thrombocytopenia, injection-site reactions |
| **2'-MOE** | 2'-O-methoxyethyl | high affinity, strong nuclease resistance, extensive precedent | blocks RNase H |
| **2'-OMe** | 2'-O-methyl | nuclease resistance, reduced immunostimulation | blocks RNase H; lower affinity than MOE |
| **LNA** | locked nucleic acid | very high affinity, so shorter oligos work | blocks RNase H; hepatotoxicity association |
| **cEt** | constrained ethyl | LNA-like affinity, better tolerability record | blocks RNase H |
| **2'-F** | 2'-fluoro | affinity and nuclease resistance; standard in siRNA | blocks RNase H |
| **5mC** | 5-methylcytosine | removes TLR9 agonism at CpG | essentially none |
| **GalNAc** | triantennary conjugate | ASGPR-mediated hepatocyte uptake; 10–30× potency | restricts delivery to liver |

**Every 2' modification blocks RNase H.** That single fact is why a gapmer exists at all.

## The gapmer architecture

```
5'  MOE MOE MOE MOE MOE | dC dG dA dT dC dG dA dT dC dG | MOE MOE MOE MOE MOE  3'
    <---- 5' wing ----> <--------- DNA gap ---------> <---- 3' wing ---->
         affinity              RNase H substrate            affinity
```

A **5-10-5 MOE gapmer** is the canonical design. The wings supply binding affinity and nuclease
resistance; the central DNA gap is what RNase H1 recognises.

**The gap must be at least about eight DNA residues.** Below that RNase H stops cleaving, and the
failure is silent — the molecule binds its target with excellent affinity and does nothing.
`chemistry_plan.py gapmer` refuses to emit a pattern with a shorter gap.

Higher-affinity wings (LNA, cEt) allow shorter wings and shorter oligos — a 3-10-3 LNA gapmer is
common. But a shorter oligo is inherently **less specific**, and LNA gapmers carry a documented
hepatotoxicity association. cEt was developed largely as a better-tolerated alternative.

5-methylcytosine at every CpG is standard and should be treated as mandatory: unmethylated CpG is
a TLR9 agonist and provokes an innate immune response.

## siRNA patterning is different

No DNA anywhere — RISC needs an RNA-like duplex. The standard pattern is **alternating 2'-OMe and
2'-F** across both strands, with **phosphorothioate at the termini only** rather than throughout.
The duplex is already nuclease-resistant and RISC-loaded, so full PS is unnecessary and its
tolerability cost is not worth paying.

Applying gapmer patterning to an siRNA is a category error and abolishes activity.

## Phosphorothioate is the central trade-off

PS replaces a non-bridging oxygen with sulfur. It does three things at once:

1. **Nuclease resistance** — the reason it is used.
2. **Plasma protein binding**, which prevents rapid renal clearance and drives uptake into liver
   and kidney. This is delivery, and it is why unconjugated ASOs reach the liver at all.
3. **The class tolerability profile** — the same protein binding causes complement activation,
   thrombocytopenia, and injection-site reactions.

Points 2 and 3 are the same mechanism. You cannot have the uptake without the liability, which is
why reducing PS content is a genuine and much-used tolerability lever, and why partial-PS designs
exist.

PS also creates a **stereocentre at every linkage**: a 20-mer full-PS oligo is a mixture of 2¹⁹
diastereomers. Stereopure synthesis is an active area (Wave Life Sciences built a platform on it),
with the argument that specific stereochemistry improves both potency and tolerability.

## GalNAc changed the field

Triantennary N-acetylgalactosamine binds the asialoglycoprotein receptor, which is expressed at
very high density on hepatocytes and recycles rapidly. Conjugating it gives **10–30-fold potency
gains** and makes subcutaneous dosing at monthly or quarterly intervals possible.

It is the single most important delivery advance in the field — and it delivers to the liver and
nowhere else. **Every approved siRNA to date targets a hepatic gene**, which is a statement about
delivery rather than about biology.

## Approved drugs as precedent

| Drug | Class | Chemistry | Target |
|---|---|---|---|
| Nusinersen | splice-switching ASO | full 2'-MOE PS | SMN2, intrathecal |
| Inotersen | gapmer ASO | 5-10-5 MOE PS | TTR |
| Eplontersen | gapmer ASO | MOE PS + GalNAc | TTR |
| Patisiran | siRNA | 2'-OMe, lipid nanoparticle | TTR |
| Givosiran, lumasiran, inclisiran, vutrisiran | siRNA | 2'-OMe/2'-F PS + GalNAc | hepatic |
| Eteplirsen | PMO | phosphorodiamidate morpholino | DMD exon 51 |

Two patterns worth reading off this table. **TTR appears four times** — it is hepatic, its
knockdown is well tolerated, and it validated both modalities. And **route follows delivery**:
intrathecal for CNS, LNP or GalNAc for liver, and essentially nothing for anywhere else.

## Morpholinos, briefly

PMOs replace the ribose-phosphate backbone entirely with morpholine rings and phosphorodiamidate
linkages. Uncharged, so no protein binding, no PS toxicity — and also poor cellular uptake, which
is why PMO doses are enormous. Used for splice switching in Duchenne muscular dystrophy.
