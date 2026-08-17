---
name: rdkit
description: Cheminformatics toolkit for fine-grained molecular control. Parse and write SMILES, SDF, MOL and InChI; compute descriptors (MW, LogP, TPSA, QED, Bertz); build fingerprints (Morgan/ECFP, RDKit, MACCS, atom pair, torsion) and score Tanimoto, Dice or cosine similarity; run SMARTS substructure search and reaction SMARTS; generate 2D depictions and ETKDG 3D conformers; extract Murcko scaffolds and canonical hashes; control sanitization and stereochemistry directly. Also trigger on rdkit, Chem.MolFromSmiles, rdFingerprintGenerator, SDMolSupplier, SMARTS query, ETKDG, or FilterCatalog. For standard workflows with a simpler interface use the datamol skill, which wraps RDKit; use rdkit for advanced control, custom sanitization, and specialized algorithms.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Examples target RDKit 2026.03.x. Use conda-forge for the broadest binary support or PyPI package `rdkit` for supported platform wheels; `rdkit-pypi` is the legacy PyPI name.
metadata:
  version: "1.4"
  skill-author: K-Dense Inc.
---

# RDKit Cheminformatics Toolkit

## Overview

RDKit is a comprehensive cheminformatics library providing Python APIs for molecular analysis and manipulation. This skill provides guidance for reading/writing molecular structures, calculating descriptors, fingerprinting, substructure searching, chemical reactions, 2D/3D coordinate generation, and molecular visualization. Use this skill for drug discovery, computational chemistry, and cheminformatics research tasks.

**Checked against:** RDKit **2026.03.5** (`rdkit` 2026.3.5 on PyPI, released 2026-08-03), August 2026. Official installation docs continue to recommend conda-forge for most users, while cross-platform PyPI wheels are published under the `rdkit` package name. `rdkit-pypi` is the old PyPI package name and should only appear when maintaining legacy environments.

## Installation and Setup

Use `uv` when installing into an existing Python environment:

```bash
uv pip install rdkit
```

For reproducible chemistry environments, especially when mixing compiled scientific packages, conda-forge remains the upstream recommendation:

```bash
conda create -c conda-forge -n my-rdkit-env rdkit
conda activate my-rdkit-env
```

Avoid installing both conda `rdkit` and PyPI `rdkit`/`rdkit-pypi` into the same environment unless you are deliberately debugging packaging behavior. Mixed installs can make it unclear which binary extension is being imported.

## Core Capabilities

Twelve capability areas, each with worked code, are documented in
[references/core_capabilities.md](references/core_capabilities.md):

| # | Area | Covers |
| --- | --- | --- |
| 1 | Molecular I/O and creation | SMILES, MOL files and blocks, InChI, SDF and SMILES suppliers, multithreaded reading, writers |
| 2 | Sanitization and validation | disabling automatic sanitization, manual and partial sanitization, detecting problems first |
| 3 | Analysis and properties | atom and bond iteration, ring information and SSSR, chirality and stereochemistry, fragments |
| 4 | Descriptors | MW, LogP, TPSA, H-bond donors/acceptors, rotatable bonds, aromatic rings, bulk calculation, drug-likeness |
| 5 | Fingerprints and similarity | topological, Morgan/ECFP via `rdFingerprintGenerator`, MACCS, atom pair, torsion, Avalon; Tanimoto and other metrics; Butina clustering |
| 6 | Substructure searching | SMARTS queries, match retrieval, and a library of common patterns |
| 7 | Chemical reactions | reaction SMARTS, applying reactions, reaction fingerprints |
| 8 | 2D and 3D coordinates | depiction, template alignment, ETKDG embedding, force-field optimization, RMSD, constrained embedding |
| 9 | Visualization | single and grid images, substructure highlighting, custom drawer options, Jupyter integration, fingerprint bit environments |
| 10 | Molecular modification | explicit hydrogens, Kekulization, aromaticity, substructure replacement, charge neutralization |
| 11 | Hashes and standardization | Murcko scaffold and canonical hashes, regioisomer hashes, randomized SMILES for augmentation |
| 12 | Pharmacophore and 3D features | feature factories and feature extraction |

Worked workflows and the performance, thread-safety, and version-sensitivity notes are in
[references/workflows_and_best_practices.md](references/workflows_and_best_practices.md).

Prefer portable exchange formats (SMILES, SDF) for shared data; for local caches RDKit's
binary molecule representation avoids generic pickle.

## Common Pitfalls

1. **Forgetting to check for None:** Always validate molecules after parsing
2. **Sanitization failures:** Use `DetectChemistryProblems()` to debug
3. **Missing hydrogens:** Use `AddHs()` when calculating properties that depend on hydrogen
4. **2D vs 3D:** Generate appropriate coordinates before visualization or 3D analysis
5. **SMARTS matching rules:** Remember that unspecified properties match anything
6. **Thread safety with MolSuppliers:** Don't share supplier objects across threads

## Resources

### references/

All five bundled reference documents, loaded only when needed:

- [references/core_capabilities.md](references/core_capabilities.md) - the twelve capability areas above, each with worked code
- [references/workflows_and_best_practices.md](references/workflows_and_best_practices.md) - end-to-end workflows plus performance, thread-safety, and version-sensitivity notes
- [references/api_reference.md](references/api_reference.md) - RDKit modules, functions, and classes organized by functionality
- [references/descriptors_reference.md](references/descriptors_reference.md) - the available molecular descriptors with descriptions
- [references/smarts_patterns.md](references/smarts_patterns.md) - SMARTS patterns for functional groups and structural features

Only the files listed in `references/` and `scripts/` are bundled local resources. Names such as `rdkit`, `datamol`, `scipy`, and `sklearn` refer to installable Python packages, not local files in this skill.

### scripts/

```bash
# Descriptors for one molecule, or a whole file to CSV
python skills/rdkit/scripts/molecular_properties.py "CC(=O)Oc1ccccc1C(=O)O"
python skills/rdkit/scripts/molecular_properties.py --file library.smi --output properties.csv

# Fingerprint similarity screen; --method morgan|rdkit|maccs|atompair|torsion
python skills/rdkit/scripts/similarity_search.py "c1ccccc1O" library.sdf --threshold 0.6

# SMARTS filtering, with predefined libraries via --list-patterns
python skills/rdkit/scripts/substructure_filter.py library.smi --pattern "C(=O)[OH]" --report hits.csv
```

Each exits nonzero and writes to stderr on failure, so they compose in a pipeline. They are equally
usable as templates for custom workflows.

## Composing with the rest of the bundle

- `datamol` → instead: the same standardization, clustering and parallel work with sensible
  defaults. Reach for `rdkit` only when you need control datamol does not expose.
- `medchem` → after: real triage. Its rule catalogue and the full PAINS/NIBR alert sets are what you
  want for library filtering; `substructure_filter.py` here is a general SMARTS tool, not a
  curated alert set.
- `molfeat` → after: turning molecules into model-ready features rather than hand-rolled fingerprints.
- `chembl` → before: measured bioactivity to featurize, rather than a library you invented.
- `chemical-space` → after: once a SMARTS query defines the chemotype, find purchasable examples.
- `admet-prediction` / `deepchem` / `pytdc` → after: descriptors and fingerprints from here are the
  input those models expect. Desalt and standardise first or you predict on the wrong species.
