# Choosing where to bind

Judgement, not syntax. The epitope decision determines the campaign, and everything downstream is
compute spent on it. A campaign against a bad site produces designs that fold beautifully and bind
nothing — with no signal that the site was the problem.

## What makes a good epitope

**Hydrophobic and concave.** The same physics as small-molecule pockets: binding affinity comes
from burying hydrophobic surface away from water. A flat, polar, solvent-exposed patch will not
support a high-affinity interface, however good the design tool.

**Surface-exposed.** Obvious, and routinely got wrong. A buried residue cannot be contacted, and
neither BindCraft nor RFdiffusion will say so — the campaign simply fails to converge.
`binder_target_spec.py residues` reports a neighbour-count proxy for exposure.

**Rigid.** A flexible loop adopts many conformations and the design tool sees one. Ordered
secondary structure — a helix face, a β-sheet edge, a structured loop — is a much better bet.

**Compact.** Three to six hotspot residues within roughly 25 Å. Too few underdetermines the
interface; too many over-constrains it, and a spread wider than one binder can span means the
campaign is asking for something impossible. `binder_target_spec.py hotspots` checks both.

**Functionally relevant.** A perfect binder to an irrelevant face is a reagent, not a drug. If the
goal is to block an interaction, the epitope should overlap the interaction surface.

## Finding candidate epitopes

- **A known interaction interface**, from a complex structure. The best starting point by far:
  nature has already demonstrated the site supports a protein-protein interface.
- **A known antibody epitope** for the same target.
- **Conservation analysis** — a conserved surface patch is often functional.
- **Hydrophobic patch detection**, which is what `binding-site-analysis` does with fpocket; the
  cavity-detection logic transfers, though protein-protein interfaces are flatter than
  small-molecule pockets and score lower.
- **Mutational data.** Residues whose mutation abolishes function are worth binding.

## Trim the target

Designing against a 900-residue protein spends almost all of the compute on regions the binder
never touches, and both pipelines scale badly with target size.

**100–200 residues around the epitope** is the usual window. `binder_target_spec.py trim` selects
residues within a radius of the hotspots and warns outside that band — too small and the trimmed
fragment may not fold stably on its own, too large and the campaign is slow for nothing.

Keep the original residue numbering so hotspot ids stay valid, and check the trimmed fragment is
structurally self-contained rather than a slice through a domain.

## Remove what is not modelled

**Glycans** are not modelled by either pipeline and are not bindable. Leaving them in biases the
interface toward regions occluded in the real protein — and on a heavily glycosylated target, the
accessible protein surface is much smaller than the structure suggests.

**Disordered termini and loops** likewise. If it has no fixed conformation, the design tool is
binding an arbitrary one.

**Crystallographic additives** — glycerol, PEG, sulfate — occupy real surface and should go.

## Competition

If a natural ligand binds at your chosen epitope, the binder must **outcompete it at physiological
concentration**. That is a much harder affinity requirement than binding an unoccupied face, and
it should be decided before the campaign rather than discovered in the assay.

Sometimes the answer is to bind adjacent to the site and block sterically, which needs less
affinity.

## AlphaFold models as targets

Usable, with caveats. Predicted structures tend toward closed, apo-like conformations, carry no
ligands, and have unreliable side-chain placement in low-pLDDT regions.

Check pLDDT across the epitope specifically — a confident core with a low-confidence surface loop
is common, and the loop is exactly where you should not put hotspots. Use `uniprot-rcsb` to check
whether an experimental structure exists first.

## Specificity, planned in advance

A binder designed against one target frequently binds its close paralogues. If selectivity
matters:

- **Choose an epitope in a divergent region** — align the family first and pick where they differ.
- **Counter-screen against the paralogues** experimentally; it is not predictable.
- Consider that a conserved functional site may be impossible to target selectively, and that this
  is a property of the target rather than of the design method.
