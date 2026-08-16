# The ADMET endpoints, and which ones actually stop programmes

Not all endpoints carry the same weight. Some are hard stops; some are optimisation problems; some
are only meaningful with a target in mind.

## Hard stops

These end a series regardless of potency.

**hERG blockade.** Inhibition of the cardiac potassium channel causes QT prolongation and torsades
de pointes. It withdrew terfenadine, astemizole, and cisapride, and it is the reason every
programme runs a hERG patch-clamp assay. The prediction is a triage tool; the assay is the
decision. Basic amines with a lipophilic aromatic — a very common medicinal-chemistry motif — are
the classic pharmacophore, which is why this liability appears so often.

**Ames mutagenicity.** Bacterial reverse mutation. A positive is usually disqualifying outside
oncology, and structural alerts (nitroaromatics, aromatic amines, epoxides, alkyl halides) predict
it well enough that `medchem` in this bundle catches many before a model is needed.

**Drug-induced liver injury.** The commonest cause of post-marketing withdrawal and the hardest to
predict. DILI is idiosyncratic — often immune-mediated, often dose-dependent in ways that only
appear across thousands of patients. **The models are weak here.** A low predicted DILI is close
to no information; a high one is worth investigating.

**Carcinogenicity.** Disqualifying outside oncology, and expensive to disprove.

## Optimisation problems

These shape the molecule rather than killing it.

**Solubility and permeability** trade off against each other and against potency. The classic
failure is a potent, insoluble, impermeable compound — potency was optimised by adding lipophilic
bulk, and everything else followed. Watch `Lipophilicity_AstraZeneca` above 4: it drives
promiscuity, hERG, clearance, and poor solubility simultaneously, which is why logD is the single
most informative physicochemical parameter.

**Metabolic clearance and half-life.** High clearance means short exposure means more frequent
dosing means worse compliance. Fixable by blocking metabolic soft spots, which is a normal
medicinal-chemistry exercise once the site is known — and a prediction does not tell you the site.

**CYP inhibition.** A drug-drug interaction risk rather than a toxicity. CYP3A4 matters most
because it metabolises the majority of drugs. Reversible inhibition is manageable with labelling;
time-dependent (mechanism-based) inhibition is much more serious, and no public model predicts it.

**P-glycoprotein efflux.** Limits oral absorption and, more sharply, brain exposure. For a CNS
target a Pgp substrate is usually fatal to the series.

**Plasma protein binding.** Above 99% leaves very little free drug. But note the argument in
`pkpd-translation`: for a hepatically cleared drug, increasing binding lowers free clearance
proportionally, so free concentration at steady state is unchanged. Optimising fu upward is
usually a mirage. What PPBR does affect is the *interpretation* of every total-concentration
measurement you make.

## Direction depends on the programme

**Blood-brain barrier penetration** is the clear case: essential for a CNS target, a liability for
everything else, where it introduces central side effects for no benefit. `admet_report.py` gives
BBB no liability direction for this reason.

**Volume of distribution** likewise — high Vd gives a long half-life and good tissue penetration,
and also a large loading dose and slow washout if something goes wrong.

## What is missing from any public ADMET model

Worth knowing so the gaps are not mistaken for clean results:

- **Time-dependent CYP inhibition** — far more serious than reversible, not predicted.
- **Transporter interactions** beyond Pgp — BCRP, OATP, OAT, MATE all matter clinically.
- **Reactive metabolite formation** — a major DILI mechanism; structural alerts help, models do not.
- **Phospholipidosis** and **mitochondrial toxicity** — real attrition causes, poorly covered.
- **Immunogenicity** — irrelevant for small molecules, dominant for biologics; see
  `immunogenicity`.
- **Species differences.** Predictions are human-trained. Your tox species may differ, and that
  discrepancy is itself a finding.
- **Formulation.** Solubility predictions describe the neutral compound in water, not a salt, a
  co-crystal, or an amorphous dispersion. Formulation rescues many "insoluble" compounds.

## Reading the TDC leaderboard honestly

ADMET-AI tops the average rank across 41 TDC datasets. That is a real result and it is a
*benchmark* result. Concretely:

- Performance varies enormously **per endpoint**. Some (lipophilicity, solubility) are well
  predicted; some (DILI, clearance) are barely better than a coin flip. An average rank hides that.
- Benchmark splits, even scaffold splits, are kinder than prospective use on a novel series.
- Every model is trained on public data, which is biased toward compounds that were interesting
  enough to measure — usually because they were already reasonable.

The practical consequence: use predictions to **rank and triage within a series**, where relative
ordering is more reliable than absolute values, and never as a substitute for the assay on the
compounds you actually care about.

## A sensible cascade

1. **Structural alerts first** — `medchem` catches PAINS, reactive groups, and many Ames-positive
   motifs for free, before any model runs.
2. **Physicochemistry** — MW, logD, TPSA, HBD. Cheap, robust, and predictive of a great deal.
3. **ADMET-AI** across the series, read as percentiles against approved drugs.
4. **Assay the survivors.** hERG patch clamp, microsomal stability, and kinetic solubility are
   cheap enough that predictions should only ever be deciding what to assay.
