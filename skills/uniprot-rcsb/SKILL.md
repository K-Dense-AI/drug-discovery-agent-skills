---
name: uniprot-rcsb
description: Retrieve protein sequences, annotation, and structures from UniProtKB, the RCSB PDB, and AlphaFold DB. Use this skill to resolve a gene or protein name to a UniProt accession, pull sequences and FASTA files, find binding sites and domains, search the PDB by UniProt accession, sequence, ligand, or text, download mmCIF/PDB coordinates and biological assemblies, fetch AlphaFold models with their pLDDT confidence, and check whether a structure is actually usable before docking or simulating it. Also trigger on UniProt accessions, PDB ids, rest.uniprot.org, search.rcsb.org, files.rcsb.org, alphafold.ebi.ac.uk, id mapping, SEQRES, or missing residues.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+ and outbound HTTPS access to rest.uniprot.org, search.rcsb.org, data.rcsb.org, files.rcsb.org, and alphafold.ebi.ac.uk. The bundled scripts use only the Python standard library and need no API key or account.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🧬"
    homepage: https://www.rcsb.org
  hermes:
    category: research
---

# UniProt, RCSB PDB, and AlphaFold DB

The retrieval layer under every structure-based workflow: sequence in, annotation and
coordinates out, plus the checks that decide whether those coordinates are worth using.

**Services:** [rest.uniprot.org](https://rest.uniprot.org) ·
[search.rcsb.org](https://search.rcsb.org) · [data.rcsb.org](https://data.rcsb.org) ·
[files.rcsb.org](https://files.rcsb.org) · [alphafold.ebi.ac.uk](https://alphafold.ebi.ac.uk).
All unauthenticated.

Read [references/uniprot-api.md](references/uniprot-api.md) for query and field syntax,
[references/rcsb-search.md](references/rcsb-search.md) for search attributes and the data API,
and [references/choosing-a-structure.md](references/choosing-a-structure.md) before committing to
a structure — that one is judgement, not syntax.

## The four scripts

| Script | Answers |
|---|---|
| `uniprot_fetch.py` | What is this protein, what is its sequence, where are its sites, what ids does it map to |
| `rcsb_search.py` | Which structures exist, and which are worth downloading |
| `fetch_structure.py` | Get the coordinates — experimental, assembly, predicted, or ligand |
| `structure_report.py` | Is this file actually usable, and what is missing from it |

## Sequence and annotation

```bash
python skills/uniprot-rcsb/scripts/uniprot_fetch.py entry P00533
python skills/uniprot-rcsb/scripts/uniprot_fetch.py search "gene:EGFR AND organism_id:9606 AND reviewed:true"
python skills/uniprot-rcsb/scripts/uniprot_fetch.py fasta P00533 --isoforms
python skills/uniprot-rcsb/scripts/uniprot_fetch.py features P00533 --types Binding,Active,Mutagenesis
python skills/uniprot-rcsb/scripts/uniprot_fetch.py map P00533 P04637 --to PDB
```

**Put `reviewed:true` in almost every search.** UniProtKB is ~0.5 % Swiss-Prot (curated) and
~99.5 % TrEMBL (automatic); without the flag a gene-name search returns fragments and predicted
isoforms above the entry you wanted. The script reports the reviewed/unreviewed split and warns
when nothing reviewed matched.

Two UniProt behaviours the script absorbs: **pagination lives in the HTTP `Link` header**, not the
JSON body — read only the body and you silently get the first page of many — and gzip-encoded
responses are sometimes **doubly wrapped**, so one decompression leaves bytes that fail much
later as a `UnicodeDecodeError` on byte 1.

## Finding structures

```bash
# what does UniProt already cross-reference, with the residue range each covers?
python skills/uniprot-rcsb/scripts/uniprot_fetch.py pdb P00533 --max-resolution 2.0

# search the PDB properly, with ligands and mutations resolved
python skills/uniprot-rcsb/scripts/rcsb_search.py uniprot P00533 \
    --max-resolution 2.0 --has-ligand --exclude-mutants
python skills/uniprot-rcsb/scripts/rcsb_search.py sequence --fasta target.fasta --identity 0.9
python skills/uniprot-rcsb/scripts/rcsb_search.py ligand STI
python skills/uniprot-rcsb/scripts/rcsb_search.py text "SARS-CoV-2 main protease" --max-resolution 1.5
```

```
entityId  pdbId  method             resolution  rFree    ligands  uniprotIds  mutations
3POZ_1    3POZ   X-RAY DIFFRACTION  1.5         0.243    03P      P00533
3W32_1    3W32   X-RAY DIFFRACTION  1.8         0.23552  W32      P00533
2RGP_1    2RGP   X-RAY DIFFRACTION  2           0.268    HYZ      P00533
```

The RCSB search API returns **only identifiers and scores** — no resolution, no ligands, no
method. Every useful question therefore needs a second service, and the script batches that
through the data GraphQL endpoint (one request for 25 hits instead of ~60 REST calls).

Two traps it handles: a search with no hits answers **HTTP 204 with an empty body**, which
`json.loads` turns into a parse error rather than "nothing matched"; and the default
`results_content_type` **includes computational models**, so an unqualified search quietly mixes
AlphaFold predictions into a list that looks like crystal structures. The script pins
`experimental`.

`--has-ligand` excludes waters, ions, and crystallisation additives (`SO4`, `GOL`, `EDO`, `PEG`,
`MPD`, …). Without that exclusion, essentially every crystal structure looks holo.

## Downloading

```bash
python skills/uniprot-rcsb/scripts/fetch_structure.py pdb 1IEP 3POZ --out-dir structures/
python skills/uniprot-rcsb/scripts/fetch_structure.py assembly 4HHB --assembly 1
python skills/uniprot-rcsb/scripts/fetch_structure.py alphafold P00533 --metadata-only
python skills/uniprot-rcsb/scripts/fetch_structure.py ligand STI --out-dir ligands/
```

**Default to mmCIF.** Legacy `.pdb` does not exist for entries that overflow the 80-column format
— large complexes and most recent cryo-EM structures — and `files.rcsb.org/download/8ETU.pdb` is
a 404. The script says so explicitly rather than passing the 404 through.

**The asymmetric unit is not the biological unit.** Deposited coordinates may hold half a dimer
or four copies of a monomer. Use `assembly` when an interface matters.

AlphaFold output reports the confidence bands before you commit:

```
# AF-P00533-F1 (Epidermal growth factor receptor)   mean pLDDT: 75.94
band               percent
very high (>90)    47.4
confident (70-90)  23.3
low (50-70)        6.5
very low (<50)     22.8
```

An excellent kinase domain attached to a disordered tail that is 23 % of the model. Trim to the
confident region; a full-length model in a simulation box spends most of its atoms on a
prediction nobody makes. And note that **PAE, not pLDDT, governs domain arrangement** — two
confident domains can still have a guessed relative orientation.

## Checking a structure before you build on it

```bash
python skills/uniprot-rcsb/scripts/structure_report.py 3POZ.cif --gaps-near 750,790,858
```

```
## ISSUES
- 24 residues unresolved inside the modelled range (A:734-737,748-754,868-874,1004-1009)
- 10 residues present in the construct but not modelled at the chain termini (A:696-700,1018-1022)
- no hydrogens (normal for X-ray) -- add them at your target pH during receptor preparation
- 126 water atoms present -- decide deliberately which to keep
- chain A: residues of interest are UNRESOLVED: [750]
```

That last line is the point. 3POZ is a 1.5 Å structure, and a residue in the region you asked
about has no coordinates at all — your pocket has a hole in one wall, and every docking score
computed against it is optimistic. Resolution does not tell you this; nothing tells you this
except looking.

The report reads PDB and mmCIF with no parser dependency, and covers chains and numbering gaps,
non-polymer ligands with occupancy, waters and additives, alternate conformations, insertion
codes, multiple models, and hydrogens. It reads unresolved residues from `REMARK 465` /
`_pdbx_unobs_or_zero_occ_residues`, which is the only way to see **terminal** truncation — those
leave no gap in the numbering, so a report built from coordinates alone calls a truncated
construct complete.

## Numbering will not line up

UniProt numbers the canonical isoform from 1. A PDB entry carries both `auth_seq_id` (the
depositor's numbering) and `label_seq_id` (a 1-based construct index), and expression tags and
deletions shift both. Map explicitly — via `rcsb_polymer_entity_align`, or by aligning
`structure_report.py --sequence` output against the UniProt sequence. Never assume residue 790 in
the paper is residue 790 in the file.

## Composing with the rest of the bundle

- `open-targets` → this skill: its `proteinIds` are the UniProt accessions to start from.
- This skill → `autodock-vina`: a checked receptor plus a reference ligand for the box.
- This skill → `boltz`: sequences for cofolding when no suitable structure exists.
- This skill → `molecular-dynamics` / `diffdock`: coordinates, with the gaps known in advance.
- This skill → `esm` / `antibody-engineering`: sequences for language models and numbering.
- `chembl` uses UniProt accessions as its target key, so `target_components__accession=P00533`
  joins the two directly.

## Reporting honestly

Name the PDB id and its resolution, or the AlphaFold model version and its pLDDT distribution.
Say whether you used the asymmetric unit or an assembly. Say which residues near the site of
interest were unresolved. A structure-based result whose provenance is "the EGFR structure" is
not reproducible.
