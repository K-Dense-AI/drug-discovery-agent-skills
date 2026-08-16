# 💊 Drug Discovery Agent Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)
[![Version](https://img.shields.io/badge/Version-1.0.0-blue.svg)](pyproject.toml)
[![Skills](https://img.shields.io/badge/Skills-17-brightgreen.svg)](#-whats-included)
[![Agent Skills](https://img.shields.io/badge/Standard-Agent_Skills-blueviolet.svg)](https://agentskills.io/)
[![Agent Plugins](https://img.shields.io/badge/Standard-Agent_Plugins-0A7A72.svg)](https://agent-plugins.org/)
[![X](https://img.shields.io/badge/Follow_on_X-%40k__dense__ai-000000?logo=x)](https://x.com/k_dense_ai)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-K--Dense_Inc.-0A66C2?logo=linkedin)](https://www.linkedin.com/company/k-dense-inc)
[![YouTube](https://img.shields.io/badge/YouTube-K--Dense_Inc.-FF0000?logo=youtube)](https://www.youtube.com/@K-Dense-Inc)
[![Reddit](https://img.shields.io/badge/Reddit-u%2F--k--dense---FF4500?logo=reddit&logoColor=white)](https://www.reddit.com/user/-k-dense-/)

Agent Skills for small-molecule and protein therapeutics: cheminformatics, molecular ML, docking and dynamics, protein design platforms, and target-discovery knowledge graphs.

Part of the **K-Dense agent skills family** — 17 of the ready-to-use skills from
[scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills), repackaged as a
focused, standalone bundle so your agent loads only the domains you work in. Every skill follows
the open [Agent Skills](https://agentskills.io/) standard, and the repository is a portable
[Agent Plugins](https://agent-plugins.org/) 1.0.0 package (`plugin.json` + `skills/`). Works with
**Claude Code, Cursor, Codex, Google Antigravity, and more**. Created by [K-Dense](https://www.k-dense.ai).

## 🎯 Getting Started

### Option 1: npx (supported hosts)

```bash
npx skills add K-Dense-AI/drug-discovery-agent-skills
```

### Option 2: GitHub CLI (`gh skill`, v2.90.0+)

```bash
# Install the whole bundle
gh skill install K-Dense-AI/drug-discovery-agent-skills

# Install a single skill
gh skill install K-Dense-AI/drug-discovery-agent-skills adaptyv

# Pin to a release tag for reproducible installs
gh skill install K-Dense-AI/drug-discovery-agent-skills --pin v1.0.0
```

### Option 3: Agent Plugins (Cursor, Codex, and other plugin clients)

This repository is a valid [Agent Plugins](https://agent-plugins.org/) 1.0.0 package. For example, in Cursor:

```bash
mkdir -p ~/.cursor/plugins/local
ln -s "$(pwd)" ~/.cursor/plugins/local/drug-discovery-agent-skills
```

### Manual install (hosts that scan `~/.agents/skills/`)

```bash
git clone https://github.com/K-Dense-AI/drug-discovery-agent-skills.git ~/.agents/skills/drug-discovery-agent-skills   # user-level
git clone https://github.com/K-Dense-AI/drug-discovery-agent-skills.git .agents/skills/drug-discovery-agent-skills      # project-level
```

## 📦 What's included

| Skill | What it does |
|---|---|
| [`adaptyv`](skills/adaptyv) | How to use the Adaptyv Bio Foundry API and Python SDK for protein experiment design, submission, and results retrieval. |
| [`datamol`](skills/datamol) | Pythonic wrapper around RDKit with simplified interface and sensible defaults. |
| [`deepchem`](skills/deepchem) | Molecular ML with diverse featurizers and pre-built datasets. |
| [`depmap`](skills/depmap) | Query the Cancer Dependency Map (DepMap) for cancer cell line gene dependency scores (CRISPR Chronos), drug sensitivity data, and gene effect profiles. |
| [`diffdock`](skills/diffdock) | DiffDock and DiffDock-L molecular docking. |
| [`esm`](skills/esm) | Use when working directly with the `esm` Python SDK, ESM3 or ESMC model IDs, Forge/Biohub inference clients, or ESMFold2 folding workflows. |
| [`glycoengineering`](skills/glycoengineering) | Analyze and engineer protein glycosylation. |
| [`medchem`](skills/medchem) | Medicinal chemistry filters for compound triage. |
| [`molecular-dynamics`](skills/molecular-dynamics) | Run and analyze molecular dynamics simulations with OpenMM and MDAnalysis. |
| [`molfeat`](skills/molfeat) | Molecular featurization for ML (100+ featurizers). |
| [`ncats-arax`](skills/ncats-arax) | Queries the NCATS Translator ARAX production API for bounded, typed, provenance-rich one-hop and endpoint-pinned two-hop biomedical knowledge-graph relationships. |
| [`primekg`](skills/primekg) | Query the Precision Medicine Knowledge Graph (PrimeKG) for multiscale biological data including genes, drugs, diseases, phenotypes, and more. |
| [`pytdc`](skills/pytdc) | Use Therapeutics Data Commons through the PyTDC Python package for registry discovery, approved dataset access, task-aware splits, evaluator metrics, benchmark groups, and bounded molecular-oracle... |
| [`rdkit`](skills/rdkit) | Cheminformatics toolkit for fine-grained molecular control. |
| [`rowan`](skills/rowan) | Rowan is a cloud-native molecular modeling and medicinal-chemistry workflow platform with a Python API. |
| [`tamarind`](skills/tamarind) | Access a collection of open-source molecular design and structural biology tools on the Tamarind Bio platform, via its REST API or MCP server — no local GPUs required. |
| [`torchdrug`](skills/torchdrug) | Build and troubleshoot TorchDrug 0.2.1 workflows for molecular graphs, property prediction, self-supervised pretraining, molecule generation, retrosynthesis, protein representation learning, and kn... |

## 🗂 The rest of the family

Install any combination — each bundle is standalone:

- [🧬 Genomics Agent Skills](https://github.com/K-Dense-AI/genomics-agent-skills) — DNA-level bioinformatics: sequence analysis, variants, genomic intervals, phylogenetics, pathogen surveillance, and pipeline platforms (Nextflow, DNAnexus, Latch).
- [🧫 Omics Agent Skills](https://github.com/K-Dense-AI/omics-agent-skills) — molecular profiling: bulk and single-cell transcriptomics, spatial omics, cytometry, proteomics, metabolomics, metabolic modeling, and omics data management.
- [🏥 Clinical Research Agent Skills](https://github.com/K-Dense-AI/clinical-research-agent-skills) — human-health research: clinical documentation scaffolds, healthcare ML, survival analysis, PK/PD modelling, radiology and pathology imaging, and pharma quality and regulatory readiness.
- [🧠 Neuroscience Agent Skills](https://github.com/K-Dense-AI/neuroscience-agent-skills) — neuroscience and physiology data: BIDS dataset structure, physiological time-series analysis, and Neuropixels electrophysiology.
- [🤖 Lab Automation Agent Skills](https://github.com/K-Dense-AI/lab-automation-agent-skills) — connect agents to the lab: liquid-handling robots, cloud labs, ELN and LIMS integrations, microscopy data servers, protocol repositories, and custom lab hardware design.
- [📊 Data Analysis Agent Skills](https://github.com/K-Dense-AI/data-analysis-agent-skills) — domain-agnostic analysis: dataframes at any scale, classical statistics and Bayesian inference, machine learning basics, time series, model explanation, and publication-quality plotting.
- [🧮 Machine Learning Agent Skills](https://github.com/K-Dense-AI/machine-learning-agent-skills) — building and running models: deep-learning frameworks, graph neural networks, reinforcement learning, GPU optimization, and serverless model compute.
- [🔭 Physical Sciences Agent Skills](https://github.com/K-Dense-AI/physical-sciences-agent-skills) — physics and engineering computation: astronomy, quantum computing and dynamics, materials science, fluid dynamics, geospatial analysis, symbolic math, simulation, and optimization.
- [📚 Literature Agent Skills](https://github.com/K-Dense-AI/literature-agent-skills) — finding and managing external evidence: academic search, full-text retrieval, systematic review, citation and reference management, web search, and reproducible database lookups.
- [🔬 Research Methods Agent Skills](https://github.com/K-Dense-AI/research-methods-agent-skills) — thinking before data: hypothesis generation, structured brainstorming, experimental design, power and sample-size planning, and critical appraisal of claims and evidence.
- [✍️ Scientific Communication Agent Skills](https://github.com/K-Dense-AI/scientific-communication-agent-skills) — publishing research: manuscripts, venue templates, grant proposals, peer review, talks and slides, posters in LaTeX and PowerPoint, and AI-assisted scientific graphics.
- [📄 Documents Agent Skills](https://github.com/K-Dense-AI/documents-agent-skills) — document formats: create and edit Word, PowerPoint, Excel, and PDF files, convert documents to Markdown, and parse documents with layout-preserving OCR.
- [🛠️ Meta Agent Skills](https://github.com/K-Dense-AI/meta-agent-skills) — the skill system itself: drafting new skills from observed workflows, host resource detection, and the Pi coding harness.

The original [scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) repository
remains the full monolithic collection.

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) for skill authoring rules,
testing requirements, and the pull-request checklist. Report vulnerabilities per
[SECURITY.md](SECURITY.md), not in public issues.

## 📜 License

[MIT](LICENSE.md) — created and maintained by [K-Dense](https://www.k-dense.ai).
