# What makes a pocket druggable

Judgement, not syntax. "Druggable" is a claim about whether a site can bind a drug-like small
molecule with useful affinity — not about whether the target is worth pursuing, and not about
whether a molecule you make will work.

## The physical basis

Binding affinity is dominated by burying hydrophobic surface away from water. A site that binds a
nanomolar small molecule almost always:

- is **enclosed** — the ligand is surrounded rather than lying on a surface;
- is **predominantly apolar**, so desolvation is favourable;
- has a **volume of roughly 300–1000 Å³**, matching a 300–500 Da ligand;
- offers **a few well-placed polar contacts** for specificity, not a polar wall;
- is **not too flexible**, so the entropic cost of ordering it is bearable.

Enclosure is the single best discriminator. A shallow, solvent-exposed groove of the same volume
and composition will not deliver the same affinity, because water competes everywhere.

## What the scores actually measure

fpocket's Druggability Score is a logistic regression over local hydrophobic density, normalised
polarity, and alpha-sphere density, trained to separate holo sites carrying drug-like ligands from
other cavities. It is a **similarity-to-known-druggable-sites** measure.

That framing matters, because it inherits the training set's biases. The model was built on the
classes of target that had been drugged by then — enzymes with defined active sites, GPCRs,
nuclear receptors. It systematically underrates:

- **protein–protein interfaces**, which are flat and broad, yet have yielded venetoclax,
  navitoclax, and the MDM2 inhibitors;
- **allosteric sites**, which are often shallower than the orthosteric site;
- **cryptic sites**, which by definition are not open in the structure you scored;
- **covalent sites**, where a warhead supplies affinity that geometry does not predict.

A low druggability score means "this does not look like the sites we have drugged before". That is
useful information and it is not a verdict.

## Reading the numbers together

No single number decides it. In rough order of usefulness:

1. **Druggability score** — the trained summary.
2. **Apolar fraction of SASA** — below ~0.35 the site is polar, and polar sites bind polar
   ligands, which have poor permeability.
3. **Volume** — below ~200 Å³ nothing lead-like fits; above ~1500 Å³ the site is probably not a
   discrete pocket, and selectivity gets hard.
4. **Enclosure**, approximated by alpha-sphere count relative to volume.
5. **Conservation** of the lining residues, if you have an alignment — a conserved pocket is more
   likely functional, and a non-conserved one is a selectivity opportunity.

## Undruggable, and what to do about it

If every cavity scores poorly, the conclusion is not "give up" but "not with a conventional
reversible small molecule". The alternatives, roughly in order of how often they work:

- **Covalent inhibition.** A nucleophilic residue near a shallow site can supply the affinity
  geometry cannot. This is how KRAS G12C, undrugged for thirty years, was drugged.
- **Targeted degradation.** A degrader does not need an inhibitory pocket — only a binding site
  good enough to recruit an E3 ligase. This is the most important expansion of target space in the
  last decade; see `degraders`.
- **Molecular glues**, where the pocket is formed by two proteins together.
- **Cryptic sites**, which need simulation to find; see
  [cryptic-and-allosteric.md](cryptic-and-allosteric.md).
- **Biologics**, if the target is extracellular — antibodies bind flat epitopes happily.
- **Oligonucleotides**, which sidestep the protein entirely by acting on the transcript; see
  `oligonucleotides`.

The order of that list is roughly the order in which to consider them, and the decision belongs
before the screening campaign, not after it fails.

## The step people skip

**Check the pocket before spending on the library.** A billion-compound screen against a shallow,
polar, solvent-exposed site still returns a ranked list that looks exactly like an answer. The
score distribution has a top even when nothing in it binds.

fpocket costs seconds. Running it first is the cheapest risk reduction available in
structure-based design.

## Structure quality first

Pocket detection is only as good as the coordinates. Before trusting any of this:

- **Missing loops** near the site can open a cavity that does not exist, or close one that does.
- **Alternate conformations** — pick one deliberately.
- **Crystallographic additives** (glycerol, PEG, sulfate, DMSO) occupy real pockets and mark them;
  their presence is a *positive* signal that a small molecule can sit there, but they must be
  stripped before running the detector.
- **Resolution.** Above roughly 2.5 Å, side-chain rotamers near the site are uncertain, and
  rotamers determine enclosure.
- **AlphaFold models** carry no ligands and no induced fit. Side chains in low-pLDDT regions are
  unreliable, and predicted structures tend toward closed apo-like conformations.

Use `uniprot-rcsb` to check completeness and resolution before running fpocket, not after.
