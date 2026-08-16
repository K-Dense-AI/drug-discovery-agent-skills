# Antibody tooling

What exists, what it is for, and how to install it.

## Numbering and annotation

| Tool | Install | Use |
|---|---|---|
| **ANARCI** | `pip install anarci` + HMMER | Numbering in any scheme; chain-type identification. The foundation everything else sits on |
| **AbNumber** | `conda install -c bioconda abnumber` | Friendlier Python API over ANARCI: regions, slicing, alignment, CDR grafting. Not on Windows |
| **IgBLAST** | NCBI download, or `conda install -c bioconda igblast` | Germline V/D/J assignment with identities. The standard for repertoire work |
| **IMGT/V-QUEST** | Web | The reference annotation, authoritative but not scriptable |
| **Change-O / pRESTO** | `pip install changeo presto` | Repertoire pipelines: clonal clustering, lineage trees |

HMMER is the awkward dependency. `conda install -c bioconda hmmer`, `brew install hmmer`, or
your distribution's package. Without `hmmscan` on PATH, ANARCI imports and then fails at run
time.

## Structure prediction

| Tool | Speed | Notes |
|---|---|---|
| **ABodyBuilder3** | Seconds | Antibody-specific, accurate framework and canonical CDRs; CDR-H3 is the hard part, as always |
| **IgFold** | Seconds | Language-model based, comparable accuracy, bundles refinement |
| **Boltz-2** (this bundle) | Minutes on a GPU | General cofolding; the option when you need antigen complex, not just Fv |
| **AlphaFold-Multimer** | Slow | Antibody–antigen complexes remain hard for general folders |
| **Rosetta antibody** | Slow | Classical, good CDR loop modelling |

For developability work, an ABodyBuilder3 or IgFold model of the Fv is enough and takes seconds.
For an antibody–antigen complex, expect low confidence and check ipTM before believing the
interface — antibody–antigen docking is the acknowledged weak spot of every current method,
because the interface is a rearranged loop, not a conserved surface.

## Repertoire and reference data

| Resource | Contents |
|---|---|
| **OAS** (Observed Antibody Space) | > 10⁹ annotated repertoire sequences. Ask "is this CDR-H3 natural?", "how common is this framework?" |
| **SAbDab** | Every antibody structure in the PDB, annotated with numbering, species, antigen, and affinity where known |
| **Thera-SAbDab** | Therapeutic antibodies, with clinical stage — the reference set for "is my property in the clinical-stage range?" |
| **abYsis** | Integrated sequence and structure database with numbering |
| **IMGT** | Germline gene reference; the source of the germline sequences everyone aligns to |

Thera-SAbDab is what makes a developability flag meaningful: a property is concerning when it
sits outside the distribution of molecules that reached the clinic, not when it exceeds an
arbitrary cut-off.

## Developability

| Tool | Kind |
|---|---|
| **TAP** (Therapeutic Antibody Profiler) | Structure-based; five metrics against clinical-stage distributions |
| **`scan_liabilities.py`** (this skill) | Sequence motifs, region-weighted |
| **`physchem_profile.py`** (this skill) | pI, charge, extinction, GRAVY |
| **Hu-mAb / OASis** | Humanness scoring against the human repertoire |
| **NetMHCIIpan** | T-cell epitope prediction |
| **SAP / SASA patch analysis** | Structure-based aggregation propensity |

## Design

| Tool | Kind |
|---|---|
| **AbLang / AntiBERTy / ESM** | Antibody or general protein language models; scoring and infilling |
| **RFdiffusion / RFantibody** | De novo binder design; antibody-specific variants exist |
| **ProteinMPNN** | Sequence design onto a fixed backbone |
| **Rosetta / FoldX** | Physics-based stability and affinity prediction for point mutants |
| **`adaptyv`** (this bundle) | Submit designs to a cloud lab and get measured binding back |

## A workable order of operations

1. **Number** — `number_antibody.py --format regions`. Everything downstream needs regions.
2. **Scan** — `scan_liabilities.py --regions`. Cheap, immediate, catches the classics.
3. **Profile** — `physchem_profile.py`. pI, charge, extinction coefficient.
4. **Model** — ABodyBuilder3 or IgFold for the Fv.
5. **Structure-based properties** — TAP metrics, hydrophobic and charged patches.
6. **Humanness** — germline identity, then a repertoire-based score if the molecule is not
   already human.
7. **Test** — force degradation on the predicted liabilities; SEC, DSF, HIC, AC-SINS, PSR.

Steps 1–3 take seconds and rule out a surprising fraction of problems. Do them before spending a
GPU hour or a wet-lab week.

## Composing with the rest of this bundle

- `esm` — protein language models for variant scoring and embeddings.
- `glycoengineering` — the N-glycosylation sequons this skill flags, in depth: site occupancy,
  glycoform engineering, effector-function consequences.
- `boltz` — antibody–antigen cofolding when you need the complex.
- `uniprot-rcsb` — pull the antigen sequence and structure; SAbDab entries are PDB entries.
- `adaptyv` — turn designs into measured binding data.
- `open-targets` — is the antigen a validated target, and is it accessible to a biologic?
  (Its `AB` tractability buckets are exactly that question.)
