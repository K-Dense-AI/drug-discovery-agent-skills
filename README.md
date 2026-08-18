# Drug Discovery Agent Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)
[![Version](https://img.shields.io/badge/Version-1.3.0-blue.svg)](pyproject.toml)
[![Skills](https://img.shields.io/badge/Skills-37-brightgreen.svg)](#whats-included)
[![Agent Skills](https://img.shields.io/badge/Standard-Agent_Skills-blueviolet.svg)](https://agentskills.io/)
[![Agent Plugins](https://img.shields.io/badge/Standard-Agent_Plugins-0A7A72.svg)](https://agent-plugins.org/)
[![Skill Tests](https://github.com/K-Dense-AI/drug-discovery-agent-skills/actions/workflows/skill-tests.yml/badge.svg)](https://github.com/K-Dense-AI/drug-discovery-agent-skills/actions/workflows/skill-tests.yml)
[![Skill Spec Validation](https://github.com/K-Dense-AI/drug-discovery-agent-skills/actions/workflows/skill-spec-validation.yml/badge.svg)](https://github.com/K-Dense-AI/drug-discovery-agent-skills/actions/workflows/skill-spec-validation.yml)

Agent Skills for small-molecule and protein therapeutics: target validation and human genetics,
bioactivity and purchasable chemical space, generative design and retrosynthesis, docking, free
energy and dynamics, ADMET and dose projection, protein, antibody, degrader and oligonucleotide
design, and the clinical and regulatory record.

Thirty-seven skills that teach your coding agent the tools computational chemists and biologists
actually use — how to install them, which API to call, what the parameters mean, and where each one
breaks. The bundle runs end to end: resolve a disease to a target, check whether healthy humans have
already lost it, pull the chemistry and structures that exist, find or design molecules, work out
whether they can be made and what dose they would need, and check what the clinic already tried.

Every skill follows the open [Agent Skills](https://agentskills.io/) standard, and the
repository is a portable [Agent Plugins](https://agent-plugins.org/) 1.0.0 package
(`plugin.json` + `skills/`). Works with **Claude Code, Cursor, Codex, Google Antigravity, and more**.
Created by [K-Dense](https://www.k-dense.ai).

> 🎬 **New to Agent Skills?** Watch [Getting Started with Scientific Agent Skills](https://youtu.be/ZxbnDaD_FVg) for a walkthrough of how these skills plug into your coding agent.

## What you can ask your agent

The skills compose — a single request usually pulls in two or three:

> **"Which targets have genetic evidence in asthma, which are small-molecule tractable, and are any of them pan-essential?"**
> `open-targets` → `depmap` → `chembl`

> **"Build me a clean EGFR IC50 dataset from ChEMBL and tell me how much of it I had to throw away."**
> `chembl` → `medchem` → `pytdc`

> **"Find the best EGFR structure with an inhibitor bound, check the ATP site is fully resolved, and dock these 200 compounds into it."**
> `uniprot-rcsb` → `medchem` → `autodock-vina`

> **"There is no structure of this target — cofold it with my hit series and predict affinity."**
> `uniprot-rcsb` → `boltz`

> **"Number this antibody, flag its CDR liabilities and glycosylation sequons, and tell me its pI."**
> `antibody-engineering` → `glycoengineering`

> **"Filter this SDF for PAINS alerts and Lipinski violations, then dock what survives into my receptor PDB."**
> `medchem` → `rdkit` → `diffdock`

> **"Is MCL1 a selective dependency in AML lines, and what does the knowledge graph link it to?"**
> `depmap` → `primekg` → `ncats-arax`

> **"Featurize these 2,000 compounds with ECFP4 and benchmark a solubility model on the TDC scaffold split."**
> `molfeat` → `pytdc` → `deepchem`

> **"Fold this sequence, check it for N-glycosylation sequons, and submit the top designs for BLI."**
> `esm` → `glycoengineering` → `adaptyv`

> **"Run 100 ns of MD on this complex and give me RMSD, RMSF, and a contact map."**
> `molecular-dynamics`

> **"Do healthy humans exist who have lost this protein, and has anyone taken it into a trial?"**
> `target-safety` → `open-targets` → `clinicaltrials`

> **"Generate analogues of this hit, throw away the ones nobody can make, and tell me what's left."**
> `generative-design` → `retrosynthesis` → `admet-prediction`

> **"Which of these twenty analogues should I actually make? I need better than a docking score."**
> `free-energy-perturbation` → `retrosynthesis`

> **"This target has no druggable pocket. What are my options?"**
> `binding-site-analysis` → `degraders` → `oligonucleotides`

> **"Is this cheap enough to buy, and is anyone already claiming it?"**
> `chemical-space` → `patent-landscape`

> **"What's already approved against this target, and what did it do to people?"**
> `openfda` → `chembl` → `clinicaltrials`

> **"I have rat PK and a cell IC50. What human dose does that imply, and is it safe?"**
> `pkpd-translation` → `admet-prediction`

> **"Design binders to this epitope and tell me which ones will provoke an immune response."**
> `protein-binder-design` → `immunogenicity` → `adaptyv`

## Getting Started

The 37 skills install together as one bundle — they cross-reference each other, and the agent
loads only the ones a given task calls for.

### Option 1: `skills` CLI (npx)

Detects your installed agent hosts and installs there.

```bash
npx skills add K-Dense-AI/drug-discovery-agent-skills
```

### Option 2: GitHub CLI (`gh skill`, v2.90.0+)

```bash
# Install the bundle
gh skill install K-Dense-AI/drug-discovery-agent-skills

# Pin to a release tag for reproducible installs
gh skill install K-Dense-AI/drug-discovery-agent-skills --pin v1.3.0
```

### Option 3: Agent Plugins (Cursor, Codex, and other plugin clients)

This repository is a valid [Agent Plugins](https://agent-plugins.org/) 1.0.0 package. For example, in Cursor:

```bash
mkdir -p ~/.cursor/plugins/local
ln -s "$(pwd)" ~/.cursor/plugins/local/drug-discovery-agent-skills
```

### Option 4: Manual (hosts that scan `~/.agents/skills/`)

```bash
git clone https://github.com/K-Dense-AI/drug-discovery-agent-skills.git ~/.agents/skills/drug-discovery-agent-skills   # user-level
git clone https://github.com/K-Dense-AI/drug-discovery-agent-skills.git .agents/skills/drug-discovery-agent-skills      # project-level
```

Installing a skill installs instructions, not packages. The agent sets up each tool's environment
when you first use it, following the requirements in that skill's `SKILL.md`.

## What's included

The **Needs** column is the first thing worth checking: `local` runs on your machine with no
account, `network, no key` reaches a public API that needs no credentials, `key` requires
credentials you supply, `GPU` means practical runtimes need one, and a Python bound means that
tool will not install on a newer interpreter.

### Databases and retrieval

| Skill | Use it for | Needs |
|---|---|---|
| [`open-targets`](skills/open-targets) | Target-disease associations, genetic and clinical evidence, tractability buckets, safety liabilities, prioritisation metrics — the question that comes before any modelling | network, no key |
| [`chembl`](skills/chembl) | Measured bioactivity: curated SAR datasets for a target, compound lookup by structure or name, similarity and substructure search, mechanisms of action | network, no key |
| [`uniprot-rcsb`](skills/uniprot-rcsb) | Sequences, domains and binding sites, PDB search by accession or sequence, mmCIF and AlphaFold downloads, and the check that a structure is usable before you build on it | network, no key |
| [`chemical-space`](skills/chemical-space) | Make-on-demand catalogues — ZINC-22 through CartBlanche, Enamine REAL synthon space — purchasability with price and lead time, tranche selection, and costing a giga-scale screening cascade | network, no key |
| [`patent-landscape`](skills/patent-landscape) | Whether a series is already claimed: SureChEMBL's patent-extracted chemistry through its bulk tree, and US assignee filings through PatentsView | network; bulk FTP, optional key |

### Target discovery and knowledge graphs

| Skill | Use it for | Needs |
|---|---|---|
| [`depmap`](skills/depmap) | Cancer cell-line dependency scores (CRISPR Chronos), drug sensitivity, and gene-effect profiles — finding selective vulnerabilities and synthetic lethals | local + public data download |
| [`primekg`](skills/primekg) | Querying the Precision Medicine Knowledge Graph across genes, drugs, diseases, and phenotypes | local + dataset download (`PRIMEKG_DATA`) |
| [`ncats-arax`](skills/ncats-arax) | Provenance-rich one- and two-hop biomedical relationships from NCATS Translator ARAX, with Biolink typing and source attribution | network, no key |
| [`target-safety`](skills/target-safety) | Human genetic evidence before a molecule exists: gnomAD constraint (LOEUF, pLI) for whether healthy human knockouts exist, and GWAS Catalog associations for whether losing the protein does anything | network, no key |

### Cheminformatics and compound triage

| Skill | Use it for | Needs |
|---|---|---|
| [`rdkit`](skills/rdkit) | Descriptors, fingerprints, substructure search, reactions, 2D/3D generation — when you need fine-grained control | local |
| [`datamol`](skills/datamol) | The same work with sensible defaults: standardization, clustering, parallel processing over SMILES | local |
| [`medchem`](skills/medchem) | Triaging libraries: Lipinski/Veber/CNS rules, PAINS and NIBR alerts, complexity metrics, query-language filters | local |

### Molecular ML and property prediction

| Skill | Use it for | Needs |
|---|---|---|
| [`molfeat`](skills/molfeat) | Turning SMILES into features — 100+ featurizers from ECFP and MACCS to pretrained ChemBERTa | local, Python ≤ 3.10 |
| [`deepchem`](skills/deepchem) | ADMET and toxicity prediction with MoleculeNet benchmarks and pretrained models | local, Python ≤ 3.11 |
| [`pytdc`](skills/pytdc) | Therapeutics Data Commons datasets, task-aware splits, evaluator metrics, and benchmark groups | local, Python 3.11, downloads |
| [`admet-prediction`](skills/admet-prediction) | Ready-made ADMET numbers from ADMET-AI across 41 TDC endpoints, read as percentiles against approved drugs and flagged per endpoint direction | local, Python 3.11+ |

### Structure, docking, and simulation

| Skill | Use it for | Needs |
|---|---|---|
| [`autodock-vina`](skills/autodock-vina) | Classical docking: box definition, receptor and ligand preparation through Meeko, batch screening, and pose/affinity interpretation with the box-edge and convergence checks | local, Vina + Meeko binaries |
| [`boltz`](skills/boltz) | Boltz-2 cofolding with a trained binding-affinity head — structure and potency for a complex with no experimental structure | GPU, `pip install boltz` |
| [`diffdock`](skills/diffdock) | Protein–ligand pose prediction from PDB + SMILES, batch docking, and reading pose confidence (not affinity) | GPU, repo or Docker install |
| [`molecular-dynamics`](skills/molecular-dynamics) | OpenMM + MDAnalysis end to end: system setup, minimization, production MD, RMSD/RMSF/contacts/free-energy surfaces | GPU recommended |
| [`esm`](skills/esm) | ESM3 and ESMC through the `esm` SDK, ESMFold2 folding, and Forge/Biohub inference clients | GPU locally, or `ESM_API_KEY` |
| [`binding-site-analysis`](skills/binding-site-analysis) | Whether a pocket is worth targeting at all: fpocket cavity detection and druggability, apo/holo comparison for cryptic sites, and the docking box coordinates that follow | local, fpocket binary |
| [`free-energy-perturbation`](skills/free-energy-perturbation) | Rigorous relative binding free energies with OpenFE — perturbation network design, cycle-closure validation, and error against experiment | GPU, conda-forge only |

### Biologics

| Skill | Use it for | Needs |
|---|---|---|
| [`antibody-engineering`](skills/antibody-engineering) | IMGT/Kabat/Chothia numbering and CDR annotation, sequence-liability scanning weighted by region, pI and charge profiling, and humanisation planning | local; numbering needs ANARCI + HMMER |
| [`glycoengineering`](skills/glycoengineering) | N-glycosylation sequon scanning, O-glycosylation hotspots, and curated glycoengineering tooling | local |
| [`protein-binder-design`](skills/protein-binder-design) | De novo binders with BindCraft or RFdiffusion: epitope and hotspot selection, target trimming, and filtering designs on the interface metrics that predict success | GPU, BindCraft install |
| [`immunogenicity`](skills/immunogenicity) | Anti-drug antibody risk from sequence: class II epitope tiling, NetMHCIIpan output parsing, promiscuity across a population allele panel, and deimmunisation planning | local; NetMHCpan needs academic licence |

### Cloud platforms and wet-lab handoff

| Skill | Use it for | Needs |
|---|---|---|
| [`rowan`](skills/rowan) | pKa/macropKa, conformers and tautomers, cofolding, permeability — batch chemistry without local HPC | key (`ROWAN_API_KEY`), Python 3.12+ |
| [`tamarind`](skills/tamarind) | Cloud runs of AlphaFold, Boltz, RFdiffusion, ProteinMPNN, Vina, and more via REST or MCP — no local GPUs | key |
| [`adaptyv`](skills/adaptyv) | Designing and submitting real protein experiments (BLI/SPR, thermostability) and pulling results back | key |

### Design and synthesis

| Skill | Use it for | Needs |
|---|---|---|
| [`generative-design`](skills/generative-design) | REINVENT 4 de novo generation, scaffold decoration, linker design and analogue generation — building the run config, composing a multi-parameter objective, and detecting mode collapse | GPU, REINVENT4 from GitHub |
| [`retrosynthesis`](skills/retrosynthesis) | Whether a molecule can actually be made: AiZynthFinder route search, solved fraction against a named stock, route depth, and the building blocks a series shares | local, Python 3.10–3.12 |

### Clinical, regulatory, and translational

| Skill | Use it for | Needs |
|---|---|---|
| [`clinicaltrials`](skills/clinicaltrials) | The ClinicalTrials.gov v2 registry: who is developing what, phases and enrolment, primary endpoints, eligibility, and why studies stopped | network, no key |
| [`openfda`](skills/openfda) | The post-market record: FAERS adverse events with PRR/ROR disproportionality, Drugs@FDA approvals and efficacy supplements, and Structured Product Labels | network, no key |
| [`pkpd-translation`](skills/pkpd-translation) | From IC50 to a dose: non-compartmental analysis, steady-state simulation, allometric scaling and human equivalent dose, and free-drug exposure margins | local |

### Modalities beyond small molecules

| Skill | Use it for | Needs |
|---|---|---|
| [`degraders`](skills/degraders) | PROTACs and molecular glues: beyond-rule-of-five property windows, E3 and linker choice, ternary complex prediction setup, and reading DC50, Dmax and the hook effect | local |
| [`oligonucleotides`](skills/oligonucleotides) | siRNA and antisense design: transcript tiling, nearest-neighbour thermodynamics, duplex asymmetry, seed off-target scanning, and gapmer modification patterns | local |

## Version pinning

`main` is the development branch: skills change there between releases. For reproducible installs,
pin to a release tag and move the pin forward deliberately.

```bash
gh skill install K-Dense-AI/drug-discovery-agent-skills --pin v1.3.0   # a release tag
git clone --branch v1.3.0 --depth 1 https://github.com/K-Dense-AI/drug-discovery-agent-skills.git
```

Each skill also carries its own `metadata.version` in its `SKILL.md`, bumped whenever that skill
changes — check it to see whether an upgrade touched the skills you actually use. A pin you never
move stops receiving fixes, including security fixes; see [SECURITY.md](SECURITY.md).

## How these are maintained

Skill instructions rot faster than code, so the repository is set up to catch that:

- **Spec-validated on every pull request.** All 37 skills run through
  [`skills-ref validate`](https://github.com/agentskills/agentskills/tree/main/skills-ref) against
  the Agent Skills specification, plus repo rules the reference validator does not cover.
  `plugin.json` conforms to Agent Plugins 1.0.0.
- **Tested in the environment each tool actually needs.** Skills with bundled scripts have pytest
  suites that run in isolated per-skill `uv` environments defined in
  [`tests/skill-requirements.toml`](tests/skill-requirements.toml) — Python 3.10 for `molfeat`,
  3.11 for `deepchem` and `pytdc` — so one tool's pins never constrain another's. The
  database skills ship standard-library-only clients and so have no dependencies to pin at all. A
  repo-wide contract and coverage guard runs alongside them.
- **Dated version baselines.** `SKILL.md` files record the upstream release they were checked
  against, so you can tell how current the guidance is before trusting it.
- **Scanned automatically.** [`cisco-ai-skill-scanner`](https://pypi.org/project/cisco-ai-skill-scanner/)
  runs on every pull request and weekly; the current report is in
  [`docs/security-report.md`](docs/security-report.md).

## Security disclaimer

Agent Skills are instructions an AI agent reads, plus scripts it may execute on your machine. That
is what makes them useful, and it is also the risk: installing a skill grants it the agent's
reach over your files, your credentials, and the network.

- **Review the bundle before you install it.** Read the `SKILL.md` files for the tools you expect
  to use, and check [`docs/security-report.md`](docs/security-report.md).
- Skills here reach external services and read API keys from your environment. Some are
  unauthenticated public APIs (Open Targets, ChEMBL, UniProt, RCSB PDB, AlphaFold DB, NCATS ARAX,
  DepMap, ClinicalTrials.gov, openFDA, gnomAD, GWAS Catalog, CartBlanche/ZINC-22, and the
  SureChEMBL bulk tree); others need credentials you supply (Adaptyv, ESM Forge, Rowan, Tamarind,
  and optionally PatentsView). Each
  `SKILL.md` says which credentials and network access it needs — read that section before
  supplying a key. Note that a query sent to a public API is not private: `boltz --use_msa_server`
  sends sequences to the public ColabFold server, and knowledge-graph queries may be logged.
- Bundled scripts run scientific tooling. Nothing here is validated for clinical, diagnostic, or
  regulatory use; treat every result as a hypothesis to confirm with your own methods.
- A skill performing the work it documents is not a vulnerability. Something a skill does that its
  documentation does not describe **is** — report it per [SECURITY.md](SECURITY.md).

Scanning is a prompt to review, not a certification.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for skill authoring rules, testing requirements, and the
pull-request checklist. Report vulnerabilities per [SECURITY.md](SECURITY.md), not in public issues.

## License

[MIT](LICENSE.md) — created and maintained by [K-Dense](https://www.k-dense.ai).

The MIT license covers the skill instructions and bundled scripts in this repository. The tools and
services these skills drive carry their own licenses and terms of use; each `SKILL.md` records the
license it found upstream, and several platform skills are marked proprietary and API-key-gated.

[![X](https://img.shields.io/badge/Follow_on_X-%40k__dense__ai-000000?logo=x)](https://x.com/k_dense_ai)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-K--Dense_Inc.-0A66C2?logo=linkedin)](https://www.linkedin.com/company/k-dense-inc)
[![YouTube](https://img.shields.io/badge/YouTube-K--Dense_Inc.-FF0000?logo=youtube)](https://www.youtube.com/@K-Dense-Inc)
[![Reddit](https://img.shields.io/badge/Reddit-u%2F--k--dense---FF4500?logo=reddit&logoColor=white)](https://www.reddit.com/user/-k-dense-/)
