# Receptor preparation

More docking runs are ruined here than in the docking itself. The receptor arrives as a crystal
structure with no hydrogens, ambiguous protonation, waters of unknown importance, and possibly a
hole where a loop should be. Vina will happily dock into all of that.

## The current toolchain

Meeko 0.7 is the maintained path; MGLTools/`prepare_receptor4.py` is legacy and still in most
tutorials.

```bash
# 1. fix the structure (see below), producing a receptor with hydrogens
# 2. prepare the PDBQT, the box config, and a viewable box PDB in one step
mk_prepare_receptor.py -i receptor_H.pdb -o receptor -p -v \
    --box_center 15.190 53.903 16.917 --box_size 20 20 20
```

- `-p` writes `receptor.pdbqt`, `-v` writes `receptor.box.txt` (a Vina config) and
  `receptor.box.pdb` (the box, for loading in PyMOL).
- `-j` also writes a JSON of the whole receptor data structure, which `mk_export.py` needs to
  rebuild the receptor with updated side chains after flexible docking.
- `-g` additionally writes a GPF for `autogrid4`, needed only for the `ad4` scoring function.
- `--delete_residues` drops components you do not want (waters, cofactors, a co-crystal ligand)
  without editing the file by hand.
- `-f A:42` makes residue 42 of chain A a flexible side chain.

The ADFR Suite alternative, which requires hydrogens already present:

```bash
prepare_receptor -r receptor_H.pdb -o receptor.pdbqt
```

## Before Meeko: fixing the structure

Run `structure_report.py` from the `uniprot-rcsb` skill first. Then, in order:

**1. Choose the right copy.** Asymmetric unit or biological assembly, and which chain. A dimer
interface pocket needs the assembly; a monomeric domain does not.

**2. Decide about the co-crystal ligand.** Keep it as the box reference, then delete it before
docking — leaving it in means docking into an occupied pocket.

**3. Repair missing atoms and loops.** Missing side-chain atoms are common and usually fixable;
missing backbone is not. Tools:

- **PDBFixer** (`pip install pdbfixer`, part of the OpenMM stack — see the `molecular-dynamics`
  skill) adds missing heavy atoms, builds short missing loops, and adds hydrogens at a chosen pH.
- **Modeller** or **Rosetta** for longer loops, if you have a licence.
- If a loop bordering the pocket cannot be modelled reliably, say so in the result. A rebuilt
  loop is a prediction, and docking scores against it inherit that uncertainty.

```python
from pdbfixer import PDBFixer
from openmm.app import PDBFile

fixer = PDBFixer(filename="receptor.pdb")
fixer.findMissingResidues()
fixer.findMissingAtoms()
fixer.addMissingAtoms()
fixer.addMissingHydrogens(pH=7.4)
PDBFile.writeFile(fixer.topology, fixer.positions, open("receptor_H.pdb", "w"))
```

**4. Protonation is a real decision, not a default.** Histidine has three states (HID, HIE, HIP)
and the choice flips a hydrogen-bond donor into an acceptor inside the pocket. Aspartate and
glutamate in buried environments can be neutral. Catalytic residues frequently have shifted pKa.

- **PROPKA** or **H++** predict residue pKa in context.
- **REDUCE** optimises hydrogen placement and flips Asn/Gln/His amides — a flipped Asn is
  chemically identical and geometrically opposite, and crystallographers cannot tell them apart
  from density alone.

**5. Waters.** Delete them all, or keep specific ones — never keep them by default. A water
bridging ligand and protein in several structures of the same target is probably part of the
site; the other 200 are noise that block the pocket. Meeko treats retained waters as part of the
rigid receptor.

**6. Metals and cofactors.** Zinc, magnesium, and haem are frequently essential and are handled
poorly by all standard scoring functions. If your site has a catalytic metal, expect Vina to
under-rank chelators, and consider a metal-aware protocol.

## Flexible side chains

```bash
mk_prepare_receptor.py -i receptor_H.pdb -o receptor -p -j -f A:790 -f A:797 \
    --box_center ... --box_size ...
vina --receptor receptor_rigid.pdbqt --flex receptor_flex.pdbqt --ligand lig.pdbqt --config box.txt
mk_export.py out.pdbqt -j receptor.json -s poses.sdf -p receptor_docked.pdb
```

Each flexible side chain multiplies the search space. Two or three gatekeeper residues is
reasonable; ten is not, and the run will be worse than rigid docking at the same exhaustiveness.

## What PDBQT actually stores

Atom types (AutoDock's own set), Gasteiger partial charges, and rotatable-bond topology. It does
**not** store bond orders. That is why:

- Converting a docked pose back to a real molecule needs `mk_export.py`, which uses the SMILES
  Meeko wrote into the PDBQT header. Open Babel has to guess, and guesses wrong on aromatics,
  tautomers, and charged groups.
- Preparing a ligand *from PDB format* is a bad idea for the same reason — PDB has no bond
  orders either, so the perception step is guessing twice.

Only polar hydrogens are kept; nonpolar hydrogens are merged into their heavy atom. A PDBQT with
no hydrogens at all means the preparation step silently did nothing useful.

## Checklist

- [ ] Right assembly and chain
- [ ] Co-crystal ligand removed (after using it for the box)
- [ ] Missing side-chain atoms repaired; missing loops modelled or documented
- [ ] Hydrogens added at the intended pH; His/Asn/Gln states checked
- [ ] Waters deliberately kept or removed
- [ ] Metals and cofactors accounted for
- [ ] Box centred on the site, not on the protein
- [ ] PDBQT contains polar hydrogens and charges (`grep -c "^ATOM" receptor.pdbqt` is non-zero)
