# Humanisation, humanness, and design

## Humanisation by CDR grafting

The standard route from a mouse antibody to a clinical candidate:

1. **Number both sequences** and delimit the CDRs. The scheme choice matters here — Kabat CDRs
   are wider than Chothia's, so a Kabat graft carries more mouse residues.
2. **Choose a human acceptor framework.** Two philosophies:
   - *Closest germline* — highest framework identity to the donor, so fewest back-mutations.
   - *Fixed frameworks* — a small set of well-behaved, well-expressed human germlines
     (IGHV3-23, IGKV1-39 and friends), reused across programmes.
3. **Graft the CDRs** into the acceptor framework.
4. **Restore Vernier and interface residues.** The framework positions that support CDR
   conformation. Grafting without them typically loses 10–100× in affinity.
5. **Test, and titrate back-mutations.** Each mouse residue restored buys affinity and costs
   humanness.

```python
from abnumber import Chain

chain = Chain(mouse_sequence, scheme="imgt")
humanised = chain.graft_cdrs_onto_human_germline()
chain.align(humanised).print()
```

### Vernier and interface positions

The framework residues that matter, in Kabat numbering (the literature's usual convention):

- **Heavy Vernier:** 2, 27, 28, 29, 30, 47, 48, 49, 67, 69, 71, 73, 78, 93, 94
- **Light Vernier:** 2, 4, 35, 36, 46, 47, 48, 49, 64, 66, 68, 69, 71
- **VH/VL interface:** heavy 37, 39, 45, 47, 91, 103; light 36, 38, 43, 44, 46, 87, 98

Positions 71 (H) and 47 (H) are the ones most often required. Try the graft first, then add
back-mutations one at a time — a full set of back-mutations defeats the purpose.

## Humanness and immunogenicity

Humanness is a proxy for the risk of an anti-drug antibody response. Three levels, in increasing
usefulness:

1. **Germline identity.** Percentage identity of the frameworks to the closest human germline.
   Crude, easy, and what most programmes report.
2. **Repertoire-based humanness.** How likely the sequence is under a model of the human
   repertoire — OASis, Hu-mAb, AbLSTM, and similar. Better calibrated than germline identity
   because it accounts for what humans actually express.
3. **T-cell epitope prediction.** MHC class II binding prediction over 15-mers
   (NetMHCIIpan, and specialised tools like EpiVax/iTope). Epitopes in CDRs are unavoidable to
   some degree; those in frameworks are removable.

None of these predict immunogenicity reliably. Fully human antibodies still raise ADAs, and
mouse-derived ones sometimes do not. Report humanness as a risk indicator, not a clearance.

## Alternatives to humanisation

- **Human-derived discovery.** Phage or yeast display from human libraries, or B cells from
  immunised transgenic mice with human V genes. No humanisation step at all.
- **Germlining.** Reverting framework residues in an already-human antibody to the nearest
  germline, which usually improves stability and expression as well as humanness.
- **VHH humanisation.** Camelid single domains need the framework-2 hallmark residues
  (IMGT 42, 49, 50, 52) handled deliberately — they are what keeps a VHH soluble without a light
  chain, and naively humanising them causes aggregation.

## Affinity maturation

- **Library approaches.** CDR randomisation (soft or NNK), error-prone PCR, chain shuffling,
  selected by phage/yeast/mammalian display. Still the workhorse.
- **Structure-guided design.** A model plus interface analysis, testing tens of variants rather
  than millions. Works when a structure is available and the interface is well defined.
- **ML-guided design.** Language models (`esm` in this bundle) score variants; small
  design-build-test rounds beat one large in-silico screen. The `adaptyv` skill submits designs
  to a cloud lab and returns measured binding.

Deep mutational scanning of the paratope, if you can run it, gives a per-position map that is
worth more than any prediction.

## Formats

| Format | Size | Notes |
|---|---|---|
| IgG | ~150 kDa | Long half-life via FcRn, effector functions, standard |
| Fab | ~50 kDa | No Fc, shorter half-life, better tissue penetration |
| scFv | ~28 kDa | VH-linker-VL; aggregation-prone, common as a CAR or bispecific building block |
| VHH / nanobody | ~15 kDa | Single domain, very stable, small epitopes, cheap to make |
| Bispecific | varies | Dozens of architectures; chain pairing is the engineering problem |
| ADC | ~150 kDa + payload | Conjugation site and DAR become critical quality attributes |

Format choice changes which liabilities matter. An scFv has an artificial VH/VL interface and is
much more aggregation-prone than the same Fv in an IgG; a VHH has no light chain, so framework-2
is solvent-exposed; an ADC adds conjugation chemistry that interacts with surface Cys and Lys.

## Sanity checks before committing

- Both chains number cleanly and the CDRs are the expected lengths for the format.
- Cysteines are even and in the canonical positions.
- No new N-glycosylation sequon was introduced by the graft or by an affinity-maturation
  mutation — this is easy to do accidentally and `scan_liabilities.py` catches it.
- pI and net charge are in a sensible range (`physchem_profile.py`).
- The construct includes what you think it does: signal peptide, tags, linkers, and the correct
  constant-domain allotype.
