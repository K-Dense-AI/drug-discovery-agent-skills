# 💊 Drug Discovery Agent Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)
[![Version](https://img.shields.io/badge/Version-1.0.0-blue.svg)](pyproject.toml)
[![Skills](https://img.shields.io/badge/Skills-17-brightgreen.svg)](#-whats-included)
[![Agent Skills](https://img.shields.io/badge/Standard-Agent_Skills-blueviolet.svg)](https://agentskills.io/)
[![Agent Plugins](https://img.shields.io/badge/Standard-Agent_Plugins-0A7A72.svg)](https://agent-plugins.org/)
[![Skill Tests](https://github.com/K-Dense-AI/drug-discovery-agent-skills/actions/workflows/skill-tests.yml/badge.svg)](https://github.com/K-Dense-AI/drug-discovery-agent-skills/actions/workflows/skill-tests.yml)
[![Skill Spec Validation](https://github.com/K-Dense-AI/drug-discovery-agent-skills/actions/workflows/skill-spec-validation.yml/badge.svg)](https://github.com/K-Dense-AI/drug-discovery-agent-skills/actions/workflows/skill-spec-validation.yml)

Agent Skills for small-molecule and protein therapeutics: cheminformatics, molecular ML, docking and
dynamics, protein design platforms, and target-discovery knowledge graphs.

Seventeen skills that teach your coding agent the tools computational chemists and biologists
actually use — how to install them, which API to call, what the parameters mean, and where each one
breaks. Every skill follows the open [Agent Skills](https://agentskills.io/) standard, and the
repository is a portable [Agent Plugins](https://agent-plugins.org/) 1.0.0 package
(`plugin.json` + `skills/`). Works with **Claude Code, Cursor, Codex, Google Antigravity, and more**.
Created by [K-Dense](https://www.k-dense.ai).

## 💬 What you can ask your agent

The skills compose — a single request usually pulls in two or three:

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

## 🎯 Getting Started

The 17 skills install together as one bundle — they cross-reference each other, and the agent
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
gh skill install K-Dense-AI/drug-discovery-agent-skills --pin v1.0.0
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

## 📦 What's included

The **Needs** column is the first thing worth checking: `local` runs on your machine with no
account, `key` requires credentials you supply, `GPU` means practical runtimes need one, and a
Python bound means that tool will not install on a newer interpreter.

### Target discovery and knowledge graphs

| Skill | Use it for | Needs |
|---|---|---|
| [`depmap`](skills/depmap) | Cancer cell-line dependency scores (CRISPR Chronos), drug sensitivity, and gene-effect profiles — finding selective vulnerabilities and synthetic lethals | local + public data download |
| [`primekg`](skills/primekg) | Querying the Precision Medicine Knowledge Graph across genes, drugs, diseases, and phenotypes | local + dataset download (`PRIMEKG_DATA`) |
| [`ncats-arax`](skills/ncats-arax) | Provenance-rich one- and two-hop biomedical relationships from NCATS Translator ARAX, with Biolink typing and source attribution | network, no key |

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
| [`torchdrug`](skills/torchdrug) | Graph-first PyTorch workflows: GNN property prediction, pretraining, generation, retrosynthesis | local, Python ≤ 3.10 |
| [`pytdc`](skills/pytdc) | Therapeutics Data Commons datasets, task-aware splits, evaluator metrics, and benchmark groups | local, Python 3.11, downloads |

### Structure, docking, and simulation

| Skill | Use it for | Needs |
|---|---|---|
| [`diffdock`](skills/diffdock) | Protein–ligand pose prediction from PDB + SMILES, batch docking, and reading pose confidence (not affinity) | GPU, repo or Docker install |
| [`molecular-dynamics`](skills/molecular-dynamics) | OpenMM + MDAnalysis end to end: system setup, minimization, production MD, RMSD/RMSF/contacts/free-energy surfaces | GPU recommended |
| [`esm`](skills/esm) | ESM3 and ESMC through the `esm` SDK, ESMFold2 folding, and Forge/Biohub inference clients | GPU locally, or `ESM_API_KEY` |

### Cloud platforms and wet-lab handoff

| Skill | Use it for | Needs |
|---|---|---|
| [`rowan`](skills/rowan) | pKa/macropKa, conformers and tautomers, cofolding, permeability — batch chemistry without local HPC | key (`ROWAN_API_KEY`), Python 3.12+ |
| [`tamarind`](skills/tamarind) | Cloud runs of AlphaFold, Boltz, RFdiffusion, ProteinMPNN, Vina, and more via REST or MCP — no local GPUs | key |
| [`adaptyv`](skills/adaptyv) | Designing and submitting real protein experiments (BLI/SPR, thermostability) and pulling results back | key |
| [`glycoengineering`](skills/glycoengineering) | N-glycosylation sequon scanning, O-glycosylation hotspots, and curated glycoengineering tooling | local |

## 📌 Version pinning

`main` is the development branch: skills change there between releases. For reproducible installs,
pin to a release tag and move the pin forward deliberately.

```bash
gh skill install K-Dense-AI/drug-discovery-agent-skills --pin v1.0.0   # a release tag
git clone --branch v1.0.0 --depth 1 https://github.com/K-Dense-AI/drug-discovery-agent-skills.git
```

Each skill also carries its own `metadata.version` in its `SKILL.md`, bumped whenever that skill
changes — check it to see whether an upgrade touched the skills you actually use. A pin you never
move stops receiving fixes, including security fixes; see [SECURITY.md](SECURITY.md).

## 🔬 How these are maintained

Skill instructions rot faster than code, so the repository is set up to catch that:

- **Spec-validated on every pull request.** All 17 skills run through
  [`skills-ref validate`](https://github.com/agentskills/agentskills/tree/main/skills-ref) against
  the Agent Skills specification, plus repo rules the reference validator does not cover.
  `plugin.json` conforms to Agent Plugins 1.0.0.
- **Tested in the environment each tool actually needs.** Skills with bundled scripts have pytest
  suites that run in isolated per-skill `uv` environments defined in
  [`tests/skill-requirements.toml`](tests/skill-requirements.toml) — Python 3.10 for `molfeat` and
  `torchdrug`, 3.11 for `deepchem` and `pytdc` — so one tool's pins never constrain another's. A
  repo-wide contract and coverage guard runs alongside them.
- **Dated version baselines.** `SKILL.md` files record the upstream release they were checked
  against, so you can tell how current the guidance is before trusting it.
- **Scanned automatically.** [`cisco-ai-skill-scanner`](https://pypi.org/project/cisco-ai-skill-scanner/)
  runs on every pull request and weekly; the current report is in
  [`docs/security-report.md`](docs/security-report.md).

## 🔒 Security disclaimer

Agent Skills are instructions an AI agent reads, plus scripts it may execute on your machine. That
is what makes them useful, and it is also the risk: installing a skill grants it the agent's
reach over your files, your credentials, and the network.

- **Review the bundle before you install it.** Read the `SKILL.md` files for the tools you expect
  to use, and check [`docs/security-report.md`](docs/security-report.md).
- Skills here reach external services (Adaptyv, ESM Forge, Rowan, Tamarind, NCATS ARAX, DepMap) and
  read API keys from your environment. Each `SKILL.md` says which credentials and network access it
  needs — read that section before supplying a key.
- Bundled scripts run scientific tooling. Nothing here is validated for clinical, diagnostic, or
  regulatory use; treat every result as a hypothesis to confirm with your own methods.
- A skill performing the work it documents is not a vulnerability. Something a skill does that its
  documentation does not describe **is** — report it per [SECURITY.md](SECURITY.md).

Scanning is a prompt to review, not a certification.

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for skill authoring rules, testing requirements, and the
pull-request checklist. Report vulnerabilities per [SECURITY.md](SECURITY.md), not in public issues.

## 📜 License

[MIT](LICENSE.md) — created and maintained by [K-Dense](https://www.k-dense.ai).

The MIT license covers the skill instructions and bundled scripts in this repository. The tools and
services these skills drive carry their own licenses and terms of use; each `SKILL.md` records the
license it found upstream, and several platform skills are marked proprietary and API-key-gated.

[![X](https://img.shields.io/badge/Follow_on_X-%40k__dense__ai-000000?logo=x)](https://x.com/k_dense_ai)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-K--Dense_Inc.-0A66C2?logo=linkedin)](https://www.linkedin.com/company/k-dense-inc)
[![YouTube](https://img.shields.io/badge/YouTube-K--Dense_Inc.-FF0000?logo=youtube)](https://www.youtube.com/@K-Dense-Inc)
[![Reddit](https://img.shields.io/badge/Reddit-u%2F--k--dense---FF4500?logo=reddit&logoColor=white)](https://www.reddit.com/user/-k-dense-/)
