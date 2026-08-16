# What actually drives anti-drug antibodies

Judgement, not syntax. Sequence-based epitope prediction is one input, and frequently not the
largest one.

## The pathway

1. The therapeutic is taken up by an antigen-presenting cell.
2. It is proteolysed into peptides.
3. Some peptides are loaded onto MHC class II and presented at the surface.
4. A CD4 T cell with a matching receptor recognises the complex — **if that T cell survived
   central tolerance**.
5. T-cell help drives B-cell activation, class switching, and affinity maturation.
6. Anti-drug antibodies appear.

Every step is a place the process can fail, and epitope prediction only addresses step 3.

## Central tolerance is why humanness matters

Step 4 is the one that makes germline identity dominant. **A fully human sequence still contains
plenty of predicted MHC-II binders** — human proteins are full of them. The difference is that T
cells recognising self-peptides are deleted in the thymus, so those presented peptides find no
partner.

The consequences for reading a scan:

- **Predicted epitopes in germline framework are largely noise.**
- **Predicted epitopes in engineered regions, CDRs, junctions, and non-human segments are the
  signal.**
- A scan reporting "40 epitopes" without saying where they sit is nearly uninformative.

This is why `ada_risk.py score` takes `--humanness` and changes its interpretation accordingly, and
why germline identity should be computed first with `antibody-engineering`.

**Humanisation reduces risk without abolishing it.** Murine muromonab-CD3 provoked ADA in most
patients; chimeric infliximab in roughly 10–60% depending on regimen; humanised trastuzumab under
1%. But **fully human adalimumab still reaches around 26%**, and higher without methotrexate. The
trend is real and the variance within each category is larger than the difference between them.

## Aggregation is usually the biggest factor

Protein aggregates are potent immunogens. They present repetitive arrays of epitopes that can
cross-link B-cell receptors and activate B cells with reduced T-cell help, and they are taken up by
antigen-presenting cells far more efficiently than monomer.

A well-designed, low-epitope sequence that aggregates in the vial will be more immunogenic than a
higher-epitope sequence that does not.

Practically this means formulation, purification, and physical stability work do more for
immunogenicity than sequence engineering usually does — and that an epitope scan on a molecule
with an unresolved aggregation problem is answering the wrong question.

## The other determinants

Roughly ordered by how much they move ADA incidence:

| Factor | Effect |
|---|---|
| **Aggregation** | the largest non-sequence factor |
| **Route** | subcutaneous > intramuscular > intravenous |
| **Frequency** | chronic frequent dosing sensitises; single doses rarely do |
| **Dose** | non-monotonic — very high doses can induce tolerance |
| **Patient population** | autoimmune patients respond more; immunosuppressed less |
| **Concomitant immunosuppression** | methotrexate materially reduces ADA against TNF blockers |
| **Impurities** | host cell protein and leachables act as adjuvants |
| **Glycosylation** | non-human glycans (α-gal, NGNA) are immunogenic epitopes in their own right |

That last row connects to `glycoengineering`: an otherwise human sequence expressed in a system
adding non-human glycans carries epitopes no sequence scan will find.

## Consequences of ADA, which vary enormously

Not all ADA matters, and the distinction decides how much effort is warranted:

- **Non-neutralising, low titre** — often clinically silent.
- **Neutralising** — blocks the drug; efficacy is lost.
- **Clearing** — accelerates elimination; exposure falls, often before efficacy is visibly lost,
  which is why ADA and PK should be measured together.
- **Cross-reactive with an endogenous protein** — the worst case. ADA against an erythropoiesis
  agent that cross-reacted with endogenous EPO caused pure red cell aplasia, and it is the standing
  reason this is taken seriously for any therapeutic with an endogenous counterpart.

## Deimmunisation, and what it costs

When a scan flags a promiscuous epitope in an engineered region:

1. **Check it is not in a CDR.** Mutating a CDR risks affinity, and it is often not worth it.
2. **Substitute toward germline** where the position is in framework — the most reliable route.
3. **Break the binding core** by mutating an anchor residue (P1, P4, P6, P9 of the 9-mer).
4. **Re-scan**, because a substitution frequently creates a new epitope from a different register.
5. **Re-measure affinity and stability.** Deimmunisation that costs a log of affinity is not a win.

Step 4 catches a genuinely common failure: the fix creates a new problem one register over.

## What to trust

**Trust more:** germline identity, aggregation propensity, the presence of non-human sequence
segments, non-human glycans, and MAPPs or T-cell assay data.

**Trust less:** absolute epitope counts, any single-allele prediction, and any claim to predict an
ADA percentage. Clinical ADA for approved antibodies spans under 1% to over 60% and no in-silico
method resolves that range.

## Reporting

Say which regions carry promiscuous epitopes, not just how many there are. Give germline identity
alongside. Say which alleles were scanned and note that DP and DQ were not. State that aggregation
and route are likely larger contributors. Call the output a triage aid and recommend MAPPs or a
T-cell proliferation assay before any decision that matters.

Never report a predicted ADA rate.
