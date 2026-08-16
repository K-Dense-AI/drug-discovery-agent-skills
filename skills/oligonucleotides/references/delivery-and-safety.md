# Delivery is the whole problem

Judgement, not syntax. Designing a potent oligonucleotide is a solved problem. Getting it into the
cell you care about is not, and it is the reason this modality is confined to a handful of tissues.

## Why delivery is hard

An oligonucleotide is large (~7 kDa), highly negatively charged, and hydrophilic. Every property
that makes it bind its target makes it unable to cross a membrane. Unmodified, it is also cleared
renally within minutes.

The consequence is stark: **every approved siRNA targets a hepatic gene**. That is a fact about
delivery, not about which diseases are worth treating.

## Where oligonucleotides currently reach

| Tissue | Route | Status |
|---|---|---|
| **Liver** | GalNAc conjugate, subcutaneous | solved; multiple approvals |
| **CNS** | intrathecal | works, but requires intrathecal dosing |
| **Eye** | intravitreal | works, local administration |
| **Kidney** | PS accumulation | partial, and dose-limited by tubular toxicity |
| **Muscle** | — | poor; the central obstacle in Duchenne |
| **Lung** | inhaled | in development |
| **Tumour** | — | poor |
| **Everywhere else** | — | unsolved |

The liver is easy for two convergent reasons: ASGPR is hepatocyte-specific, expressed at very high
density, and recycles rapidly; and the liver receives a large fraction of cardiac output through a
fenestrated endothelium.

Approaches for other tissues — antibody conjugates, peptide conjugates, lipid nanoparticles beyond
the liver, exosomes — are active and none is yet reliable.

## The safety profile is class-based and predictable

**Hepatotoxicity** is the main dose-limiting toxicity for gapmer ASOs. Two mechanisms, and they
need different fixes:

- **RNase H off-target cleavage.** A contiguous 12–14 nucleotide match elsewhere in the
  transcriptome is enough. Fixed by design — `offtarget_scan.py contig`.
- **Non-hybridisation-dependent toxicity**, associated with high-affinity chemistry, especially
  LNA. Not fixable by sequence; fixed by changing chemistry, and one reason cEt exists.

**Thrombocytopenia**, seen with several PS ASOs and the reason inotersen carries platelet
monitoring. Related to PS content and protein binding.

**Complement activation**, particularly in non-human primates. Largely PS-driven, and a
recognised cause of tox findings that do not translate cleanly to humans.

**Injection-site reactions**, near-universal for subcutaneous PS oligonucleotides.

**Innate immune activation** through TLR9 (unmethylated CpG) and TLR7/8 (specific single-stranded
motifs). Largely designed out by 5-methylcytosine and 2' modification, but worth checking.

**Renal tubular accumulation.** PS oligonucleotides concentrate in the proximal tubule; usually
tolerated, occasionally dose-limiting.

Notice how many of these trace to phosphorothioate. It is simultaneously what makes the modality
work and what limits its dose.

## Off-target silencing, honestly

Two distinct problems:

**Seed-mediated (siRNA).** Antisense positions 2–8 pairing with a 3' UTR gives microRNA-like
repression. A 7-mer hits hundreds of transcripts in any transcriptome, so **zero is not
achievable**. Mitigations: choose the least-bad seed comparatively, chemically modify position 2
to reduce seed pairing, or use seed-mismatch controls to distinguish on- from off-target effects
experimentally.

**RNase H-mediated (ASO).** Partial complementarity is enough. More tractable by design than
seed effects, because it needs a longer match.

For both, the essential control is a **panel of oligonucleotides against the same target**. If
five sequences with different seeds all produce the phenotype, it is on-target. If one does, it
probably is not. This control is worth more than any computational prediction.

## What computation can and cannot do here

**Can**: tile a transcript, apply thermodynamic and composition rules, rank seeds by promiscuity,
find contiguous off-target matches, and lay out a modification pattern. This skill does all of that
and it is genuinely useful triage.

**Cannot**: predict target site accessibility in a folded, protein-coated transcript — which
dominates in practice; predict delivery to any tissue; predict hepatotoxicity that is not
sequence-driven; or predict potency. Published hit rates for rule-compliant designs run around one
in three to one in ten.

So the deliverable from a design exercise is **a panel of 20–50 to synthesise and screen**, never
a single molecule. Anyone promising a designed oligonucleotide that will work is overselling.

## Choosing the modality

**siRNA** when: the target is hepatic, the transcript is cytoplasmic mRNA, and you want long
duration — GalNAc siRNA supports quarterly dosing.

**Gapmer ASO** when: the target is nuclear, intronic, or a non-coding RNA; or the tissue is CNS
(intrathecal); or you need a shorter-acting agent.

**Splice-switching ASO** when: the goal is to redirect splicing rather than degrade the transcript
— exon skipping or inclusion. Fully modified by design, with no RNase H recruitment.

**Something else entirely** when the tissue is not liver, CNS, or eye. That is the honest answer
more often than the field's enthusiasm suggests.

## Reporting

Say which modality and why. Give the design rules applied and note that they are necessary rather
than sufficient. State that accessibility is not modelled. Give seed off-target counts
comparatively, never as an absolute. Name the tissue and the delivery route, and if it is not
liver, CNS, or eye, say plainly that delivery is unsolved. Recommend a panel and a seed-mismatch
control, not a molecule.
