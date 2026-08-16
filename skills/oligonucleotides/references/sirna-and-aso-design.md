# siRNA and ASO: two mechanisms, two sets of rules

Both silence a transcript. They do it by different machinery, in different compartments, and the
design rules follow from that rather than from convention.

## The mechanisms

**siRNA** — a 21-nucleotide double-stranded RNA. One strand is loaded into Argonaute-2 within the
RISC complex; the loaded strand guides RISC to a complementary mRNA, which Ago2 cleaves
catalytically. **Cytoplasmic**, catalytic, and it needs an RNA-like duplex throughout.

**Gapmer ASO** — a 16–20 nucleotide single strand with a central DNA core. The DNA core paired with
target RNA forms a heteroduplex, which **RNase H1** recognises and cleaves. **Nuclear and
cytoplasmic**, and it needs an unmodified DNA gap.

Two consequences that decide everything downstream:

- **ASOs can target pre-mRNA and introns**, because RNase H1 is nuclear and acts before splicing.
  siRNA cannot — RISC only sees mature cytoplasmic mRNA. If the target is an intron, a splice
  junction, or a nuclear non-coding RNA, the answer is an ASO.
- **Applying gapmer chemistry to an siRNA abolishes it**, and fully modifying an ASO silently
  removes RNase H recruitment. These are not interchangeable molecules.

A third class, **splice-switching oligonucleotides**, is fully modified *by design*: it binds a
splice site to redirect splicing without recruiting RNase H at all. Nusinersen and eteplirsen work
this way, and for them "no cleavage" is the mechanism rather than a failure.

## Duplex asymmetry: the siRNA rule that matters most

RISC loads the strand whose **5' end is less thermodynamically stable**. If the sense strand has
the weaker 5' end, RISC loads the sense strand, silences whatever the sense strand is
complementary to, and your intended target is untouched.

The molecule then looks simply inactive, which sends people to look for delivery problems that do
not exist.

`oligo_design.py` computes the asymmetry and reports `antisense_loaded`. Positive asymmetry means
the antisense 5' end is the weaker one. Supporting rules from the same literature: an A or U at
antisense position 1, and a G or C at sense position 1.

## The seed, and why off-targets are unavoidable

Antisense positions **2–8** are the **seed**. Pairing between the seed and a 3' UTR is sufficient
for microRNA-like translational repression, entirely independent of full-length complementarity.

This is the dominant off-target mechanism for siRNA, and a full-length aligner scores it as a
non-hit. A 7-mer occurs by chance often enough to hit hundreds of transcripts in any real
transcriptome — **zero off-targets is not achievable**. The useful question is comparative:
`offtarget_scan.py seeds` ranks candidates against each other.

For ASOs the equivalent risk is different: RNase H cleaves on **partial** complementarity, so a
contiguous 12–14 nucleotide match elsewhere in the transcriptome is a real liability, and one of
the recognised causes of gapmer hepatotoxicity. `offtarget_scan.py contig` searches for that.

## The design rules, and their standing

| Rule | Window | Standing |
|---|---|---|
| GC content | 30–60% | well supported; a window, not a direction |
| Duplex asymmetry | antisense 5' less stable | the strongest siRNA rule |
| Antisense position 1 | A or U | well supported |
| Homopolymer runs | ≤ 3 | synthesis and specificity |
| Poly-G (GGGG) | avoid | G-quadruplex, non-specific protein binding |
| Length | 21 nt siRNA, 16–20 nt gapmer | conventional |

**GC content is a window.** Below ~30% the duplex is too weak to hybridise; above ~60% it is too
stable to unwind, and RISC cannot separate the strands. Optimising GC upward is a common silent
error.

These rules are **necessary and nowhere near sufficient**. Published hit rates for rule-compliant
designs are on the order of one in three to one in ten reaching useful potency. Design a panel and
screen it — nobody designs one oligonucleotide.

## What the rules leave out

**Target site accessibility dominates in practice, and none of this models it.** mRNA is folded
and coated with protein; a site buried in stable secondary structure or occupied by an RBP is
inaccessible however good its thermodynamics look.

Approaches: secondary-structure prediction (`RNAfold` from the ViennaRNA package, `mfold`),
experimental accessibility from SHAPE or DMS-seq, or simply tiling densely and screening. The last
is the honest default, which is why `oligo_design.py tile` produces a panel rather than a pick.

Also absent: **SNPs** in the target site, which abolish activity in a fraction of patients;
**cross-species conservation**, which decides whether your tox species can be dosed with the same
molecule; and **splice-isoform coverage**, since a site in one exon may miss the isoform that
matters.

## Practical workflow

1. Tile the transcript densely — `oligo_design.py tile`.
2. Apply the thermodynamic and composition rules.
3. Scan the survivors for seed and contiguous off-targets against a real transcriptome.
4. Check the sites are conserved in your tox species and free of common SNPs.
5. Fold the transcript and prefer accessible sites.
6. **Synthesise and screen 20–50**, not one.
7. Take the best few forward into modification optimisation.
