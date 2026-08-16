# Installing and running Boltz

## Install

```bash
pip install boltz            # 2.2.1; requires Python >=3.10,<3.13
# or, for the development version
pip install git+https://github.com/jwohlwend/boltz.git
```

Weights and the CCD data download on first run to `~/.boltz`, or to `$BOLTZ_CACHE` if set. That
first run therefore takes several extra minutes and a few GB of disk; pre-warm the cache before
timing anything or running in a container.

Boltz-2 weights are released under a permissive licence that allows commercial use — one of the
main reasons to prefer it over AlphaFold3, whose weights are not.

## Hardware

| Complex | Practical minimum |
|---|---|
| Small protein + ligand (< 500 residues) | 16 GB GPU |
| Typical protein–ligand | 24 GB GPU (A10, 3090, 4090, L4) |
| Large complexes (> 1500 tokens) | 40–80 GB (A100, H100) |
| Anything | `--accelerator cpu` runs, at roughly 50–100× the wall time |

Memory scales steeply with token count (residues plus ligand atoms). Out-of-memory is the most
common failure; the mitigations, in order of what to try first: `--subsample_msa` with
`--num_subsampled_msa 512`, lower `--max_parallel_samples`, lower `--diffusion_samples`, trim
the construct to the domain you care about.

## Running

```bash
boltz predict input.yaml \
    --out_dir predictions/ \
    --use_msa_server \
    --use_potentials \
    --diffusion_samples 5 \
    --recycling_steps 3 \
    --output_format mmcif \
    --devices 1
```

`<INPUT_PATH>` may be one YAML or a **directory**, in which case every `.yaml` inside is
predicted — which is how a screen is run.

### Options worth setting

| Option | Default | Set it because |
|---|---|---|
| `--use_msa_server` | off | Auto-generates MSAs via ColabFold. **Sends your sequence to a public server.** |
| `--use_potentials` | off | Inference-time potentials; noticeably better physical plausibility of poses |
| `--diffusion_samples` | 1 | More samples, ranked by confidence. 5 is a reasonable screening default |
| `--recycling_steps` | 3 | 10 with 25 samples reproduces AlphaFold3's settings, at much greater cost |
| `--output_format` | mmcif | `pdb` if a downstream tool insists |
| `--override` | off | Boltz reuses cached predictions in an existing `--out_dir`; without this, changed parameters may silently reuse an old result |
| `--seed`-like reproducibility | — | Diffusion is stochastic; rerunning gives different poses |
| `--affinity_mw_correction` | off | Adds a molecular-weight correction to the affinity value |
| `--sampling_steps_affinity` | 200 | Affinity sampling effort |
| `--diffusion_samples_affinity` | 5 | Affinity ensemble size |
| `--write_full_pae` | off | Needed to judge inter-domain or interface positioning properly |
| `--num_workers` | 2 | Dataloader workers |
| `--accelerator` | gpu | `cpu` works and is very slow |
| `--no_kernels` | off | Disable trifast kernels if they fail to build on your GPU |

**`--override` deserves attention.** Boltz caches by output directory, so re-running with new
parameters into the same directory can return the old prediction. If a change you made appears to
have had no effect, that is the first thing to check.

## Screening efficiently

The MSA is the expensive shared step. For N ligands against one target:

```bash
# 1. one input with the protein only, to build the MSA once
boltz predict target_only.yaml --use_msa_server --out_dir msa_run/

# 2. point every screening input at a precomputed MSA
python screen_library.py --protein-fasta target.fasta --smiles library.smi \
    --out-dir screen/ --affinity --msa-path target.a3m

# 3. predict the whole directory
boltz predict screen/ --out_dir screen/predictions --use_potentials --diffusion_samples 5

# 4. collect
python collect_results.py screen/predictions --out scores.tsv
```

Rough throughput on a 24 GB GPU with a ~350-residue target and a precomputed MSA: a few minutes
per ligand at `--diffusion_samples 5` with affinity. Budget accordingly — this is a hundreds-to-
low-thousands of compounds method, not a million-compound one. For larger libraries, filter with
`autodock-vina` or a fast ML score first and bring the top few thousand here.

## Errors

**`CUDA out of memory`**
See the mitigations above. Note that peak memory occurs during the diffusion samples, so a run
can survive the trunk and die later.

**MSA server timeout or 429**
The public ColabFold server is shared and rate-limited. Precompute MSAs instead, or retry with
backoff. `--msa_server_url` points at your own instance;
`BOLTZ_MSA_USERNAME`/`BOLTZ_MSA_PASSWORD` supply basic auth.

**`ValueError` on the input file**
Almost always the YAML: an unquoted SMILES containing `#` (YAML comment), both `smiles` and
`ccd` on one ligand, a duplicate chain id, or a protein with no `msa` and no `--use_msa_server`.
`make_boltz_yaml.py` avoids all four.

**Affinity is missing from the output**
No `properties: affinity` block, or the binder is not a ligand chain.

**The prediction did not change after editing the input**
Cached. Add `--override` or use a fresh `--out_dir`.

**Poses vary between runs**
Expected — diffusion is stochastic. Use several `--diffusion_samples` and read the
confidence-ranked top pose rather than assuming determinism.

## Related tools

| Tool | Difference |
|---|---|
| **AlphaFold3** | Similar architecture and accuracy; weights are not available for commercial use |
| **Chai-1** | Comparable open cofolding model, no affinity head |
| **Boltz-1** | The earlier version; no affinity module |
| **`diffdock`** (this bundle) | Pose prediction into a *given* receptor structure; no folding, no affinity |
| **`autodock-vina`** (this bundle) | CPU docking into a known site with a physics-style score |
| **`tamarind`** (this bundle) | Runs Boltz and others as a hosted service, if you have no GPU |
