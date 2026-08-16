# Boltz input YAML

One file describes one complex. `boltz predict` accepts a single YAML or a directory of them.
FASTA input is deprecated — use YAML.

## Full schema

```yaml
version: 1
sequences:
  - ENTITY_TYPE:              # protein | dna | rna | ligand
      id: CHAIN_ID            # or [A, B] for identical copies
      sequence: SEQUENCE      # polymers only
      smiles: 'SMILES'        # ligand only, exclusive with ccd
      ccd: CCD                # ligand only, exclusive with smiles
      msa: MSA_PATH           # protein only; `empty` for single-sequence mode
      modifications:
        - position: RES_IDX   # 1-based
          ccd: CCD
      cyclic: false
constraints:
  - bond:
      atom1: [CHAIN_ID, RES_IDX, ATOM_NAME]
      atom2: [CHAIN_ID, RES_IDX, ATOM_NAME]
  - pocket:
      binder: CHAIN_ID
      contacts: [[CHAIN_ID, RES_IDX], [CHAIN_ID, ATOM_NAME]]
      max_distance: 6
      force: false
  - contact:
      token1: [CHAIN_ID, RES_IDX]
      token2: [CHAIN_ID, RES_IDX]
      max_distance: 6
      force: false
templates:
  - cif: path/to/template.cif
    chain_id: [A]
    template_id: [A]
    force: false
    threshold: 5.0
properties:
  - affinity:
      binder: CHAIN_ID
```

## Sequences

- `protein`, `dna`, `rna` take `sequence`; `ligand` takes `smiles` **or** `ccd`, never both.
- `id` must be unique. A list (`[A, B]`) creates identical copies of that entity — the right way
  to build a homodimer, and much cheaper than repeating the block.
- **Always quote SMILES.** `#` starts a YAML comment, so an unquoted alkyne truncates the string
  silently; `[`, `\`, and `,` also have YAML meanings.
- CCD codes come from the PDB chemical component dictionary (`ATP`, `SAH`, `HEM`, `STI`). The
  `uniprot-rcsb` skill's `fetch_structure.py ligand <ID>` prints the code, name, and SMILES.

## MSA

Protein chains need an MSA. Three options:

| Option | How | When |
|---|---|---|
| Auto | omit `msa`, run with `--use_msa_server` | Quick work on non-confidential sequences |
| Precomputed | `msa: path/to/aln.a3m` | Screens, reproducibility, confidential sequences |
| None | `msa: empty` | Smoke tests only — accuracy drops noticeably |

`--use_msa_server` sends your sequence to the public ColabFold server. **Do not use it for
unpublished targets.**

For several protein chains that must be paired, the MSA is a CSV with `sequence` and `key`
columns; rows sharing a key are treated as aligned across chains.

In a screen, all N inputs share one protein, so compute the MSA once and point every YAML at it.
That is usually the largest single saving — `screen_library.py --msa-path` does it.

## Constraints

**`pocket`** is the one that matters most for docking. It tells the model where the binder goes:

```yaml
constraints:
  - pocket:
      binder: B                                  # the ligand chain
      contacts: [[A, 790], [A, 797], [A, 855]]   # pocket residues, 1-based
      max_distance: 6                            # 4-20 A, default 6
      force: false                               # true adds an enforcing potential
```

Without it, Boltz decides where to put the ligand — often correctly for a well-defined site, less
so for a shallow or multi-site protein. With known pocket residues, supply them. `force: true`
makes it a hard constraint rather than a bias; use it when you are confident, since forcing a
wrong pocket produces a confident wrong answer.

`bond` specifies covalent links (CCD ligands and canonical residues only). `contact` restrains a
single residue or atom pair. `RES_IDX` is 1-based, and for a ligand chain it is 1.

## Templates

Provide a CIF or PDB to bias the fold. Boltz matches chains automatically unless you give
`chain_id` and `template_id`. `force: true` requires `threshold` — the Angstrom deviation the
prediction may take from the template.

Useful when you have an experimental structure of the apo protein and want the model to keep it
while placing a ligand.

## Affinity

```yaml
properties:
  - affinity:
      binder: B
```

Constraints, from the Boltz documentation:

- Exactly **one** small molecule per prediction. It must be a `ligand` chain, not a polymer.
- At most **128 atoms** (heavy plus hydrogens kept by RDKit's `RemoveHs`).
- The head was trained on ligands up to roughly **56 atoms**; beyond that, expect degradation.
- **Protein targets only.** With an RNA/DNA/cofactor target the code runs and the output is
  unreliable.

The affinity module is a separate head from the structure module, so requesting it costs extra
time (`--diffusion_samples_affinity`, default 5) on top of the structure prediction.

## Worked examples

Protein–ligand with affinity:

```yaml
version: 1
sequences:
  - protein:
      id: A
      sequence: MVTPEGNVSLVDESLLVGVTDEDRAVRSAHQFYERLIG
  - ligand:
      id: B
      smiles: 'Cc1ccc(cc1Nc1nccc(n1)c1cccnc1)NC(=O)c1ccc(CN2CCN(C)CC2)cc1'
properties:
  - affinity:
      binder: B
```

Homodimer with a cofactor and a pocket constraint, single-sequence mode:

```yaml
version: 1
sequences:
  - protein:
      id: [A, B]
      sequence: MVTPEG...
      msa: empty
  - ligand:
      id: C
      ccd: SAH
constraints:
  - pocket:
      binder: C
      contacts: [[A, 790], [A, 797], [B, 855]]
      max_distance: 6.0
      force: true
```

Protein–protein complex (no affinity — the head is small-molecule only):

```yaml
version: 1
sequences:
  - protein:
      id: A
      sequence: RECEPTOR_SEQUENCE
  - protein:
      id: B
      sequence: BINDER_SEQUENCE
```

`make_boltz_yaml.py` builds all of these and validates the parts that fail at runtime: unknown
amino-acid characters, an affinity binder that is not a ligand chain, `--pocket` without a
ligand, and an out-of-range `max_distance`.
