# Ligand preparation

A ligand reaches the docking program as a 3D structure with explicit hydrogens, a defined
protonation state, defined stereochemistry, and correct bond orders. Getting there from a SMILES
string is four decisions, and the defaults are wrong often enough to matter.

## From SMILES to a dockable ligand

```bash
# 3D coordinates, protonation at pH 7.4, tautomers
scrub.py library.smi -o library_3d.sdf --ph 7.4

# SDF -> PDBQT
mk_prepare_ligand.py -i library_3d.sdf -o ligand.pdbqt
```

`scrub.py` is from [Molscrub](https://github.com/forlilab/molscrub), by the same lab as Meeko.
It generates conformers, enumerates protonation and tautomeric states, and adds hydrogens.

The RDKit route, when you want control (see the `rdkit` and `datamol` skills):

```python
from rdkit import Chem
from rdkit.Chem import AllChem

mol = Chem.MolFromSmiles(smiles)
mol = Chem.AddHs(mol)
AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
AllChem.MMFFOptimizeMolecule(mol)
Chem.MolToMolFile(mol, "ligand.sdf")
```

ETKDGv3 plus a force-field minimisation gives a reasonable starting conformer. Vina samples
torsions itself, so a single good conformer is enough — but ring conformations are **not**
sampled, so a molecule with a flexible ring (piperidine chair/boat, macrocycle) needs conformers
generated up front and docked separately.

## The four decisions

**1. Protonation state at your pH.** This is the one most often skipped and it changes results
more than anything else. A carboxylic acid is ionised at pH 7.4; a basic amine is protonated; an
imidazole is borderline. A neutral amine docked into an aspartate-lined pocket will not find the
salt bridge that drives real binding, and the pose comes out wrong rather than merely
mis-scored.

Use `scrub.py --ph 7.4`, or Dimorphite-DL, or the `rowan` skill for proper micro-pKa when the
molecule is genuinely ambiguous.

**2. Tautomers.** 2-hydroxypyridine and 2-pyridone are different hydrogen-bonding patterns.
Where the dominant tautomer is unclear, dock both and say which one the reported pose used.

**3. Stereochemistry.** SMILES without `@`/`@@` is a mixture. Enumerate the stereocentres you
care about and dock each — a docking program will silently pick whichever the embedding
produced.

**4. Charged groups and counterions.** Strip salts and keep the parent. Docking a hydrochloride
as-is puts a chloride ion in your pocket.

## What Vina samples, and what it does not

| Sampled | Not sampled |
|---|---|
| Ligand translation and rotation | Ring conformations |
| Rotatable single bonds | Protonation and tautomeric states |
| Flexible receptor side chains (if declared) | Amide bond isomerism (fixed as input) |
| | Receptor backbone |
| | Explicit water networks |

Everything in the right column is decided by you, before docking. That is why preparation, not
search, is where most accuracy is won or lost.

Vina's rotatable-bond count also affects the search directly: above roughly 10 rotatable bonds
the default exhaustiveness is not enough, and above ~15 the pose prediction is unreliable
regardless of effort. Check with `mk_prepare_ligand.py` output or RDKit's
`Descriptors.NumRotatableBonds`.

## Never prepare a ligand from PDB format

PDB and PDBQT store no bond orders. Preparing a ligand from a PDB file means the toolkit infers
bonds from distances — wrong for aromatics, charged groups, and anything unusual. Use SDF or
MOL2 as the source, always. This is the AutoDock documentation's own warning, and it is
routinely ignored.

Coming back the other way, use Meeko rather than Open Babel:

```bash
mk_export.py docked_out.pdbqt -s docked.sdf
```

Meeko writes the input SMILES into the PDBQT header and uses it to rebuild the molecule with the
original bond orders and formal charges. Open Babel has to guess and gets aromatics and
tautomers wrong.

## Library-scale preparation

```bash
scrub.py library.smi -o library_3d.sdf --ph 7.4
python dock_batch.py run --receptor rec.pdbqt --config box.txt \
    --ligands library_3d.sdf --workers 8 --exhaustiveness 32 --seed 42
```

Before docking a library at all, triage it — the `medchem` skill applies PAINS and NIBR alerts,
drug-likeness rules, and complexity filters. Docking 100,000 compounds of which 20,000 are
assay-interfering frequent hitters wastes the compute and pollutes the hit list.

Standardise first as well (`datamol` or `rdkit`): salt stripping, charge neutralisation before
re-protonation, and deduplication by InChIKey. The same compound under three vendor ids will
otherwise appear three times in the top 100.

## Reference ligand for validation

Before trusting any screen, redock the co-crystal ligand into its own structure and measure the
RMSD to the crystal pose. Under 2 Å means the setup — box, protonation, receptor preparation —
can reproduce a known answer. Above that, fix the setup before docking anything unknown. This
step costs one run and is the only calibration you get.
