# Security Scan Report

**Generated:** 2026-08-17 00:35 UTC  
**Skills scanned:** 37  
**Total findings:** 154  
**Critical:** 0 | **High:** 0 | **Safe skills:** 37/37

**Scanner:** cisco-ai-skill-scanner 2.0.13 · **Model:** claude-opus-5  
**This run:** full rescan of all 37 skill(s).  

## Summary

| Skill | Severity | Findings | Safe | Duration |
|-------|----------|----------|------|----------|
| adaptyv | 🟡 MEDIUM | 4 | ✅ | 34.0s |
| esm | 🟡 MEDIUM | 5 | ✅ | 46.6s |
| patent-landscape | 🟡 MEDIUM | 3 | ✅ | 23.4s |
| openfda | 🟡 MEDIUM | 4 | ✅ | 31.9s |
| tamarind | 🟡 MEDIUM | 12 | ✅ | 32.9s |
| admet-prediction | 🔵 LOW | 2 | ✅ | 17.3s |
| boltz | 🔵 LOW | 2 | ✅ | 21.9s |
| antibody-engineering | 🔵 LOW | 2 | ✅ | 23.4s |
| autodock-vina | 🔵 LOW | 2 | ✅ | 23.8s |
| chembl | 🔵 LOW | 2 | ✅ | 22.9s |
| chemical-space | 🔵 LOW | 3 | ✅ | 22.3s |
| clinicaltrials | 🔵 LOW | 3 | ✅ | 24.7s |
| deepchem | 🔵 LOW | 3 | ✅ | 28.4s |
| datamol | 🔵 LOW | 3 | ✅ | 30.8s |
| depmap | 🔵 LOW | 2 | ✅ | 23.9s |
| diffdock | 🔵 LOW | 2 | ✅ | 26.1s |
| immunogenicity | 🔵 LOW | 1 | ✅ | 16.2s |
| free-energy-perturbation | 🔵 LOW | 2 | ✅ | 28.6s |
| generative-design | 🔵 LOW | 2 | ✅ | 24.1s |
| glycoengineering | 🔵 LOW | 4 | ✅ | 30.7s |
| medchem | 🔵 LOW | 3 | ✅ | 26.9s |
| molfeat | 🔵 LOW | 1 | ✅ | 18.3s |
| molecular-dynamics | 🔵 LOW | 3 | ✅ | 26.4s |
| ncats-arax | 🔵 LOW | 4 | ✅ | 28.8s |
| oligonucleotides | 🔵 LOW | 2 | ✅ | 23.1s |
| open-targets | 🔵 LOW | 2 | ✅ | 23.0s |
| primekg | 🔵 LOW | 2 | ✅ | 17.6s |
| protein-binder-design | 🔵 LOW | 3 | ✅ | 23.9s |
| pkpd-translation | 🔵 LOW | 3 | ✅ | 31.8s |
| rdkit | 🔵 LOW | 2 | ✅ | 26.3s |
| rowan | 🔵 LOW | 2 | ✅ | 18.9s |
| pytdc | 🔵 LOW | 2 | ✅ | 30.4s |
| retrosynthesis | 🔵 LOW | 3 | ✅ | 24.4s |
| target-safety | 🔵 LOW | 2 | ✅ | 22.0s |
| uniprot-rcsb | 🔵 LOW | 2 | ✅ | 21.0s |
| binding-site-analysis | 🟢 SAFE | 0 | ✅ | 8.5s |
| degraders | 🟢 SAFE | 0 | ✅ | 15.0s |

## Detailed Findings

### adaptyv — 🟡 MEDIUM

- **🟡 MEDIUM** `LLM_HARMFUL_CONTENT` — Documented workflow auto-accepts quotes and creates invoices without user confirmation
  > The instructions present an "Automated Pipeline (Skip Draft + Auto-Accept Quote)" example using `skip_draft: True` and `auto_accept_quote: True`. Per the bundled endpoint reference, accepting a quote finalizes a Stripe quote and creates a draft invoice, i.e. a real financial commitment. Encouraging the agent to use these flags removes the human review checkpoint (Draft → QuoteSent) and could lead to unintended paid lab orders if the agent acts autonomously. No explicit instruction to confirm cost with the user before setting these flags is provided.
  > **Remediation:** Add an explicit guardrail: require the agent to run `cost-estimate` and obtain explicit user approval before using `skip_draft` or `auto_accept_quote`, and default examples to the Draft + manual quote-confirmation flow.

- **🟡 MEDIUM** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installed directly from a GitHub repository
  > The skill instructs the agent to install the `adaptyv-sdk` package directly from a GitHub URL with no version tag, commit hash, or hash verification (`uv pip install "git+https://github.com/adaptyvbio/adaptyv-sdk.git"` and `uv add "adaptyv-sdk @ git+..."`). Installing from a mutable default branch means whatever code is on HEAD at install time is executed in the user's environment; a repository compromise or force-push would silently deliver arbitrary code. The package is explicitly described as beta and not on PyPI, so no registry-level provenance checks apply.
  > **Remediation:** Pin the dependency to an immutable revision (e.g. `git+https://github.com/adaptyvbio/adaptyv-sdk.git@<tag-or-commit-sha>`), and advise the user to review/approve the install command before execution.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Instruction to locate and load .env secret files
  > The skill directs the agent to look for a `.env` file in the project root and load it to obtain the API key. This is standard, benign secret-handling guidance (and the skill correctly forbids hardcoding tokens), but it does broaden the agent's access to a file that commonly contains unrelated credentials. No exfiltration path is present.
  > **Remediation:** Scope the guidance to reading only the `ADAPTYV_API_KEY`/`ADAPTYV_API_URL` variables and instruct the agent never to echo, log, or transmit other values found in `.env`.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Referenced files missing from the package
  > The instruction set and referenced-file list include `adaptyv.py`, `assets/api-endpoints.md`, and `templates/api-endpoints.md`, none of which exist in the package (only `references/api-endpoints.md` is present). Missing referenced artifacts are a packaging/documentation integrity issue and could cause the agent to search for or fabricate files.
  > File: `references/api-endpoints.md`
  > **Remediation:** Remove stale references or ship the missing files with the package.

### esm — 🟡 MEDIUM

- **🟡 MEDIUM** `LLM_SUPPLY_CHAIN_ATTACK` — Installation instructions point to an unverified GitHub organization for the `esm` package
  > The skill and its reference file instruct the agent to install the `esm` SDK from `git+https://github.com/Biohub/esm.git` and cite `https://github.com/Biohub/esm` as the canonical repository. The authoritative EvolutionaryScale ESM repository is `github.com/evolutionaryscale/esm`; the `Biohub` organization referenced here is not the verified publisher of the `esm` PyPI package, and `biohub.ai` is presented as the hosted API host. Following these instructions could cause the agent to install code from an unverified/attacker-controllable namespace (name-confusion / typosquat risk) with `Bash` already permitted in allowed-tools. The commit SHA is a placeholder, so the version pin provides no real provenance guarantee.
  > **Remediation:** Restrict installation guidance to the verified PyPI release (`uv pip install "esm==3.2.3"`) and reference the official upstream repository (github.com/evolutionaryscale/esm). Remove or clearly label unverified GitHub install paths and require the user to confirm repository provenance before any VCS install.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Instructions direct agent to read a local .env file for credentials
  > The Authentication section instructs the agent to check a local `.env` file for `ESM_API_KEY` if the environment variable is unset. Reading `.env` files touches a common secrets store. Mitigating factors: the instruction is explicitly scoped ('for ESM_API_KEY only (do not load unrelated secrets)'), the skill repeatedly warns against hardcoding or committing tokens, there is no network egress of the key beyond the trusted, hardcoded Forge/Biohub endpoints, and no scripts perform any credential collection.
  > **Remediation:** Prefer requiring the user to export ESM_API_KEY in the environment or use a secrets manager; avoid instructing the agent to parse .env files, or require explicit user confirmation before reading them.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-baiting trigger list in skill description
  > The YAML description ends with an explicit activation keyword list ('Also trigger on esm, ESM3, ESMC, ESM Cambrian, ESMFold2, `from esm.models`, ESMProtein, GenerationConfig, forge.evolutionaryscale.ai, biohub.ai, or ESM_API_KEY'), including the secret environment variable name `ESM_API_KEY`. Broad trigger lists — particularly one keyed on a credential variable name — can increase unintended activation of the skill in contexts involving API keys. The listed keywords are, however, topically consistent with the skill's stated protein-language-model purpose, so impact is limited.
  > **Remediation:** Narrow the description to the functional scope and remove credential/environment-variable names (ESM_API_KEY) from the activation keyword list.

- **🔵 LOW** `LLM_COMMAND_INJECTION` — Documented caching examples use pickle deserialization of on-disk files
  > Reference documentation includes example caching/checkpointing helpers that call `pickle.load()` on files read from disk (`checkpoint.pkl`, `embeddings_cache.pkl`, `forge_cache/*.pkl`). If an attacker can write to those paths, pickle deserialization enables arbitrary code execution. This is a code-quality issue in illustrative sample code rather than an active exploit in the skill itself.
  > File: `SKILL.md`
  > **Remediation:** Replace pickle-based caching examples with a safe serialization format (JSON, npz, safetensors) or note that pickle files must be treated as trusted-only inputs.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced files are missing from the package
  > The reference extraction lists paths that do not exist in the package (templates/*.md, assets/*.md, esm.py). Missing referenced resources can cause the agent to search for or fabricate content, though most of these appear to be filename-matching artifacts rather than genuine broken instructions; the five files actually cited in the SKILL.md References section (references/*.md) are present and benign.
  > File: `references/biohub-platform.md`
  > **Remediation:** Ensure all referenced paths resolve within the package, or remove references to non-existent template/asset/script files.

### patent-landscape — 🟡 MEDIUM

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Description includes an explicit keyword trigger list to broaden activation
  > The frontmatter description appends 'Also trigger on SureChEMBL, patent chemistry, Markush structure, freedom to operate, composition of matter, assignee, priority date, patent family, or PatentsView.' This is discovery-surface tuning via keyword enumeration. The listed terms are all genuinely in scope for a patent-chemistry skill and there is no brand impersonation or over-broad 'general assistant' claim, so the risk is informational only.
  > **Remediation:** Describe capabilities functionally rather than listing activation keywords, to avoid unintended activation on unrelated queries.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — API endpoint base URL is overridable via environment variable, key sent to whatever host is configured
  > `_common.py` reads PATENTSVIEW_URL (and SURECHEMBL_FTP) from the environment with a safe default. `patent_search.search()` attaches the PATENTSVIEW_API_KEY as an `X-Api-Key` header to a URL built from that base. If the environment is tampered with (e.g., by another skill, a poisoned shell profile, or a compromised CI config), the free API key would be transmitted to an arbitrary host. Impact is low because the default is the legitimate PatentsView endpoint, the credential is a free low-value key, and no other secrets or local files are read or transmitted.
  > File: `scripts/_common.py`
  > **Remediation:** Validate the resolved host against an allow-list (search.patentsview.org, ftp.ebi.ac.uk) before attaching credential headers, or only send the API key when the URL scheme is https and the host matches the expected domain.

- **🟡 MEDIUM** `BEHAVIOR_ENV_VAR_HARVESTING` — Environment variable harvesting detected
  > Script iterates through environment variables in skills/patent-landscape/scripts/_common.py
  > File: `skills/patent-landscape/scripts/_common.py`
  > **Remediation:** Remove environment variable collection unless explicitly required and documented

### openfda — 🟡 MEDIUM

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Explicit activation keyword list in skill description
  > The description ends with an explicit trigger-keyword list ("Also trigger on openFDA, api.fda.gov, FAERS, Drugs@FDA, SPL, NDC, pharmacovigilance, boxed warning, adverse event report, drug recall, or safety signal"). This is discovery-surface tuning that can broaden activation beyond strict user intent. All listed keywords are, however, tightly scoped to the skill's genuine domain (FDA post-market drug data), there is no brand impersonation, no priority-manipulation language ("use me first"), and no over-broad claims, so the risk is minimal.
  > **Remediation:** Optional: describe capabilities declaratively rather than enumerating trigger tokens, letting the runtime perform semantic matching.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Declared allowed-tools broader than observed behavior
  > The manifest declares `allowed-tools: Read, Write, Edit, Bash`, but the bundled scripts perform only outbound HTTPS GET requests to api.fda.gov and write formatted tables to stdout/stderr. No file writes, edits, or shell command construction occur anywhere in the package. This is an over-permissive declaration rather than a violation (no code exceeds the declared tools), and Bash is legitimately needed to invoke the Python scripts.
  > **Remediation:** Narrow `allowed-tools` to the minimum actually required (e.g. Read, Bash) to reduce the blast radius if the skill is ever compromised.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — API key can be sent to an arbitrary host via base-URL override
  > `_common.py` reads the API root from the `OPENFDA_API_URL` environment variable and every CLI exposes a `--base-url` flag. `_build_url()` unconditionally appends `api_key` (from `OPENFDA_API_KEY`) to the query string for whatever host is configured. If an attacker (or a poisoned environment/agent prompt) sets `OPENFDA_API_URL` or passes `--base-url https://attacker.example`, the user's openFDA API key would be transmitted to that host in a GET query string. Impact is limited because the key is free, low-privilege, and public-quota-only, and no other secrets are read, so this is informational rather than a real exfiltration channel.
  > File: `scripts/_common.py`
  > **Remediation:** Only attach `api_key` when the resolved host matches an allowlist (e.g. `api.fda.gov`), and warn on stderr when a non-default base URL is used.

- **🟡 MEDIUM** `BEHAVIOR_ENV_VAR_HARVESTING` — Environment variable harvesting detected
  > Script iterates through environment variables in skills/openfda/scripts/_common.py
  > File: `skills/openfda/scripts/_common.py`
  > **Remediation:** Remove environment variable collection unless explicitly required and documented

### tamarind — 🟡 MEDIUM

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Skill workflows upload local structure/sequence files and API key to an external cloud service
  > By design the skill reads the TAMARIND_API_KEY environment variable and transmits it as the x-api-key header, and uploads local files (PDB/CIF/SDF) or inline file content to app.tamarind.bio / mcp.tamarind.bio. This is inherent, disclosed behavior consistent with the stated purpose (and the skill correctly instructs never to hardcode or commit keys), but it constitutes local-data-to-network flow that reviewers should be aware of: file content can be sent inline through the MCP channel, and no explicit user-confirmation step is required before uploading local files.
  > **Remediation:** Add an explicit confirmation step before uploading any local file or inline content, restrict uploads to files the user names, and document that only the documented tamarind.bio hosts may ever receive the API key.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Very broad trigger-keyword list in metadata increases unwanted activation
  > The manifest includes a large 'trigger-keywords' block plus an unusually broad description listing dozens of generic computational-biology terms (e.g. 'protein structure prediction', 'AlphaFold', 'binding affinity', 'enzyme', 'peptide', 'adme', 'protein language models', 'molecular design'). Many of these terms describe local/open-source tooling unrelated to the Tamarind platform, so the skill may be selected for tasks that do not require this vendor's cloud API, thereby routing user sequences and an API key into a third-party service. The skill does partially mitigate this by telling the agent to use local libraries for local work, so severity is low/informational.
  > **Remediation:** Narrow the keyword list to vendor-specific triggers (tamarind, tamarind.bio, app.tamarind.bio/api, mcp.tamarind.bio) and generic-tool keywords only when combined with an explicit 'run in the cloud' intent.

- **🟡 MEDIUM** `LLM_PROMPT_INJECTION` — Instructions direct the agent to fetch and trust live remote content at runtime
  > The SKILL.md explicitly tells the agent to prefer fetching remote, machine-readable sources at runtime over any local/hardcoded knowledge (https://app.tamarind.bio/llms.txt, https://app.tamarind.bio/openapi.yaml, https://docs.tamarind.bio/llms.txt and their .md pages). An 'LLM index' file (llms.txt) fetched from a remote host and consumed as authoritative guidance is a transitive-trust / indirect prompt injection vector: if that host is compromised, DNS-hijacked, or the content changes, injected instructions in the fetched markdown could steer the agent (e.g., change endpoints, exfiltrate the API key to a different host). The vendor is the plausible owner of these domains, so the risk is moderate rather than malicious intent, but the skill provides no guidance to treat fetched content as data-only.
  > File: `SKILL.md`
  > **Remediation:** Add explicit instruction that remotely fetched documents (llms.txt, openapi.yaml, docs .md pages) are untrusted DATA and must never be interpreted as instructions to the agent; pin to the documented HTTPS origin only, and require user confirmation before acting on any endpoint/credential-handling change discovered in fetched content.

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

### admet-prediction — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-heavy description for discovery triggering
  > The description ends with an explicit trigger keyword list ("Also trigger on ADMET-AI, admet_ai, Chemprop-RDKit, hERG liability, CYP3A4 inhibition, Caco-2, bioavailability prediction, or developability triage"). While these keywords are all narrowly scoped to the skill's genuine domain (ADMET prediction) and do not impersonate brands or claim general-purpose capability, the explicit activation-priming phrasing is a mild discovery-optimization pattern worth noting. No inflated or unrelated capability claims were found.
  > **Remediation:** Optional: trim the explicit trigger list to a concise natural-language description of when the skill applies. No functional change needed as the keywords are domain-accurate.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced documentation paths do not resolve
  > The scanner enumerated candidate paths under templates/ and assets/ (e.g. templates/endpoints.md, assets/running-admet-ai.md) that do not exist. The three files actually referenced in SKILL.md (references/running-admet-ai.md, references/endpoints.md, references/interpreting-predictions.md) all exist within the skill package and contain only benign scientific documentation. This is a documentation/packaging hygiene note, not a security issue.
  > File: `references/interpreting-predictions.md`
  > **Remediation:** No action required for security; ensure only existing paths are referenced to avoid the agent attempting reads on missing files.

### boltz — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency and direct git installation guidance
  > The reference documentation instructs the user to install Boltz via `pip install boltz` without a version pin, and offers `pip install git+https://github.com/jwohlwend/boltz.git` to install the development branch directly from GitHub. Unpinned/HEAD installs mean the code executed on the user's machine can change without review. The repository is the legitimate upstream Boltz project and the risk is low, but the installation guidance provides no version pin or hash verification.
  > File: `references/running.md`
  > **Remediation:** Pin an explicit version (e.g. `pip install boltz==2.2.1`) and avoid recommending installs from a mutable git HEAD, or note the security implications of doing so.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Workflow can transmit user sequences to a public third-party server
  > The documented workflow uses `boltz predict ... --use_msa_server`, which uploads the user's protein sequence to the public ColabFold MSA server. This is inherent to the upstream tool rather than to the skill's own code, and the skill repeatedly and explicitly warns not to use it for confidential or unpublished sequences (in the compatibility field, SKILL.md, running.md, yaml-schema.md, and a runtime reminder printed by make_boltz_yaml.py). Flagged only as informational data-egress awareness; no covert exfiltration exists in the bundled scripts.
  > File: `scripts/make_boltz_yaml.py`
  > **Remediation:** No change required; the existing warnings are adequate. Optionally default guidance to precomputed local MSAs for sensitive targets.

### antibody-engineering — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Description contains an explicit trigger-keyword list
  > The YAML description ends with an enumerated activation keyword list ("Also trigger on antibody, nanobody, VHH, scFv, Fab, CDR, framework, ANARCI, abnumber, IgBLAST, OAS, SAbDab, humanization, Vernier residues, or developability"). This is discovery-optimisation language rather than a functional description. All listed keywords are, however, tightly scoped to the skill's actual domain (antibody sequence numbering, CDR annotation, liability scanning, physicochemical profiling), so there is no capability inflation or brand impersonation and no attempt to claim priority over other skills. Informational only.
  > **Remediation:** Optionally trim the keyword enumeration to a concise natural-language description of capability; no security action required.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Some referenced documentation paths do not resolve
  > The instruction body links four reference documents (references/numbering-schemes.md, references/developability.md, references/humanization-and-design.md, references/tools.md) which are all present and contain only benign scientific documentation. The additional candidate paths probed under templates/ and assets/ do not exist. This is a documentation/packaging completeness note, not a security exposure: no external URLs are fetched and no instruction tells the agent to execute content found in any file.
  > File: `references/humanization-and-design.md`
  > **Remediation:** Ensure only existing in-package paths are referenced so the agent does not attempt to resolve missing resources.

### autodock-vina — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Broad activation keyword list in skill description
  > The description appends an explicit trigger list ('Also trigger on vina, smina, gnina, mk_prepare_ligand, mk_prepare_receptor, mk_export, scrub.py, PDBQT, autogrid4, docking box, or binding-pose prediction'). The keywords are all tightly scoped to molecular docking and match the skill's actual functionality, so this is normal domain-specific discoverability rather than capability inflation. Noted only for completeness; no over-broad or brand-impersonating claims were found.
  > **Remediation:** No action strictly required; keep the trigger keyword list confined to the skill's true domain, as it currently is.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instructions in documentation
  > The SKILL.md compatibility field and reference documentation instruct users to install third-party toolchain components (`pip install meeko`, `pip install molscrub`, `pip install vina`, `conda install -c conda-forge vina`, `pip install pdbfixer`) without version pinning or hash verification. The scripts themselves do not perform installs, so this is informational only, but unpinned installs from public registries carry a minor supply-chain risk if a package is compromised or typosquatted.
  > File: `SKILL.md`
  > **Remediation:** Pin exact versions (e.g., `pip install meeko==0.7.1 vina==1.2.7 molscrub==<version>`) and prefer verified conda-forge/PyPI sources; note that installation is a user action, not performed automatically by the skill.

### chembl — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Configurable API base URL allows redirection of queries to arbitrary hosts
  > All bundled scripts expose a `--base-url` flag that overrides the ChEMBL API root. If an agent is influenced by untrusted input (e.g., a user or document instructing it to use a different base URL), query parameters — including SMILES strings, target ids, and other potentially proprietary chemical structures — could be sent to an attacker-controlled host. Default behavior is the legitimate `https://www.ebi.ac.uk/chembl/api/data` endpoint, and no credentials are used, so real-world impact is limited to disclosure of query content and potential ingestion of untrusted JSON responses.
  > File: `scripts/_common.py`
  > **Remediation:** Optionally restrict `--base-url` to an allowlist of trusted hosts (e.g., *.ebi.ac.uk) or require an explicit environment-variable opt-in, and reject plain http:// schemes.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Unbounded paging / large default fetch volumes could consume significant network and CPU resources
  > `paged()` follows `page_meta.next` until exhaustion when no limit is supplied, and `target_activities.py` defaults to `--max-rows 20000` with automatic per-assay-type paging plus batched assay lookups. Combined with a 4-attempt retry loop and exponential backoff (up to 30s sleeps), a broad query could generate many hundreds of HTTP requests and long-running execution. Retries are bounded and there is a safety cap, so this is informational rather than a genuine DoS primitive.
  > File: `scripts/_common.py`
  > **Remediation:** Document expected request volumes and consider a global request-count ceiling plus a wall-clock timeout for paging loops.

### chemical-space — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-heavy description for discovery triggering
  > The YAML description ends with an explicit trigger keyword list ('Also trigger on ZINC22, CartBlanche, Enamine REAL, make-on-demand, tangible library, synthon, tranche, giga-scale enumeration, or ultra-large virtual screening.'). While all keywords are topically consistent with the skill's actual chemoinformatics purpose and not over-broad or brand-impersonating, the pattern is a mild form of activation keyword stuffing worth noting. No capability inflation was detected — the scripts do exactly what the description claims.
  > **Remediation:** Keep the description to a natural-language statement of purpose; trigger keyword lists are acceptable but should remain narrowly scoped to the domain, as they are here.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Missing referenced files (templates/ and assets/ variants)
  > Several referenced paths (templates/zinc22-and-cartblanche.md, templates/screening-strategy.md, templates/combinatorial-spaces.md, assets/*.md) do not exist in the package. The three genuinely referenced files under references/ are present and benign. Missing paths are a documentation/packaging hygiene issue rather than a security threat, but dangling references could later be satisfied by attacker-supplied files of the same name.
  > File: `references/zinc22-and-cartblanche.md`
  > **Remediation:** Remove stale path references or ship the referenced files inside the skill package so resolution cannot fall through to unexpected locations.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Base URL overridable via environment variable and CLI flag
  > The HTTP base URL is read from the CARTBLANCHE_URL environment variable and can also be overridden by the --base-url CLI flag. If an attacker can set that environment variable in the agent's environment, lookups would be redirected to an arbitrary host, sending ZINC identifiers (non-sensitive) there and returning attacker-controlled JSON that would be rendered into the agent's context. Impact is low: only public compound identifiers are transmitted, no credentials or local files are read, and responses are parsed as JSON rather than executed.
  > File: `scripts/_common.py`
  > **Remediation:** Optionally validate that the resolved base URL uses HTTPS and belongs to an allowlist of expected hosts (e.g. *.docking.org), and log the effective endpoint when it differs from the default.

### clinicaltrials — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — API base URL overridable via environment variable and CLI flag
  > The HTTP base URL is read from the CTGOV_API_URL environment variable and can also be overridden with --base-url. If an attacker (or a poisoned environment) sets this variable, requests intended for clinicaltrials.gov would be sent to an arbitrary host, redirecting query terms and returning attacker-controlled JSON that is then summarised into the agent's context. No credentials or local files are transmitted, and only query parameters (condition, drug, sponsor names) are sent, so exposure impact is low. Note _build_url also returns a raw path unchanged when it starts with http(s)://, though no code path currently supplies user-controlled absolute URLs.
  > **Remediation:** Pin the base URL to the official HTTPS registry host by default, validate any override against an allowlist of trusted hosts, and reject non-HTTPS schemes.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-baiting phrases appended to skill description
  > The description ends with an explicit trigger-word list ("Also trigger on ClinicalTrials.gov, NCT number, trial registry, study phase, enrolment, primary outcome measure, recruiting status, trial sponsor, or competitive landscape"). This increases activation likelihood via keyword stuffing. However, all listed keywords are directly relevant to the skill's genuine function (querying the ClinicalTrials.gov v2 API), so the practical risk is minimal and there is no capability inflation beyond the actual scope.
  > **Remediation:** Optionally trim the explicit trigger-keyword list to a concise natural-language description of scope.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Paged API walking can issue large numbers of outbound requests
  > ct_landscape.py and ct_search.py page through matching studies with a cursor, and count commands issue one total_count request per phase/status value. With a large --limit and a broad condition this can result in many sequential HTTPS requests plus exponential backoff sleeps (up to 30s each, 4 attempts). Defaults are bounded (limit 50-200, pageSize<=1000) and the skill documentation explicitly warns to use --limit deliberately, so this is a mild resource-consumption consideration rather than an intentional DoS pattern.
  > File: `scripts/_common.py`
  > **Remediation:** Consider capping --limit to a sane maximum and adding a total request budget to prevent accidental heavy polling of the public registry.

### deepchem — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation and install directly from a Git branch
  > The SKILL.md installation instructions tell the agent to run `uv pip install deepchem`, `uv pip install --pre deepchem`, and `pip install git+https://github.com/deepchem/deepchem.git` without version pinning or hash verification. Installing an untagged build from the default branch of a GitHub repository means the exact code executed is not reproducible and could change between runs. The instructions also suggest `conda install "mkl<2025"`. This is standard practice for scientific Python tooling and the repository is the legitimate upstream project, so the risk is limited, but it is an unverified supply-chain path.
  > File: `SKILL.md`
  > **Remediation:** Pin explicit versions (e.g. `deepchem==2.8.0`) and prefer tagged releases over installing from a mutable Git branch; document that nightly/git installs are unverified builds.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced documentation paths do not exist in the package
  > The instructions/reference resolution list includes files under templates/ and assets/ (e.g. templates/api_reference.md, assets/workflows.md, assets/core_capabilities.md) that are not present in the skill package. Missing references can cause the agent to search elsewhere or fabricate content, but there is no evidence of malicious intent — the actual reference documents exist under references/.
  > File: `references/core_capabilities.md`
  > **Remediation:** Remove or correct stale reference paths so all referenced files resolve inside the skill directory.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Automatic download and execution of third-party pretrained model weights
  > The transfer_learning.py script instantiates HuggingFace models by remote identifier ('seyonec/ChemBERTa-zinc-base-v1', 'ibm/MoLFormer-XL-both-10pct') and GroverModel with a local model_dir, causing weights/tokenizer configs to be fetched from the HuggingFace Hub at runtime without pinned revisions or checksum verification. Loading remote model artifacts can execute arbitrary deserialization code depending on the backend. These are well-known public model repositories and the behavior is disclosed in the skill documentation, so severity is low.
  > File: `scripts/transfer_learning.py`
  > **Remediation:** Pin model revisions (commit hashes) when loading HuggingFace checkpoints and prefer safetensors weights; note the network download requirement in the manifest compatibility field.

### datamol — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Documented cloud I/O paths use provider credentials from the environment
  > The skill documents remote read/write via fsspec (s3://, gs://, https://), which implicitly uses provider credentials from environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, GOOGLE_APPLICATION_CREDENTIALS). This is a legitimate library feature and the skill explicitly instructs that cloud paths should only be used when the user requests them, that write destinations must be confirmed, that credential scope should be limited to provider variables, and that no environment data is transmitted to third parties. No exfiltration endpoint, no credential reading code, and no automated upload behavior is present — flagged only as an informational data-egress surface for the operator to be aware of.
  > **Remediation:** No change strictly required. Optionally reiterate that the agent must obtain explicit user confirmation before any remote write and must never echo credential values into chat or logs.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instructions
  > The skill instructs the agent to install packages via `uv pip install datamol`, `uv pip install s3fs`, and `uv pip install gcsfs` without version pinning or hash verification. While these are well-known, legitimate PyPI packages from a reputable maintainer (datamol-io/Valence Labs), unpinned installs mean the resolved artifact is whatever is current at install time, which is a minor supply-chain exposure. No typosquatting or untrusted GitHub sources are used.
  > **Remediation:** Recommend pinned versions consistent with the documented tested release (e.g., `uv pip install "datamol==0.12.5"`) and note that installation should be user-approved.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Broken/non-existent file references in extracted reference list
  > The reference extraction lists several paths that do not exist in the package (assets/*.md, templates/*.md, sklearn.py, datamol.py). Inspection shows these are artifacts of pattern extraction: the six real reference documents exist under references/ and are present; `sklearn.py` and `datamol.py` originate from `import datamol as dm` / `from sklearn.ensemble import ...` code snippets, and the SKILL.md explicitly clarifies these are third-party PyPI packages, not bundled scripts. Impact is documentation hygiene only, but dangling references could later be satisfied by an attacker-dropped file of the same name in the skill directory.
  > File: `references/core_api.md`
  > **Remediation:** Keep all reference links limited to the actual references/ directory paths and avoid phrasing that causes import statements to be parsed as local file references.

### depmap — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Example download helper fetches remote files without validation or integrity checks
  > The SKILL.md includes a `download_depmap_data` helper that streams an arbitrary URL to a local file path with no HTTPS/host allow-listing, no checksum or size verification, and no status-code check. The documented URLs (depmap.org, figshare.com) are legitimate public data sources and the pattern is inbound download rather than outbound exfiltration, so risk is low, but content written to disk is unverified remote data. The skill itself acknowledges the portal returns HTML browser-verification pages with HTTP 200, meaning non-data content could silently be saved and later parsed as data.
  > File: `SKILL.md`
  > **Remediation:** Add response.raise_for_status(), verify Content-Type is CSV/octet-stream (not text/html), restrict to an allow-list of known DepMap/Figshare hosts, and validate a checksum or expected file size before use.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Instructions reference files that do not exist in the package
  > The instruction body and reference material imply resources that are not present in the package (templates/dependency_analysis.md, assets/dependency_analysis.md) and the reference guide imports from a non-existent local module `depmap_utils`. Missing referenced resources can cause the agent to improvise, fetch substitutes from the network, or generate code that fails at runtime. No malicious content is involved; this is a documentation/packaging defect.
  > File: `references/dependency_analysis.md`
  > **Remediation:** Bundle the referenced helper module and any templates/assets, or remove the references and inline the loader function that is already defined in SKILL.md.

### diffdock — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned external repository clone and Docker image pull in setup instructions
  > Installation guidance instructs the agent/user to clone the upstream DiffDock GitHub repository at HEAD and pull the `rbgcsail/diffdock` Docker image without a commit hash, tag, or digest pin. Additionally, ESM install guidance uses `uv pip install fair-esm` with no version pin. This is standard practice for scientific tooling and the sources are the legitimate upstream projects, but unpinned third-party code retrieval is a mild supply-chain exposure (upstream compromise or tag mutation would be silently inherited).
  > **Remediation:** Pin the upstream repository to a specific release tag or commit (e.g., `git clone --branch v1.1.3 --depth 1`), pull the Docker image by digest, and pin `fair-esm==<version>`.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced bundle files are missing
  > SKILL.md references `references/workflows_examples.md` and the resolver also probed `templates/` and `assets/` variants of the reference documents that do not exist. Missing referenced files are a documentation/integrity defect rather than a security threat: the agent may attempt Read operations that fail, or fall back to inventing content. No malicious content was found in the files that do exist (`references/confidence_and_limitations.md`, `references/parameters_reference.md`, `assets/custom_inference_config.yaml`).
  > File: `references/confidence_and_limitations.md`
  > **Remediation:** Ship all referenced documents inside the skill package or remove the references so the agent does not attempt reads on non-existent paths.

### immunogenicity — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger keyword list in description
  > The skill description includes an explicit list of activation keywords ('Also trigger on immunogenicity, anti-drug antibody, ADA, T-cell epitope, MHC class II, HLA-DRB1, NetMHCIIpan, NetMHCpan, deimmunisation, tregitope, or population coverage'). While all listed terms are tightly scoped to the skill's actual domain (MHC class II epitope prediction and ADA risk triage) and are not over-broad or brand-impersonating, this pattern is a mild discovery-optimisation technique worth noting.
  > **Remediation:** Optional: describe capabilities in prose rather than enumerating trigger keywords. No action required given the keywords are domain-accurate and narrowly scoped.

### free-energy-perturbation — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list appended to skill description
  > The YAML description ends with an explicit activation-keyword list ("Also trigger on OpenFE, alchemical transformation, thermodynamic cycle, RBFE, ABFE, SepTop, lambda window, MBAR, cycle closure, or perturbation map"). This is a mild discovery-optimisation pattern that can broaden activation beyond strictly relevant requests. All listed keywords are, however, tightly scoped to the skill's genuine domain (alchemical free energy calculations), so the risk of unwanted activation or capability inflation is minimal and no brand impersonation or over-broad "general assistant" claims are present.
  > **Remediation:** Optional: describe capabilities in prose rather than enumerating trigger keywords, to keep activation scope tightly aligned with intent.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Documented environment-creation command installs unpinned package from conda-forge
  > The instructions and reference docs tell the user to run `mamba create -n openfe -c conda-forge openfe` without a pinned version. This is a documentation-level suggestion (the agent would need Bash to run it) and points at a well-known, legitimate channel and package; the skill explicitly warns that the PyPI `openfe` name is an unrelated 0.0.12 placeholder, which is actually good typosquatting/name-confusion hygiene. Impact is limited to normal reproducibility concerns rather than a supply-chain attack.
  > **Remediation:** Pin the intended version (e.g. `openfe=1.12`) in the documented install command and note that the command should be run with user confirmation.

### generative-design — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list in skill description
  > The description ends with an explicit activation keyword list ("Also trigger on REINVENT, LibInvent, LinkInvent, Mol2Mol, scaffold hopping, R-group replacement, linker design, chemical language model, or reinforcement-learning molecule optimisation"). All terms are narrowly scoped to the skill's actual domain (REINVENT 4 generative molecular design), so this is normal discoverability tuning rather than capability inflation; noted for completeness only. No over-broad claims such as "general assistant" or "use me first" are present.
  > **Remediation:** No action strictly required; optionally trim the explicit trigger-word list to keep activation scope tight.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned installation from external GitHub repository
  > The SKILL.md body and references/reinvent-configuration.md instruct the user to install REINVENT 4 via `git clone https://github.com/MolecularAI/REINVENT4.git` followed by `pip install -e .` with no commit/tag pin and no integrity verification. The skill itself does not execute this, but if an agent follows the documentation it would install unversioned code (and its transitive dependencies) from a network source. The repository is the legitimate AstraZeneca/MolecularAI project, so risk is low, but the lack of a pinned revision is a supply-chain hygiene gap.
  > File: `references/reinvent-configuration.md`
  > **Remediation:** Pin a specific release tag or commit hash (e.g. `git clone --branch v4.8 --depth 1 ...`) and recommend verifying the repository owner/signature before installing; note that `pip install -e .` pulls unpinned transitive dependencies.

### glycoengineering — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Outbound HTTP requests to external bioinformatics web services
  > Sample code performs GET requests to external endpoints (GlyConnect API, GlyTouCan API, DTU Health Tech webface CGI). The data sent is a user-supplied UniProt accession or protein sequence, which is the stated purpose of the skill. No credentials, environment variables, local files, or system information are collected or transmitted, and all destinations are well-known public scientific resources. Flagged only as informational: any protein sequence submitted to a remote predictor leaves the local environment, which may matter for proprietary/unpublished sequences.
  > **Remediation:** Document that sequences/IDs are transmitted to third-party servers and require explicit user consent before any remote submission; keep the bundled standard-library sequon/O-glycan analysis as the default offline path.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list in description broadens activation surface
  > The frontmatter description ends with an explicit activation keyword list ('Also trigger on N-glycosylation, sequon, NXS/NXT, O-glycosylation, glycoform heterogeneity, afucosylation, high-mannose, GlyTouCan, or WURCS'). All listed terms are tightly scoped to the skill's genuine glycobiology domain and there is no brand impersonation, priority manipulation, or claim of general-purpose capability, so the discovery-inflation risk is minimal. Noted for completeness only.
  > **Remediation:** Optionally replace the explicit trigger list with a concise natural-language capability statement to avoid over-activation on tangential queries.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Two referenced resource paths do not exist in the package
  > Path resolution surfaced references to `assets/glycan_databases.md` and `templates/glycan_databases.md`, neither of which exists in the package; only `references/glycan_databases.md` (the path actually cited in SKILL.md) is present and benign. Missing files can cause the agent to fail or to search outside the package directory for a substitute, but there is no evidence of malicious intent here.
  > File: `SKILL.md`
  > **Remediation:** Ensure all referenced resource paths resolve inside the skill package and instruct the agent not to fall back to files outside the skill directory.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation via uv pip install
  > The SKILL.md documents installing the third-party package `glycoshield` with `uv pip install glycoshield` without any version pin or hash verification. If the agent executes this documented command (Bash is an allowed tool), the resolved version is whatever the index currently serves, exposing the environment to dependency-confusion or malicious-release risk. This is a common documentation pattern rather than intentional malice, and the package/domain referenced (MPCDF GitLab project) is a legitimate scientific tool.
  > File: `SKILL.md`
  > **Remediation:** Pin the version explicitly (e.g., `uv pip install glycoshield==<x.y.z>`), prefer a lockfile/hash-pinned requirements file, and note that installation should be confirmed by the user rather than executed automatically.

### medchem — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Activation-trigger keyword list embedded in description
  > The YAML description ends with an explicit trigger list ("Also trigger on medchem, `import medchem as mc`, RuleFilters, NIBRFilters, CommonAlertsFilters, NamedCatalogs, QueryFilter, PAINS filtering, or structural alerts") designed to broaden skill discovery/activation. The listed keywords are all genuinely within the skill's stated domain (medicinal chemistry filtering), so this is a minor discovery-optimization pattern rather than capability inflation or brand impersonation, but it is worth noting as it increases unsolicited activation likelihood.
  > File: `SKILL.md`
  > **Remediation:** Describe capabilities functionally without an explicit activation keyword-bait list; keep the description scoped to what the skill actually does.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instructions
  > The SKILL.md instructs installation of dependencies via `uv pip install medchem datamol` and `mamba install -c conda-forge lilly-medchem-rules` without version pinning or hash verification. While these are well-known, legitimate open-source cheminformatics packages from datamol-io/conda-forge, unpinned installs leave the skill open to pulling a compromised or unexpected future version (supply-chain risk). No install command executes from an untrusted or unknown repository.
  > File: `SKILL.md`
  > **Remediation:** Pin exact versions (e.g., `medchem==2.0.5`) consistent with the version the skill claims to be verified against, and prefer a lockfile or hash-verified installation.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced file paths do not exist in the package
  > The extraction lists referenced paths that are absent from the package (assets/rules_catalog.md, assets/api_guide.md, templates/api_guide.md, templates/rules_catalog.md, medchem.py, datamol.py). The two genuinely used references (references/api_guide.md and references/rules_catalog.md) are present and contain only benign API documentation. The missing entries appear to stem from module-name/path heuristics in documentation rather than malicious intent, but broken references can lead the agent to attempt reads of non-existent or ambiguously-resolved paths.
  > File: `references/rules_catalog.md`
  > **Remediation:** Reference only files that ship with the package and use consistent relative paths so the agent does not attempt to resolve non-existent resources.

### molfeat — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Instructions direct installation of external packages and download of third-party pretrained models
  > The skill instructs the agent to run package installs (`uv pip install "molfeat==0.11.0"` and extras) and to download pretrained model weights from the HuggingFace Hub (`HFModel.from_pretrained("DeepChem/ChemBERTa-77M-MLM", ...)`), and references installing MAP4 from an external GitHub repository (reymond-group/map4). This is normal for a cheminformatics tooling skill and versions are explicitly pinned, but it does introduce third-party code/artifact execution on the user's machine. Downloaded store artifacts are noted as checksum-verified; HF Hub weights are not independently verified in the skill.
  > File: `SKILL.md`
  > **Remediation:** Keep explicit version pins (already done), and note that model weights and the external MAP4 repository are third-party artifacts that should be reviewed/verified (e.g., checksum or trusted mirror) before installation in sensitive environments.

### molecular-dynamics — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-dense description with explicit trigger list
  > The frontmatter description ends with an explicit 'Also trigger on ...' list enumerating many tool names and API symbols (OpenMM, MDAnalysis, mdtraj, Simulation.step, LangevinMiddleIntegrator, PDBFixer, DCD/XTC, RMSD analysis, production MD). This increases discovery/activation surface. In this case the keywords are all directly relevant to the skill's genuine molecular dynamics scope, so the risk is minimal and not deceptive, but it is a mild activation-broadening pattern worth noting.
  > **Remediation:** Keep the description focused on the skill's purpose and avoid explicit 'trigger on' keyword lists; rely on natural-language relevance for activation.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instructions
  > The skill instructs installing packages via `conda install -c conda-forge openmm mdanalysis nglview`, `uv pip install openmm mdanalysis`, and `uv pip install openff-toolkit` without version pinning. While these are well-known, legitimate scientific packages from reputable channels, unpinned installs allow a future compromised or typosquatted release to be pulled in, and the versions may not match the documented 'checked against' versions (OpenMM 8.5.2 / MDAnalysis 2.10.0).
  > **Remediation:** Pin dependency versions (e.g., `openmm==8.5.2 mdanalysis==2.10.0`) or provide an environment.yml/requirements.txt with hashes, and require explicit user confirmation before performing any installation.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced file paths do not exist in the package
  > The reference scan lists paths that are not present (assets/mdanalysis_analysis.md, templates/mdanalysis_analysis.md, plus module-name artifacts such as matplotlib.py, openmm.py, MDAnalysis.py, pdbfixer.py, openff.py that come from Python import statements rather than real files). The only genuinely referenced document, references/mdanalysis_analysis.md, exists and contains benign analysis documentation. Missing files are a documentation-hygiene issue, not evidence of malice, but broken references can lead an agent to search for or fabricate substitutes.
  > File: `references/mdanalysis_analysis.md`
  > **Remediation:** Ensure all referenced paths resolve within the package and remove or correct dangling references; import statements should not be interpreted as bundled file references.

### ncats-arax — 🔵 LOW

- **🔵 LOW** `LLM_COMMAND_INJECTION` — User-supplied provider identifiers are interpolated into an ARAX DSL (ARAXi) action string
  > The query contract states that provider identifiers passed via `--kp` are interpolated into an ARAXi action string sent to the remote service. String interpolation of user-controlled values into a domain-specific command language is an injection surface. The documented mitigation is a strict allow-list regex (`^infores:[A-Za-z0-9._-]+$`) plus duplicate rejection, which appears adequate, but the enforcing code is absent from the package so the control cannot be confirmed.
  > **Remediation:** Include the client code so the regex allow-list and list-valued `kp=` construction can be reviewed; prefer structured parameter assembly over string interpolation into the DSL.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Outbound transmission of user query terms to a third-party public API (disclosed)
  > The skill sends user-supplied entity names and CURIEs to the external NCATS Translator ARAX production endpoint over HTTPS, where query and caller metadata may be publicly visible. This is inherent to the skill's stated purpose and is prominently disclosed in the manifest compatibility field and a dedicated safety-boundary section, with an explicit `--acknowledge-public-query` gate and instructions to never place user, project, or query terms into the submitter or User-Agent headers. No credential access, environment harvesting, or covert exfiltration channel is described. Recorded as informational only.
  > **Remediation:** No change required; retain the explicit acknowledgment gate, the fixed constant submitter identity, and the prohibition on submitting sensitive or patient-specific content.

- **🔵 LOW** `LLM_COMMAND_INJECTION` — Referenced executable script not included in package; instructions direct agent to run it via Bash
  > SKILL.md instructs the agent to execute `python skills/ncats-arax/scripts/arax_client.py` for preflight, normalize, one-hop, two-hop, and summarize commands, but no script files are present in the analyzed package. The security properties described (URL allow-listing, HTTPS-only, private-address rejection, byte-exact artifact handling, size caps, regex validation of CURIEs/providers) therefore cannot be verified. If the script is supplied later or from another source, its actual behavior may diverge from the documented contract, and the Bash invocation would execute unreviewed code.
  > File: `scripts/arax_client.py`
  > **Remediation:** Bundle the referenced `scripts/arax_client.py` inside the skill package so its network, filesystem, and input-validation behavior can be audited, or remove the execution instructions until the script is included.

- **⚪ INFO** `LLM_CONTEXT_BUDGET_EXCEEDED` — 'scripts/arax_client.py' excluded from LLM analysis (84,318 chars)
  > file size (84,318 chars) exceeds per-file limit (75,000)
  > File: `scripts/arax_client.py`
  > **Remediation:** Increase llm_analysis.max_code_file_chars in your scan policy to include this content in LLM analysis.

### oligonucleotides — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword list appended to description to broaden activation
  > The skill description ends with an explicit trigger-keyword enumeration ("Also trigger on siRNA, antisense oligonucleotide, ASO, gapmer, RNase H, seed region, duplex asymmetry, 2'-MOE, locked nucleic acid, phosphorothioate, or GalNAc conjugate"). While all terms are genuinely within the skill's stated domain and no priority/override language is used, keyword stuffing in a description is a discovery-surface pattern worth noting. Impact is minimal here because the claims match the implemented functionality.
  > File: `SKILL.md`
  > **Remediation:** Optional: replace the keyword enumeration with a concise natural-language capability statement; avoid list-style activation baiting.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Unbounded compute in transcriptome-wide contiguous-match scan
  > offtarget_scan.py 'contig' runs longest_common_substring (nested loop with repeated substring containment checks) for every candidate against every transcript in a user-supplied FASTA. With a full transcriptome (hundreds of thousands of records, hundreds of MB) and multiple candidates this becomes very expensive CPU/memory work (read_fasta also loads the entire FASTA into memory). This is an inefficiency/resource-consumption concern on locally supplied data rather than a malicious pattern — there is no network access, no external data fetch, and no hidden behaviour.
  > File: `scripts/offtarget_scan.py`
  > **Remediation:** Add caps on FASTA size / record count, stream records instead of loading all into memory, and expose a timeout or max-candidates limit.

### open-targets — 🔵 LOW

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Documentation claims verification against a future-dated data release
  > SKILL.md states it was 'Checked against: the live API, August 2026 — meta reports API 26.6.3, data release 26.06'. A future-dated provenance claim cannot be verified and could lead the agent to present unverifiable schema/version assertions (e.g., renamed datasource ids, removed fields) as authoritative. This is a documentation accuracy issue, not a malicious payload, and the skill correctly instructs the agent to report the release and verify decision-relevant results against primary sources.
  > File: `SKILL.md`
  > **Remediation:** Replace the verification date with an accurate one, or instruct the agent to query the `meta` field at runtime to confirm the live API and data release version.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — GraphQL endpoint is overridable via environment variable and CLI flag
  > The shared transport module reads the API endpoint from the OPEN_TARGETS_API_URL environment variable and also exposes a `--api-url` flag on every subcommand. If an attacker can influence the agent's environment or the command line, all query traffic (including any identifiers or free-text search terms supplied by the user) can be silently redirected to an arbitrary host. This is a common and generally acceptable configurability pattern, and no data beyond query terms is transmitted, so impact is limited; the default is the legitimate public Open Targets endpoint.
  > File: `scripts/_common.py`
  > **Remediation:** Optionally validate that the resolved URL uses HTTPS and belongs to an allow-listed host (e.g. api.platform.opentargets.org), and log the effective endpoint when it differs from the default.

### primekg — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Description includes broad trigger-keyword list for activation
  > The skill description appends an explicit list of activation keywords ('Also trigger on PrimeKG, kg.csv, Harvard Dataverse knowledge graph, disease_protein, drug_protein, indication and contraindication edges, or network pharmacology...'). This is a mild form of discovery/activation tuning. However, all listed keywords are directly relevant to the skill's genuine functionality (PrimeKG edge-list querying), so this is informational rather than deceptive capability inflation.
  > **Remediation:** Keep the description focused on capabilities; avoid explicit keyword-baiting phrasing such as 'Also trigger on ...'.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Full in-memory load of a multi-gigabyte CSV without size guards
  > The script reads the entire ~4M-row PrimeKG edge list into a pandas DataFrame via pd.read_csv with no row limits, chunking, or size checks, and caches it in a module-level dict. The two-hop path search additionally iterates nested pandas frames per intermediate node, which for hub nodes can produce very large path enumerations. This is documented behavior (compatibility notes warn about several GB of RAM) and is inherent to the stated purpose, so risk is low, but a user-supplied --data path to an arbitrarily large file could exhaust memory/CPU.
  > File: `scripts/query_primekg.py`
  > **Remediation:** Add optional row/size limits or chunked reading, cap the number of intermediate nodes/paths enumerated, and validate file size before loading.

### protein-binder-design — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list appended to skill description
  > The frontmatter description ends with an explicit activation-bait list ("Also trigger on BindCraft, RFdiffusion, ProteinMPNN, minibinder, hallucination, inverse folding, hotspot residue, epitope targeting, ipTM, or de novo binder"). The keywords are all genuinely within the skill's stated domain, so this is at most mild discovery optimisation rather than deceptive capability inflation, but it does broaden automatic activation (e.g. the generic term "hallucination").
  > File: `SKILL.md`
  > **Remediation:** Trim generic/ambiguous trigger terms (e.g. "hallucination") and rely on a concise functional description for discovery.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Documentation suggests cloning and running an external installer without pinning
  > A bundled reference file documents cloning a third-party GitHub repository and executing its install script, with no commit/tag pin or integrity verification. No bundled script performs this action automatically, and the referenced repository is the legitimate, well-known upstream project for the documented tool, so risk is informational; the agent would only run this at explicit user direction.
  > File: `references/bindcraft-and-rfdiffusion.md`
  > **Remediation:** Pin a specific release tag or commit hash and note that the user should review the installer before execution; state that installation is a manual, user-approved step.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Instructions reference several files that are not present in the package
  > SKILL.md/reference discovery lists paths under templates/ and assets/ (e.g. templates/epitope-selection.md, assets/filtering-and-validation.md) that do not exist in the package. Missing internal references are a documentation-hygiene issue; they can cause the agent to search elsewhere or fail, and dangling paths could later be satisfied by unvetted files.
  > File: `references/bindcraft-and-rfdiffusion.md`
  > **Remediation:** Reference only files bundled in the package (references/*.md) and remove or ship the missing templates/assets paths.

### pkpd-translation — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list appended to skill description
  > The YAML description ends with an explicit list of activation keywords ("Also trigger on non-compartmental analysis, AUC, clearance, volume of distribution, allometric scaling, human equivalent dose, first-in-human, NOAEL, therapeutic index, or exposure margin"). This is keyword-baiting that broadens discovery/activation surface. In this case all keywords are tightly scoped to the skill's genuine pharmacokinetic functionality, so the risk of inappropriate activation or capability inflation is minimal — informational only.
  > **Remediation:** Optionally trim the explicit keyword enumeration and rely on a concise natural-language description of the skill's purpose.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Clinical dose-projection arithmetic could be misapplied without qualification
  > The skill computes human-equivalent doses, first-in-human maximum recommended starting doses, and safety margins — outputs that, if taken as authoritative, could contribute to unsafe clinical decisions. The package mitigates this well: the manifest compatibility field, the SKILL.md body, the reference documents, and the scripts' stderr commentary all repeatedly state that results are planning arithmetic and not a regulatory submission, flag the TGN1412 precedent, warn about protein-binding errors, extrapolation limits, non-linear PK, and population variability, and direct users to PBPK/population-PK tooling when the assumptions break. No deceptive or misleading claims were identified; this is noted as informational context only.
  > File: `SKILL.md`
  > **Remediation:** No action required; the existing caveats are appropriate. Continue to surface the non-regulatory disclaimer in any summarized output.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Sibling-module import via sys.path manipulation
  > exposure_margin.py inserts its own directory at the front of sys.path and imports pk_compartmental. This is a normal pattern for a self-contained skill bundle and only loads a file shipped inside the skill package, but prepending to sys.path[0] means a same-named module placed in the skill directory would take precedence over standard-library/site-packages modules. No untrusted or network-sourced code is loaded, and no packages are installed at runtime (standard library only, no pip/npm calls), so supply-chain exposure is negligible.
  > File: `scripts/exposure_margin.py`
  > **Remediation:** Prefer a relative/package import or append rather than insert at index 0 to avoid shadowing standard modules.

### rdkit — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Description includes explicit activation trigger keyword list
  > The YAML description ends with an explicit instruction to the agent's discovery mechanism: "Also trigger on rdkit, Chem.MolFromSmiles, rdFingerprintGenerator, SDMolSupplier, SMARTS query, ETKDG, or FilterCatalog." This is keyword baiting to increase activation likelihood. In this case the keywords are all narrowly and accurately scoped to RDKit cheminformatics functionality (no brand impersonation, no over-broad 'general assistant' claims), so the practical risk of unwanted activation or capability inflation is minimal. Noted for completeness only.
  > **Remediation:** Optional: describe capabilities declaratively rather than instructing the discovery layer to 'trigger on' specific tokens. No change strictly required since the terms match the actual scope.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced documentation paths do not resolve (templates/, assets/)
  > The dependency scan lists reference paths under templates/ and assets/ (e.g. templates/api_reference.md, assets/core_capabilities.md) that do not exist in the package. The SKILL.md body itself only links the five files under references/, all of which exist and are benign; the unresolved paths appear to be inferred alternates rather than authored links. No external URLs or network-sourced instruction files are referenced, so there is no indirect prompt injection surface. Informational documentation hygiene issue only.
  > File: `references/core_capabilities.md`
  > **Remediation:** Ensure the bundled resource list matches the actual on-disk layout (references/ only) so integrity checks do not report phantom dependencies.

### rowan — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Documentation examples hardcode API key assignment in source
  > Multiple code examples instruct setting `rowan.api_key = "your_api_key_here"` / `rowan.api_key = "..."` directly in Python code rather than exclusively via the ROWAN_API_KEY environment variable. No real secret is present, and the skill does recommend the env-var approach first, so this is only a minor secure-coding hygiene issue that could encourage users/agents to commit credentials.
  > **Remediation:** Standardize examples on reading the key from the ROWAN_API_KEY environment variable and remove inline literal-assignment examples.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Metered cloud compute spend with no explicit user-confirmation gate for batch jobs
  > The skill orchestrates a commercial, credit-metered cloud service and encourages batch submission loops and 50+ workflow campaigns. While the manifest transparently discloses that compute is billed and that large batches have real cost, and the guidance actively recommends pre-filtering to save credits, there is no instruction requiring explicit user confirmation before submitting large batches. An agent acting autonomously could incur unintended financial cost. No unbounded loops or local resource exhaustion patterns are present.
  > **Remediation:** Add an explicit instruction to estimate credit cost and obtain user confirmation before submitting batches above a small threshold (e.g., >5 workflows).

### pytdc — 🔵 LOW

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Instruction body references files that are not present in the package
  > The SKILL.md body and reference extraction list several paths that do not exist in the bundle (e.g., assets/*.md, templates/*.md, tdc.py). Only references/datasets.md, references/utilities.md, references/oracles.md and references/sources.md are actually shipped. Missing referenced resources can cause an agent to search elsewhere or fabricate content, a documentation-hygiene issue rather than a security exploit. No external URL is instructed to be fetched and treated as instructions; the only URLs are documentation citations (PyPI, tdcommons.ai, GitHub) used for human verification, and references/sources.md explicitly states web results were treated as untrusted text.
  > File: `SKILL.md`
  > **Remediation:** Remove or correct stale file references so every path named in SKILL.md resolves inside the package.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Execution paths download and load third-party model artifacts (pickled checkpoints) from remote hosts
  > The oracle workflow (scripts/molecular_generation.py, execute_scores) constructs `tdc.Oracle(...)` for DRD2/GSK3B/JNK3/CYP3A4_Veith/LogP/SA, which upstream PyTDC downloads from Harvard Dataverse and deserializes as model artifacts. Similarly, benchmark_evaluation.py constructs BenchmarkGroup classes that download and extract remote archives. Loading serialized model artifacts from a remote host is an inherent supply-chain/deserialization risk. Mitigations are strong: the behavior is default-off and requires explicit `--execute` plus `--download` flags, is written into a validated relative workspace directory via a chdir sandbox, and references/oracles.md explicitly warns the operator to review artifact origin and trust boundary. No checksum verification is performed (PyTDC provides none), which is documented as an upstream gap.
  > File: `scripts/molecular_generation.py`
  > **Remediation:** Where feasible, record and verify checksums/sizes of downloaded checkpoints and archives, and surface the resolved download URL to the user in the plan output before `--download` is granted.

### retrosynthesis — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list in description broadens activation surface
  > The frontmatter description ends with an explicit list of activation keywords ("Also trigger on AiZynthFinder, retrosynthetic tree search, synthetic accessibility, SAscore, RAscore, building-block stock, reaction template, or route scoring"). All listed terms are genuinely within the skill's stated domain, so this is not deceptive capability inflation, but keyword enumeration does increase the chance of unintended activation. Informational only — no evidence of brand impersonation or over-broad claims.
  > File: `SKILL.md`
  > **Remediation:** Optional: trim the explicit keyword list to a concise natural-language description of when the skill applies.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency install instruction (pip install aizynthfinder)
  > SKILL.md and references/aizynthfinder-setup.md instruct the user to run `pip install aizynthfinder` without a pinned version, and `download_public_data <dir>` to fetch multi-gigabyte model/stock artifacts from the upstream project. The package is a well-known, MIT-licensed AstraZeneca/MolecularAI project and the documented version (4.4.1) matches the referenced homepage, so supply-chain risk is low, but the install is unpinned and no checksum verification is performed on the downloaded model artifacts. The bundled scripts themselves do not install anything or make network calls.
  > File: `references/aizynthfinder-setup.md`
  > **Remediation:** Pin the version explicitly (e.g. `pip install aizynthfinder==4.4.1`) and note that downloaded model/stock files should be validated against upstream checksums.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced file paths do not exist in the package
  > The reference list includes paths under templates/ and assets/ (templates/synthesizability-scores.md, assets/aizynthfinder-setup.md, assets/route-quality.md, templates/aizynthfinder-setup.md, assets/synthesizability-scores.md, templates/route-quality.md) that are not present. The three files actually linked from SKILL.md (references/aizynthfinder-setup.md, references/synthesizability-scores.md, references/route-quality.md) all exist and contain only benign, domain-appropriate chemistry guidance. The missing entries appear to be path-resolution artifacts rather than intentional misdirection, but broken references could cause the agent to search elsewhere or fabricate content.
  > File: `references/synthesizability-scores.md`
  > **Remediation:** Ensure all referenced documentation resolves to files bundled inside the skill directory and remove stale path references.

### target-safety — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — API endpoints overridable via environment variables and CLI flags
  > Both service base URLs are read from the environment (GNOMAD_API_URL, GWAS_API_URL) and can also be overridden with --gnomad-url / --gwas-url. If the environment or command line were influenced by untrusted input, gene symbols and query traffic could be redirected to an attacker-controlled host, and untrusted JSON would then be parsed and rendered as authoritative results. Defaults point to the legitimate, documented public endpoints (gnomad.broadinstitute.org, www.ebi.ac.uk), no credentials or local files are transmitted, and the data sent is only user-supplied gene symbols, so impact is limited.
  > **Remediation:** Validate overridden URLs against an allowlist of expected hosts (or require https and warn loudly when a non-default endpoint is used).

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list in skill description
  > The frontmatter description ends with an explicit activation keyword list ('Also trigger on gnomAD, LOEUF, pLI, loss-of-function intolerance, mutational constraint, GWAS Catalog, credible set, human knockout, genetic support, or target safety dossier'). This is keyword-loading intended to increase discovery/activation. The keywords are, however, narrowly scoped to the skill's actual domain (human genetic evidence for drug targets) and do not make over-broad or brand-impersonating claims, so the practical risk of unwanted activation or capability inflation is minimal.
  > **Remediation:** Optionally trim the explicit trigger-keyword enumeration to a concise natural-language description of the skill's purpose.

### uniprot-rcsb — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-heavy description for discovery triggering
  > The description ends with an explicit trigger-keyword list ('Also trigger on UniProt accessions, PDB ids, rest.uniprot.org, search.rcsb.org, files.rcsb.org, alphafold.ebi.ac.uk, id mapping, SEQRES, or missing residues'). While the keywords are tightly scoped to the skill's genuine bioinformatics domain and the implementation matches the claims, this pattern is technically activation/discovery optimization. Impact is minimal because there is no capability inflation beyond actual behavior.
  > **Remediation:** Optionally trim the explicit trigger-keyword list to a natural-language description of scope; no functional change required.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Unvalidated identifiers interpolated into download URLs (path traversal / SSRF surface)
  > fetch_structure.py builds download URLs by interpolating user-supplied PDB ids, assembly numbers, accessions, and component ids directly into f-strings without validating character sets (e.g. f"{RCSB_FILES}/{pdb_id}.{suffix}"). Because the host prefix is a hardcoded constant, a crafted identifier containing '../' or '@' could at most redirect the request to another path on files.rcsb.org, and the AlphaFold branch fetches URLs returned by the AlphaFold API (server-controlled) and writes them to a local file whose name comes from the remote URL basename. No credentials, environment variables, or local sensitive files are read, and no data is sent outward, so real-world risk is low.
  > File: `scripts/fetch_structure.py`
  > **Remediation:** Validate identifiers against strict regexes (e.g. ^[0-9A-Za-z]{4}$ for PDB ids, ^[A-Z0-9]{1,5}$ for CCD codes, ^[A-Z0-9]+$ for accessions) and confirm AlphaFold-returned URLs match an allowlisted host before downloading.
