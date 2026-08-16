# Numbering schemes and CDR definitions

An antibody residue number means nothing without its scheme. "Residue 52" is a different residue
in IMGT, Kabat, and Chothia numbering, and the CDRs those schemes define overlap only partially.
Every position you report, and every position you read from a paper, needs its scheme attached.

## The schemes

| Scheme | Basis | Notes |
|---|---|---|
| **IMGT** | Structural alignment across all immunoglobulin superfamily domains | The same CDR positions for heavy and light chains. Gaps are placed at the centre of loops. The modern default |
| **Kabat** | Sequence variability in the original Kabat database | The oldest and still the most cited in the clinical literature. Heavy and light differ; insertion codes (35A, 35B, 100A…) are common |
| **Chothia** | Structural loop definition | Same numbering as Kabat with insertions moved to structurally correct positions; CDR-H1 differs from Kabat |
| **Martin** (enhanced Chothia) | Corrected Chothia | Fixes inconsistencies in the original Chothia definition |
| **AHo** | Structural alignment, fixed 149-position frame | Positions are directly comparable across all domains; used in some engineering pipelines |

**Use IMGT unless you have a reason not to.** One definition for both chains, structurally
principled gap placement, and the germline database is IMGT-numbered. Convert to Kabat when
matching legacy literature.

## CDR definitions

Inclusive ranges in each scheme's own numbering:

| Scheme | CDR-H1 | CDR-H2 | CDR-H3 | CDR-L1 | CDR-L2 | CDR-L3 |
|---|---|---|---|---|---|---|
| IMGT | 27–38 | 56–65 | 105–117 | 27–38 | 56–65 | 105–117 |
| Kabat | 31–35B | 50–65 | 95–102 | 24–34 | 50–56 | 89–97 |
| Chothia | 26–32 | 52–56 | 95–102 | 24–34 | 50–56 | 89–97 |
| Martin | 26–32 | 52–56 | 95–102 | 24–34 | 50–56 | 89–97 |
| AHo | 27–42 | 57–76 | 109–137 | 27–42 | 57–76 | 109–137 |

The same trastuzumab heavy chain, numbered two ways:

```
IMGT    CDRH1 GFNIKDTY (8)   CDRH2 IYPTNGYT (8)            CDRH3 SRWGGDGFYAMDY (13)
Kabat   CDRH1 DTYIH    (5)   CDRH2 RIYPTNGYTRYADSVKG (17)  CDRH3 WGGDGFYAMDY   (11)
```

Neither is wrong. IMGT CDR-H1 includes the structural loop that Kabat's sequence-variability
definition omits; Kabat CDR-H2 includes framework residues that IMGT excludes. A "CDR-H2
mutation at position 55" is ambiguous until you say which.

`number_antibody.py --scheme kabat` switches; the region tables it writes carry the scheme in a
column so downstream tools cannot lose it.

## ANARCI

```bash
pip install anarci          # needs HMMER: conda install -c bioconda hmmer, or brew install hmmer
```

ANARCI aligns a sequence to HMMs built from IMGT germline V and J genes, then applies the
requested numbering. It handles heavy, kappa, lambda, TCR alpha/beta/gamma/delta, and single-domain
(VHH) sequences.

Command line:

```bash
ANARCI -i antibody.fasta --scheme imgt --outfile numbered.txt
ANARCI -i "EVQLVESGGGLVQPGG..." --scheme kabat
```

Python:

```python
from anarci import run_anarci

numbering, details, hits = run_anarci([("H", sequence)], scheme="imgt")[1:]
# numbering[0] -> [(positions, start, end), ...] one entry per detected domain
# positions -> [((number, insertion_code), residue), ...] with '-' for gaps
```

Two things to know about its output:

- **The gaps matter.** Positions with `-` are alignment gaps, not residues. Mapping scheme
  positions back onto your input sequence means skipping them and counting only real residues —
  which is what `number_antibody.py` does to produce input-sequence coordinates.
- **The species call is the closest germline, not an annotation.** The ANARCI authors say
  explicitly that it should not be used as a species-annotation tool. A humanised antibody often
  returns `human` because its frameworks are human, and that tells you nothing about the CDRs.

## AbNumber

A friendlier Python layer over ANARCI:

```python
from abnumber import Chain

chain = Chain(sequence, scheme="imgt")
chain.cdr3_seq                       # 'SRWGGDGFYAMDY'
chain.regions                        # dict of region -> {position: residue}
chain.print(numbering=True)
chain.align(other_chain)             # pairwise alignment in the numbering
chain.graft_cdrs_onto_human_germline()
```

Bioconda only (`conda install -c bioconda abnumber`) and not available on Windows, because of
the HMMER dependency. Worth it if you are doing much scheme-aware manipulation; the bundled
scripts use ANARCI directly so they install from PyPI.

## Other identification tools

- **IgBLAST** (NCBI) — germline gene assignment (V/D/J calls with identity), the standard for
  repertoire work. Use this when you need to know *which* germline, not just the numbering.
- **IMGT/V-QUEST** — the reference web tool, authoritative but not scriptable at scale.
- **OAS** (Observed Antibody Space) — over a billion annotated repertoire sequences, already
  numbered. The right place to ask "is this CDR-H3 natural?" or "how common is this framework?"

## Practical rules

1. State the scheme with every position. Always.
2. Convert once, at the boundary, and carry the scheme through your tables — `number_antibody.py`
   writes it as a column for exactly this reason.
3. CDR-H3 length and composition dominate specificity; it is also the region germline-based
   tools understand least, since it spans the V-D-J junction.
4. Insertion codes (`100A`, `100B`, `35A`) are part of the position. Sorting positions as
   integers silently reorders them.
5. For single-domain antibodies (VHH/nanobodies), the hallmark residues are in framework 2
   (positions 42, 49, 50, 52 in IMGT); ANARCI numbers them as heavy chains.
