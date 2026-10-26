# Security Scan Report

**Generated:** 2026-10-26 09:26 UTC  
**Skills scanned:** 37  
**Total findings:** 157  
**Critical:** 0 | **High:** 0 | **Safe skills:** 37/37

**Scanner:** cisco-ai-skill-scanner 2.0.13 · **Model:** claude-opus-5  
**This run:** full rescan of all 37 skill(s).  

## Summary

| Skill | Severity | Findings | Safe | Duration |
|-------|----------|----------|------|----------|
| esm | 🟡 MEDIUM | 5 | ✅ | 46.3s |
| openfda | 🟡 MEDIUM | 4 | ✅ | 26.9s |
| patent-landscape | 🟡 MEDIUM | 4 | ✅ | 27.2s |
| tamarind | 🟡 MEDIUM | 12 | ✅ | 33.6s |
| chembl | 🔵 LOW | 1 | ✅ | 17.3s |
| autodock-vina | 🔵 LOW | 2 | ✅ | 19.2s |
| admet-prediction | 🔵 LOW | 2 | ✅ | 21.4s |
| boltz | 🔵 LOW | 2 | ✅ | 21.8s |
| antibody-engineering | 🔵 LOW | 2 | ✅ | 22.8s |
| chemical-space | 🔵 LOW | 2 | ✅ | 24.4s |
| adaptyv | 🔵 LOW | 5 | ✅ | 32.1s |
| clinicaltrials | 🔵 LOW | 3 | ✅ | 23.2s |
| datamol | 🔵 LOW | 3 | ✅ | 22.6s |
| diffdock | 🔵 LOW | 2 | ✅ | 18.1s |
| depmap | 🔵 LOW | 3 | ✅ | 22.5s |
| deepchem | 🔵 LOW | 3 | ✅ | 26.4s |
| free-energy-perturbation | 🔵 LOW | 1 | ✅ | 17.1s |
| generative-design | 🔵 LOW | 3 | ✅ | 26.6s |
| immunogenicity | 🔵 LOW | 2 | ✅ | 20.6s |
| molfeat | 🔵 LOW | 2 | ✅ | 17.8s |
| glycoengineering | 🔵 LOW | 4 | ✅ | 27.9s |
| medchem | 🔵 LOW | 3 | ✅ | 25.4s |
| molecular-dynamics | 🔵 LOW | 3 | ✅ | 22.0s |
| ncats-arax | 🔵 LOW | 4 | ✅ | 30.3s |
| open-targets | 🔵 LOW | 2 | ✅ | 20.1s |
| oligonucleotides | 🔵 LOW | 2 | ✅ | 23.1s |
| primekg | 🔵 LOW | 2 | ✅ | 18.0s |
| protein-binder-design | 🔵 LOW | 4 | ✅ | 28.7s |
| pytdc | 🔵 LOW | 2 | ✅ | 25.5s |
| retrosynthesis | 🔵 LOW | 2 | ✅ | 21.0s |
| rowan | 🔵 LOW | 3 | ✅ | 22.6s |
| rdkit | 🔵 LOW | 3 | ✅ | 32.3s |
| target-safety | 🔵 LOW | 3 | ✅ | 24.3s |
| uniprot-rcsb | 🔵 LOW | 2 | ✅ | 24.7s |
| binding-site-analysis | 🟢 SAFE | 0 | ✅ | 14.2s |
| degraders | 🟢 SAFE | 0 | ✅ | 11.4s |
| pkpd-translation | 🟢 SAFE | 0 | ✅ | 8.9s |

## Detailed Findings

### esm — 🟡 MEDIUM

- **🟡 MEDIUM** `LLM_SUPPLY_CHAIN_ATTACK` — Install instruction pointing to a possibly misattributed GitHub repository (github.com/Biohub/esm)
  > The skill repeatedly presents `https://github.com/Biohub/esm` as the official ESM repository and includes a `uv pip install "esm@git+https://github.com/Biohub/esm.git@<sha>"` command. The canonical EvolutionaryScale ESM repository is `github.com/evolutionaryscale/esm`; the `Biohub` organization reference is unverified and could be an impersonated or typosquat-style namespace. Installing a Python package directly from an unverified GitHub organization is a supply-chain risk, even if the documentation advises pinning a commit SHA (the SHA is a placeholder the agent/user must fill in).
  > **Remediation:** Reference only the verified upstream repository (github.com/evolutionaryscale/esm) and the PyPI release `esm==3.2.3`. Remove or clearly caveat git+https installs from unverified organizations, and require explicit user confirmation plus a verified release tag/SHA before any VCS install.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Instruction to read API key from local .env file
  > The Authentication section directs the agent to read a local `.env` file to find `ESM_API_KEY` when the environment variable is unset. Reading dotfiles containing secrets is inherently sensitive, though the skill explicitly scopes it ('do not load unrelated secrets') and never transmits the key anywhere other than the documented inference endpoints.
  > **Remediation:** Prefer requiring the user to export the variable explicitly; if .env parsing is needed, never echo or log the value and confirm with the user before reading secret-bearing files.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Unverifiable / future-dated model identifiers and platform claims
  > The references claim ESMFold2 model families dated 2026-04/2026-05 and assert a platform migration from Forge to biohub.ai. These claims cannot be verified and may be fabricated or outdated, which could lead the agent to generate non-working code, point users at wrong consoles, or create API keys on an incorrect platform. No executable harm, but it is potentially misleading technical content.
  > **Remediation:** Cite authoritative upstream documentation for model IDs and availability, or instruct the agent to query the provider's model list at runtime rather than hardcoding unverified identifiers.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword stuffing in skill description
  > The YAML description ends with an explicit activation-keyword list ('Also trigger on esm, ESM3, ESMC, ESM Cambrian, ESMFold2, `from esm.models`, ESMProtein, GenerationConfig, forge.evolutionaryscale.ai, biohub.ai, or ESM_API_KEY'), including the environment variable name `ESM_API_KEY`. This biases discovery/activation, and keying on a secret-variable name can cause the skill to activate in credential-handling contexts. The keywords are domain-relevant and not over-broad, so impact is limited.
  > **Remediation:** Describe capabilities in natural language and remove the explicit trigger-token list, especially the secret environment-variable name.

- **🟡 MEDIUM** `LLM_DATA_EXFILTRATION` — API key transmitted to an unverified third-party host (biohub.ai)
  > Multiple code samples instruct the agent to read `ESM_API_KEY` from the environment or a local `.env` file and pass it to clients configured with `url="https://biohub.ai"`. The association of `biohub.ai` with EvolutionaryScale/Forge is not independently verifiable in the skill, and `biohub.org` (Chan Zuckerberg Biohub) is a distinct organization. If the domain attribution is inaccurate or the domain is attacker-controlled, following these instructions would send a user credential to an untrusted endpoint. Mitigating factors: the skill explicitly warns not to hardcode tokens, restricts `.env` reading to the single `ESM_API_KEY` variable, and tells the agent not to accept endpoint URLs from untrusted input.
  > File: `SKILL.md`
  > **Remediation:** Verify and document the provenance of the hosted endpoint; prefer the well-known `https://forge.evolutionaryscale.ai` host, and require explicit user confirmation before sending an API key to any alternative domain.

### openfda — 🟡 MEDIUM

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-baiting trigger list in skill description
  > The description ends with an explicit activation bait list ("Also trigger on openFDA, api.fda.gov, FAERS, Drugs@FDA, SPL, NDC, pharmacovigilance, boxed warning, adverse event report, drug recall, or safety signal."). While all keywords are tightly scoped to the skill's genuine functionality (FDA public API queries) and therefore not deceptive, enumerating trigger keywords is a discovery-influencing pattern worth noting. No capability inflation or brand impersonation beyond the legitimate data source is present.
  > **Remediation:** Optional: describe capabilities declaratively rather than listing explicit activation triggers; the keywords here are domain-accurate so risk is minimal.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — API endpoint overridable via environment variable and --base-url flag
  > The HTTP base URL is read from the OPENFDA_API_URL environment variable and can also be overridden per-invocation with --base-url. If an attacker could set that environment variable or inject the flag, all queries (including the optional OPENFDA_API_KEY which _build_url appends as a query parameter) would be redirected to an attacker-controlled host, leaking the API key and returning attacker-controlled data to the agent. This is a standard configurability pattern and no default points anywhere but https://api.fda.gov, so the practical risk is low.
  > **Remediation:** Restrict overrides to an allowlist of trusted hosts, or suppress attaching OPENFDA_API_KEY whenever the base URL differs from the default api.fda.gov host.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Medical/pharmacovigilance output requires careful interpretation
  > The skill produces disproportionality statistics (PRR, ROR, chi-squared) that could be misread as causal risk estimates in a clinical context. Notably, the skill itself mitigates this extensively: SKILL.md and references/disproportionality.md repeatedly state that FAERS counts reports rather than patients, list six reasons a signal is not a risk, mandate quoting 'a' alongside every ratio, and require the phrasing "reports mention this event disproportionately" instead of causal language. This is documented responsibly; flagged only as informational given the health-adjacent domain.
  > File: `references/disproportionality.md`
  > **Remediation:** No change required; the existing disclaimers are thorough and should be preserved verbatim in any derived output.

- **🟡 MEDIUM** `BEHAVIOR_ENV_VAR_HARVESTING` — Environment variable harvesting detected
  > Script iterates through environment variables in skills/openfda/scripts/_common.py
  > File: `skills/openfda/scripts/_common.py`
  > **Remediation:** Remove environment variable collection unless explicitly required and documented

### patent-landscape — 🟡 MEDIUM

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — API endpoints overridable via environment variables while an API key is transmitted
  > PATENTSVIEW_URL and SURECHEMBL_FTP are read from the environment with hardcoded HTTPS defaults. The PatentsView request sends the user's PATENTSVIEW_API_KEY in an X-Api-Key header to whatever host PATENTSVIEW_URL points at. If an attacker can set that environment variable, the key could be forwarded to a third-party host. This is a common configurability pattern and the defaults are legitimate official endpoints, so risk is low; the key is never written to disk, logged, or sent anywhere else.
  > **Remediation:** Validate that the resolved endpoint host matches an allow-list (e.g. search.patentsview.org, ftp.ebi.ac.uk) before attaching credentials, or refuse to send the API key to non-default hosts.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Documentation suggests multi-gigabyte bulk downloads
  > The skill instructs the user/agent to download SureChEMBL bulk Parquet tables totalling roughly 15 GB via curl. The scripts themselves never download these files — they only list directories and issue HEAD requests for sizes, and the 'plan' command exists specifically to minimise what is fetched and warn about disk usage. This is disclosed transparently in both the manifest compatibility field and the body, so it is informational rather than an abuse pattern.
  > **Remediation:** No action required; the skill already surfaces sizes and requires explicit user action to download. Ensure the agent confirms with the user before executing any suggested curl commands.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list appended to skill description
  > The YAML description ends with an explicit activation keyword list ('Also trigger on SureChEMBL, patent chemistry, Markush structure, freedom to operate, composition of matter, assignee, priority date, patent family, or PatentsView'). While all terms are genuinely within the skill's domain and the capability claims are narrow and honest, enumerating trigger keywords is a mild discovery-surface broadening pattern. No evidence of brand impersonation or capability inflation beyond the actual functionality.
  > File: `SKILL.md`
  > **Remediation:** Optional: describe capabilities in prose rather than listing activation keywords; the terms used are domain-appropriate so no change is strictly required.

- **🟡 MEDIUM** `BEHAVIOR_ENV_VAR_HARVESTING` — Environment variable harvesting detected
  > Script iterates through environment variables in skills/patent-landscape/scripts/_common.py
  > File: `skills/patent-landscape/scripts/_common.py`
  > **Remediation:** Remove environment variable collection unless explicitly required and documented

### tamarind — 🟡 MEDIUM

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — User sequence/structure data and API key are transmitted to a third-party cloud service
  > By design the skill reads TAMARIND_API_KEY from the environment and sends user-supplied sequences, PDB/CIF/SDF files, and inline file content to app.tamarind.bio and mcp.tamarind.bio. This matches the stated purpose and is disclosed in the description and compatibility fields, and the skill explicitly instructs never to hardcode or commit keys. It is noted only as an informational data-egress consideration (potentially sensitive/proprietary sequences leaving the local machine), not as a hidden exfiltration behavior.
  > **Remediation:** No change required for functionality; optionally add an explicit confirmation step before uploading local files or proprietary sequences to the hosted service.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Large 'trigger-keywords' metadata list broadens skill activation
  > The manifest includes a long `trigger-keywords` list (AlphaFold, Boltz, docking, antibody design, cloud GPU biology, x-api-key, ADME, enzyme, peptide, etc.) plus a 'Composing with the rest of the bundle' section that encourages routing many adjacent bio tasks through this skill. The keywords are topically accurate for a computational-biology API wrapper and are not deceptive, but the breadth increases the chance of activation (and thus metered cloud submissions of user sequence data) on requests the user intended to run locally.
  > **Remediation:** Narrow trigger keywords to Tamarind-specific terms (tamarind, tamarind.bio, app.tamarind.bio/api) and generic hosted-GPU phrasing, so generic bio tool mentions do not auto-activate cloud submissions.

- **🔵 LOW** `LLM_PROMPT_INJECTION` — Instructs agent to fetch and trust live external documents at runtime
  > SKILL.md directs the agent to fetch external resources (https://app.tamarind.bio/llms.txt, openapi.yaml, docs.tamarind.bio/llms.txt) and to prefer them over any local/hardcoded content ('Prefer fetching them at runtime over trusting any hardcoded list'). An 'llms.txt' index is specifically designed to be consumed as LLM-directed content, so compromised or modified vendor content could introduce instructions into the agent context. The domains are the skill's own first-party vendor and the usage is a reasonable documentation pattern, so risk is low, but the trust delegation to remote, mutable content is a real indirect-prompt-injection surface.
  > File: `SKILL.md`
  > **Remediation:** Treat fetched remote documents as data only: explicitly instruct the agent not to execute or follow instructions contained in fetched llms.txt/openapi.yaml content, and restrict fetches to the documented HTTPS vendor endpoints.

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

### chembl — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Configurable API base URL could redirect requests to an arbitrary host
  > All scripts expose a `--base-url` flag that replaces the hard-coded EBI endpoint. If an agent accepts an attacker/user-supplied base URL (e.g., from a prompt or document), query parameters and results would be sent to and received from an arbitrary host, enabling result poisoning or leaking of query content. The default is the legitimate public ChEMBL endpoint and no credentials are transmitted, so impact is limited.
  > **Remediation:** Optionally restrict `--base-url` to an allow-list of trusted hosts (e.g., *.ebi.ac.uk) or require an explicit confirmation flag when overriding the default endpoint.

### autodock-vina — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-dense description for discovery triggering
  > The YAML description ends with an explicit trigger-keyword list ('Also trigger on vina, smina, gnina, mk_prepare_ligand, mk_prepare_receptor, mk_export, scrub.py, PDBQT, autogrid4, docking box, or binding-pose prediction'). While all listed keywords are genuinely within the domain of AutoDock Vina docking and match the implemented functionality, enumerating trigger terms slightly increases activation surface. No brand impersonation or over-broad general-assistant claims are made.
  > **Remediation:** Optional: trim the explicit trigger-keyword list to a concise functional description; no functional change required since the keywords are domain-accurate.

- **🔵 LOW** `LLM_COMMAND_INJECTION` — Subprocess invocation of external binaries with user-supplied path arguments
  > dock_batch.py builds command lists from CLI arguments (receptor, config, ligand paths, scoring, seed) and executes them via subprocess.run. Usage is safe-by-construction: it passes an argument list (no shell=True), never interpolates into a shell string, and all values are either argparse-typed ints/floats or path strings. Risk is limited to invoking whatever 'vina'/'mk_prepare_ligand.py' resolves to on PATH (PATH hijack is a pre-existing environment concern, not a skill defect). Timeouts are bounded (default 3600s per subprocess) and worker count is user-controlled.
  > File: `scripts/dock_batch.py`
  > **Remediation:** No change strictly required. Optionally validate that --receptor/--config/--ligands resolve inside an expected working directory and resolve tool paths via shutil.which once, documenting the PATH dependency.

### admet-prediction — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list in skill description
  > The YAML description ends with an explicit activation-keyword list ('Also trigger on ADMET-AI, admet_ai, Chemprop-RDKit, hERG liability, CYP3A4 inhibition, Caco-2, bioavailability prediction, or developability triage'). This is a mild discovery-optimization pattern. All listed terms are narrowly scoped to the skill's actual cheminformatics/ADMET domain, and no brand impersonation, priority manipulation, or over-broad ('can do anything') claims are present, so the risk is informational only.
  > **Remediation:** Optional: trim the explicit trigger-keyword enumeration to a plain functional description to minimize unintended skill activation.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned third-party package installation instruction
  > Documentation instructs the user to run `pip install admet-ai` without a pinned version, which pulls chemprop, RDKit, and PyTorch and downloads model weights from the network on first use. The skill does not execute the install automatically, and the upstream project is named and linked (MIT, github.com/swansonk14/admet_ai), so exposure is limited to normal dependency trust. Still, unpinned installs plus first-use remote weight download are a supply-chain consideration.
  > File: `references/running-admet-ai.md`
  > **Remediation:** Pin an exact version (e.g., `pip install admet-ai==2.0.1`) and note the expected provenance/checksum of downloaded model weights.

### boltz — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Optional third-party network transmission of input sequences via ColabFold MSA server
  > The workflow recommends `boltz predict ... --use_msa_server`, which transmits user-provided protein sequences to the public ColabFold MSA service. The bundled scripts themselves perform no network I/O, and the skill repeatedly and explicitly warns that this sends sequences to a public server and must not be used for confidential/unpublished targets. This is disclosed, user-controlled behavior rather than covert exfiltration, so it is informational only.
  > **Remediation:** No change required; the disclosure is adequate. Optionally default documentation examples to precomputed MSAs so network transmission is always an explicit opt-in.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation guidance, including direct GitHub install
  > The reference documentation instructs users to install the Boltz package without a pinned version and also offers an install directly from a GitHub repository (`pip install git+https://github.com/jwohlwend/boltz.git`). Unpinned/VCS installs pull whatever code is currently published, so a future compromise of the upstream repository or PyPI package would be executed locally. This is standard documentation practice for an open-source scientific tool and the repository referenced matches the skill's stated homepage, so the risk is low, but version pinning would be preferable.
  > File: `references/running.md`
  > **Remediation:** Recommend a pinned install (e.g., `pip install boltz==2.2.1`) and discourage installing from the VCS main branch unless explicitly required and verified.

### antibody-engineering — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-dense description for discovery triggering
  > The YAML description ends with an explicit trigger-word list ('Also trigger on antibody, nanobody, VHH, scFv, Fab, CDR, framework, ANARCI, abnumber, IgBLAST, OAS, SAbDab, humanization, Vernier residues, or developability'). While all the terms are tightly scoped to the skill's genuine domain (antibody sequence analysis) and the claims match the bundled scripts, the pattern constitutes mild activation-surface broadening within the same subject area. No evidence of over-broad or deceptive capability claims.
  > **Remediation:** Optional: trim the explicit trigger list to a concise natural-language description; the domain terms already appear in the functional description.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced documentation paths do not resolve
  > The analysis harness enumerated candidate paths (templates/*.md, assets/*.md) that were not found in the package. The paths actually cited in SKILL.md (references/numbering-schemes.md, references/developability.md, references/humanization-and-design.md, references/tools.md) all exist and contain benign, domain-accurate documentation. This is a packaging/documentation hygiene note only, not a security threat.
  > File: `references/humanization-and-design.md`
  > **Remediation:** No action required for security; ensure only existing reference paths are enumerated by tooling.

### chemical-space — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-baiting phrasing in skill description
  > The YAML description ends with an explicit activation-trigger keyword list ('Also trigger on ZINC22, CartBlanche, Enamine REAL, make-on-demand, tangible library, synthon, tranche, giga-scale enumeration, or ultra-large virtual screening'). The keywords are all genuinely in-domain and match the skill's actual behaviour, so this is a routing-hint convention rather than deceptive capability inflation, but it does bias discovery toward this skill.
  > **Remediation:** Describe the capability in prose and avoid explicit 'trigger on <keyword list>' directives in the description field.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Network endpoint overridable via environment variable and CLI flag
  > The HTTP base URL is read from the `CARTBLANCHE_URL` environment variable and can also be overridden with `--base-url`. If an attacker can influence the environment or arguments, lookups (ZINC identifiers only, no credentials) could be redirected to an arbitrary host. Impact is limited: no authentication headers, tokens, or local files are transmitted, and the data sent is only public chemical identifiers. Responses are parsed as JSON and printed, never executed.
  > File: `scripts/_common.py`
  > **Remediation:** Optionally restrict the override to an allow-list of known docking.org hosts, or log the effective endpoint when it differs from the documented default.

### adaptyv — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Instructs reading API key from environment and local .env files
  > The skill directs the agent to locate and load a `.env` file from the project root and to read `ADAPTYV_API_KEY` from the environment. This is standard, recommended secret-handling practice (it explicitly warns against hardcoding or committing tokens) and no exfiltration path exists, but it does involve the agent touching credential material, which warrants awareness.
  > **Remediation:** Ensure the agent only passes the key to the documented Adaptyv API endpoint and never echoes, logs, or writes key values into files or chat output.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Documented workflow bypasses human review for billable operations
  > A documented 'Automated Pipeline' pattern sets `skip_draft: true` and `auto_accept_quote: true`, which bypasses the Draft review stage and auto-accepts a financial quote, generating a Stripe invoice without a human confirmation step. If the agent applies this pattern autonomously it could commit the user to real laboratory costs. This is a legitimate vendor API feature, not malicious, but it is an autonomy/financial-risk pattern.
  > **Remediation:** Add an explicit instruction that the agent must obtain user confirmation before setting `auto_accept_quote` or `skip_draft`, since these create binding financial commitments.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Broad activation triggers including code-import and domain detection
  > The description specifies many activation triggers, including automatic triggering when code imports `adaptyv`, `adaptyv_sdk`, or `FoundryClient`, or references the vendor domain. These triggers are all tightly scoped to the vendor's own namespace and product terminology, so this is reasonable rather than keyword baiting, but it does slightly widen passive activation surface (the skill can activate from file content rather than explicit user request).
  > **Remediation:** No change strictly required; optionally narrow activation to explicit user intent rather than passive code-content matching.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installed directly from GitHub
  > The skill instructs installation of `adaptyv-sdk` directly from a GitHub repository (`git+https://github.com/adaptyvbio/adaptyv-sdk.git`) without any version, tag, or commit pin. While the repository appears to be the vendor's official one and matches the documented domain, unpinned VCS installs mean whatever code is on the default branch at install time is executed, creating a supply-chain exposure if the repo or account is ever compromised.
  > **Remediation:** Pin the dependency to a specific tag or commit hash (e.g., `git+https://github.com/adaptyvbio/adaptyv-sdk.git@v0.1.0` or `@<commit-sha>`), and prefer PyPI with hash verification once published.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Referenced files declared but missing from package
  > The skill references `adaptyv.py`, `templates/api-endpoints.md`, and `assets/api-endpoints.md`, none of which are present in the package. Only `references/api-endpoints.md` exists. Missing referenced files can lead to the agent searching for or fabricating substitutes, and could become a resolution hazard if files with those names later appear from untrusted sources.
  > File: `references/api-endpoints.md`
  > **Remediation:** Remove references to non-existent files or bundle them in the package; keep documentation references limited to files actually shipped with the skill.

### clinicaltrials — 🔵 LOW

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Unbounded paging walk with retry backoff can consume significant time and network resources
  > paged() follows nextPageToken until exhaustion when no limit is given, and _count_by_phase / _count_by_status issue one network request per enum value. Combined with up to 4 retries per request and sleeps of up to 30 seconds, a broad query can produce long-running, request-heavy execution. Defaults are bounded (--limit 50/200) and the documentation explicitly warns about cost, so this is a mild efficiency/availability consideration rather than an abuse pattern.
  > **Remediation:** Enforce a hard upper bound on total pages/records fetched per invocation and cap cumulative retry sleep time.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-baited description for activation breadth
  > The YAML description ends with an explicit trigger-keyword list ("Also trigger on ClinicalTrials.gov, NCT number, trial registry, study phase, enrolment, primary outcome measure, recruiting status, trial sponsor, or competitive landscape."). This is a discovery-surface optimization that can broaden activation beyond narrowly relevant requests. The keywords are, however, all tightly scoped to the skill's genuine function (clinical trial registry queries), so the inflation risk is minimal and no capability is overstated.
  > **Remediation:** Optionally trim the explicit trigger-word list to a natural-language description of the skill's purpose; no functional change required since the claims match the implemented behaviour.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — API base URL overridable via environment variable and CLI flag
  > The HTTP base URL is read from the CTGOV_API_URL environment variable and can also be overridden with --base-url. _build_url() additionally short-circuits and returns any path that already begins with http:// or https://. A poisoned environment or a crafted argument could therefore redirect all registry requests to an attacker-controlled host, causing the agent to ingest untrusted JSON that is then rendered into its context. No credentials or local data are transmitted, so the impact is limited to potential indirect content manipulation rather than exfiltration.
  > **Remediation:** Restrict the override to an allow-list of trusted hosts (or require https and reject non-clinicaltrials.gov hosts unless explicitly confirmed), and drop the absolute-URL passthrough in _build_url.

### datamol — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Cloud I/O with provider credentials and remote write paths
  > The skill documents reading from and writing to remote S3/GCS/HTTPS locations via fsspec, which involves use of provider credentials from the environment (AWS_*, GOOGLE_APPLICATION_CREDENTIALS). This is an inherent capability of the datamol library and the skill explicitly instructs the agent to only use cloud paths when the user requests them, to confirm destinations before writing, and states that no environment variables are transmitted to third parties. No exfiltration endpoint or credential harvesting logic is present; this is noted only as an informational data-flow boundary (local -> network).
  > **Remediation:** Continue requiring explicit user confirmation for any remote write destination and avoid reading cloud credentials unless a cloud operation is explicitly requested.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-dense activation description
  > The frontmatter description enumerates many explicit trigger tokens (`datamol`, `import datamol as dm`, `dm.to_mol`, `dm.standardize_mol`, `dm.cluster_mols`, `dm.pick_diverse`) to increase skill activation. The keywords are all accurate and tightly scoped to the stated cheminformatics domain, and the skill defers to the `rdkit` skill for advanced use, so this is routine discoverability tuning rather than capability inflation. Flagged for completeness only.
  > **Remediation:** No action required; keep trigger terms scoped to the actual library surface.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned package installation instructions
  > The skill instructs the agent to run `uv pip install datamol`, `uv pip install s3fs`, and `uv pip install gcsfs` without version pinning. While these are well-known, legitimate PyPI packages and the skill documents a verified version (0.12.5), unpinned installs can pull in unexpected or compromised future releases. This is a minor supply-chain hygiene concern rather than malicious behavior.
  > **Remediation:** Pin versions explicitly (e.g., `uv pip install datamol==0.12.5`) and prefer installation into an isolated virtual environment.

### diffdock — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned external repository and container image installation instructions
  > SKILL.md instructs the agent to clone the upstream DiffDock GitHub repository at HEAD, create a conda environment from an unpinned environment.yml, and pull the `rbgcsail/diffdock` Docker image without a digest or version tag. These are the legitimate upstream sources for DiffDock, but without pinning, the retrieved code/image contents can change over time, which is a minor supply-chain exposure if the agent executes them autonomously.
  > File: `SKILL.md`
  > **Remediation:** Pin to a specific release tag/commit (e.g., v1.1.3) and a Docker image digest, and require explicit user confirmation before running clone/pull/install commands.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced documentation files are missing or path-inconsistent
  > The instructions and resource listing reference files such as `references/workflows_examples.md`, and resolution attempts show missing paths like `templates/parameters_reference.md`, `assets/parameters_reference.md`, `assets/confidence_and_limitations.md`, and `references/custom_inference_config.yaml`. Missing/ambiguous references can cause the agent to search the filesystem or fall back to unverified sources. No malicious content was found in the files that do exist.
  > File: `references/workflows_examples.md`
  > **Remediation:** Ensure all referenced files exist at the exact paths stated in SKILL.md (references/ and assets/), or remove references to files that are not bundled.

### depmap — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Unvalidated network download of large remote files
  > The example download helper performs requests.get on a configurable URL and streams the response directly to a local file path without validating the URL host, TLS/content type, response status, or file size. The destinations documented are legitimate (depmap.org, figshare.com) and no sensitive local data is read or transmitted, so this is a hygiene concern rather than exfiltration. Note the ~500 MB download is disk/bandwidth heavy but is disclosed in the manifest compatibility field.
  > **Remediation:** Add response.raise_for_status(), restrict allowed hosts to depmap.org/figshare.com, validate content-type and size limits, and verify a published checksum for downloaded release files.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-dense description for discovery triggering
  > The YAML description ends with an explicit trigger-keyword list ('Also trigger on DepMap, Chronos gene effect, CRISPRGeneEffect.csv, DEMETER2, PRISM repurposing, co-essentiality, pan-essential, or ACH- cell line identifiers'). This is keyword baiting to increase activation likelihood. However, all keywords are tightly scoped to the skill's genuine domain (cancer dependency data analysis), so the capability claim is not inflated and the risk is minimal/informational.
  > **Remediation:** Keep the description to a natural-language statement of purpose; avoid explicit trigger keyword enumerations in discovery metadata.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Missing referenced files and placeholder download URLs
  > The skill's reference list includes files that do not exist in the package (scipy.py, templates/dependency_analysis.md, assets/dependency_analysis.md), and the sample code contains a placeholder URL ('https://figshare.com/ndownloader/files/...') plus an import of a non-existent module 'depmap_utils'. A missing/placeholder path could later be filled with untrusted content, and an unresolvable import may cause the agent to install an arbitrary package of that name. No malicious behavior is present; this is a documentation/integrity issue.
  > File: `references/dependency_analysis.md`
  > **Remediation:** Ship all referenced files inside the package, remove stale references, replace placeholder URLs with concrete pinned release URLs, and define load_cell_line_info locally instead of importing an undefined 'depmap_utils' module.

### deepchem — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation, including direct install from GitHub master
  > The SKILL.md instructs the agent/user to install packages without version pins (`uv pip install deepchem`, `'deepchem[torch]'`, `--pre` nightly builds) and explicitly suggests installing an untagged build directly from a GitHub repository (`pip install git+https://github.com/deepchem/deepchem.git`). Unpinned and VCS-based installs pull arbitrary current code at install time, which weakens supply-chain integrity (a compromised upstream commit or release would be executed). The target repository is the legitimate, well-known DeepChem project, so risk is low, but provenance is not verified.
  > File: `SKILL.md`
  > **Remediation:** Pin explicit versions (e.g., `deepchem==2.8.0`) and avoid `--pre`/git installs by default; if a VCS install is required, pin to a specific commit hash and document the reason.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced documentation files are missing from the package
  > The instruction body and bundled references point to files such as `references/core_capabilities.md`, `references/typical_workflows.md`, and `references/api_reference.md` (present) while the resolver also probed `assets/` and `templates/` variants that do not exist. Missing referenced paths are a documentation hygiene issue and could cause the agent to search elsewhere for content, but no malicious behavior was observed.
  > File: `references/core_capabilities.md`
  > **Remediation:** Ensure all referenced paths resolve to files bundled inside the skill directory and remove or correct stale references.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Automatic download and execution of third-party pretrained models from Hugging Face
  > scripts/transfer_learning.py loads remote pretrained checkpoints by identifier (`seyonec/ChemBERTa-zinc-base-v1`, `ibm/MoLFormer-XL-both-10pct`) and GROVER weights, which are downloaded from external hubs at runtime. Remote model artifacts are untrusted third-party content; some loading paths can execute remote code or deserialize untrusted weights. This behavior is disclosed in the skill documentation and is standard for the domain, so severity is low.
  > File: `scripts/transfer_learning.py`
  > **Remediation:** Pin model revisions/commit hashes, prefer safetensors, ensure `trust_remote_code` remains disabled, and surface a notice before the first network download.

### free-energy-perturbation — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list appended to skill description
  > The YAML description ends with an explicit activation keyword list ('Also trigger on OpenFE, alchemical transformation, thermodynamic cycle, RBFE, ABFE, SepTop, lambda window, MBAR, cycle closure, or perturbation map.'). This is a discovery-broadening pattern. In this case every term is tightly scoped to the skill's actual domain (alchemical free energy calculations) and no unrelated or brand-impersonating keywords are present, so the practical risk of unwanted activation is minimal. Informational only.
  > **Remediation:** Optional: express activation conditions as natural-language usage criteria rather than a raw keyword list, to avoid over-matching unrelated prompts.

### generative-design — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list in skill description
  > The YAML description ends with an explicit activation-keyword list ("Also trigger on REINVENT, LibInvent, LinkInvent, Mol2Mol, scaffold hopping, R-group replacement, linker design, chemical language model, or reinforcement-learning molecule optimisation"). This is a mild form of discovery/activation tuning that broadens how often the skill is selected. The keywords are, however, tightly scoped to the skill's genuine domain (REINVENT 4 generative molecular design) and do not impersonate other tools or claim general-purpose capability, so the risk is informational only.
  > **Remediation:** Keep the description focused on the functional capability; keyword lists for activation are acceptable only when narrowly domain-relevant, as here.

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Several referenced documentation paths do not resolve
  > The package scan lists references to templates/*.md and assets/*.md variants of the three reference documents that are not present in the package. The canonical references/ versions (reinvent-configuration.md, scoring-functions.md, evaluating-generated-molecules.md) are present and are the ones actually cited in SKILL.md, so this appears to be path-resolution noise rather than a missing-dependency risk. No external or network-sourced file is referenced anywhere.
  > File: `references/evaluating-generated-molecules.md`
  > **Remediation:** Ensure all referenced documentation paths resolve to files bundled inside the skill directory; remove stale alternate paths.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Documentation recommends unpinned install from a GitHub repository
  > SKILL.md and references/reinvent-configuration.md instruct the user to `git clone https://github.com/MolecularAI/REINVENT4.git` and `pip install -e .` without a pinned tag or commit hash. This is editable installation of third-party code from a remote source with no version/provenance pinning. The repository is the legitimate, well-known AstraZeneca MolecularAI project and no script in this package performs the install automatically (it is documentation only), so impact is limited; a compromised upstream branch would, however, be installed without verification.
  > File: `references/reinvent-configuration.md`
  > **Remediation:** Recommend pinning a release tag or commit (e.g. `git clone --branch v4.8 --depth 1 ...`) and verifying the repository origin before installation.

### immunogenicity — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword list appended to skill description
  > The YAML description ends with an explicit activation-keyword list ('Also trigger on immunogenicity, anti-drug antibody, ADA, T-cell epitope, MHC class II, HLA-DRB1, NetMHCIIpan, NetMHCpan, deimmunisation, tregitope, or population coverage.'). This is a mild discovery/activation-shaping pattern. All listed terms are tightly scoped to the skill's genuine domain (MHC class II epitope prediction and ADA risk triage), there are no over-broad claims ('use me first', 'general assistant'), and no brand impersonation, so the practical risk is minimal and informational only.
  > **Remediation:** Optional: keep the description to a plain statement of purpose and rely on semantic matching rather than an explicit trigger-term list.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced-file paths resolve to missing files
  > The scanner resolved documentation references to multiple paths (templates/what-drives-ada.md, templates/running-netmhciipan.md, templates/deimmunisation.md, assets/*.md) that do not exist in the package. The three paths actually cited in SKILL.md (references/running-netmhciipan.md, references/deimmunisation.md, references/what-drives-ada.md) are present and contain only domain guidance. The missing paths appear to be path-variant resolution artifacts rather than deliberate dangling references, but unresolved reference paths can cause the agent to silently skip guidance or, in a shared workspace, to pick up an attacker-dropped file at that location.
  > File: `references/running-netmhciipan.md`
  > **Remediation:** Ship only the exact relative paths cited in SKILL.md and ensure every referenced file is bundled inside the skill directory; remove or create any additional variant paths.

### molfeat — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-heavy description for discovery optimization
  > The skill description packs many trigger keywords ('Also trigger on molfeat, MoleculeTransformer, FPVecTransformer, PretrainedHFTransformer, molfeat model store, or featurizer selection'). This is a mild discovery-optimization pattern, but the keywords are all domain-relevant to the skill's actual, narrow purpose (molecular featurization), so impact is minimal and no capability inflation beyond the stated domain is present.
  > **Remediation:** Trim the explicit trigger-keyword list to a concise functional description; no security action otherwise required.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Instructions install packages and reference an external GitHub repository
  > The SKILL.md and reference files instruct installation of PyPI packages (molfeat and extras) and point users to an external GitHub repo (reymond-group/map4) for the MAP4 featurizer. Package versions are explicitly pinned (molfeat==0.11.0, extras pinned identically), which mitigates supply-chain risk, but the external GitHub install is unpinned and unverified. Documented runtime behavior also includes downloading pretrained models from HuggingFace Hub and the molfeat model store (https://fs.molfeat.datamol.io/artifacts/), which pull remote model artifacts onto the host; these are legitimate, well-known upstream sources and the store performs sha256 verification.
  > File: `SKILL.md`
  > **Remediation:** Pin or checksum any external GitHub installation, and note that model downloads from HF Hub / the molfeat store fetch remote artifacts into the local cache.

### glycoengineering — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Outbound network requests to third-party bioinformatics APIs
  > Example code performs HTTP requests to external services (GlyConnect, GlyTouCan, DTU Health Tech web services) using user-supplied identifiers such as UniProt accessions. This transmits the query target (which may be proprietary research identifiers or sequences) to third-party servers. The behavior is disclosed in both the description and compatibility fields and the endpoints are well-known public academic databases, so risk is minimal, but users should be aware data leaves the local environment.
  > **Remediation:** Explicitly warn users that sequence/identifier queries are sent to external academic servers, validate/sanitize identifiers before URL interpolation, and make network lookups opt-in.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-dense activation description
  > The YAML description ends with an explicit trigger keyword list ('Also trigger on N-glycosylation, sequon, NXS/NXT, O-glycosylation, glycoform heterogeneity, afucosylation, high-mannose, GlyTouCan, or WURCS'). This is discovery-surface tuning, but all keywords are tightly scoped to the skill's genuine domain and there are no over-broad claims, brand impersonation, or priority-manipulation phrases, so the impact is informational only.
  > **Remediation:** Keep trigger terms limited to the domain (already the case); avoid expanding the keyword list beyond the skill's actual capability.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation via uv pip install
  > The SKILL.md instructs installation of the 'glycoshield' package with no version pin and no hash/provenance verification ('uv pip install glycoshield'). An agent executing this bash snippet would pull the latest version from PyPI at install time, exposing the user to dependency-confusion/typosquatting or a compromised upstream release. Severity is low because the package is a legitimate, named scientific tool and installation is clearly documented as optional tooling, not a hidden action.
  > File: `SKILL.md`
  > **Remediation:** Pin the dependency to a specific, verified version (e.g., 'uv pip install glycoshield==X.Y.Z') and note that installation requires explicit user confirmation; consider documenting the expected package provenance/repository.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Referenced files missing from package
  > The analysis reports 'templates/glycan_databases.md' and 'assets/glycan_databases.md' as referenced but not present in the package (only 'references/glycan_databases.md' exists). Missing referenced resources can cause the agent to search for or fetch substitute content; this is a documentation hygiene issue rather than an active threat.
  > File: `references/glycan_databases.md`
  > **Remediation:** Remove or correct references to non-existent paths so the agent only loads bundled, in-package resources.

### medchem — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword stuffing in skill description
  > The YAML description ends with an explicit activation-bait clause enumerating trigger tokens ('Also trigger on medchem, `import medchem as mc`, RuleFilters, NIBRFilters, CommonAlertsFilters, NamedCatalogs, QueryFilter, PAINS filtering, or structural alerts'). This is a mild discovery-optimization pattern. The keywords are all tightly scoped to the skill's genuine domain (medicinal-chemistry filtering), so the inflation risk is minimal and there is no brand impersonation or over-broad 'general assistant' claim.
  > **Remediation:** Describe capabilities in prose without an explicit trigger-token list; rely on semantic matching for activation.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instructions
  > The skill instructs installing packages via `uv pip install medchem datamol` and `mamba install -c conda-forge lilly-medchem-rules` without version pinning. While the packages are well-known, legitimate open-source cheminformatics libraries from datamol-io/conda-forge, unpinned installs allow the agent to pull arbitrary future versions, which is a minor supply-chain consideration. No typosquatting or untrusted GitHub installs were observed.
  > **Remediation:** Pin package versions (e.g., `medchem==2.0.5`) and document expected hashes/provenance for reproducible, verifiable installs.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced files do not exist in the package
  > The analysis context lists referenced paths (assets/rules_catalog.md, assets/api_guide.md, templates/api_guide.md, templates/rules_catalog.md, datamol.py, medchem.py) that are not present in the package. These appear to be artifacts of reference extraction (module names such as `medchem` and `datamol` being parsed as file paths) rather than intentional misdirection; the genuinely referenced files references/api_guide.md and references/rules_catalog.md exist and contain only benign API documentation. Missing references can still cause the agent to attempt reads of non-existent paths.
  > File: `references/rules_catalog.md`
  > **Remediation:** Ensure all referenced resource paths resolve within the package and avoid phrasing that causes module names to be interpreted as file paths.

### molecular-dynamics — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Broad trigger-keyword list in description
  > The YAML description ends with an explicit activation keyword list ('Also trigger on OpenMM, MDAnalysis, mdtraj, Simulation.step, LangevinMiddleIntegrator, PDBFixer, DCD or XTC trajectory, RMSD analysis, or production MD'). The keywords are all tightly scoped to the skill's genuine molecular-dynamics domain, so this is accurate rather than deceptive, but the explicit trigger phrasing is a mild discovery/activation-shaping pattern worth noting.
  > File: `SKILL.md`
  > **Remediation:** Describe capabilities declaratively without explicit 'trigger on' keyword lists; rely on the functional description for matching.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instructions
  > The SKILL.md instructs the agent/user to install packages via 'conda install -c conda-forge openmm mdanalysis nglview' and 'uv pip install openmm mdanalysis' (plus 'uv pip install openff-toolkit') without any version pins or integrity verification. While these are well-known, legitimate scientific packages from reputable channels, unpinned installs allow uncontrolled version drift and leave a theoretical supply-chain surface if a channel/package is compromised. No install is performed automatically by a bundled script.
  > File: `SKILL.md`
  > **Remediation:** Pin explicit versions (e.g., openmm==8.5.2, mdanalysis==2.10.0) consistent with the 'Checked against' statement, and require explicit user confirmation before any package installation.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Referenced files that do not exist in the package
  > The reference-extraction lists several file names (templates/mdanalysis_analysis.md, assets/mdanalysis_analysis.md, pdbfixer.py, openmm.py, MDAnalysis.py, openff.py, matplotlib.py) that are not present in the package. Most of these are false positives from Python import statements in code examples (e.g., 'from pdbfixer import PDBFixer' -> pdbfixer.py). The only genuinely referenced document, references/mdanalysis_analysis.md, exists and contains benign analysis documentation. Risk is documentation hygiene only, not malicious resolution of external content.
  > File: `references/mdanalysis_analysis.md`
  > **Remediation:** No action strictly required; optionally ensure all documented relative paths resolve inside the package to avoid ambiguous file resolution.

### ncats-arax — 🔵 LOW

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Outbound network transmission of user query content to a third-party service
  > The skill, by design, POSTs user-supplied biomedical identifiers and query parameters to the external endpoint https://arax.transltr.io/api/arax/v1.4 and performs GET requests against /openapi.json and /entity. This is the declared purpose of the skill and the endpoint is the legitimate public NCATS Translator ARAX service, so it is not covert exfiltration. The skill explicitly warns that query and caller metadata may be publicly visible, requires an `--acknowledge-public-query` flag, forbids embedding user/project names in the submitter or User-Agent, restricts base URLs to HTTPS without credentials, and rejects loopback/private/link-local targets and cross-origin or protocol-downgrade redirects. Noted for data-flow awareness only.
  > File: `SKILL.md`
  > **Remediation:** No change required. Retain the explicit public-query acknowledgment, the constant submitter string, and the HTTPS/no-private-address URL policy; continue to prohibit automatic fallback to alternate ARA endpoints.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Unverifiable future-dated provenance claim in documentation
  > SKILL.md states the client was 'Checked against: the live production service, August 2026', a date that may be in the future relative to use. A forward-dated validation claim can give the operator unwarranted confidence that the pinned ARAX 1.5.4 / TRAPI 1.5.0 compatibility assertions have been empirically confirmed. Impact is minimal because the skill performs a runtime preflight version check and warns on untested versions.
  > File: `SKILL.md`
  > **Remediation:** Replace the hard-coded verification date with an accurate last-tested date and rely on the runtime `preflight` version check as the authoritative compatibility signal.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Referenced executable script is absent from the package
  > SKILL.md repeatedly instructs the agent to execute `python skills/ncats-arax/scripts/arax_client.py` (preflight, normalize, one-hop, two-hop, summarize), but no script files are present in the analyzed package. A missing executable that the instructions assume exists creates a resolution gap: the agent may attempt to locate, generate, or fetch a substitute implementation, and any file later dropped at that path would be executed with Bash without review. No malicious behavior is observable in the delivered content.
  > File: `scripts/arax_client.py`
  > **Remediation:** Ship the referenced `scripts/arax_client.py` inside the skill package with a pinned, reviewable implementation, or remove the execution instructions until the script is bundled. Instruct the agent to fail closed rather than synthesize a replacement client if the script path is missing.

- **⚪ INFO** `LLM_CONTEXT_BUDGET_EXCEEDED` — 'scripts/arax_client.py' excluded from LLM analysis (84,318 chars)
  > file size (84,318 chars) exceeds per-file limit (75,000)
  > File: `scripts/arax_client.py`
  > **Remediation:** Increase llm_analysis.max_code_file_chars in your scan policy to include this content in LLM analysis.

### open-targets — 🔵 LOW

- **🔵 LOW** `LLM_UNAUTHORIZED_TOOL_USE` — Declared allowed-tools (Write, Edit) broader than the skill's demonstrated behaviour
  > The manifest declares `allowed-tools: Read, Write, Edit, Bash`, but the documented workflow only reads bundled reference files and runs read-only Python CLIs that print results to stdout; no component writes or edits files. This is an over-broad declaration rather than a violation (no code exceeds the declared permissions), so it is informational only.
  > **Remediation:** Narrow allowed-tools to the minimum actually required (e.g. Read, Bash) to follow least privilege.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — GraphQL endpoint is overridable via environment variable and CLI flag
  > The shared transport reads the API endpoint from the OPEN_TARGETS_API_URL environment variable and also exposes an `--api-url` override on every subcommand. If an attacker (or a poisoned environment/agent context) sets this variable, all query payloads and identifiers would be POSTed to an arbitrary host instead of api.platform.opentargets.org. The transmitted data is low-sensitivity (public gene/disease/drug identifiers and GraphQL documents), and configurable endpoints are a common, legitimate pattern, so impact is limited.
  > File: `scripts/_common.py`
  > **Remediation:** Optionally validate that the configured endpoint uses HTTPS and warn on stderr when a non-default host is used, so redirection of traffic is visible to the user.

### oligonucleotides — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Explicit trigger-keyword list appended to skill description
  > The YAML description ends with an explicit activation-keyword list ("Also trigger on siRNA, antisense oligonucleotide, ASO, gapmer, RNase H, seed region, duplex asymmetry, 2'-MOE, locked nucleic acid, phosphorothioate, or GalNAc conjugate."). This is a discovery/activation-shaping pattern. In this case all keywords are tightly scoped to the skill's actual nucleic-acid design functionality, there are no over-broad claims ("use for anything", "priority tool") and no brand impersonation, so the risk is informational only.
  > **Remediation:** Optional: express the activation hints as a natural-language description of scope rather than a raw keyword list, to avoid over-triggering on tangential conversations.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Unbounded O(n*m) substring scan over user-supplied transcriptome FASTA
  > offtarget_scan.py's `contig` command runs `longest_common_substring` for every candidate against every record of a user-supplied FASTA, and `read_fasta` loads the entire file into memory. With a full transcriptome FASTA (hundreds of MB) and many candidates this can consume large amounts of CPU and RAM. There is no record-count, size, or runtime limit. This is a performance/robustness issue rather than an intentional denial-of-service, and the input is supplied by the user themselves.
  > File: `scripts/offtarget_scan.py`
  > **Remediation:** Document expected FASTA sizes, stream records instead of loading all into memory, and add optional caps on the number of records/candidates processed.

### primekg — 🔵 LOW

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Unbounded in-memory load of a multi-gigabyte CSV
  > _load_kg() reads the entire ~4M-row PrimeKG edge list into a pandas DataFrame and caches it in a module-level dictionary, consuming several GB of RAM. The two-hop path search additionally performs nested per-row iteration over frontier edges, which can be expensive for hub nodes with very large degree. This is documented in the compatibility field and is inherent to the stated purpose, so it is an operational/resource consideration rather than a deliberate DoS, but it can exhaust memory or CPU on constrained hosts.
  > **Remediation:** Consider chunked reading or column pruning (usecols) and cap the number of returned two-hop paths / intermediate nodes to bound memory and CPU usage.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword padding in skill description
  > The description ends with an explicit activation-bait clause ("Also trigger on PrimeKG, kg.csv, Harvard Dataverse knowledge graph, disease_protein, drug_protein, indication and contraindication edges, or network pharmacology..."). While the keywords are topically relevant and consistent with the script's actual functionality, this pattern inflates discovery surface and can cause unnecessary activation. No capability inflation beyond the implemented behaviour was observed.
  > **Remediation:** Trim the explicit trigger-keyword list to a concise functional description; rely on semantic matching rather than keyword stuffing.

### protein-binder-design — 🔵 LOW

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — O(n^2) pairwise distance computation over PDB residues
  > neighbour_counts() performs an all-pairs distance calculation over every parsed residue with no upper bound on input size. A very large user-supplied PDB (e.g., a large assembly with tens of thousands of residues) would cause quadratic CPU growth. This is a local, bounded-by-input-file performance characteristic typical of simple structural tooling rather than a deliberate DoS, and the script is read-only with no network or recursion.
  > **Remediation:** Add a residue-count guard (e.g., warn/abort above ~20k residues) or use spatial binning/grid hashing to reduce complexity.

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-dense description for discovery breadth
  > The YAML description ends with an explicit trigger-keyword list ('Also trigger on BindCraft, RFdiffusion, ProteinMPNN, minibinder, hallucination, inverse folding, hotspot residue, epitope targeting, ipTM, or de novo binder'). This is a mild discovery/activation optimization pattern. The keywords are, however, all tightly scoped to the skill's actual domain (de novo protein binder design) and the skill makes no over-broad claims ('general assistant', 'use me first'), so the real risk of unwanted activation or capability inflation is minimal.
  > **Remediation:** Optionally trim the explicit trigger keyword list to a natural-language description of capabilities; no functional change required since all keywords are domain-accurate.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Missing referenced files (assets/ and templates/ variants)
  > The scan lists several referenced paths under assets/ and templates/ that do not exist in the package. In practice the SKILL.md body only links the three references/*.md files, all of which are present and benign; the assets/ and templates/ entries appear to be path-resolution variants from the scanner rather than genuine broken links. No dangling reference resolves to an external URL or user-controlled location, so there is no transitive-trust risk.
  > File: `SKILL.md`
  > **Remediation:** No action strictly required; confirm all documentation links resolve to files bundled under references/.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Documentation suggests unpinned clone-and-install from GitHub
  > The reference file for pipeline selection documents cloning BindCraft from GitHub at an unpinned HEAD and running its installer shell script with CUDA. This is documentation of the upstream project's own published install procedure (the official MIT-licensed repository cited in the manifest homepage), not code executed by the skill's bundled scripts, and no automated installation occurs. Still, an agent following the docs verbatim would execute a third-party install script without a pinned commit or integrity check.
  > File: `references/bindcraft-and-rfdiffusion.md`
  > **Remediation:** Pin a specific release tag or commit SHA when documenting the clone, and note that the install script should be reviewed before execution. Consider instructing the agent to request user confirmation before any install step.

### pytdc — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Remote dataset and model-checkpoint downloads (pickled artifacts) from third-party hosts
  > The skill directs the agent to install PyTDC and, when explicitly approved, construct loaders and oracles that download datasets, benchmark archives, and serialized model checkpoints (DRD2/GSK3B/JNK3/CYP3A4_Veith/fpscores) from Harvard Dataverse and other upstream services. Loading serialized model artifacts from a remote source is an inherent supply-chain/deserialization risk. Mitigating factors are strong: package versions are pinned (PyTDC==1.1.15, setuptools==80.9.0), a --dry-run is recommended, no checksum-less silent download occurs (both --execute and --download acknowledgement flags are required), docking/remote-service/synthesis oracles are explicitly refused, and the SKILL.md documents that PyTDC provides no dataset-wide checksum manifest.
  > File: `SKILL.md`
  > **Remediation:** Keep the explicit --execute/--download approval gates, and where possible record and verify checksums of downloaded dataset/checkpoint artifacts before loading them; consider documenting that checkpoint files are deserialized by upstream code.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Several referenced files are absent from the package
  > The instruction/reference set resolves to files such as assets/*.md, templates/*.md and tdc.py that are not present in the package. Only references/datasets.md, references/utilities.md, references/sources.md and references/oracles.md exist. Missing referenced resources are a documentation hygiene issue and could cause the agent to search for or fabricate content, but no malicious behavior is implied here (the actually-referenced reference files are bundled internally and benign).
  > File: `references/utilities.md`
  > **Remediation:** Ensure all referenced paths exist within the package or remove stale references.

### retrosynthesis — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-laden activation description
  > The frontmatter description ends with an explicit trigger-keyword list ('Also trigger on AiZynthFinder, retrosynthetic tree search, synthetic accessibility, SAscore, RAscore, building-block stock, reaction template, or route scoring'). All listed keywords are tightly scoped to the skill's genuine domain (retrosynthesis/cheminformatics), so this is not capability inflation or brand impersonation — it is noted only as an informational observation about discovery-surface broadening.
  > **Remediation:** Optional: trim the explicit trigger-keyword list to a natural-language description to avoid over-activation; no security impact as the keywords match the actual functionality.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instruction
  > The SKILL.md and reference documentation instruct the user to run `pip install aizynthfinder` and `download_public_data <dir>` without a pinned version or hash. While the package is a well-known open-source project (MolecularAI/AstraZeneca, MIT) and the docs state 'Checked against 4.4.1', installing without a pin leaves a small supply-chain surface (e.g., a compromised future release). The download of several GB of model/stock data from a remote source is also implicitly trusted. No automated execution of these commands occurs in the bundled scripts; they are documentation only.
  > File: `SKILL.md`
  > **Remediation:** Recommend a pinned version (e.g., `pip install aizynthfinder==4.4.1`) and note that model/stock downloads come from the upstream project; verify checksums where available.

### rowan — 🔵 LOW

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation instruction
  > The skill instructs the agent to run `uv pip install rowan-python` without a pinned version or integrity verification. If the agent executes this via Bash (which is in allowed-tools), it installs whatever version is current from PyPI, creating a minor supply-chain risk (version drift or a compromised upstream release). The package name matches the vendor's official client and there are no typosquatting or untrusted-repo indicators.
  > **Remediation:** Pin an explicit version (e.g., `uv pip install rowan-python==X.Y.Z`) and, ideally, verify hashes or install into an isolated virtual environment.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Documentation patterns that print secrets and embed API keys inline
  > Example code in the skill prints webhook secret values to stdout (`print(f"Secret key: {secret.secret}")`, `print(f"New secret created...: {new_secret.secret}")`) and shows assigning the API key directly in source (`rowan.api_key = "your_api_key_here"`). These are placeholders — no real credentials are hardcoded and no data is sent to third-party endpoints — but if copied verbatim by the agent, secrets could be written into terminal logs, transcripts, or source files.
  > File: `SKILL.md`
  > **Remediation:** Prefer the documented ROWAN_API_KEY environment variable exclusively, and avoid printing secret material; mask or omit secret values in example output.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Metered cloud compute usage without explicit user-confirmation guidance
  > The skill encourages batch submission of large compound libraries and long-running cloud workflows to a commercial, metered service (credits are billed per compute minute). While the manifest's compatibility field notes cost implications, the instruction body does not require user confirmation before submitting large batches, so an agent could consume a substantial amount of the user's paid credits autonomously. This is a cost/resource-consumption concern rather than a malicious pattern.
  > File: `references/access_and_pricing.md`
  > **Remediation:** Add explicit guidance to confirm with the user before submitting batches above a small threshold and to report estimated credit cost prior to submission.

### rdkit — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Explicit activation-trigger keyword list in skill description
  > The YAML description ends with an explicit trigger directive: 'Also trigger on rdkit, Chem.MolFromSmiles, rdFingerprintGenerator, SDMolSupplier, SMARTS query, ETKDG, or FilterCatalog.' This is discovery-channel keyword baiting intended to raise activation frequency. In this case the keywords are tightly scoped to the skill's genuine domain (RDKit cheminformatics) and are not over-broad ('general assistant', 'use me first'), so the practical risk is minimal. It also cross-references other skills (datamol, medchem, molfeat, chembl) for routing, which is informational rather than privilege-seeking.
  > **Remediation:** Optional: describe capabilities in prose and let the host runtime handle matching, rather than embedding an explicit trigger-keyword list in the description.

- **🔵 LOW** `LLM_SUPPLY_CHAIN_ATTACK` — Unpinned dependency installation guidance
  > The skill instructs the agent to install RDKit via `uv pip install rdkit` and `conda create -c conda-forge -n my-rdkit-env rdkit` with no version pin, despite documenting version-sensitive behavior changes (canonical SMILES/stereo changes in 2026.03, descriptor SMARTS corrections in 2024.09). Unpinned installs from a public index are a minor supply-chain exposure and can also produce silently different numeric results. The package names used are the correct upstream ones (no typosquatting indicators), and the skill correctly distinguishes `rdkit` from the legacy `rdkit-pypi` name.
  > **Remediation:** Pin an exact version (e.g. `uv pip install rdkit==2026.3.5`) in the documented install commands, consistent with the skill's own 'pin RDKit versions' guidance.

- **🔵 LOW** `LLM_HARMFUL_CONTENT` — Help text mislabels a five-motif pattern set as a PAINS filter
  > The argparse epilog of substructure_filter.py contains the example '# Remove PAINS' applied to the five-entry 'reactive-groups' library, and references/smarts_patterns.md has a section headed 'Toxicity Alerts (PAINS)' listing six patterns. Both the SKILL.md body and an in-code comment explicitly warn that this is NOT the 480-filter Baell & Holloway PAINS set and direct users to RDKit FilterCatalog / the medchem skill, so the skill largely self-corrects. The residual risk is scientific/decision-quality (a caller could report a library 'PAINS-clean' after testing a tiny fraction of the alert set), not a security compromise.
  > File: `references/smarts_patterns.md`
  > **Remediation:** Rename the example to 'Remove common frequent-hitter motifs' and retitle the reference section to avoid implying full PAINS coverage; point to FilterCatalogParams.FilterCatalogs.PAINS for the authoritative set.

### target-safety — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Keyword-bait trigger list in skill description
  > The YAML description ends with an explicit activation-trigger keyword list ('Also trigger on gnomAD, LOEUF, pLI, loss-of-function intolerance, mutational constraint, GWAS Catalog, credible set, human knockout, genetic support, or target safety dossier'). While the keywords are all genuinely in-scope for the skill's stated genetics purpose and do not impersonate other tools or claim general-purpose capability, enumerating trigger terms is a discovery-surface optimisation that can increase unintended activation.
  > **Remediation:** Describe capabilities functionally and remove the explicit trigger-keyword enumeration; rely on semantic matching of the description.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — API endpoints overridable via environment variables and CLI flags
  > Both API base URLs are read from the environment (GNOMAD_API_URL, GWAS_API_URL) and can also be overridden with --gnomad-url / --gwas-url. A poisoned environment or a crafted command line could point the clients at an attacker-controlled host, sending gene-symbol queries there and returning attacker-controlled JSON that is then summarised by the agent. Impact is low because no credentials, local file contents, or secrets are transmitted (only gene symbols) and no response content is executed, but it is an unvalidated network destination.
  > File: `scripts/_common.py`
  > **Remediation:** Validate overridden URLs against an allowlist of expected hosts (or require an explicit opt-in flag), and enforce HTTPS, before issuing requests.

- **🔵 LOW** `LLM_RESOURCE_ABUSE` — Generous timeouts with exponential backoff and multi-page walks
  > The HTTP clients use a 120-second timeout, up to 4 attempts with exponential backoff (capped at 30 s per sleep), and gwas_paged() walks pages until totalPages is reached. Invoking the scripts with many gene symbols or a large --limit against a slow endpoint could consume substantial wall-clock time. Mitigations are present (per-gene --limit defaults of 100-200, MAX_PAGE_SIZE cap, bounded retries), so this is informational rather than a true DoS primitive.
  > File: `scripts/_common.py`
  > **Remediation:** Add an overall wall-clock budget across the symbol loop and document expected runtime for multi-gene invocations.

### uniprot-rcsb — 🔵 LOW

- **🔵 LOW** `LLM_SKILL_DISCOVERY_ABUSE` — Trigger-keyword enumeration in skill description
  > The frontmatter description ends with an explicit activation-trigger list ('Also trigger on UniProt accessions, PDB ids, rest.uniprot.org, search.rcsb.org, files.rcsb.org, alphafold.ebi.ac.uk, id mapping, SEQRES, or missing residues.'). This is keyword baiting that broadens discovery/activation. In this case all keywords are tightly scoped to the skill's actual domain (UniProt/RCSB/AlphaFold retrieval), so the inflation risk is minimal and the claims match the implemented functionality, but it is worth noting as an activation-surface consideration.
  > **Remediation:** Optional: trim the explicit trigger-word list to a concise natural-language description of capability to avoid over-activation on unrelated prompts.

- **🔵 LOW** `LLM_DATA_EXFILTRATION` — Service-supplied URLs and filenames used for local file writes
  > fetch_structure.py downloads files whose URLs come from the AlphaFold API response body (cifUrl, pdbUrl, paeDocUrl) and derives the output filename with Path(url).name. If the upstream service were compromised or spoofed (e.g., DNS/MITM), the URL could point off-domain and the written filename is partly attacker-influenced. Risk is low: the request layer is HTTPS-only to well-known public endpoints, Path(url).name strips directory components (preventing traversal), downloads are size-capped at 256 MB, and files are written only under the user-specified --out-dir. Content is never executed or interpreted as instructions.
  > File: `scripts/fetch_structure.py`
  > **Remediation:** Validate that service-returned URLs match an allow-list of expected hosts (alphafold.ebi.ac.uk) and sanitize the derived filename against an expected pattern before writing to disk.
