# Troubleshooting

## Installation

| Route | Command | Notes |
|---|---|---|
| conda | `conda install -c conda-forge vina` | Simplest; brings the binary and the Python bindings |
| pip | `pip install vina` | 1.2.7; needs a compiler and Boost on some platforms |
| binary | GitHub releases | Prebuilt for Linux/macOS/Windows |
| Meeko | `pip install meeko` | 0.7.1; provides `mk_prepare_ligand.py`, `mk_prepare_receptor.py`, `mk_export.py` |
| Molscrub | `pip install molscrub` | `scrub.py`, for SMILES → 3D with protonation |
| AutoGrid4 | AutoDock Suite / ADFR Suite | Only needed for `--scoring ad4` |

`python dock_batch.py check` reports what is present.

The Python bindings mirror the CLI:

```python
from vina import Vina

v = Vina(sf_name="vina", seed=42)
v.set_receptor("receptor.pdbqt")
v.set_ligand_from_file("ligand.pdbqt")
v.compute_vina_maps(center=[15.19, 53.90, 16.92], box_size=[20, 20, 20])
v.dock(exhaustiveness=32, n_poses=9)
v.write_poses("out.pdbqt", n_poses=9, overwrite=True)
print(v.energies())
```

Useful when scoring many ligands against the same receptor: `compute_vina_maps` is the expensive
step and the bindings let you reuse it, where the CLI recomputes per invocation.

## Errors

**`Parse error on line N in file "receptor.pdbqt"`**
The PDBQT is malformed — usually a hand-edited file, or output from a converter that is not
Meeko. Regenerate it. Non-standard residues and unusual atom types are the common triggers.

**`ERROR: Could not find any atoms in the search space`**
The box is in the wrong place. Load `receptor.pdbqt` and the box PDB from
`make_box.py --box-pdb` together in PyMOL and look. Nearly always a coordinate mix-up between
the structure you took the centre from and the one you prepared.

**`Could not open ...` / silent empty output**
Check the file actually exists and has content. Meeko writes nothing and exits 0 in some failure
modes; `wc -l` the PDBQT before docking.

**Docking runs but every score is around −3 to −5**
The ligand is probably not in the pocket — it is floating in solvent inside an oversized box, or
the box is centred on the protein rather than the site.

**All poses at the box edge**
The box is too small or misplaced. `parse_vina_output.py --config` flags this.

**Enormous run times**
Exhaustiveness × box volume × rotatable bonds. A 30 Å cube at exhaustiveness 64 for a 15-rotatable-
bond ligand is hours per compound. Shrink the box first — it is the cheapest fix and it also
improves accuracy.

**Results differ between runs**
Expected: the search is stochastic. Pass `--seed`. If results differ *a lot* with a fixed
exhaustiveness, that is the signal to raise it.

**`mk_export.py` produces a molecule with wrong bond orders**
The PDBQT lacks the SMILES header, which means it was not written by Meeko. Re-prepare the
ligand with `mk_prepare_ligand.py` so the round trip has something to rebuild from.

## Alternatives to plain Vina

| Tool | Adds |
|---|---|
| **smina** | Custom scoring functions, `--autobox_ligand` for box definition, better scoring flexibility |
| **gnina** | CNN rescoring on top of smina; often better pose selection, needs a GPU |
| **QuickVina2 / QVina-W** | Faster search for large-scale screening |
| **AutoDock-GPU** | The AD4 force field on GPU; large speed-up for big campaigns |
| **DiffDock** (skill in this bundle) | Diffusion-based pose generation, no box needed, no affinity |
| **Boltz-2** (skill in this bundle) | Cofolding plus a trained affinity head |

`smina` and `gnina` read Vina's input files unchanged, so switching is cheap.

## Where docking systematically fails

Be explicit about these rather than reporting a score anyway:

- **Metalloenzymes.** Standard scoring functions handle coordination geometry badly and
  under-rank chelators.
- **Highly polar or charged pockets.** Desolvation dominates and is modelled crudely.
- **Water-mediated binding.** If a conserved bridging water is part of the site, docking without
  it is docking a different pocket.
- **Induced fit.** Rigid-receptor docking cannot find a pose requiring backbone movement.
  Cross-docking failures are the diagnostic.
- **Covalent inhibitors.** Vina has no covalent mode; use a covalent-docking protocol.
- **Very flexible ligands.** Above ~15 rotatable bonds, pose prediction is unreliable at any
  exhaustiveness.
- **Fragments.** Small, weakly bound, and the scoring function's discrimination is smallest
  exactly there. Use ligand efficiency and expect noise.

Reporting "docking found no strong binders" for any of these says more about the method than the
compounds.
