# Cryptic and allosteric sites

A **cryptic** site is a pocket that is not open in the apo structure and forms only on ligand
binding. An **allosteric** site is one away from the active site whose occupancy changes activity.
They are different properties and often co-occur, because allosteric sites are frequently cryptic.

Both matter for the same reason: **a static apo structure systematically under-reports the
pockets a protein actually has.** If pocket detection says a target is undruggable, that verdict
is about one conformation.

## Why this is not a corner case

The best-known examples were all invisible in the structures available at the time:

- **KRAS G12C** — the switch II pocket does not exist in unliganded KRAS. It opens under the
  covalent inhibitors that became sotorasib and adagrasib, and thirty years of "undruggable" rested
  on structures that could not show it.
- **Bcl-2 / Bcl-xL** — the groove that venetoclax occupies is far more open in the complex.
- **Interleukin-2** — the small-molecule site is absent from apo IL-2.
- **HIV-1 integrase** — the allosteric LEDGF site.

Estimates from simulation studies suggest a substantial minority of proteins possess a cryptic
site that a single crystal structure does not reveal.

## Finding them

Ordered by cost:

**1. Compare structures you already have.** The cheapest method by far. If the PDB holds several
structures of the target — apo, holo with different ligands, different space groups — run fpocket
on each and compare. `site_compare.py match` does the pairing.

```bash
fpocket -f apo.pdb && fpocket -f holo.pdb
python site_compare.py match --apo apo_out --holo holo_out
```

**Superpose the structures first.** The matching is spatial, so unaligned inputs make every
cavity look cryptic. The script says so when nothing matches at any distance.

**2. Mixed-solvent molecular dynamics.** Simulate with a few percent of small organic probes —
benzene, isopropanol, acetonitrile — dissolved in the water box. Probes cluster where a ligand
would sit, and pockets that only transiently open get occupied and held. This is the most reliable
computational method and the one most used in practice. `molecular-dynamics` in this bundle can
run the simulation; the probe setup and clustering are extra work.

**3. Plain MD with pocket tracking.** Run a long trajectory and run fpocket on frames. Cheaper
conceptually, much less sensitive — cryptic pockets are rare states, and unbiased MD may not visit
them in reachable time.

**4. Enhanced sampling.** Metadynamics, accelerated MD, SWISH (with scaled hydrophobic
interactions). Designed to reach the rare states plain MD misses, at the cost of setup complexity
and careful collective-variable choice.

**5. Machine-learned predictors.** CryptoSite, PocketMiner, and successors predict cryptic-site
propensity per residue from sequence and structure, in seconds rather than microseconds. Use as
triage to decide where to spend simulation, not as an answer.

**6. Fragment screening, experimentally.** Crystallographic fragment screening — XChem at
Diamond, PanDDA analysis — finds cryptic sites by putting fragments into them. It is the ground
truth the computational methods are approximating, and PanDDA specifically exists to detect the
weak partial-occupancy density that cryptic-site fragments produce.

## Reading `site_compare.py match`

| Classification | Meaning |
|---|---|
| `cryptic` | scored in holo, absent in apo — opens on binding |
| `induced fit` | present in both, materially better in holo |
| `stable` | comparable in both; druggability delta below 0.1 |
| `closes on binding` | worse in holo; often an allosteric site that shuts |
| `apo only` | present in apo, gone in holo |

Differences below 0.1 in druggability are treated as noise and reported as `stable`, because
fpocket's score is not precise enough to support finer distinctions between structures that differ
in resolution and crystal form.

## What to do with a cryptic site once found

**Dock into the holo conformation, not the apo one.** This is the whole practical point. The
receptor conformation is part of the model, and using the closed form guarantees failure.

Where no holo structure exists, an ensemble approach — docking against several conformations from
simulation and keeping the best score per ligand — recovers some of the benefit. It also
multiplies false positives, since taking a maximum over conformations takes a maximum over errors
too. Report which conformation produced each pose.

## Allosteric sites specifically

Reasons to want one even when the orthosteric site is druggable:

- **Selectivity.** Orthosteric sites are conserved across a family by definition, since they bind
  the same endogenous ligand. Allosteric sites are not, and that is where family selectivity
  usually comes from.
- **Modulation rather than blockade.** A negative allosteric modulator reduces signalling without
  abolishing it, which is frequently the better pharmacology.
- **Escaping competition.** An allosteric inhibitor is not out-competed by rising substrate
  concentration — which is exactly how ATP-competitive kinase inhibitors lose potency in cells,
  where ATP is millimolar.

Finding them computationally is harder than finding cryptic sites, because there is no structural
signature of "allosteric" — only of "pocket". Normal mode analysis, dynamic network analysis, and
coevolution-based methods (SCA, statistical coupling) identify residues coupled to the active
site, which narrows where to look.

## Honest caveats

Cryptic-site prediction has a **high false-positive rate**. Transient openings in simulation are
common; sites that stably accept a drug-like ligand are rare. Treat any predicted cryptic site as
a hypothesis needing experimental confirmation — a fragment soak, a thermal shift, an NMR
perturbation — before designing against it.

And the reverse error is real too: a site being cryptic does not make it useful. It must still be
druggable when open, and binding it must still do something to the biology.
