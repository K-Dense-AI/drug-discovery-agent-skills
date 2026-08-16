# Security Scan Report

**Generated:** 2026-08-16 18:15 UTC  
**Skills scanned:** 23  
**Total findings:** 73  
**Critical:** 0 | **High:** 1 | **Safe skills:** 23/23

**Scanner:** cisco-ai-skill-scanner 2.0.13 · **Model:** claude-opus-5  
**This run:** 7 skill(s) rescanned; 16 unchanged since the last scan and carried forward unmodified. Per-skill scan dates are in [`security-report.json`](security-report.json) (`last_scanned`).  

## Summary

| Skill | Severity | Findings | Safe | Duration |
|-------|----------|----------|------|----------|
| tamarind | 🟡 MEDIUM | 12 | ✅ | 31.6s |
| adaptyv | 🔵 LOW | 4 | ✅ | 33.4s |
| datamol | 🔵 LOW | 3 | ✅ | 26.2s |
| deepchem | 🔵 LOW | 4 | ✅ | 33.6s |
| depmap | 🔵 LOW | 3 | ✅ | 22.8s |
| diffdock | 🔵 LOW | 2 | ✅ | 25.2s |
| esm | 🔵 LOW | 4 | ✅ | 33.8s |
| glycoengineering | 🔵 LOW | 3 | ✅ | 21.0s |
| medchem | 🔵 LOW | 2 | ✅ | 19.3s |
| molecular-dynamics | 🔵 LOW | 2 | ✅ | 16.2s |
| ncats-arax | 🔵 LOW | 3 | ✅ | 25.1s |
| primekg | 🔵 LOW | 3 | ✅ | 19.2s |
| pytdc | 🔵 LOW | 2 | ✅ | 22.3s |
| rowan | 🔵 LOW | 4 | ✅ | 27.4s |
| chembl | 🔵 LOW | 1 | ✅ | 19.8s |
| molfeat | 🔵 LOW | 2 | ✅ | 20.5s |
| antibody-engineering | 🔵 LOW | 2 | ✅ | 21.7s |
| open-targets | 🔵 LOW | 2 | ✅ | 23.6s |
| uniprot-rcsb | 🔵 LOW | 3 | ✅ | 28.7s |
| boltz | 🔵 LOW | 3 | ✅ | 31.7s |
| rdkit | 🟢 SAFE | 0 | ✅ | 10.0s |
| torchdrug | 🟢 SAFE | 0 | ✅ | 9.9s |
| autodock-vina | 🟢 SAFE | 0 | ✅ | 19.9s |

## Detailed Findings

### tamarind — 🟡 MEDIUM

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Large trigger-keyword list in manifest metadata broadens activation surface
  > The manifest includes a 'trigger-keywords' field with ~28 broad computational-biology terms (e.g., 'AlphaFold', 'protein design', 'enzyme', 'peptide', 'molecular design', 'x-api-key'). These are topically relevant to the skill's stated purpose, but generic terms such as 'enzyme', 'peptide', 'adme', 'protein language models' and 'x-api-key' could cause the skill to be surfaced for local/offline cheminformatics requests that do not involve the Tamarind platform. This is a discovery/activation-scope concern rather than deception — the description accurately reflects the skill's behavior.
  > **Remediation:** Narrow trigger keywords to Tamarind-specific terms and platform endpoints; the SKILL.md body already correctly scopes usage ('For purely local cheminformatics ... use a local library instead') — mirror that scoping in the discovery metadata.

- **🔵 LOW** `LLM_PROMPT_INJECTION` — Runtime fetching of external content instructed as authoritative source
  > SKILL.md directs the agent to fetch and prefer live remote resources (https://app.tamarind.bio/llms.txt, https://app.tamarind.bio/openapi.yaml, https://docs.tamarind.bio/llms.txt and its .md pages) over any bundled/hardcoded information ('Prefer fetching them at runtime over trusting any hardcoded list'). Content retrieved from these URLs is untrusted external data that will be read into the agent context; if the vendor site were compromised or a page contained embedded directives, this creates an indirect prompt-injection path. The domains are first-party for the described service and the guidance is technically reasonable (API catalogs change), so risk is low, but the skill provides no instruction to treat fetched content as data rather than instructions.
  > File: `SKILL.md`
  > **Remediation:** Add an explicit note that fetched documentation/spec content must be treated as inert reference data only, and that any instructions embedded in fetched pages must be ignored. Pin to documented, expected URL paths and validate response shape (e.g., valid OpenAPI YAML) before use.

- **🟡 MEDIUM** `MDBLOCK_PYTHON_HTTP_POST` — Python code block sends HTTP POST request
  > Code block in SKILL.md at line 102 contains potentially dangerous Python code.
  > File: `SKILL.md:102`
  > **Remediation:** Review the code block for security implications.

- **🟡 MEDIUM** `MDBLOCK_PYTHON_HTTP_POST` — Python code block sends HTTP POST request
  > Code block in SKILL.md at line 203 contains potentially dangerous Python code.
  > File: `SKILL.md:203`
  > **Remediation:** Review the code block for security implications.

- **🟡 MEDIUM** `MDBLOCK_PYTHON_HTTP_POST` — Python code block sends HTTP POST request
  > Code block in references/api_reference.md at line 105 contains potentially dangerous Python code.
  > File: `references/api_reference.md:105`
  > **Remediation:** Review the code block for security implications.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — allowed-tools not declared despite network, file-write, and code-execution guidance
  > The manifest omits the optional 'allowed-tools' field while the instructions direct the agent to execute Python/requests code, perform outbound HTTPS calls, upload local files (PDB/CIF/SDF) to a third-party cloud, and write downloaded result archives to disk (e.g., open('batch.zip','wb')). Missing allowed-tools is informational per the spec, but given the breadth of operations (local file read → external upload) an explicit declaration would let the host enforce boundaries.
  > File: `references/workflows.md`
  > **Remediation:** Declare allowed-tools explicitly (e.g., [Bash, Python, Read, Write]) and document that user files are transmitted to app.tamarind.bio, so users can consent to the data egress.

- **🟡 MEDIUM** `MDBLOCK_PYTHON_HTTP_POST` — Python code block sends HTTP POST request
  > Code block in references/workflows.md at line 29 contains potentially dangerous Python code.
  > File: `references/workflows.md:29`
  > **Remediation:** Review the code block for security implications.

- **🟡 MEDIUM** `MDBLOCK_PYTHON_HTTP_POST` — Python code block sends HTTP POST request
  > Code block in references/workflows.md at line 61 contains potentially dangerous Python code.
  > File: `references/workflows.md:61`
  > **Remediation:** Review the code block for security implications.

- **🟡 MEDIUM** `MDBLOCK_PYTHON_HTTP_POST` — Python code block sends HTTP POST request
  > Code block in references/workflows.md at line 104 contains potentially dangerous Python code.
  > File: `references/workflows.md:104`
  > **Remediation:** Review the code block for security implications.

- **🟡 MEDIUM** `MDBLOCK_PYTHON_HTTP_POST` — Python code block sends HTTP POST request
  > Code block in references/workflows.md at line 158 contains potentially dangerous Python code.
  > File: `references/workflows.md:158`
  > **Remediation:** Review the code block for security implications.

- **🟡 MEDIUM** `MDBLOCK_PYTHON_HTTP_POST` — Python code block sends HTTP POST request
  > Code block in references/workflows.md at line 228 contains potentially dangerous Python code.
  > File: `references/workflows.md:228`
  > **Remediation:** Review the code block for security implications.

- **🟡 MEDIUM** `MDBLOCK_PYTHON_HTTP_POST` — Python code block sends HTTP POST request
  > Code block in references/workflows.md at line 250 contains potentially dangerous Python code.
  > File: `references/workflows.md:250`
  > **Remediation:** Review the code block for security implications.

### adaptyv — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Instruction to locate and load .env secrets files
  > The skill directs the agent to look for a `.env` file in the project root and load it to obtain the API token. While this is a common and legitimate credential-handling pattern (and the skill correctly warns against hardcoding or committing tokens), it does broaden the agent's interaction with secret-bearing files, which could surface unrelated secrets from that file into the agent context.
  > **Remediation:** Instruct the agent to read only the specific `ADAPTYV_API_KEY` variable, avoid echoing the value or other .env contents, and prefer environment variables over parsing secret files.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Documented automation pattern bypasses human review of financial commitment
  > The skill documents an 'Automated Pipeline' pattern that sets `skip_draft: true` and `auto_accept_quote: true`, which bypasses the Draft review stage and automatically accepts a paid quote and creates a Stripe invoice. If an agent follows this example without explicit user confirmation, it can commit the user to real laboratory costs autonomously. The skill does not include a caution to obtain user confirmation before enabling auto-accept.
  > **Remediation:** Add an explicit instruction that the agent must obtain user confirmation (and show the cost estimate) before using `skip_draft` or `auto_accept_quote`, and default examples to Draft-first workflows.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installed directly from GitHub
  > The skill instructs the agent to install the `adaptyv-sdk` package directly from a GitHub repository with no version, tag, or commit pin (`git+https://github.com/adaptyvbio/adaptyv-sdk.git`). Any future compromise of, or force-push to, the default branch of that repository would result in arbitrary code being installed and executed in the user's environment. The repository appears to be the vendor's official org, which lowers risk, but the lack of provenance pinning is a supply-chain weakness.
  > **Remediation:** Pin the install to an immutable ref (e.g., `@v0.1.0` tag or a full commit SHA) and prefer a PyPI release with hash verification once available. Note the expected publisher/fingerprint in the skill docs.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Missing referenced files and unspecified allowed-tools
  > The skill package references `adaptyv.py`, `templates/api-endpoints.md`, and `assets/api-endpoints.md`, none of which exist in the package (only `references/api-endpoints.md` is present). Broken references can lead the agent to search the filesystem or fabricate content. Additionally, `allowed-tools` is not declared (optional per spec, informational only) for a skill that implies network/HTTP and package-install activity.
  > File: `references/api-endpoints.md`
  > **Remediation:** Remove or fix dangling file references and declare `allowed-tools` explicitly (e.g., Read, Bash/Python) so tool usage matches documented behavior.

### datamol — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Documentation of cloud credential environment variables and remote write paths
  > Reference documentation describes cloud storage I/O via fsspec, naming credential environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, GOOGLE_APPLICATION_CREDENTIALS) and showing writes to remote S3/GCS destinations. This is legitimate library documentation for datamol and includes explicit mitigations ("Only use cloud paths when the user explicitly requests them", "Confirm the destination before writing", "does not collect or transmit environment variables to third-party endpoints", "Scope credential access to the named provider variables only"). No code reads or transmits these credentials. Flagged informationally only: any remote-write pattern is a potential data egress channel if the agent is later given an attacker-controlled destination.
  > **Remediation:** Keep the existing user-confirmation requirement for any remote read/write; avoid enumerating credential variable names in guidance and never allow destination URLs sourced from untrusted files or model-generated content without explicit user approval.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instructions
  > The skill instructs the agent to install packages via `uv pip install datamol`, `s3fs`, and `gcsfs` without version pinning or hash verification. While these are legitimate, well-known PyPI packages (datamol-io project), unpinned installs create a minor supply-chain exposure if a registry or package is compromised. No GitHub/unknown-repo installs or typosquatted names were detected.
  > **Remediation:** Pin versions explicitly (e.g., `uv pip install datamol==0.12.5`) and prompt the user for confirmation before installing packages into their environment.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Missing/unresolved referenced files (broken provenance surface)
  > The extracted reference list includes many paths that do not exist in the package (assets/*.md, templates/*.md, plus 'sklearn.py' and 'datamol.py'). The SKILL.md body explicitly clarifies that scipy/scikit-learn are PyPI packages and not bundled scripts, and the 'sklearn.py'/'datamol.py' entries appear to be artifacts of import-statement parsing rather than real files. No malicious content is present, but unresolved reference paths could allow a later-added file at those paths to be loaded implicitly (indirect instruction surface).
  > File: `references/core_api.md`
  > **Remediation:** Ensure the reference list matches only files actually bundled under references/, and remove/ignore ambiguous names that collide with third-party module names to avoid accidental local file shadowing.

### deepchem — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Undeclared network access despite compatibility metadata omitting it
  > The skill's scripts perform network operations (MoleculeNet dataset downloads via dc.molnet.load_* and Hugging Face model downloads) and the instructions include pip/conda installation commands, but the `compatibility` field only mentions Python/backend requirements and does not disclose outbound network usage. This is a minor manifest/behavior transparency gap rather than deceptive capability inflation; the description accurately reflects the skill's molecular-ML purpose.
  > **Remediation:** Explicitly state in the manifest/compatibility notes that the skill requires outbound network access to download benchmark datasets and pretrained model weights.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instructions including nightly pre-release builds
  > SKILL.md instructs the agent to install packages via `uv pip install deepchem`, `uv pip install 'deepchem[torch]'`, `conda install "mkl<2025"`, and even nightly pre-release builds via `uv pip install --pre deepchem` without any version pinning. Unpinned/pre-release installs expose the environment to supply-chain risk (malicious or broken package versions) and non-reproducible builds. This is standard documentation practice for ML libraries, so risk is low, but the `--pre` nightly recommendation is notable.
  > File: `SKILL.md`
  > **Remediation:** Pin explicit versions (e.g. `deepchem==2.8.0`) consistent with the stated version note, and avoid recommending nightly `--pre` builds by default. Require explicit user confirmation before any package installation.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Long-running compute-intensive training defaults without resource guardrails
  > Scripts default to 50 epochs of GNN/regressor training (and 10-20 epochs of transformer fine-tuning) on datasets such as Tox21/HIV, which can consume substantial CPU/GPU time and memory when invoked by an agent. There is no timeout, sample cap, or user confirmation prompt. This is expected behavior for an ML training skill and is user-parameterized (--epochs), so severity is low.
  > File: `scripts/graph_neural_network.py`
  > **Remediation:** Lower default epoch counts for agent-driven runs, add optional max-runtime/max-sample limits, and note expected resource cost in the skill instructions so the agent can confirm with the user before long jobs.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Automatic download and execution of remote pretrained model weights
  > scripts/transfer_learning.py loads third-party pretrained checkpoints from Hugging Face Hub identifiers ('seyonec/ChemBERTa-zinc-base-v1', 'ibm/MoLFormer-XL-both-10pct') and GROVER weights, which triggers network downloads of remote model artifacts on first run. Remote model artifacts (especially pickle-based checkpoints) are a recognized supply-chain vector. The identifiers are well-known public models and are hardcoded (not user-controlled), so the risk is limited.
  > File: `scripts/transfer_learning.py`
  > **Remediation:** Document the network egress requirement, pin model revisions/commit hashes, and prefer safetensors-format weights to avoid arbitrary code execution during checkpoint deserialization.

### depmap — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Downloading and writing remote data files to local disk without validation
  > The skill includes example code that downloads arbitrary URLs via requests and streams the content directly to a local file path (download_depmap_data). While the intended sources are legitimate (depmap.org, figshare.com), the helper accepts any URL and output path, and the FILES dict contains a placeholder URL. If an agent substitutes an untrusted URL, this becomes an unvalidated remote-file write. No exfiltration of local data occurs; the flow is inbound only.
  > **Remediation:** Restrict downloads to an allowlist of trusted domains (depmap.org, figshare.com), validate/normalize output paths to a working directory, verify checksums of downloaded datasets, and require user confirmation before writing files.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Unbounded full-matrix correlation loop can exhaust compute/memory
  > The co_essentiality helper iterates over every column of the DepMap gene-effect matrix (~18,000 genes x ~1,100 cell lines) performing pairwise index intersections and correlations in pure Python. On the full dataset this is a long-running, memory-heavy operation with no cap, timeout, or progress bound. This appears to be inefficiency rather than intentional DoS.
  > **Remediation:** Use vectorized pandas/numpy correlation (df.corrwith) and add limits or timeouts on dataset size for interactive use.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Missing allowed-tools and compatibility metadata while performing network and file operations
  > The manifest does not declare allowed-tools or compatibility, yet the documented workflows require Python execution, outbound HTTP requests, and local file writes. This is informational only (allowed-tools is optional per spec), but the absence means the network/file-write capability is not surfaced to the user or enforced by the agent runtime.
  > **Remediation:** Declare allowed-tools (e.g., [Read, Write, Bash, Python]) and note that the skill performs outbound network requests to depmap.org/figshare.com.

### diffdock — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned external repository and Docker image installation instructions
  > The SKILL.md instructs cloning the upstream DiffDock repository from GitHub (`git clone https://github.com/gcorso/DiffDock.git`) and pulling a Docker image (`docker pull rbgcsail/diffdock`) without commit pins or image digests. The skill also suggests `uv pip install fair-esm` without a version pin. While these are the legitimate, well-known upstream sources for DiffDock, unpinned fetch-and-execute of third-party code means the executed content can change over time and is not verifiable. This is a common practice in scientific tooling and is informational rather than malicious.
  > File: `SKILL.md`
  > **Remediation:** Pin a specific release tag/commit for the repository, a digest for the Docker image, and exact versions for pip packages (e.g., `fair-esm==2.0.0`) so the executed dependency set is reproducible and verifiable.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced files are missing from the package
  > The instructions reference documentation/asset paths that do not exist in the package (e.g., references/custom_inference_config.yaml, assets/parameters_reference.md, templates/*.md, assets/confidence_and_limitations.md, references/workflows_examples.md). Missing referenced files are a documentation-consistency defect: the agent may attempt reads that fail, or could be induced to search for and read same-named files from elsewhere in the working tree, which would be untrusted content. No malicious content is implied.
  > File: `references/workflows_examples.md`
  > **Remediation:** Correct the referenced paths to match the files actually bundled (references/parameters_reference.md, references/confidence_and_limitations.md, assets/custom_inference_config.yaml, assets/batch_template.csv) and either ship or remove references to workflows_examples.md and the templates/ paths.

### esm — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Guidance to read API key from local .env file
  > The Authentication section instructs the agent to check a local `.env` file for `ESM_API_KEY` if the environment variable is unset. Reading local secret files is a sensitive operation that could lead to secret exposure in transcripts or logs. Mitigating factors: the instruction is explicitly scoped to only `ESM_API_KEY` ('do not load unrelated secrets'), explicitly forbids hardcoding tokens, and there is no network transmission of the secret to any non-official endpoint. No hardcoded credentials are present anywhere in the package.
  > **Remediation:** Prefer requiring the user to export the environment variable or use a secrets manager rather than having the agent read `.env` files; if read, never echo the value into output.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Dual-use protein design content (documentation-only, with responsible-use guidance)
  > The skill instructs generative protein design, inverse folding, and function-conditioned generation, which is inherently dual-use biological content. However, the material is standard published ESM/EvolutionaryScale API documentation, contains no guidance toward toxin/pathogen design, and includes an explicit Responsible Use section pointing to the Responsible Biodesign Framework and Biohub Acceptable Use Policy, plus repeated caveats that outputs are hypotheses requiring experimental validation. Recorded for awareness only; no misuse-facilitating content was found.
  > **Remediation:** No action required; retain the responsible-use guidance and biosafety caveats.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Installation guidance points to an unverified GitHub repository for the `esm` SDK
  > The skill's reference documentation instructs installing the `esm` package from `git+https://github.com/Biohub/esm.git`. The canonical upstream repository for the ESM SDK is `evolutionaryscale/esm`; the `Biohub/esm` org/repo referenced here is not a well-known provenance-verified source and could be a typosquat or repo-transfer confusion. Installing directly from a git source executes arbitrary setup code from that repository. Mitigating factor: the doc explicitly warns against floating-branch installs and recommends pinning a full 40-character commit SHA and reviewing the release before installing.
  > **Remediation:** Prefer the pinned PyPI release (`esm==3.2.3`) exclusively, and verify the GitHub organization/repository ownership against official EvolutionaryScale documentation before recommending any git-based install.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — No `allowed-tools` declaration despite instructing package installation and code execution
  > The manifest omits the optional `allowed-tools` and `compatibility` fields, while the instruction body contains bash install commands (`uv pip install ...`) and substantial Python code intended to be run, plus network calls to hosted inference APIs. This is informational only — there is no declared restriction being violated — but explicit tool scoping would improve least-privilege posture for a skill that guides package installation and remote API usage.
  > **Remediation:** Declare `allowed-tools` (e.g., [Read, Write, Bash, Python]) and `compatibility` to make the skill's execution and network footprint explicit.

### glycoengineering — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Outbound network requests to external bioinformatics web services
  > Example code performs HTTP requests to external services (DTU Health Tech webface CGI endpoint and the GlyConnect Expasy API), transmitting protein sequences or UniProt identifiers off-machine. These are well-known, legitimate public academic resources and only scientific inputs are sent, so exfiltration risk is minimal. However, the manifest does not declare network usage or compatibility constraints, so users may not expect outbound traffic.
  > **Remediation:** Document that the skill may send user-supplied sequences to third-party servers, require explicit user confirmation before submission, and avoid sending any data other than the sequence explicitly provided by the user.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned package installation instruction
  > The skill documents installing a third-party Python package via `uv pip install glycoshield` without any version pin or hash verification. If executed by the agent, this pulls the latest available version from PyPI, which introduces a supply-chain risk (package takeover, malicious release, or typosquatting of a low-profile scientific package). The risk is limited because this appears in documentation as an optional external tool rather than an auto-executed script.
  > **Remediation:** Pin the dependency to a specific verified version (e.g., `glycoshield==<x.y.z>`), reference the official project source, and recommend installation in an isolated virtual environment with user confirmation.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Missing allowed-tools, license, and compatibility metadata
  > The YAML frontmatter omits the optional `allowed-tools`, `license`, and `compatibility` fields even though the skill includes Python code that uses the network and documents shell commands. This is informational only; no declared restriction is violated.
  > **Remediation:** Declare `allowed-tools` (e.g., [Read, Python, Bash]), add a license, and note that the skill may require network access.

### medchem — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instructions
  > The SKILL.md instructs the agent to install packages via `uv pip install medchem datamol` and `mamba install -c conda-forge lilly-medchem-rules` without version pinning, despite the documentation stating examples target medchem 2.0.5. Unpinned installs can pull in a future or compromised version of the dependency chain. Packages are well-known, legitimate open-source cheminformatics libraries from datamol-io/conda-forge, so risk is low, but pinning would be safer.
  > File: `SKILL.md`
  > **Remediation:** Pin explicit versions (e.g., `uv pip install medchem==2.0.5 datamol==0.12.*`) and require explicit user confirmation before running installation commands.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced file paths do not exist in the package
  > The instruction/reference scan lists paths such as templates/rules_catalog.md, assets/api_guide.md, assets/rules_catalog.md, templates/api_guide.md, medchem.py and datamol.py that are not present in the package (the latter two are Python import names rather than bundled files). Missing referenced resources are a documentation-hygiene issue and could cause the agent to attempt to create or fetch files that do not exist; no malicious content is involved.
  > File: `references/rules_catalog.md`
  > **Remediation:** Ensure only actually bundled files (references/api_guide.md, references/rules_catalog.md, scripts/filter_molecules.py) are referenced, and avoid ambiguous references to module names as file paths.

### molecular-dynamics — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instructions
  > The skill instructs installation of packages via conda/uv pip without version pinning (e.g., 'conda install -c conda-forge openmm mdanalysis nglview', 'uv pip install openmm mdanalysis', 'uv pip install openff-toolkit'). Unpinned installs from public registries introduce a minor supply-chain risk (dependency confusion / upstream compromise), though the packages named are legitimate, well-known scientific libraries from trusted channels.
  > **Remediation:** Pin explicit versions (e.g., openmm==8.1.1, mdanalysis==2.7.0) and note the trusted channel/registry so installs are reproducible and verifiable.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Missing allowed-tools and compatibility metadata
  > The YAML frontmatter does not declare allowed-tools or compatibility, although the skill's guidance involves executing Python code, installing packages via shell commands, and writing files (PDB, DCD, PNG, checkpoints). This is informational only, as allowed-tools is optional per spec, but declaring it would constrain the shell/Python execution the skill implies.
  > **Remediation:** Declare allowed-tools (e.g., [Read, Write, Bash, Python]) and compatibility so the execution surface implied by the installation and simulation steps is explicit.

### ncats-arax — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Outbound transmission of user query content to third-party public API
  > The skill directs the agent to send user-supplied biomedical entities (CURIEs, free-text names) over HTTPS to the external NCATS Translator ARAX production service (arax.transltr.io). This is inherent to the stated purpose and is unusually well-mitigated: the skill requires an explicit --acknowledge-public-query flag, warns that query and caller metadata may be publicly visible, forbids patient/proprietary data, fixes a constant non-identifying submitter/User-Agent, restricts base URLs to HTTPS production endpoints, and rejects loopback/private/link-local addresses and protocol-downgrade or cross-origin redirects. No credential, environment, or local-file harvesting is described. Recorded as informational data-egress awareness only.
  > **Remediation:** No change required. Continue to require explicit user acknowledgment before any network call and keep the prohibition on submitting sensitive, patient, or proprietary content.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Referenced executable script (scripts/arax_client.py) is not present in the package
  > SKILL.md instructs the agent to run `python skills/ncats-arax/scripts/arax_client.py` for preflight, normalize, one-hop, two-hop, and summarize commands, but no script files are included in the analyzed package. The documented safety controls (byte-exact artifact handling, 25 MiB response cap, URL validation, fixed ARAXi operations, no raw-query escape hatch, 0600 file modes, atomic writes) therefore cannot be verified, and the command path could be satisfied by an unvetted or attacker-supplied file placed at that location. No malicious behavior is observable in the shipped content.
  > File: `SKILL.md`
  > **Remediation:** Ship the referenced arax_client.py inside the skill package (with a checksum or version pin) so its behavior can be reviewed, or remove the execution instructions until the script is bundled.

- **⚪ INFO** `LLM_CONTEXT_BUDGET_EXCEEDED` — 'scripts/arax_client.py' excluded from LLM analysis (84,318 chars)
  > file size (84,318 chars) exceeds per-file limit (75,000)
  > File: `scripts/arax_client.py`
  > **Remediation:** Increase llm_analysis.max_code_file_chars in your scan policy to include this content in LLM analysis.

### primekg — 🔵 LOW

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Referenced file 'scripts.py' not present in package
  > The instructions reference imports from `scripts.query_primekg`, and the analysis harness resolved a referenced file `scripts.py` that does not exist in the package. A missing referenced module is a documentation/packaging inconsistency; if an agent later creates or resolves an arbitrary `scripts.py` from the working directory, unintended code could be imported.
  > **Remediation:** Ship the referenced module path exactly as documented (include `scripts/__init__.py` if package-style imports are intended) and remove references to non-existent files.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Memory/CPU intensive full-graph load and O(n^2) two-hop path expansion
  > `_load_kg()` reads a ~4 million-row CSV fully into memory (hundreds of MB) and caches it. `find_paths` with max_depth=2 performs nested iterrows over all first- and second-hop edges for each shared intermediate; for hub nodes (e.g., highly connected proteins) this can produce a combinatorial explosion of paths and consume large CPU/memory. This appears to be a performance characteristic rather than intentional abuse — the author bounds depth to 1 or 2 and clears the cache to avoid holding multiple frames — but there is no cap on the number of returned paths.
  > **Remediation:** Add a maximum result cap / degree threshold for hub intermediates and consider chunked or indexed loading (e.g., parquet, sqlite) to bound memory usage.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — No allowed-tools / compatibility / license metadata declared
  > The YAML frontmatter omits `allowed-tools`, `license` (listed as Unknown), and `compatibility`. This is optional per spec and only informational, but it means the skill's file-read and Python-execution behavior (reading a local CSV via pandas) is not constrained or declared. No violation was observed, as the code performs only local read operations consistent with its stated purpose.
  > **Remediation:** Add explicit `allowed-tools: [Read, Python]`, a license identifier, and compatibility notes to the frontmatter.

### pytdc — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Dependency installation of a large unaudited transitive graph
  > Installation instructions run `uv pip install` for PyTDC 1.1.15 and setuptools 80.9.0, which resolves ~123 transitive packages that are not version-pinned by the skill. Direct pins are provided for the top-level packages and a `--dry-run` review step is recommended, so risk is modest, but transitive versions remain floating unless the user generates a lockfile.
  > **Remediation:** Ship or generate a platform-specific uv.lock / hash-pinned requirements file so the full transitive dependency graph is reproducible and auditable.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Optional download and loading of remote model checkpoints (serialized artifacts)
  > The oracle workflow can download model checkpoints (fpscores, DRD2/GSK3B/JNK3/CYP3A4_Veith) from upstream Harvard Dataverse endpoints via PyTDC and load them locally. Loading third-party serialized model artifacts carries inherent deserialization/supply-chain risk. The skill explicitly documents this, restricts execution to an allowlist of oracle categories, requires both --execute and --download acknowledgement flags, contains writes to a relative runtime directory, and refuses remote-service/docking/composite oracles, so residual risk is low and clearly disclosed.
  > File: `scripts/molecular_generation.py`
  > **Remediation:** Optionally record and verify checksums for downloaded checkpoints and surface artifact size/origin to the user before loading.

### rowan — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Documentation shows inline hardcoding of API key in source
  > Several examples set the API key directly in Python source (`rowan.api_key = "your_api_key_here"` / `rowan.api_key = "..."`). These are clearly placeholders, not real secrets, and the skill correctly recommends the ROWAN_API_KEY environment variable first. Still, the inline pattern can lead an agent to write literal credentials into generated scripts that may be committed or logged. Notably, the skill never reads credential files (~/.aws, ~/.ssh) and never transmits secrets anywhere other than the documented vendor API.
  > **Remediation:** Consistently show only environment-variable based configuration (os.environ["ROWAN_API_KEY"]) and explicitly warn against embedding keys in committed code.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Dense trigger-keyword metadata for activation targeting
  > The manifest includes a 'trigger-keywords' field listing many activation terms (pKa prediction, molecular docking, conformer search, chemistry workflow, drug discovery, SMILES, protein structure, batch molecular modeling, cloud chemistry). The keywords are all narrowly scoped to the skill's genuine domain and there are no over-broad claims ('general assistant', 'use me first'), so this is at most a minor discovery-surface concern rather than capability inflation.
  > **Remediation:** No action strictly required; keep keyword lists limited to the skill's actual domain, as is currently the case.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation from PyPI
  > The skill instructs the agent to install the 'rowan-python' package via `uv pip install rowan-python` without a pinned version or hash. While this is the vendor's own legitimate client library, unpinned installs expose the workflow to supply-chain risk (malicious version upload, dependency confusion, or typosquatting if the name is mistyped). No install from unknown GitHub repos or arbitrary URLs is present.
  > **Remediation:** Pin the package version (e.g., `uv pip install rowan-python==<x.y.z>`) and, where possible, verify hashes or use a lockfile.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — allowed-tools not declared while skill implies code execution and network use
  > The manifest omits the optional `allowed-tools` field even though the skill's guidance drives Bash (package install), Python execution, network calls to the Rowan cloud API, protein/PDB file uploads from the local filesystem, and file writes (e.g., best_pose.pdb, workflow_uuids.json). This is informational only — no declared restriction is violated, and all behavior is consistent with the stated purpose.
  > **Remediation:** Declare `allowed-tools` (e.g., [Read, Write, Bash, Python]) so that the skill's actual capability surface is explicit and auditable.

### chembl — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Configurable API base URL could redirect queries (and query content) to an arbitrary host
  > All bundled scripts expose a `--base-url` flag that defaults to the public EBI endpoint but accepts any URL. `_common._build_url` will pass through any absolute http(s) path unmodified. If an agent is instructed (e.g., by untrusted user text or by a poisoned reference file) to pass a different base URL, the queries — including user-supplied SMILES, target ids, and other search terms — would be sent to a third-party host, and the returned JSON would be written into local TSV/CSV/JSON files. This is a normal, documented convenience feature for mirrors and is not malicious, but it is an unauthenticated outbound-request surface controlled by a plain string argument with no host allow-list.
  > **Remediation:** Optionally validate that `--base-url` resolves to an expected host (e.g., restrict to www.ebi.ac.uk or require explicit user confirmation for other hosts), and reject plain http:// schemes.

### molfeat — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Documented downloads of remote model artifacts and datasets
  > The skill documents fetching pretrained model artifacts from the molfeat model store (https://fs.molfeat.datamol.io/artifacts/) and the HuggingFace Hub, and mentions environment variables (MOLFEAT_MODEL_STORE_ROOT / MOLFEAT_MODEL_STORE_BUCKET) that can redirect the store root. This is normal, expected behavior for a molecular ML featurization library and involves inbound model downloads only — no user data is transmitted outward. Noted for awareness that the skill performs network access despite no explicit network declaration in the manifest.
  > **Remediation:** Optionally document that network access is required and that model artifacts are checksum-verified (sha256sum) so users are aware of the trust boundary when overriding the store root.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Suggests installing an unpinned package from an external GitHub repository
  > The skill instructs the user to install the MAP4 fingerprint package directly from the third-party GitHub repository reymond-group/map4 without a pinned version or commit hash. This is a minor supply-chain consideration; all other install commands are strictly version-pinned (e.g., molfeat==0.11.0). The referenced repository is the well-known upstream project for MAP4, so risk is low.
  > **Remediation:** Recommend installing MAP4 from a pinned tag/commit and verifying provenance, or explicitly state that the user should review the third-party repository before installation.

### antibody-engineering — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger keyword list in description broadens activation surface
  > The YAML description ends with an explicit activation directive listing many trigger terms ('Also trigger on antibody, nanobody, VHH, scFv, Fab, CDR, framework, ANARCI, abnumber, IgBLAST, OAS, SAbDab, humanization, Vernier residues, or developability'). All listed keywords are genuinely within the skill's stated antibody-engineering domain, so this is not deceptive capability inflation, but the pattern does deliberately maximise discovery/activation and could cause the skill to load in loosely related conversations. Informational only.
  > File: `SKILL.md`
  > **Remediation:** Keep the description scoped to the actual capabilities and avoid explicit 'trigger on <keyword list>' directives; rely on natural description matching.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Some referenced documentation paths do not exist in the package
  > The instruction body references four reference documents; three of the four (references/numbering-schemes.md, references/developability.md, references/humanization-and-design.md, references/tools.md) are present. The scanner additionally probed templates/ and assets/ variants that are absent. No missing file is actually required by the instructions, and no external URLs or user-supplied files are fetched or executed, so the risk is documentation-completeness only, not indirect prompt injection.
  > File: `references/humanization-and-design.md`
  > **Remediation:** Ensure all referenced paths resolve within the package; remove or correct any stale links.

### open-targets — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — GraphQL endpoint overridable via environment variable and CLI flag
  > The shared transport module reads the API endpoint from the OPEN_TARGETS_API_URL environment variable, and every subcommand exposes an --api-url flag. If an attacker (or a prompt-injected instruction) can set that variable or pass the flag, all query payloads — including any identifiers or free-text terms the agent submits — would be POSTed to an arbitrary host instead of the documented Open Targets API. Impact is limited because the skill only sends public biomedical identifiers and no credentials, and endpoint configurability is a common, legitimate pattern.
  > File: `scripts/_common.py`
  > **Remediation:** Optionally validate that the resolved URL uses HTTPS and belongs to an allow-listed host (e.g. *.opentargets.org), and print the effective endpoint to stderr so a redirected destination is visible to the user.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Arbitrary GraphQL document execution from a user-supplied file ('raw' subcommand)
  > The 'raw' subcommand reads any file path given on the command line and sends its contents as a GraphQL document to the configured endpoint, with variables parsed from --var name=value. This is a documented convenience feature and the target API is read-only and unauthenticated, so the security impact is minimal; however it does mean arbitrary local file content can be transmitted to the endpoint if the agent is tricked into pointing it at a non-GraphQL file.
  > File: `scripts/ot_query.py`
  > **Remediation:** Restrict raw query files to a known extension/directory (e.g. .graphql under the working directory) and warn the user before transmitting file contents to a remote endpoint.

### uniprot-rcsb — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Broad keyword-baiting trigger list in description
  > The description ends with an explicit list of activation triggers ("Also trigger on UniProt accessions, PDB ids, rest.uniprot.org, search.rcsb.org, files.rcsb.org, alphafold.ebi.ac.uk, id mapping, SEQRES, or missing residues"). While all listed keywords are tightly scoped to the skill's genuine bioinformatics domain, enumerating trigger tokens is a mild discovery-optimization pattern that can increase unwanted activation. No over-broad or unrelated capability claims (no "general assistant", no brand impersonation) are present, and the declared behavior matches the bundled scripts exactly.
  > **Remediation:** Optional: trim the explicit trigger-keyword list to a concise natural-language description of the skill's purpose.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Unbounded pagination and download size with no byte cap
  > `uniprot_pages` follows `Link: rel="next"` headers in an unbounded `while url:` loop, and `download()` reads the full HTTP body into memory before writing to disk. A very large query result or an unexpectedly large structure file could consume substantial memory, bandwidth, or time. Mitigations are present (per-request 90s timeout, max 4 attempts with capped 30s backoff, a bounded 3-round gzip decompression loop, and `--limit` defaults of 25-100 rows), so practical DoS risk is low, and there is no infinite retry or spin.
  > File: `scripts/_common.py`
  > **Remediation:** Add a maximum page count to `uniprot_pages` and stream downloads in chunks with a configurable maximum byte size.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Unvalidated user-supplied path in file write/append destinations
  > Several commands write to caller-supplied paths without normalization or containment checks: `uniprot_fetch.py fasta --out` opens the path in append mode, and `fetch_structure.py` creates arbitrary directories via `Path(args.out_dir).mkdir(parents=True, exist_ok=True)` and writes downloaded bytes there. A path such as `--out ~/.ssh/authorized_keys` or `--out-dir ../../` would append/overwrite outside the working directory. This is a normal CLI convention rather than malicious behavior, and the written content is remote biological data, but the agent should not pass unvalidated paths. Note the manifest declares `Write` and `Edit`, so file creation itself is within the declared tool scope.
  > File: `scripts/uniprot_fetch.py`
  > **Remediation:** Resolve and validate output paths against an allowed base directory, reject `..` traversal, and prefer non-append/exclusive writes or explicit overwrite confirmation.

### boltz — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list appended to skill description
  > The YAML description ends with an explicit activation-keyword list ("Also trigger on Boltz, Boltz-1, Boltz-2, cofolding, boltz predict, affinity_pred_value, affinity_probability_binary, ipTM, or open-weights AlphaFold3 alternatives"). This is a discovery-optimisation pattern. In this case all keywords are tightly scoped to the skill's genuine domain (Boltz cofolding/affinity prediction) and there is no brand impersonation or over-broad claim such as "general assistant", so the risk is informational only.
  > **Remediation:** Keep the description to a functional summary; rely on semantic matching rather than an explicit trigger-word list to avoid unnecessary activation.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency install, including direct install from a Git repository
  > references/running.md instructs the user to run `pip install boltz` without a version pin and offers `pip install git+https://github.com/jwohlwend/boltz.git` to obtain the development branch. Unpinned and VCS-HEAD installs mean the executed code is whatever the upstream repository currently contains, so a future upstream compromise would flow directly onto the user's machine. The repository referenced is the genuine upstream project for Boltz and the skill's own bundled scripts have no third-party dependencies, so impact is limited.
  > File: `references/running.md`
  > **Remediation:** Pin the tested release (e.g. `pip install boltz==2.2.1`) and, if a development install is offered, pin it to a specific commit hash. Recommend installing into an isolated virtual environment.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Documented workflow transmits input sequences to a third-party public server
  > The recommended `boltz predict ... --use_msa_server` workflow sends the user's protein sequence to the public ColabFold MSA server, i.e. local input data crosses a network boundary to a third party. This is inherent to the upstream tool rather than hidden behaviour: the skill's compatibility field, references/yaml-schema.md, references/running.md, and a runtime warning printed by make_boltz_yaml.py all state this explicitly and advise against use with confidential or unpublished sequences. The bundled scripts themselves make no network calls. Noted for awareness of the data-flow only.
  > File: `references/yaml-schema.md`
  > **Remediation:** No change required; the existing warnings are appropriate. Optionally default screening guidance to precomputed MSAs (`--msa-path`) or a self-hosted `--msa_server_url` so that no sequence leaves the environment by default.
