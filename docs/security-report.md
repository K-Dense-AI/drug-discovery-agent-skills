# Security Scan Report

**Generated:** 2026-09-21 09:24 UTC  
**Skills scanned:** 37  
**Total findings:** 157  
**Critical:** 0 | **High:** 0 | **Safe skills:** 37/37

**Scanner:** cisco-ai-skill-scanner 2.0.13 · **Model:** claude-opus-5  
**This run:** full rescan of all 37 skill(s).  

## Summary

| Skill | Severity | Findings | Safe | Duration |
|-------|----------|----------|------|----------|
| patent-landscape | 🟡 MEDIUM | 4 | ✅ | 25.7s |
| openfda | 🟡 MEDIUM | 4 | ✅ | 29.1s |
| tamarind | 🟡 MEDIUM | 13 | ✅ | 36.2s |
| autodock-vina | 🔵 LOW | 1 | ✅ | 16.3s |
| admet-prediction | 🔵 LOW | 1 | ✅ | 16.6s |
| chembl | 🔵 LOW | 2 | ✅ | 22.4s |
| antibody-engineering | 🔵 LOW | 2 | ✅ | 23.0s |
| chemical-space | 🔵 LOW | 2 | ✅ | 23.7s |
| adaptyv | 🔵 LOW | 4 | ✅ | 28.4s |
| boltz | 🔵 LOW | 4 | ✅ | 31.6s |
| datamol | 🔵 LOW | 3 | ✅ | 22.1s |
| degraders | 🔵 LOW | 1 | ✅ | 17.5s |
| clinicaltrials | 🔵 LOW | 3 | ✅ | 27.2s |
| depmap | 🔵 LOW | 2 | ✅ | 20.1s |
| deepchem | 🔵 LOW | 3 | ✅ | 27.6s |
| diffdock | 🔵 LOW | 2 | ✅ | 20.5s |
| free-energy-perturbation | 🔵 LOW | 2 | ✅ | 19.8s |
| generative-design | 🔵 LOW | 2 | ✅ | 20.1s |
| molecular-dynamics | 🔵 LOW | 2 | ✅ | 17.4s |
| glycoengineering | 🔵 LOW | 4 | ✅ | 25.2s |
| immunogenicity | 🔵 LOW | 2 | ✅ | 22.9s |
| molfeat | 🔵 LOW | 3 | ✅ | 22.0s |
| medchem | 🔵 LOW | 3 | ✅ | 23.3s |
| esm | 🔵 LOW | 4 | ✅ | 41.1s |
| ncats-arax | 🔵 LOW | 4 | ✅ | 26.5s |
| primekg | 🔵 LOW | 2 | ✅ | 17.5s |
| open-targets | 🔵 LOW | 2 | ✅ | 25.4s |
| pkpd-translation | 🔵 LOW | 2 | ✅ | 22.3s |
| oligonucleotides | 🔵 LOW | 3 | ✅ | 31.8s |
| protein-binder-design | 🔵 LOW | 2 | ✅ | 22.5s |
| retrosynthesis | 🔵 LOW | 2 | ✅ | 15.9s |
| rdkit | 🔵 LOW | 2 | ✅ | 22.5s |
| pytdc | 🔵 LOW | 2 | ✅ | 29.0s |
| target-safety | 🔵 LOW | 2 | ✅ | 18.2s |
| rowan | 🔵 LOW | 4 | ✅ | 25.2s |
| uniprot-rcsb | 🔵 LOW | 2 | ✅ | 25.2s |
| binding-site-analysis | 🟢 SAFE | 0 | ✅ | 15.2s |

## Detailed Findings

### patent-landscape — 🟡 MEDIUM

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Documented multi-gigabyte bulk downloads
  > The skill instructs downloading SureChEMBL bulk Parquet tables totalling roughly 15 GB via curl. This is disk/bandwidth intensive, but the skill explicitly warns about size, provides a `plan` command to minimise downloads, and prints (rather than executes) the curl commands, so the user retains control. Informational only.
  > **Remediation:** No change required; the skill already prints commands instead of running them and warns about disk usage. Optionally require explicit user confirmation before any automated download.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Explicit trigger-keyword list in description
  > The frontmatter description ends with 'Also trigger on SureChEMBL, patent chemistry, Markush structure, freedom to operate, composition of matter, assignee, priority date, patent family, or PatentsView.' This is activation-keyword seeding. The keywords are all genuinely within the skill's stated domain and there is no brand impersonation or over-broad 'general assistant' claim, so activation-abuse risk is minimal.
  > File: `SKILL.md`
  > **Remediation:** Optional: describe the capability in prose rather than enumerating trigger keywords.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — API endpoint overridable via environment variable while API key is attached
  > `_common.py` allows the PatentsView base URL (and the SureChEMBL FTP base) to be overridden through the `PATENTSVIEW_URL` / `SURECHEMBL_FTP` environment variables. `patent_search.py` then sends the user's `PATENTSVIEW_API_KEY` in the `X-Api-Key` header to whatever host that variable points at. In a compromised or shared environment this could silently redirect the credential to an attacker-controlled endpoint. This is a common configurability pattern and low risk in practice, but no scheme/host allow-listing is performed.
  > File: `scripts/_common.py`
  > **Remediation:** Validate that the resolved base URL uses HTTPS and matches an expected host allow-list (search.patentsview.org, ftp.ebi.ac.uk) before attaching credentials, or refuse to send the key to non-default hosts.

- **🟡 MEDIUM** `BEHAVIOR_ENV_VAR_HARVESTING` — Environment variable harvesting detected
  > Script iterates through environment variables in skills/patent-landscape/scripts/_common.py
  > File: `skills/patent-landscape/scripts/_common.py`
  > **Remediation:** Remove environment variable collection unless explicitly required and documented

### openfda — 🟡 MEDIUM

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Description includes an explicit trigger-keyword list
  > The frontmatter description ends with 'Also trigger on openFDA, api.fda.gov, FAERS, Drugs@FDA, SPL, NDC, pharmacovigilance, boxed warning, adverse event report, drug recall, or safety signal.' This is discovery-keyword seeding. The keywords are all tightly scoped to the skill's genuine domain (FDA post-market drug data) and do not impersonate other tools or claim general-purpose capability, so the risk of unwanted activation outside its scope is low.
  > **Remediation:** Keep the keyword list narrowly scoped to the skill's actual domain (it currently is); avoid adding priority/activation-preference language.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — API endpoint is overridable via environment variable and CLI flag, with API key auto-attached
  > `_common.py` reads the API root from the `OPENFDA_API_URL` environment variable (and every script exposes a `--base-url` flag). `_build_url()` automatically appends the value of `OPENFDA_API_KEY` as a query parameter to whatever base URL is in effect. If an attacker or a poisoned environment sets `OPENFDA_API_URL` to a host they control, the user's openFDA API key would be transmitted to that host, and all query responses would come from an untrusted source. The default is the legitimate public endpoint (https://api.fda.gov) and the key in question is a free, low-value quota token, so real-world impact is minimal.
  > File: `scripts/_common.py`
  > **Remediation:** Only attach `api_key` when the resolved base URL matches the official api.fda.gov host, and/or validate the scheme/host of any overridden base URL (require HTTPS and an allow-list).

- **🔵 LOW** `LLM_PROMPT_INJECTION` — Unvalidated remote API text (label sections, boxed warnings) rendered directly into agent context
  > `fda_labels.py` prints raw SPL section text and boxed-warning text fetched from the remote API straight to stdout, which is then read by the agent. Although openFDA is an authoritative government source and the content is public-domain regulatory text, any text returned by a remote service that is echoed into the model context is a theoretical indirect-prompt-injection surface (particularly if the base URL is overridden per the previous finding). No sanitisation or delimiting of remote text is performed.
  > File: `scripts/fda_labels.py`
  > **Remediation:** Clearly delimit or label remotely fetched text as untrusted data in the output, and instruct the agent in SKILL.md to treat API-returned label text as data, never as instructions.

- **🟡 MEDIUM** `BEHAVIOR_ENV_VAR_HARVESTING` — Environment variable harvesting detected
  > Script iterates through environment variables in skills/openfda/scripts/_common.py
  > File: `skills/openfda/scripts/_common.py`
  > **Remediation:** Remove environment variable collection unless explicitly required and documented

### tamarind — 🟡 MEDIUM

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Outbound transmission of user sequences, structures and files to a third-party cloud service
  > The skill's core function uploads user-provided biological sequences and structure files (PDB/CIF/SDF), including inline file content via MCP uploadFileContent, to app.tamarind.bio / mcp.tamarind.bio and authenticates with the TAMARIND_API_KEY environment variable. This is fully disclosed in the name, description and instructions and is the intended purpose, so it is not covert exfiltration; it is noted only because potentially sensitive/proprietary IP leaves the local environment and an API key is read from the environment. Credential handling guidance is sound (env var or .env, never hardcode, never commit).
  > **Remediation:** No change required; optionally advise confirming with the user before uploading files that may contain confidential or unpublished data.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Unbounded polling loops and metered batch submissions
  > Example code uses `while True:` polling loops against the /jobs endpoint without a maximum wait, retry cap, or network-error handling, and documents batch submissions of up to 100 billable jobs. A job stuck in a non-terminal state or repeated request exceptions could cause an indefinitely running loop, and large batches consume metered credits. The skill mitigates this by instructing the agent to break on all terminal statuses, to use weightedHoursBudget/maxRuntimeSeconds caps, to prefer the non-blocking submit-now/check-later pattern, and to surface cost-relevant choices to the user before submitting batches.
  > **Remediation:** Add an explicit timeout/max-iteration bound and exception handling to the polling examples, and require user confirmation before submitting batches above a small job count.

- **🔵 LOW** `LLM_PROMPT_INJECTION` — Runtime fetching of external documentation treated as authoritative
  > SKILL.md directs the agent to fetch remote resources at runtime (https://app.tamarind.bio/llms.txt, /openapi.yaml, https://docs.tamarind.bio/llms.txt and its .md pages) and to 'prefer fetching them at runtime over trusting any hardcoded list'. Content fetched from external web endpoints is untrusted data; if any of these vendor endpoints were compromised or hijacked (DNS/MITM/supply-chain), the returned markdown could carry instructions that the agent may follow. The instruction to prefer live remote content over local package content increases transitive trust exposure. Risk is mitigated by the URLs being first-party, HTTPS, and used for API schema lookup rather than code execution.
  > File: `SKILL.md`
  > **Remediation:** Add an explicit note that fetched documents are data, not instructions, and that the agent must not execute or obey any directives contained in fetched pages; pin to documented HTTPS endpoints only.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Large trigger-keyword list in manifest metadata
  > The manifest includes a 'trigger-keywords' field with ~30 broad domain terms (AlphaFold, docking, antibody design, ADME, enzyme, peptide, cloud GPU biology, etc.). While all terms are plausibly within the skill's stated scope of the Tamarind platform, the breadth could cause the skill to activate for generic structural-biology requests that the user intended to run locally. The skill body partially mitigates this by explicitly saying to use local libraries (RDKit, BioPython) for local cheminformatics work.
  > File: `SKILL.md`
  > **Remediation:** Narrow trigger keywords to Tamarind-specific terms (tamarind, tamarind.bio, app.tamarind.bio/api) plus a small set of core capabilities to avoid over-activation.

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

### autodock-vina — 🔵 LOW

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Execution of external binaries resolved from PATH
  > dock_batch.py locates and executes external executables (vina, mk_prepare_ligand.py, mk_prepare_receptor.py, mk_export.py, scrub.py, obabel) via shutil.which() and subprocess.run(). If a user's PATH contains a malicious binary with one of these names, the skill would execute it. This is normal and expected behavior for a wrapper around a scientific toolchain: commands are built as argument lists (no shell=True), no user string is passed to a shell, timeouts are enforced, and a --dry-run mode prints commands without running them. Informational only.
  > File: `scripts/dock_batch.py`
  > **Remediation:** No change required. Optionally document that the skill executes whichever vina/Meeko binaries are first on PATH, and recommend running within a dedicated conda environment.

### admet-prediction — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instruction
  > Documentation instructs the user to run `pip install admet-ai` without a pinned version (the SKILL.md mentions 'admet-ai 2.0+'). The package also downloads model weights from the network on first use. This is standard practice for scientific tooling and the referenced repository (swansonk14/admet_ai) is a well-known MIT-licensed project, but unpinned installs plus remote weight download introduce a minor supply-chain consideration.
  > File: `references/running-admet-ai.md`
  > **Remediation:** Pin an exact version (e.g., `pip install admet-ai==2.0.1`) and document the expected model weight source/checksums.

### chembl — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — User-overridable API base URL allows requests to arbitrary hosts
  > All scripts expose a `--base-url` argument that replaces the hard-coded EBI endpoint. If an agent is induced (e.g., by untrusted text in a user prompt or a document) to pass an attacker-controlled base URL, query parameters and results would be routed to that host. This is a standard convenience flag and no default behaviour is malicious \u2014 the default is the legitimate https://www.ebi.ac.uk/chembl/api/data \u2014 so risk is minimal, but it is the only outbound-network control surface in the package.
  > **Remediation:** Optionally validate that a supplied base URL resolves to an allow-listed host (e.g., www.ebi.ac.uk) or warn the user when a non-default endpoint is used.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Documentation references files that are not present in some expected paths
  > The instructions reference references/api-reference.md, references/data-curation.md and references/entity-fields.md, all of which are bundled and benign. Scanner-reported paths under templates/ and assets/ do not exist; this is a documentation/packaging artifact rather than a security issue. No external URLs are fetched and executed, and the bundled reference files contain only descriptive ChEMBL documentation with no embedded instructions to the agent.
  > File: `SKILL.md`
  > **Remediation:** No action required for security; ensure all referenced paths exist in the packaged skill.

### antibody-engineering — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Activation keyword list appended to description
  > The YAML description ends with an explicit trigger-keyword list ('Also trigger on antibody, nanobody, VHH, scFv, Fab, CDR, framework, ANARCI, abnumber, IgBLAST, OAS, SAbDab, humanization, Vernier residues, or developability'). This is a discovery-optimisation pattern that can broaden activation. In this case every keyword is tightly scoped to the skill's genuine antibody-engineering domain and none impersonate other tools or brands, so the practical risk is minimal and this is informational only.
  > **Remediation:** Optional: trim the explicit trigger list to a natural-language description of when the skill applies, to avoid over-activation on generic terms such as 'framework'.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Referenced documentation paths partially unresolved
  > The analysis harness lists several referenced markdown files under templates/ and assets/ that do not exist in the package (e.g., templates/tools.md, assets/developability.md). The SKILL.md body only links to files under references/, all four of which are present and contain benign technical documentation. The missing paths appear to be scan artefacts rather than skill behaviour and create no exploitable condition, but unresolved references could allow a later-added file to be silently picked up.
  > File: `references/numbering-schemes.md`
  > **Remediation:** Keep reference links restricted to files actually bundled in the package and verify at load time that referenced paths resolve inside the skill directory.

### chemical-space — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list appended to the skill description
  > The frontmatter description ends with an explicit activation keyword list ('Also trigger on ZINC22, CartBlanche, Enamine REAL, make-on-demand, tangible library, synthon, tranche, giga-scale enumeration, or ultra-large virtual screening'). This is discovery-surface tuning, but all listed terms are tightly scoped to the skill's genuine domain (purchasable chemical space / ultra-large virtual screening), so there is no capability inflation or brand impersonation. Informational only.
  > **Remediation:** Optional: describe capabilities in prose rather than an explicit trigger-word list to avoid over-activation on tangentially related queries.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — API base URL overridable via environment variable and CLI flag
  > The transport layer resolves the service root from the CARTBLANCHE_URL environment variable (and a --base-url flag) without validation or scheme/host allow-listing. If an attacker can influence the environment or arguments, ZINC identifier lookups could be redirected to an attacker-controlled host, and the get_json helper also accepts fully-qualified paths beginning with 'http'. Impact is limited because the only data transmitted is public ZINC identifiers and no credentials or tokens are attached to requests.
  > File: `scripts/_common.py`
  > **Remediation:** Validate the configured base URL against an allow-list of known docking.org hosts and require HTTPS; reject absolute URLs passed through the path parameter.

### adaptyv — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Instruction to locate and load project .env files
  > The skill instructs the agent to check the project root for a `.env` file and load it to obtain the API token. While this is a common and generally safe credential-handling practice (and the skill explicitly forbids hardcoding or committing tokens), it does direct the agent to read files that commonly contain unrelated secrets, which could surface those secrets in the conversation context.
  > **Remediation:** Scope the guidance to reading only the `ADAPTYV_API_KEY` variable and instruct the agent never to echo or log the contents of `.env` files.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Documented automation pattern that bypasses human review of billing commitments
  > The skill documents an 'Automated Pipeline' example that sets `skip_draft: True` and `auto_accept_quote: True`, which bypasses the Draft state and automatically accepts a vendor quote and creates a Stripe invoice. If an agent copies this pattern verbatim, the user could incur real financial charges without explicit confirmation. This is a legitimate upstream API feature, but the skill presents it without a caution to confirm with the user first.
  > **Remediation:** Add an explicit instruction that the agent must obtain user confirmation before using `auto_accept_quote`/`skip_draft`, since these create binding financial commitments.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installed directly from GitHub
  > The skill instructs the agent to install the `adaptyv-sdk` package directly from a GitHub repository without pinning a commit, tag, or version (`uv pip install "git+https://github.com/adaptyvbio/adaptyv-sdk.git"`). Any change to the default branch of that repository (including a compromise of the upstream account) would be executed on the user's machine at install time. The repository appears to be the legitimate vendor org and the package is documented as not yet on PyPI, so the risk is limited, but provenance is unverified.
  > **Remediation:** Pin the install to a specific tag or commit hash (e.g., `git+https://github.com/adaptyvbio/adaptyv-sdk.git@<commit-sha>`) and advise the user to review the repository before installation.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Referenced files declared but absent from package
  > The skill's file references include `templates/api-endpoints.md`, `assets/api-endpoints.md`, and `adaptyv.py`, none of which exist in the package. Only `references/api-endpoints.md` is present and its content is benign API documentation. Missing referenced files are a documentation-hygiene issue and could lead to the agent attempting to resolve paths outside the package.
  > File: `references/api-endpoints.md`
  > **Remediation:** Remove references to non-existent files or bundle them with the skill package.

### boltz — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list appended to the skill description
  > The frontmatter description ends with an explicit activation keyword list ("Also trigger on Boltz, Boltz-1, Boltz-2, cofolding, boltz predict, affinity_pred_value, affinity_probability_binary, ipTM, or open-weights AlphaFold3 alternatives."). This is discovery-surface tuning. All terms are tightly scoped to the skill's genuine domain (Boltz cofolding and affinity prediction) and there are no over-broad claims such as "general assistant" or "use me first", so this is informational rather than abusive.
  > **Remediation:** Keep the keyword list limited to domain-specific terms (as it currently is) and avoid adding generic or priority-elevating phrasing.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Referenced documentation paths partially unresolved
  > The scanner resolved several candidate reference paths; only `references/yaml-schema.md`, `references/confidence-and-affinity.md`, and `references/running.md` exist, while `assets/*` and `templates/*` variants were not found. The three files actually linked from SKILL.md all exist and contain benign, on-topic documentation. The unresolved paths appear to be scanner path-permutation artifacts rather than missing skill content, and no external URLs are loaded as instructions.
  > File: `references/confidence-and-affinity.md`
  > **Remediation:** No action needed; ensure all linked reference files remain bundled inside the skill package.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Workflow sends biological sequences to a third-party public server (disclosed)
  > The recommended default workflow uses `boltz predict --use_msa_server`, which transmits the user's protein sequences to the public ColabFold MSA server, an external third party. This is an outbound data flow of potentially proprietary/unpublished sequence data. The skill discloses this clearly and repeatedly (in the manifest `compatibility` field, in SKILL.md, in references/running.md, and via a runtime stderr warning in make_boltz_yaml.py advising against use for confidential sequences), and offers precomputed-MSA and single-sequence alternatives. No covert exfiltration occurs: none of the bundled scripts perform any network I/O.
  > File: `references/running.md`
  > **Remediation:** No change strictly required given the explicit disclosures; optionally make `--msa-path`/`--no-msa` the documented default for sensitive targets and mention self-hosting via `--msa_server_url`.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency install and direct GitHub install instruction
  > The reference documentation instructs installing the `boltz` package without a pinned version (`pip install boltz`) and also offers a direct install from a GitHub repository (`pip install git+https://github.com/jwohlwend/boltz.git`). Unpinned/VCS installs pull whatever code is at HEAD at install time, which weakens supply-chain reproducibility and integrity. The repository referenced is the legitimate upstream Boltz project and no typosquatting indicators were found, so real-world risk is low.
  > File: `references/running.md`
  > **Remediation:** Pin an explicit version (e.g. `pip install boltz==2.2.1`) and prefer PyPI releases over `git+https` installs; note a commit hash if the development branch must be used.

### datamol — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Documentation references cloud credential environment variables
  > Reference material describes that fsspec backends read provider credentials from environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, GOOGLE_APPLICATION_CREDENTIALS). This is informational and the docs explicitly state that credentials are used locally by fsspec and are not collected or transmitted to third-party endpoints, and instruct scoping access to only the named provider variables. No code reads, harvests, or transmits credentials. Flagged only as an awareness item since remote read/write paths (s3://, https://) can move local data off-host if a user supplies an attacker-controlled URL.
  > **Remediation:** Keep the existing guidance requiring explicit user confirmation for any remote write destination, and add validation/allow-listing of remote URLs supplied by untrusted sources.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned package installation instructions
  > SKILL.md instructs the user/agent to run `uv pip install datamol`, `uv pip install s3fs`, and `uv pip install gcsfs` without any version pinning or integrity verification. This is standard practice for documentation skills, but unpinned installs leave a small supply-chain exposure window (dependency confusion / malicious release). No direct GitHub installs or typosquatted names were observed — all packages are well-known, legitimate PyPI projects.
  > File: `SKILL.md`
  > **Remediation:** Pin versions (e.g., `uv pip install datamol==0.12.5`) or document a lockfile/hash-verified install path, and prompt the user before installing packages.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Missing referenced files listed in extraction (assets/ and templates/ variants)
  > The extraction lists several referenced paths that do not exist in the package (assets/*.md, templates/*.md, datamol.py, sklearn.py). These appear to be path-resolution artifacts of the reference scanner rather than real dependencies — SKILL.md only points to references/*.md, all of which are present and benign. SKILL.md also explicitly clarifies that scipy/scikit-learn are PyPI packages and not bundled scripts, reducing the risk of accidental local-module shadowing.
  > File: `references/core_workflows.md`
  > **Remediation:** No action strictly required; ensure only existing references/*.md paths are cited so automated scanners do not resolve phantom module-like paths (datamol.py, sklearn.py).

### degraders — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Explicit activation keyword list in description
  > The YAML description ends with an explicit trigger list ("Also trigger on PROTAC, molecular glue, targeted protein degradation, E3 ligase, cereblon, VHL, ternary complex, DC50, Dmax, hook effect, cooperativity, or PROTAC-DB"). This is a discovery/activation-priority hint. All listed terms are tightly scoped to the skill's stated chemistry domain and there are no over-broad claims (e.g., 'general assistant', 'use me first'), so the risk of unwanted activation or capability inflation is minimal. Noted for completeness only.
  > **Remediation:** Optional: rely on a natural-language description of capabilities rather than an explicit keyword trigger list, to avoid over-activation in unrelated contexts.

### clinicaltrials — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list appended to the skill description
  > The description ends with an explicit activation-keyword list ('Also trigger on ClinicalTrials.gov, NCT number, trial registry, study phase, enrolment, primary outcome measure, recruiting status, trial sponsor, or competitive landscape'). This is discovery-surface tuning that can broaden activation beyond narrowly relevant requests. The keywords are all genuinely in-domain for this skill, so impact is minimal and no brand impersonation or over-broad 'do anything' claims are present.
  > **Remediation:** Describe capabilities functionally rather than embedding an explicit trigger-keyword list.

- **🔵 LOW** `LLM_PROMPT_INJECTION` — Unvalidated external registry free text is rendered into agent context
  > The scripts fetch sponsor-submitted free-text fields from ClinicalTrials.gov (whyStopped, eligibilityCriteria, outcome descriptions, brief titles) and print them directly to stdout/stderr, where they enter the agent's context. SKILL.md further instructs the agent to 'quote whyStopped verbatim'. Registry content is explicitly noted as unverified and sponsor-submitted, so a crafted record could contain instruction-like text that the agent may interpret. Risk is low because the data source is an official NLM public registry and the output is tabular, but it remains an untrusted-external-data ingestion path.
  > File: `SKILL.md`
  > **Remediation:** Treat all fetched registry text as untrusted data; delimit/neutralize it in output and add a note in SKILL.md that registry free text must never be interpreted as instructions.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — API endpoint fully overridable via environment variable and CLI flag
  > The API root is taken from the CTGOV_API_URL environment variable and can also be overridden with --base-url. In addition, _build_url returns any path that already begins with http:// or https:// unchanged. If an attacker or a poisoned environment sets CTGOV_API_URL, the queries (and any resulting agent workflow) could be silently redirected to an attacker-controlled host, which would also serve attacker-controlled content back into the agent context. No credentials are transmitted, so exposure is limited to query terms.
  > File: `scripts/_common.py`
  > **Remediation:** Restrict the effective base URL to an allowlist (e.g. https://clinicaltrials.gov), require HTTPS, and log/warn loudly when a non-default endpoint is used.

### depmap — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Example code downloads remote data files without integrity verification
  > The SKILL.md provides a helper (`download_depmap_data`) that performs an unauthenticated `requests.get` of a user-supplied URL and streams it directly to disk, with no TLS/hostname pinning beyond defaults, no checksum/hash verification, and no `raise_for_status()` check. The skill itself warns that the DepMap portal returns HTTP 200 with an HTML verification page, meaning corrupt or attacker-substituted content could be silently written to disk and later parsed as data. The URL placeholder ('https://figshare.com/ndownloader/files/...') also invites the agent or user to substitute an arbitrary URL. Impact is limited to writing a data file locally (no execution), so severity is low.
  > File: `SKILL.md`
  > **Remediation:** Add `response.raise_for_status()`, validate the Content-Type is not text/html, restrict downloads to an allowlist of official DepMap/Figshare hosts, and verify published SHA-256 checksums before parsing downloaded files.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Missing referenced files and a non-existent module import
  > The instructions/reference material point to files that are not present in the package (assets/dependency_analysis.md, templates/dependency_analysis.md, and an inferred 'scipy.py'), and references/dependency_analysis.md imports `from depmap_utils import load_cell_line_info`, a module that is not bundled with the skill. A missing local module name could in principle be satisfied by an attacker-planted file on the import path, and dangling references reduce reproducibility. No malicious content is present; this is a hygiene/quality issue.
  > File: `references/dependency_analysis.md`
  > **Remediation:** Bundle the referenced helper module (or inline the function), and remove or add the missing referenced files so all paths in the documentation resolve within the package.

### deepchem — 🔵 LOW

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Long-running training jobs with unbounded resource usage
  > The scripts launch model training loops (up to 50-100 epochs by default, `--epochs` user-controlled with no upper bound) and load large MoleculeNet datasets and transformer models. This can consume substantial CPU/GPU/memory and run for long periods. This is inherent and expected for an ML training skill rather than a deliberate abuse pattern, but there is no guardrail or user confirmation before starting a potentially very expensive run.
  > **Remediation:** Add sensible upper bounds or warnings for `--epochs`, support early stopping, and note expected runtime/resource footprint in the skill documentation.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned package installation and direct install from GitHub master
  > The SKILL.md instructions recommend installing dependencies without version pins (`uv pip install deepchem`, `uv pip install 'deepchem[torch]'`, `uv pip install --pre deepchem`) and explicitly suggest installing an untagged build directly from a GitHub repository (`pip install git+https://github.com/deepchem/deepchem.git`). Unpinned and untagged installs mean the code executed can change between runs and inherits whatever is currently on the upstream branch, which weakens supply-chain reproducibility. The repository is the well-known official DeepChem project, so the practical risk is low, but the guidance still encourages non-deterministic dependency resolution and pre-release/nightly builds.
  > File: `SKILL.md`
  > **Remediation:** Recommend pinned versions (e.g., `deepchem==2.8.0`) and, if a git install is truly needed, pin to a specific commit SHA or tag. Avoid recommending `--pre`/nightly builds for production use.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Automatic download of third-party pretrained model weights from remote hubs
  > The transfer_learning.py script instantiates `dc.models.HuggingFaceModel` with hard-coded remote model identifiers ('seyonec/ChemBERTa-zinc-base-v1', 'ibm/MoLFormer-XL-both-10pct'), which triggers network downloads of third-party model weights and tokenizers on first run. This is normal and expected behavior for a transfer-learning skill and is disclosed in the instructions ('This may take a while on the first run as the model is downloaded'), but it does constitute outbound network activity and execution of externally sourced model artifacts that is not reflected in the declared allowed-tools. No credentials, local files, or user data are transmitted.
  > File: `scripts/transfer_learning.py`
  > **Remediation:** Document the network egress requirement explicitly in the manifest/compatibility field, allow users to supply a local model path or offline cache directory, and pin model revisions/hashes where the hub supports it.

### diffdock — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned external dependency installation instructions
  > The SKILL.md instructs cloning the upstream DiffDock GitHub repository at HEAD and pulling a Docker image without a version tag/digest ('docker pull rbgcsail/diffdock', 'git clone https://github.com/gcorso/DiffDock.git'). It also suggests 'uv pip install fair-esm' with no version pin. These are well-known, reputable upstream sources, but the absence of pinning means the agent may fetch and execute arbitrary future upstream content, and model checkpoints (~500MB) are auto-downloaded from remote sources on first run. Risk is low because the sources are the canonical project repositories, but provenance is not verified.
  > File: `SKILL.md`
  > **Remediation:** Pin to a specific release tag or commit (e.g., DiffDock v1.1.3) and a Docker image digest; document expected checksums for downloaded model checkpoints.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced documentation files are missing from the package
  > The instructions and file-reference index point to paths such as assets/parameters_reference.md, templates/confidence_and_limitations.md, references/custom_inference_config.yaml and references/workflows_examples.md that are not present in the package (only references/parameters_reference.md, references/confidence_and_limitations.md and assets/custom_inference_config.yaml exist). Broken internal references are a documentation-quality issue; they could also cause the agent to search elsewhere for a similarly named file. No malicious content observed.
  > File: `references/confidence_and_limitations.md`
  > **Remediation:** Correct the referenced paths to match the actual package layout and ship all files that the instructions ask the agent to read.

### free-energy-perturbation — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Activation keyword list in description
  > The YAML description ends with an explicit trigger-keyword list ("Also trigger on OpenFE, alchemical transformation, thermodynamic cycle, RBFE, ABFE, SepTop, lambda window, MBAR, cycle closure, or perturbation map."). This is a discovery-optimisation pattern that can broaden activation. In this case all keywords are tightly scoped to the skill's actual domain (alchemical free energy calculations), the claims match the bundled scripts, and there is no brand impersonation or over-broad "general assistant" claim, so the risk is informational only.
  > **Remediation:** Optionally trim the explicit trigger list to a natural-language description of scope; no functional change required.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Missing referenced files under assets/ and templates/ paths
  > Several referenced file paths (assets/interpreting-fep.md, templates/interpreting-fep.md, templates/openfe-setup.md, templates/network-design.md, assets/network-design.md, assets/openfe-setup.md) were not found in the package. The canonical references/ copies do exist and contain the referenced content, so this is a packaging/documentation inconsistency rather than a security issue; the only risk is that a missing file path could later be shadowed by unvetted content.
  > File: `references/interpreting-fep.md`
  > **Remediation:** Reference only the existing references/*.md paths and remove stale asset/template path variants.

### generative-design — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Referenced documentation files listed in instructions are missing from the package
  > Several referenced paths (assets/scoring-functions.md, templates/scoring-functions.md, assets/evaluating-generated-molecules.md, assets/reinvent-configuration.md, templates/*) were not found in the package. The three canonical references under references/ do exist and are benign. Missing referenced files are a documentation/packaging integrity issue; if resolved later from an unexpected location they could become a vector for injected content.
  > File: `references/evaluating-generated-molecules.md`
  > **Remediation:** Remove references to non-existent files or ship the missing documents inside the skill package so all referenced content is bundled and auditable.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned installation from GitHub source repository
  > The SKILL.md body and references/reinvent-configuration.md instruct the user to install REINVENT 4 directly from a GitHub repository with `git clone` followed by `pip install -e .`, without a pinned commit, tag, or checksum. While the repository (MolecularAI/REINVENT4) is a well-known legitimate AstraZeneca project, unpinned source installs are a supply-chain risk: the resolved code can change between runs. The skill's own scripts do not execute this install automatically, so the risk is informational rather than active.
  > File: `references/reinvent-configuration.md`
  > **Remediation:** Pin to a specific release tag or commit hash (e.g., `git clone --branch v4.8 --depth 1 ...`) and verify provenance before installing; state that the agent should ask for user confirmation before running installs.

### molecular-dynamics — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Description contains an explicit trigger-keyword list
  > The YAML description ends with 'Also trigger on OpenMM, MDAnalysis, mdtraj, Simulation.step, LangevinMiddleIntegrator, PDBFixer, DCD or XTC trajectory, RMSD analysis, or production MD.' This is an explicit activation-keyword list intended to increase skill invocation. All listed keywords are tightly scoped to the skill's genuine molecular-dynamics domain, there are no over-broad claims ('use me first', 'general assistant', brand impersonation), so the risk is informational only. Noted for completeness rather than as an actual abuse pattern.
  > **Remediation:** Optionally trim the explicit trigger list to a natural-language capability statement; no security action required.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced file paths do not exist in the package
  > The scanner resolved references to templates/mdanalysis_analysis.md, assets/mdanalysis_analysis.md, MDAnalysis.py, openmm.py, openff.py, matplotlib.py and pdbfixer.py, none of which exist in the package. Most of these are artifacts of Python import statements in documentation code blocks (e.g. 'import MDAnalysis as mda') rather than real file references; the only explicitly linked file, references/mdanalysis_analysis.md, is present and contains benign analysis documentation. No external URLs are fetched for instruction content, so there is no transitive-trust or indirect-injection exposure. Minor documentation hygiene issue only.
  > File: `SKILL.md`
  > **Remediation:** No action needed for security; ensure all genuinely linked resources are bundled with the package.

### glycoengineering — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Outbound network requests to third-party bioinformatics APIs
  > Several illustrative snippets perform HTTP requests to external services (GlyConnect at glyconnect.expasy.org, GlyTouCan API, DTU Health Tech webface CGI) using user-supplied identifiers or FASTA sequences. These are well-known, reputable scientific resources and the behavior is disclosed in the description/compatibility fields, so the risk is limited; however, submitting proprietary or unpublished protein sequences to third-party web services constitutes outbound data flow that the user should explicitly approve. No credentials, environment variables, or local filesystem data are collected or transmitted.
  > **Remediation:** Add an explicit notice that sequences submitted to external predictors/databases leave the local machine, and require user confirmation before any network submission of sequence data.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list embedded in skill description
  > The description ends with an explicit activation keyword list ('Also trigger on N-glycosylation, sequon, NXS/NXT, O-glycosylation, glycoform heterogeneity, afucosylation, high-mannose, GlyTouCan, or WURCS'). This is a discovery-optimization pattern; however, all keywords are narrowly scoped to the skill's genuine glycobiology domain and there is no brand impersonation or over-broad 'general assistant' claim, so activation-abuse risk is minimal.
  > **Remediation:** Optionally trim the explicit trigger-keyword list to a natural-language description of scope; no action strictly required as the keywords match actual functionality.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned package installation via uv pip install
  > The SKILL.md instructs installing the optional 'glycoshield' package with `uv pip install glycoshield` without any version pin or hash verification. If executed by the agent via the declared Bash tool, this pulls an unpinned dependency from PyPI, exposing the user to supply-chain risk (malicious release, dependency confusion, or typosquatting of a relatively obscure package name).
  > File: `SKILL.md`
  > **Remediation:** Pin the exact version (e.g., `uv pip install glycoshield==<version>`) and ideally require hash verification or a lockfile; state clearly that installation requires explicit user confirmation.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Two referenced resource paths do not exist in the package
  > The instruction/reference scan resolves references to templates/glycan_databases.md and assets/glycan_databases.md, which are not present in the package (only references/glycan_databases.md exists). Missing internal resources can cause the agent to search elsewhere or fabricate content, but no malicious behavior is indicated.
  > File: `references/glycan_databases.md`
  > **Remediation:** Ensure all referenced paths resolve to files bundled inside the skill package, or remove stale references.

### immunogenicity — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger keyword list in description broadens activation surface
  > The YAML description ends with an explicit list of activation keywords ("Also trigger on immunogenicity, anti-drug antibody, ADA, T-cell epitope, MHC class II, HLA-DRB1, NetMHCIIpan, NetMHCpan, deimmunisation, tregitope, or population coverage"). This is a mild form of discovery/activation optimisation. All listed terms are, however, tightly scoped to the skill's actual domain (MHC class II epitope prediction and ADA risk triage), the claimed capabilities match the bundled scripts, and there is no brand impersonation or over-broad "general assistant" claim. Informational only.
  > **Remediation:** Optionally trim the explicit keyword enumeration and rely on a natural-language description of scope; no functional change required.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Several referenced documentation paths do not resolve
  > The discovery scan lists templates/*.md and assets/*.md variants of the three reference documents as not found. The three documents actually cited in SKILL.md (references/running-netmhciipan.md, references/deimmunisation.md, references/what-drives-ada.md) are all present and contain benign, domain-accurate scientific guidance with no embedded instructions to the agent, no external URLs to fetch and obey, and no code to execute. The missing paths therefore appear to be scanner path-expansion artefacts rather than genuine broken references, but they are noted for completeness.
  > File: `references/running-netmhciipan.md`
  > **Remediation:** Confirm that all documentation lives under references/ and that no templates/ or assets/ directory is expected at runtime.

### molfeat — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-dense description for discovery triggering
  > The YAML description ends with an explicit trigger list ('Also trigger on molfeat, MoleculeTransformer, FPVecTransformer, PretrainedHFTransformer, molfeat model store, or featurizer selection'). This is a mild discovery-optimization pattern. However all listed keywords are tightly scoped to the skill's actual, narrow domain (molecular featurization), so there is no meaningful capability inflation or brand impersonation.
  > **Remediation:** Acceptable as-is; keep trigger keywords limited to terms that genuinely match the skill's scope.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Installation of third-party packages and remote model artifacts
  > The skill instructs the agent to install Python packages via `uv pip install` and to download pretrained model weights from the HuggingFace Hub and the molfeat model store (https://fs.molfeat.datamol.io/artifacts/). While versions are explicitly pinned (molfeat==0.11.0) and the sources are well-known, official ecosystem endpoints, executing package installation and loading remote serialized models inherently introduces supply-chain exposure (arbitrary code execution at install/load time). It also links to an external GitHub repo (reymond-group/map4) for the optional MAP4 featurizer.
  > **Remediation:** No change strictly required; versions are pinned and sources are reputable. Optionally run installs in an isolated virtual environment (already recommended) and verify model checksums (molfeat's store already performs sha256 verification).

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Referenced files not present in package (missing resources)
  > The instruction body and file scan reference several paths that do not exist in the package (templates/*.md, assets/*.md, molfeat.py, datamol.py). These appear to be false-positive resolutions of inline code identifiers (e.g., `molfeat.py` from module names) rather than intentional references. No dangling external fetches are specified, so the risk is limited to documentation confusion; however, missing referenced paths could later be shadowed by attacker-created files in the working directory.
  > File: `references/api_reference.md`
  > **Remediation:** Ensure only existing in-package files are referenced; avoid ambiguous bare filenames that could be resolved against the current working directory.

### medchem — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Activation keyword stuffing in skill description
  > The YAML description ends with an explicit activation-baiting clause: "Also trigger on medchem, `import medchem as mc`, RuleFilters, NIBRFilters, CommonAlertsFilters, NamedCatalogs, QueryFilter, PAINS filtering, or structural alerts." This is a discovery-manipulation pattern intended to widen activation. In this case the keywords are all tightly scoped to the genuine medicinal-chemistry domain of the skill and there is no brand impersonation or over-broad general-assistant claim, so the impact is informational only.
  > **Remediation:** Describe the skill's function rather than enumerating trigger keywords; rely on the assistant's semantic matching for discovery.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instructions
  > The skill instructs installation of packages without version pins (`uv pip install medchem datamol` and `mamba install -c conda-forge lilly-medchem-rules`). Unpinned installs from public registries expose the environment to future malicious releases or dependency-confusion issues. The packages named are legitimate, well-known, correctly spelled projects (datamol-io/medchem), so risk is low.
  > **Remediation:** Pin explicit versions consistent with the documented target (e.g., `medchem==2.0.5`) and prefer a lockfile or hash-verified requirements file.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — References to non-existent files in the package
  > The instruction/reference set enumerates several files that are not present in the package (templates/api_guide.md, assets/api_guide.md, templates/rules_catalog.md, assets/rules_catalog.md, datamol.py, medchem.py). Missing referenced paths can cause the agent to attempt reads that fail, or in a shared workspace could be satisfied by an unrelated/attacker-placed file of the same name. The two files actually cited in the SKILL.md Resources section (references/api_guide.md and references/rules_catalog.md) do exist and contain only benign API documentation.
  > File: `references/rules_catalog.md`
  > **Remediation:** Ensure every referenced path is bundled in the package and remove stale or ambiguous references (bare module names like datamol.py/medchem.py).

### esm — 🔵 LOW

- **🔵 LOW** `LLM_COMMAND_INJECTION` — Example code deserializes pickle files from disk
  > Several reference examples implement caching/checkpointing using `pickle.load()` on files read from the working directory (`checkpoint.pkl`, `forge_cache/*.pkl`, `embeddings_cache.pkl`). Python pickle deserialization executes arbitrary code by design; if an attacker (or another process/user) can write to those cache paths, running the example results in arbitrary code execution. This is a common pattern in ML docs and is not evidence of malicious intent, but it is an insecure-by-default example the agent may copy verbatim.
  > **Remediation:** Use a safe serialization format (JSON, npz, safetensors) for cached embeddings/results, or validate cache file integrity/ownership before unpickling, and add a warning that pickle files must be treated as trusted code.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Instructs agent to read a local .env file for API credentials
  > The Authentication section directs the agent to fall back to reading a local `.env` file when `ESM_API_KEY` is not in the environment. Reading dotenv files is a credential-access pattern. The risk is materially reduced here because the instruction is explicitly scoped ('for ESM_API_KEY only (do not load unrelated secrets)'), the skill forbids hardcoding or committing tokens, and the token is only ever sent to fixed, trusted hosts (forge.evolutionaryscale.ai / biohub.ai) with an explicit warning not to take API hosts from untrusted input. No exfiltration path exists.
  > **Remediation:** No change strictly required. Optionally add an instruction to never echo or log the key value and to avoid printing the contents of `.env` to the conversation.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Broad trigger keyword list in skill description
  > The frontmatter description ends with an explicit activation keyword list ('Also trigger on esm, ESM3, ESMC, ESM Cambrian, ESMFold2, `from esm.models`, ESMProtein, GenerationConfig, forge.evolutionaryscale.ai, biohub.ai, or ESM_API_KEY'). This is discovery/activation tuning. The terms are narrowly domain-specific and match the skill's actual documented functionality, so this is informational rather than capability inflation, but the inclusion of the secret name `ESM_API_KEY` as a trigger could cause the skill to activate in contexts where credentials are being discussed.
  > **Remediation:** Optional: trim the trigger list to capability-descriptive terms and remove the environment-variable/secret name from activation keywords.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Recommends installing package from a GitHub repository that is not the canonical upstream
  > The Biohub reference instructs installation of the `esm` package directly from `https://github.com/Biohub/esm.git`. The canonical upstream for the EvolutionaryScale ESM SDK is `evolutionaryscale/esm`; the `Biohub/esm` organization/repository is asserted without provenance verification. Installing from an unverified GitHub organization is a supply-chain risk (potential repo-squatting / account takeover). The skill does mitigate this substantially by explicitly instructing the user to pin a full 40-character commit SHA or trusted release and to review it before installing, and by pinning the PyPI release (`esm==3.2.3`), so the residual risk is low.
  > File: `references/biohub-platform.md`
  > **Remediation:** Verify and document the canonical upstream repository (e.g., github.com/evolutionaryscale/esm) and prefer the pinned PyPI release. Keep the existing requirement for a full commit SHA and add a note to verify repository ownership/signatures before any git-based install.

### ncats-arax — 🔵 LOW

- **🔵 LOW** `LLM_COMMAND_INJECTION` — Provider identifiers interpolated into ARAXi action strings
  > The query contract states that user-supplied provider identifiers (`--kp`) are interpolated into an ARAXi DSL action sent to the remote ARAX service. String interpolation of user input into a remote DSL is an injection surface. The contract mitigates this with a strict allowlist regex (`^infores:[A-Za-z0-9._-]+$`), duplicate rejection, and a 2-5 provider cap, which appears adequate; the risk is residual and depends on the (absent) implementation actually enforcing the documented regex.
  > **Remediation:** Ensure the implementation enforces the documented allowlist regex before interpolation and prefer structured/parameterized construction of the ARAXi action over string concatenation.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Outbound transmission of user query terms to a third-party public service
  > The skill sends biomedical entity names and CURIEs to the external production endpoint https://arax.transltr.io. This is the skill's stated purpose and is clearly disclosed. The manifest and instructions explicitly require an `--acknowledge-public-query` flag, warn that query and caller metadata may be publicly visible, prohibit patient or confidential data, and forbid placing user/project names in the submitter or User-Agent headers. No credentials, environment variables, or local files are collected or transmitted. Informational only.
  > File: `SKILL.md`
  > **Remediation:** No action required; retain the explicit public-query acknowledgment and the prohibition on sensitive content.

- **🔵 LOW** `LLM_COMMAND_INJECTION` — Referenced client script not present in package; documented behavior cannot be verified
  > SKILL.md instructs the agent to execute `python skills/ncats-arax/scripts/arax_client.py` for preflight, normalize, one-hop, two-hop, and summarize commands, but no script files are included in the analyzed package. All safety controls described (URL allowlisting, CURIE/provider regex validation, response size limits, no-retry-on-POST, redirect restrictions) are therefore documentation-only and unverifiable. If the script is supplied later from an unverified source, the actual behavior could diverge from the documented, tightly bounded contract.
  > File: `scripts/arax_client.py`
  > **Remediation:** Ship the referenced `scripts/arax_client.py` inside the skill package so its network, file-write, and input-validation behavior can be audited, or remove the execution instructions until the script is bundled.

- **⚪ INFO** `LLM_CONTEXT_BUDGET_EXCEEDED` — 'scripts/arax_client.py' excluded from LLM analysis (84,318 chars)
  > file size (84,318 chars) exceeds per-file limit (75,000)
  > File: `scripts/arax_client.py`
  > **Remediation:** Increase llm_analysis.max_code_file_chars in your scan policy to include this content in LLM analysis.

### primekg — 🔵 LOW

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Full in-memory load of a ~4M-row CSV with unbounded two-hop expansion
  > _load_kg() reads the entire multi-hundred-MB kg.csv into a pandas DataFrame and caches it, and find_paths() performs a two-hop join that can enumerate a combinatorial number of paths when traversing hub nodes (e.g., highly connected proteins). This can produce high memory/CPU usage. The behavior is documented in the compatibility field ('budget a few GB of RAM') and depth is capped at 2, so this is an operational resource consideration rather than a deliberate DoS.
  > **Remediation:** Consider chunked reading or a columnar/indexed store, and add a cap on the number of returned paths or on intermediate-node degree to bound worst-case expansion.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-heavy description for discovery triggering
  > The frontmatter description ends with an explicit 'Also trigger on ...' list enumerating many keywords (PrimeKG, kg.csv, Harvard Dataverse knowledge graph, disease_protein, drug_protein, indication/contraindication edges, network pharmacology). This is a mild discovery/activation optimization pattern. However, all keywords are strictly in-domain and consistent with the skill's actual functionality, so impact is minimal and no capability inflation beyond the implemented CLI is claimed.
  > **Remediation:** Optionally trim the explicit trigger-keyword list to a concise functional description; no functional change required since keywords match real capability.

### open-targets — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — GraphQL endpoint overridable via environment variable and CLI flag
  > The shared transport module reads the API endpoint from the OPEN_TARGETS_API_URL environment variable and every CLI exposes an `--api-url` override. If an attacker can set that environment variable (or influence the command line), all GraphQL request bodies — including any user-supplied query text and variables passed through the `raw` subcommand — would be POSTed to an arbitrary host. This is a common, largely benign configurability pattern for public-API clients, but it is a theoretical redirection/exfiltration vector because there is no allow-list or scheme validation on the destination URL.
  > File: `scripts/_common.py`
  > **Remediation:** Optionally validate that the endpoint uses HTTPS and, if practical, warn on stderr when a non-default host is used so redirection to an unexpected destination is visible to the user.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — `raw` subcommand executes arbitrary GraphQL documents from a local file path
  > The `raw` subcommand reads any file path supplied on the command line and sends its contents as a GraphQL document, with `--var name=value` pairs parsed as JSON. This is intended functionality for a GraphQL client and cannot execute local code, but it does mean an agent could be induced (e.g., by a crafted .graphql file in a workspace) to issue queries beyond the documented subcommands. Impact is limited because the Open Targets API is read-only, unauthenticated, and public, and no local file contents other than the named query file are transmitted.
  > File: `scripts/ot_query.py`
  > **Remediation:** No change strictly required; optionally document that the query file should be reviewed before execution and reject documents containing GraphQL mutations.

### pkpd-translation — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Description contains an explicit trigger-keyword list
  > The YAML description ends with an explicit activation keyword list ("Also trigger on non-compartmental analysis, AUC, clearance, volume of distribution, allometric scaling, human equivalent dose, first-in-human, NOAEL, therapeutic index, or exposure margin"). This is a mild form of discovery/activation tuning. All listed keywords are tightly scoped to the skill's genuine pharmacokinetics domain and the scripts implement exactly those functions, so the risk of unwanted activation or capability inflation is minimal — informational only.
  > **Remediation:** Optional: trim the explicit keyword list to a natural-language capability statement; no functional change needed since claims match implementation.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Declared allowed-tools broader than demonstrated need (Write/Edit/Bash)
  > The manifest declares Read, Write, Edit, Bash. The documented workflows only require executing the bundled Python scripts (Bash) and reading bundled reference markdown (Read); no script writes or edits files. Over-declaration of Write/Edit grants unnecessary capability surface, though no code in the package abuses it. There is no violation of the declared restrictions — all script behavior (stdout/stderr output, optional reading of a user-supplied profile file) is within scope.
  > **Remediation:** Narrow allowed-tools to the minimum required (e.g., Read, Bash) unless file authoring is an intended feature.

### oligonucleotides — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Activation keyword list appended to description
  > The YAML description ends with an explicit trigger-keyword list ("Also trigger on siRNA, antisense oligonucleotide, ASO, gapmer, RNase H, seed region, duplex asymmetry, 2'-MOE, locked nucleic acid, phosphorothioate, or GalNAc conjugate"). This is a mild discovery-optimisation pattern. All listed keywords are tightly scoped to the skill's genuine nucleic-acid-design domain, there is no brand impersonation, no priority-manipulation language ("use me first"), and no over-broad claims, so the practical risk of unwanted activation outside the intended domain is minimal.
  > **Remediation:** Optional: describe capabilities in prose rather than an explicit trigger-keyword enumeration; the current list is domain-accurate and does not require change.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several documentation paths listed as referenced but absent from the package
  > The scanner resolved candidate paths under assets/ and templates/ (e.g. assets/chemical-modifications.md, templates/delivery-and-safety.md) that do not exist. The three files actually linked from SKILL.md (references/sirna-and-aso-design.md, references/chemical-modifications.md, references/delivery-and-safety.md) are all present, bundled inside the skill package, and contain only benign scientific reference material with no instructions to the agent that override its behaviour. Impact is limited to potential confusion if the agent attempts the non-existent paths.
  > File: `references/chemical-modifications.md`
  > **Remediation:** No action strictly required; the canonical references/ paths resolve correctly. Ensure no stale asset/template paths remain in packaging metadata.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Unbounded O(n·m) substring scan over user-supplied transcriptome FASTA
  > offtarget_scan.py `contig` runs longest_common_substring() for every candidate against every transcript record loaded fully into memory by read_fasta(). With a genuine transcriptome FASTA (hundreds of MB) this can consume large amounts of memory and CPU time with no size limit, streaming, or progress bound. This is a performance/robustness concern rather than a deliberate denial-of-service mechanism — the input is explicitly supplied by the user, and there is no loop that cannot terminate.
  > File: `scripts/offtarget_scan.py`
  > **Remediation:** Stream FASTA records rather than loading all into a dict, and optionally cap input size or number of records with a user-overridable limit.

### protein-binder-design — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list appended to skill description
  > The YAML description ends with an explicit activation keyword list ("Also trigger on BindCraft, RFdiffusion, ProteinMPNN, minibinder, hallucination, inverse folding, hotspot residue, epitope targeting, ipTM, or de novo binder."). This is a discovery-optimisation pattern that can broaden activation beyond the skill's intended scope. In this case the keywords are all tightly domain-relevant (structural biology / protein design) and match the actual capabilities of the bundled scripts, so the risk is informational rather than deceptive.
  > **Remediation:** Keep the description to a natural-language statement of capability; remove the explicit trigger-keyword enumeration or limit it to a small set of unambiguous domain terms.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Reference documentation suggests unpinned git clone plus install script execution
  > references/bindcraft-and-rfdiffusion.md documents installing BindCraft by cloning the upstream GitHub repository at HEAD and executing its installer shell script (`bash install_bindcraft.sh --cuda 12.4`). No commit hash, tag, or checksum is pinned, and the installer is run with shell privileges. This is standard practice for the cited MIT-licensed academic tool and is presented as documentation rather than executed by the bundled scripts, but an agent with Bash access could run it verbatim, inheriting whatever the upstream repository contains at that moment.
  > File: `references/bindcraft-and-rfdiffusion.md`
  > **Remediation:** Pin a specific release tag or commit hash, document expected checksums, and state that the installation step requires explicit user confirmation before any shell execution.

### retrosynthesis — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list appended to description
  > The skill description ends with an explicit list of activation keywords ("Also trigger on AiZynthFinder, retrosynthetic tree search, synthetic accessibility, SAscore, RAscore, building-block stock, reaction template, or route scoring"). This is keyword baiting for discovery, though all listed terms are directly relevant to the skill's genuine retrosynthesis domain and do not inflate capability beyond its actual function. Informational only.
  > **Remediation:** Optional: keep the description to a natural-language statement of purpose rather than an explicit trigger-keyword list.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation guidance
  > The SKILL.md and reference file instruct the user to run `pip install aizynthfinder` without a pinned version, while claiming compatibility with 4.4.1. This is standard documentation practice for a legitimate MIT-licensed public package (MolecularAI/aizynthfinder) and the scripts themselves install nothing, so the supply-chain risk is minimal. Noted for completeness.
  > File: `SKILL.md`
  > **Remediation:** Pin the version in the documented install command (e.g. `pip install aizynthfinder==4.4.1`) to match the stated 'checked against' version.

### rdkit — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword trigger list in description broadens activation surface
  > The skill description embeds an explicit activation-keyword list ("Also trigger on rdkit, Chem.MolFromSmiles, rdFingerprintGenerator, SDMolSupplier, SMARTS query, ETKDG, or FilterCatalog") and cross-references other skills. While all terms are genuinely within the cheminformatics domain and the skill's actual functionality matches its claims, explicit trigger-keyword stuffing is a discovery-layer pattern that increases unwanted activation. No brand impersonation or capability inflation beyond the actual scope was found; severity is informational only.
  > **Remediation:** Describe capabilities in natural prose rather than an explicit trigger-keyword list; rely on semantic matching for discovery.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation commands
  > SKILL.md and references/api_reference.md instruct installing RDKit with `uv pip install rdkit` and `conda create -c conda-forge -n my-rdkit-env rdkit` without version pinning. The package names are correct upstream names (no typosquatting; the doc explicitly warns that `rdkit-pypi` is only the legacy name), and channels are reputable, so the actual supply-chain risk is minimal. Lack of pinning is only a reproducibility/integrity hygiene issue.
  > File: `references/api_reference.md`
  > **Remediation:** Pin explicit versions (e.g., `rdkit==2026.3.5`) consistent with the documented 'checked against' version, and note that installs should be reviewed by the user before execution.

### pytdc — 🔵 LOW

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Large dependency installation and potentially large dataset downloads consume significant disk/network
  > The documented installation resolves ~123 packages (Torch, RDKit, TileDB, Arrow) and dataset/benchmark-group constructors can download and decompress large corpora (MolGen datasets with millions of structures). This can consume substantial disk, bandwidth, and time. The skill explicitly discloses this, recommends `uv pip install --dry-run` first, pins direct dependencies (`PyTDC==1.1.15`, `setuptools==80.9.0`), defaults every CLI to a download-free plan mode, and requires `--execute` (plus `--download` for corpora/checkpoints). Informational only.
  > **Remediation:** No change required; optionally add explicit disk-space preflight checks in the bundled CLIs before acknowledged downloads.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Downloads and loads remote model checkpoints (pickled artifacts) from upstream hosts
  > The oracle workflow constructs `tdc.Oracle(...)` for checkpoint-backed oracles (DRD2, GSK3B, JNK3, CYP3A4_Veith, fpscores for LogP/SA), which causes PyTDC to fetch serialized model artifacts from Harvard Dataverse and deserialize them locally. Deserialization of remote pickle/scikit-learn artifacts is an inherent supply-chain/code-execution risk. The skill mitigates this well: execution requires both `--execute` and `--download`, the runtime directory is constrained to a relative workspace path, remote-service/docking/composite oracles are explicitly refused, and references/oracles.md warns the user to review artifact origin and trust boundary before download. Risk is therefore residual/informational rather than an active threat.
  > File: `scripts/molecular_generation.py`
  > **Remediation:** Optionally record and verify checksums for downloaded checkpoints and surface the artifact URL/size to the user before the acknowledged download; otherwise current double-flag gating and documentation are adequate.

### target-safety — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger keyword list appended to skill description
  > The YAML description ends with an explicit activation keyword list ("Also trigger on gnomAD, LOEUF, pLI, loss-of-function intolerance, mutational constraint, GWAS Catalog, credible set, human knockout, genetic support, or target safety dossier."). This is a mild discovery-optimisation pattern. All listed keywords are tightly scoped to the skill's genuine domain (human genetic target evidence) and there are no brand-impersonation or over-broad general-assistant claims, so the practical risk of unwanted activation is minimal.
  > **Remediation:** Optional: describe capability in prose rather than enumerating trigger keywords, to keep skill-selection signals behaviour-based.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — API endpoints overridable via environment variables and CLI flags
  > Both service base URLs are read from the environment (GNOMAD_API_URL, GWAS_API_URL) and can be overridden with --gnomad-url / --gwas-url. If an attacker controls the agent's environment or argument construction, gene symbols and query traffic could be redirected to an arbitrary host. Only non-sensitive gene symbols are transmitted and no credentials or local files are read, so impact is minimal; this is a standard configurability pattern for scientific API clients.
  > File: `scripts/_common.py`
  > **Remediation:** Optionally validate that any overridden endpoint uses HTTPS and belongs to an allowlist of expected hosts.

### rowan — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Documentation encourages inline API key assignment
  > Several examples show setting the Rowan credential directly in Python source (`rowan.api_key = "your_api_key_here"` / `rowan.api_key = "..."`). These are placeholders, not real secrets, and the skill explicitly recommends the ROWAN_API_KEY environment variable first. Still, the inline pattern can lead an agent to write a real key into a file on disk or into chat output.
  > **Remediation:** Consistently use the environment-variable pattern in all examples and avoid generating code that literally embeds the key value.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Metered cloud compute with batch submission patterns (cost exposure)
  > The skill drives submission of metered, billed cloud compute (credits per CPU/GPU-minute) and includes batch/loop submission examples with no explicit user-confirmation gate before spending credits. An agent looping over a large SMILES library could incur substantial unintended cost. The skill does warn about cost in the compatibility field and composition notes, which mitigates this.
  > **Remediation:** Add an explicit instruction to confirm with the user before submitting batches above a small threshold, and to report estimated credit consumption first.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned package installation instruction
  > The skill instructs the agent to run `uv pip install rowan-python` without a pinned version or hash. While `rowan-python` is the legitimate package for the Rowan platform, unpinned installs allow a future compromised or typosquatted release to be pulled into the environment automatically. This is standard documentation practice and low risk, but noted for supply-chain hygiene.
  > **Remediation:** Pin the dependency version (e.g., `uv pip install rowan-python==<version>`) and prefer installing into an isolated virtual environment.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Referenced files missing from package
  > Several paths surfaced during discovery (assets/*.md, templates/*.md, rowan.py, rdkit.py) were not found in the package. The four genuinely linked reference documents (references/workflow_catalog.md, references/batch_and_webhooks.md, references/access_and_pricing.md, references/end_to_end_example.md, references/troubleshooting.md) are present and benign. Missing/ambiguous references are a documentation-integrity issue rather than a security threat, but unresolved file references could later be satisfied by attacker-planted files of the same name.
  > File: `references/end_to_end_example.md`
  > **Remediation:** Ensure all referenced paths resolve within the skill package and remove stale references.

### uniprot-rcsb — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list in description broadens activation surface
  > The frontmatter description ends with an explicit activation-trigger list ('Also trigger on UniProt accessions, PDB ids, rest.uniprot.org, search.rcsb.org, files.rcsb.org, alphafold.ebi.ac.uk, id mapping, SEQRES, or missing residues'). This is a discovery-optimization pattern that can increase unwanted activation. In this case the keywords are tightly scoped to the skill's actual, narrow bioinformatics domain and are consistent with the implemented scripts, so the risk is informational rather than deceptive capability inflation.
  > **Remediation:** Optional: trim the explicit trigger keyword list to a concise natural-language description of the skill's purpose.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Network downloads write arbitrary remote content to local disk paths
  > fetch_structure.py downloads mmCIF/PDB/SDF files from files.rcsb.org and alphafold.ebi.ac.uk and writes them to a user-supplied --out-dir with mkdir(parents=True). Identifiers are upper-cased but not validated against a PDB-id/accession pattern, so a crafted identifier could influence the request path and output filename. The destinations are constructed from a fixed base URL, downloads are size-capped (256 MB), and the retrieved content is only parsed as coordinates, so practical impact is low; this is standard behaviour for a structure-retrieval tool and is consistent with the declared allowed-tools (Read, Write, Edit, Bash).
  > File: `scripts/fetch_structure.py`
  > **Remediation:** Validate identifiers against a strict regex (e.g. ^[0-9A-Z]{4}$ for PDB ids, ^[A-Z0-9]{6,10}$ for UniProt accessions) and sanitise filenames before writing, to prevent path traversal or unintended URL paths.
