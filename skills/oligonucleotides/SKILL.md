---
name: oligonucleotides
description: Design small interfering RNA and antisense oligonucleotide sequences against a transcript, and screen them for the failure modes specific to nucleic-acid drugs. Use this skill to tile a target transcript, apply positional and thermodynamic selection rules including duplex asymmetry and nearest-neighbour melting temperature, scan candidates for seed-region complementarity to off-target transcripts, and lay out a chemical modification pattern — gapmer architecture, 2'-O-methyl and 2'-MOE wings, locked nucleic acid, and phosphorothioate placement. Also trigger on siRNA, antisense oligonucleotide, ASO, gapmer, RNase H, seed region, duplex asymmetry, 2'-MOE, locked nucleic acid, phosphorothioate, or GalNAc conjugate.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+ only. Sequence tiling, nearest-neighbour thermodynamics, and seed-match scanning are implemented in the standard library, so there is no install and no network access. Transcriptome-wide off-target scanning needs a local FASTA file that you supply; no reference sequence is bundled.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🧵"
    homepage: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7822268/
  hermes:
    category: research
---

# Oligonucleotide Therapeutics

The modality that sidesteps the protein entirely. If a target has no druggable pocket, no
extracellular epitope, and no ligandable cysteine, an siRNA or antisense oligonucleotide can still
silence its transcript — and the design is sequence arithmetic rather than chemistry intuition.

**No installation, no network, no key.** Sequence tiling, nearest-neighbour thermodynamics, and
seed scanning are implemented in the standard library. Transcriptome-wide off-target scanning
needs a FASTA that you supply.
**Thermodynamics:** SantaLucia (1998) unified nearest-neighbour parameters.

Read [references/sirna-and-aso-design.md](references/sirna-and-aso-design.md) before choosing a
site, [references/chemical-modifications.md](references/chemical-modifications.md) before drawing
a pattern, and [references/delivery-and-safety.md](references/delivery-and-safety.md) before
committing to the modality — **that one is judgement, not syntax, and it is where programmes
fail.**

## The three scripts

| Script | Answers |
|---|---|
| `oligo_design.py` | Which sites, and are their thermodynamics right? |
| `offtarget_scan.py` | What else will this silence? |
| `chemistry_plan.py` | What modifications, and where? |

## Two mechanisms, two incompatible rule sets

**siRNA** loads into Argonaute-2 and is cleaved by RISC in the **cytoplasm** — it needs an
RNA-like duplex throughout. **Gapmer ASO** recruits **RNase H1**, works in the **nucleus**, and
needs an unmodified DNA core.

Two consequences. ASOs can target **introns and pre-mRNA**; siRNA cannot, because RISC only sees
mature mRNA. And the chemistry is not interchangeable: a DNA gap in an siRNA breaks Argonaute
loading, while fully modifying an ASO silently removes RNase H recruitment — the molecule binds
its target beautifully and does nothing.

## Duplex asymmetry decides which strand is loaded

The siRNA rule that matters most. RISC keeps the strand whose **5' end is less thermodynamically
stable**. Get it backwards and RISC loads the sense strand, silences something else, and your
molecule looks simply inactive — sending you to hunt for delivery problems that do not exist.

```bash
python skills/oligonucleotides/scripts/oligo_design.py tile --sequence ACGT... --modality sirna
```

```
position  sense                  antisense              gc     tm_c  asymmetry  antisense_loaded  seed     passes  flags
12        CGTCCAGATCGGATCCAAGTT  AACTTGGATCCGATCTGGACG  0.524  73.5  3.2        true              ACTTGGA  true
10        TACGTCCAGATCGGATCCAAG  CTTGGATCCGATCTGGACGTA  0.524  72.6  2.4        true              TTGGATC  false   as_pos1_not_au
```

The thermodynamics are the SantaLucia 1998 unified parameters and reproduce the paper's worked
example exactly — CGTTGA gives ΔH = −41.2 kcal/mol and ΔS = −115.4 cal/mol/K.

**GC content is a window, not a direction.** Below ~30% the duplex is too weak to hybridise; above
~60% it is too stable for RISC to unwind. Optimising GC upward is a common silent error.

## Zero off-targets is not achievable

Antisense positions **2–8** are the seed, and seed pairing with a 3' UTR gives microRNA-like
repression with no full-length complementarity at all. A full-length aligner scores that as a
non-hit, which is why BLAST is the wrong tool here.

A 7-mer occurs often enough to hit hundreds of transcripts in any real transcriptome. The useful
question is comparative:

```bash
python skills/oligonucleotides/scripts/offtarget_scan.py seeds --antisense AACTTGG... --fasta tx.fa
python skills/oligonucleotides/scripts/offtarget_scan.py contig --antisense AACTTGG... --fasta tx.fa
```

`contig` searches the other risk: RNase H cleaves on **partial** complementarity, so a contiguous
12–14 nt match elsewhere is a real gapmer hepatotoxicity liability.

## The gap must be at least eight DNA residues

```bash
python skills/oligonucleotides/scripts/chemistry_plan.py gapmer --sequence GCTAGCTACGTAGCTAGCTA \
    --wing moe --wing-length 5
```

```
# 5-10-5 gapmer, MOE wings
# pattern: WWWWWddddddddddWWWWW
# 10 nt DNA gap -- RNase H needs at least ~8 to cleave the heteroduplex
# 1 CpG site(s) marked for 5-methylcytosine. Unmethylated CpG is a TLR9 agonist; this is not optional.
```

Every 2' modification blocks RNase H, which is the entire reason gapmers have an unmodified core.
The script refuses to emit a short gap, because that failure is silent.

**Phosphorothioate is the central trade-off.** It gives nuclease resistance *and* the plasma
protein binding that drives hepatic uptake — and that same protein binding causes complement
activation, thrombocytopenia, and injection-site reactions. The delivery and the toxicity are one
mechanism.

## Delivery is the whole problem

**Every approved siRNA targets a hepatic gene.** That is a fact about delivery, not about biology.
GalNAc conjugation gives 10–30× potency into hepatocytes via ASGPR and nothing anywhere else.

| Tissue | Status |
|---|---|
| Liver | solved — GalNAc, subcutaneous, multiple approvals |
| CNS | works, intrathecal |
| Eye | works, intravitreal |
| Muscle, lung, tumour, elsewhere | unsolved |

If the target tissue is not liver, CNS, or eye, say so before designing anything.

## Four ways this misleads

1. **Accessibility dominates and is not modelled here.** mRNA is folded and protein-coated; a
   thermodynamically perfect site inside stable secondary structure is inaccessible. Use ViennaRNA
   or SHAPE data, or tile densely and screen.
2. **The rules are necessary, nowhere near sufficient.** Published hit rates for rule-compliant
   designs run one in three to one in ten.
3. **A single designed molecule is not a deliverable.** Synthesise and screen 20–50.
4. **The essential control is a panel with different seeds.** If five sequences produce the
   phenotype it is on-target; if one does, it probably is not. Worth more than any prediction here.

## Composing with the rest of the bundle

- `binding-site-analysis` → here: when a target has no druggable pocket, this is one of the
  remaining routes.
- `target-safety` → before: knocking down a constrained gene carries the same warning as
  inhibiting one.
- `degraders` → alongside: the other way to act on an "undruggable" target, at the protein level
  rather than the transcript.
- `pkpd-translation` → after: oligonucleotide PK is unusual — tissue half-lives of weeks decouple
  plasma exposure from effect.

## Reporting results honestly

Say which modality and why. Give the rules applied and note they are necessary, not sufficient.
State that accessibility is not modelled. Report seed off-target counts comparatively, never as an
absolute. Name the tissue and route, and if it is not liver, CNS, or eye, say plainly that
delivery is unsolved. Recommend a panel and a seed-mismatch control — not a molecule.
