# Choosing a structure to build on

The judgement calls between "I have a target" and "I have coordinates I can dock into". Most
failed structure-based work traces to one of these, made implicitly.

## Experimental or predicted?

| Situation | Use |
|---|---|
| A crystal or cryo-EM structure of your protein exists, ideally with a ligand in the site | The experimental structure |
| Structures exist but not of your construct, mutant, or species | Experimental structure of the closest homologue, then model the differences |
| No structure, and the protein is a well-folded globular domain | AlphaFold DB model |
| No structure, and you need a ligand in the pocket | Cofolding (the `boltz` skill), not an apo model |
| Membrane protein, intrinsically disordered region, or a large multi-subunit assembly | Read the caveats below before trusting any of the above |

An AlphaFold model is a **single conformation with no ligand and no side-chain packing against
one**. Docking into an apo predicted structure is systematically harder than docking into a holo
crystal structure, because the pocket side chains have not been induced into a binding-competent
arrangement. If you must, dock into the predicted model *and* say so in the result.

## Reading an experimental structure

**Resolution** is how finely the density was sampled, and it is the first filter but not the
last:

| Range | What you can trust |
|---|---|
| < 1.5 Å | Individual atoms, alternate conformers, ordered waters, sometimes hydrogens |
| 1.5–2.5 Å | Side-chain positions, ligand pose and orientation. The usual docking range |
| 2.5–3.0 Å | Backbone and general side-chain placement; ligand orientation may be ambiguous |
| > 3.0 Å | Fold and domain arrangement. Not a basis for pose-level work |
| No resolution | NMR ensemble or a predicted model — different rules entirely |

**R-free** is the cross-validated fit of the model to the data. A rough guide is
`R-free ≈ resolution / 10` — 0.20 at 2.0 Å is normal, 0.30 at 2.0 Å suggests something was
fitted badly. A large `R-free − R-work` gap means over-fitting.

**Cryo-EM resolution is not comparable to crystallographic resolution.** A 3.0 Å cryo-EM map may
have a superbly resolved core and an uninterpretable periphery; the reported global number is an
average. Look at what is actually modelled in *your* region.

## What resolution never tells you

Run `python scripts/structure_report.py <file>` and read the ISSUES section. The recurring
problems:

- **Unresolved residues inside the chain.** A loop with no density is simply absent from the
  file. If it borders the binding site, your pocket has a hole in one wall and every docking
  score is optimistic. `3POZ` is 1.5 Å and is missing residues 734–737, 748–754, 868–874.
- **Unresolved residues at the termini.** These leave no gap in the numbering, so a report built
  from coordinates alone calls the chain complete. `1IEP` is missing 38 construct residues, all
  terminal. Read them from `REMARK 465` (PDB) or `_pdbx_unobs_or_zero_occ_residues` (mmCIF).
- **Alternate conformations.** `altloc` A/B side chains in the pocket mean the crystal saw two
  states. Pick one deliberately; preparation tools pick silently.
- **Partial occupancy.** A ligand at 0.5 occupancy was present in half the unit cells. Its
  geometry is correspondingly less certain.
- **Engineered mutations.** `pdbx_mutation` on the polymer entity. Surface-entropy-reduction
  mutations, thermostabilising mutations in GPCRs, and catalytically dead point mutants are all
  common and all easy to miss.
- **Construct boundaries.** A kinase-domain crystal structure covering residues 696–1022 tells
  you nothing about the juxtamembrane segment.
- **Waters and additives.** Glycerol, PEG, DMSO, and sulfate sit in pockets and mimic ligands.
  Some waters are conserved and mechanistically important; most are not. Decide, do not default.

## Asymmetric unit vs biological assembly

The deposited coordinates are the **asymmetric unit** — the crystallographic repeating unit.
It may contain half a dimer, four copies of a monomer, or a physiologically meaningless
arrangement. The **biological assembly** (`1IEP-assembly1.cif`) is the depositor's or PISA's
call on the functional oligomer.

Use the assembly when the interface matters (dimer interfaces, allosteric sites, protein–protein
docking) and the asymmetric unit when you want one clean copy of a monomeric domain. Getting it
backwards produces either a truncated pocket or spurious contacts, silently.

## Apo or holo?

For structure-based design, a **holo** structure with a ligand chemically similar to yours is
worth far more than a higher-resolution apo one. Side chains adopt a binding-competent
conformation only when something is bound; apo pockets are frequently collapsed.

`rcsb_search.py uniprot P00533 --has-ligand` filters to entries with a non-additive bound
component. Then check the ligand: a structure with ATP bound is the wrong template for an
allosteric inhibitor.

## Numbering will not line up

- UniProt numbers the **canonical isoform** from 1.
- A PDB entry has both `auth_seq_id` (the depositor's numbering, usually matching the literature)
  and `label_seq_id` (a 1-based index into the construct). They differ, often by a lot.
- Expression tags, cloning artefacts, and internal deletions shift things further.

Always map explicitly — via `rcsb_polymer_entity_align` in the data API, or by aligning the
observed sequence from `structure_report.py --sequence` against the UniProt sequence. Never
assume that residue 790 in the paper is residue 790 in the file.

## AlphaFold confidence

`fetch_structure.py alphafold P00533 --metadata-only` reports the bands:

| pLDDT | Meaning |
|---|---|
| > 90 | Backbone and side chains both reliable |
| 70–90 | Backbone reliable, side chains less so |
| 50–70 | Backbone unreliable — do not build a pocket here |
| < 50 | Usually intrinsically disordered; the ribbon is a placeholder, not a prediction |

For EGFR, 47 % of residues are above 90 and 23 % are below 50 — the model is excellent for the
kinase domain and meaningless for the disordered C-terminal tail. **Trim to the confident
region** before doing anything with it; a full-length AlphaFold model dropped into a simulation
box spends most of its atoms on a prediction nobody makes.

**PAE, not pLDDT, tells you about domain arrangement.** High pLDDT in two domains with high
predicted aligned error between them means both domains are right and their relative orientation
is a guess. Fetch it with `--with-pae` before trusting an inter-domain site.

## A workable default sequence

1. `uniprot_fetch.py entry <accession>` — confirm the protein, length, and isoform.
2. `uniprot_fetch.py pdb <accession> --max-resolution 2.5` — what exists, with coverage ranges.
3. `rcsb_search.py uniprot <accession> --max-resolution 2.5 --has-ligand --exclude-mutants` —
   narrow to usable holo structures.
4. `fetch_structure.py pdb <id>` — download mmCIF.
5. `structure_report.py <file> --gaps-near <your site residues>` — check the site is actually
   resolved before spending any more time.
6. Hand off to `autodock-vina` (receptor preparation), `molecular-dynamics` (system setup), or
   `boltz` (cofolding when no suitable structure exists).
