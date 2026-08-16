# Developability

Developability is whether a molecule that binds well can also be made, purified, formulated,
shipped, and dosed. Roughly a quarter to a third of otherwise good antibody candidates fail on
these properties rather than on potency, and almost all of it is knowable early.

Two categories, and the difference decides what tool you need:

- **Sequence liabilities** — motifs that undergo chemical modification. Findable by pattern
  matching; `scan_liabilities.py` does it.
- **Conformational and colloidal liabilities** — aggregation, viscosity, polyspecificity, thermal
  stability. These need structure or experiment.

## Sequence liabilities

| Liability | Motif | What happens | Where it matters |
|---|---|---|---|
| N-glycosylation | `N-X-[S/T]`, X ≠ P | Glycan attached in the variable domain; heterogeneity, possible loss of binding | Critical in CDRs; occasionally engineered in on purpose |
| Deamidation | `NG` ≫ `NS`, `NT`, `NN`, `NA`, `ND`, `NH` | Asn → Asp/iso-Asp; charge change and often loss of potency | The classic storage-stability failure. NG in a CDR is a redesign candidate |
| Isomerisation | `DG` ≫ `DS`, `DT`, `DD`, `DH` | Asp → iso-Asp via succinimide; backbone kink | Same; CDR-H3 `DG` is common and consequential |
| Fragmentation | `DP` | Acid-labile bond clips at low pH | Matters because viral inactivation and Protein A elution are low-pH steps |
| Met oxidation | `M` | Sulfoxide; loss of binding if in a contact, loss of FcRn binding if in Fc | Exposed CDR Met; Fc Met252/Met428 |
| Trp oxidation | `W` | Kynurenine and other products under light/metal stress | CDR Trp are often key contacts |
| Free cysteine | odd `C` count | Disulfide scrambling, dimerisation, aggregation | Always investigate. A VH or VL normally has exactly two |
| Pyroglutamate | N-terminal `Q`/`E` | Cyclisation; charge variant | Usually accepted as a product attribute |
| C-terminal Lys | Heavy chain C-terminal `K` | Clipped variably by CHO carboxypeptidase | Usually accepted; often removed from the construct |
| Integrin binding | `RGD`, `RYD` | Off-target cell adhesion | Rare but serious |

**Context decides severity.** The same `NG` in framework 3 is usually buried and tolerated;
in CDR-H2 it is a redesign candidate. Run `number_antibody.py --format regions` first and pass
the result to `scan_liabilities.py --regions` so CDR hits are promoted.

Rates also depend on the following residue's flexibility and on local structure: `NG` is fast
because glycine gives the backbone room to form the succinimide. A structure-aware predictor
does better than motif matching, but motif matching finds the candidates.

### What to do with a finding

1. **Confirm it is exposed and functional.** A model or a structure tells you whether the Asn
   is in the paratope.
2. **Design conservative substitutions.** `NG` → `QG`, `NA`, or `SG`; `DG` → `EG` or `DA`.
   Each is an affinity risk; test.
3. **Or accept and monitor.** Many approved antibodies carry known liabilities and are managed
   with formulation and release specifications. A liability is a question, not a veto.
4. **Force-degradation studies** (40 °C, pH stress, oxidative stress with H₂O₂ or AAPH, light)
   are what confirm whether a predicted site actually degrades.

## Charge and hydrophobicity

`physchem_profile.py` computes these from sequence alone:

- **pI.** Variable domains typically fall between 7 and 9. Formulate at least ~1 unit away from
  the pI, because near-zero net charge means low colloidal stability and aggregation.
- **Net charge at pH 7.4.** Strongly positive Fv charge (roughly > +6 in published
  developability sets) associates with fast clearance and with off-target binding to
  polyanionic surfaces. Strongly negative can slow tissue penetration.
- **Extinction coefficient.** Needed to turn A280 into a concentration. Getting it wrong scales
  every downstream number, including your reported affinities.
- **GRAVY.** A crude hydrophobicity average. Useful as a flag, not a predictor — what actually
  drives aggregation is a *patch*, which needs structure.

## What needs structure

Build a model first (ABodyBuilder3, IgFold, or `boltz`/`esm` from this bundle), then:

- **Hydrophobic patch analysis.** Contiguous exposed hydrophobic surface, particularly across the
  VH/VL interface and around CDR-H3. This is the best sequence-plus-structure predictor of
  aggregation and of HIC retention.
- **Patch positivity/negativity.** Charged patches predict polyspecificity better than net charge.
- **Therapeutic Antibody Profiler (TAP)** — five structure-based metrics with flags derived from
  the distribution of clinical-stage antibodies: total CDR length, patches of surface
  hydrophobicity, patches of positive and of negative charge, and structural Fv charge symmetry.
  Values outside the clinical-stage range are a flag to investigate, not a rejection.
- **Thermal stability (Tm).** Predictable roughly from framework germline family and VH/VL
  pairing; measured by DSF/DSC. Fv Tm below ~65 °C is a concern.

## Experimental panel

The measurements that decide it, roughly in the order people run them:

| Assay | Reads out |
|---|---|
| SEC (and after stress) | Aggregation, fragmentation |
| DSF / DSC | Thermal unfolding (Tm, Tonset) |
| HIC | Surface hydrophobicity; correlates with in-vivo clearance |
| AC-SINS | Self-association at low concentration; predicts high-concentration viscosity |
| Poly-specificity reagent (PSR/BVP ELISA) | Off-target binding; predicts fast clearance |
| Viscosity at 100–150 mg/mL | Subcutaneous feasibility |
| Accelerated stability (40 °C, 2–4 weeks) | Whether the predicted chemical liabilities actually degrade |
| Expression titre | Manufacturability |

The `adaptyv` skill in this bundle submits binding and thermostability assays to a cloud lab, if
you want measured numbers rather than predicted ones.

## Reporting

Say which liabilities were found, their region under a named numbering scheme, and which are
being carried deliberately. "Clean" means "no sequence liabilities detected by motif matching,
structure-based properties not assessed" — say that rather than "developable".
