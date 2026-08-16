# REINVENT 4 configuration

REINVENT 4 is AstraZeneca's open-source generative framework. Apache-2.0,
<https://github.com/MolecularAI/REINVENT4>. Current release v4.8 (June 2026).

**Not on PyPI.** Install from the repository:

```bash
git clone https://github.com/MolecularAI/REINVENT4.git
cd REINVENT4 && pip install -e .
```

Priors ship with the repository under `priors/`. An NVIDIA GPU is effectively required for
reinforcement learning; sampling from a prior runs acceptably on CPU.

## Four generators, four jobs

| Generator | Input | Job |
|---|---|---|
| **Reinvent** | none | de novo generation from scratch |
| **LibInvent** | scaffold with `[*]` points | decorate a fixed core with R-groups |
| **LinkInvent** | two warheads, one `[*]` each | design a linker between fragments |
| **Mol2Mol** | starting SMILES | generate analogues within a similarity regime |

Pairing the wrong prior with the wrong input fails late and confusingly, which is why
`reinvent_config.py` validates the combination before writing anything.

**Attachment points are `[*]` and they are mandatory.** A LibInvent scaffold without one has
nothing to decorate; a LinkInvent warhead needs exactly one each.

Mol2Mol ships several priors that set how far it may travel from the input:

```
mol2mol_similarity.prior          conservative analogues
mol2mol_medium_similarity.prior
mol2mol_high_similarity.prior     very close analogues
mol2mol_mmp.prior                 matched-molecular-pair style single changes
mol2mol_scaffold.prior            scaffold hopping
mol2mol_scaffold_generic.prior    aggressive scaffold hopping
```

Choosing between them *is* choosing how novel the output will be. There is no separate
"novelty" dial.

## Run types

| `run_type` | Does |
|---|---|
| `sampling` | draw from a model; **ignores any scoring function** |
| `scoring` | score existing molecules; generates nothing |
| `transfer_learning` | fine-tune a prior on your own set |
| `staged_learning` | reinforcement learning against a scoring function |

**`sampling` ignoring the scoring function is the single most common confusion.** If a run
"ignores the objective", check `run_type` first.

## The staged_learning configuration

```toml
run_type = "staged_learning"
device = "cuda:0"

[parameters]
prior_file = "priors/reinvent.prior"
agent_file = "priors/reinvent.prior"
summary_csv_prefix = "run"
batch_size = 64
use_checkpoint = false

[learning_strategy]
type = "dap"
sigma = 128
rate = 0.0001

[diversity_filter]
type = "IdenticalMurckoScaffold"
bucket_size = 25
minscore = 0.4

[[stage]]
chkpt_file = "run_stage1.chkpt"
termination = "simple"
max_score = 0.6
min_steps = 25
max_steps = 300

[stage.scoring]
type = "geometric_mean"
# ... components
```

### prior versus agent

They start as the same file and must not stay so. The **agent** is updated by the optimisation;
the **prior** stays fixed and acts as a likelihood anchor, penalising the agent for drifting into
regions the prior considers unrealistic. That anchor is what keeps output looking like chemistry.

Across stages, the agent should load the previous stage's checkpoint while the prior stays put.

### sigma

Controls how hard the agent is pushed away from the prior. The default of 128 is a reasonable
start.

- **Too high** — the agent collapses onto degenerate high-scoring molecules and stops resembling
  chemistry.
- **Too low** — the agent barely moves and the run is expensive sampling.

If output looks unrealistic, lower sigma before touching anything else.

### Learning strategies

`dap` (differentiable augmented posterior) is the default and the usual choice. `mauli`,
`mascof`, and `sdap` are alternatives from the earlier literature.

### Diversity filters — do not omit

```toml
[diversity_filter]
type = "IdenticalMurckoScaffold"
bucket_size = 25
minscore = 0.4
```

Once a scaffold accumulates `bucket_size` molecules scoring above `minscore`, further examples are
penalised. **Without this the agent will converge onto one scaffold**, because having found
something that scores well, decorating it is the cheapest way to keep scoring well.

Options: `IdenticalMurckoScaffold`, `IdenticalTopologicalScaffold`, `ScaffoldSimilarity`.

### Staging

Multiple `[[stage]]` blocks run in sequence, each with its own scoring function and termination.
This is curriculum learning: start with a permissive objective (be drug-like), then tighten
(be drug-like *and* dock well). Going straight to the hard objective often fails because early
random molecules all score zero and there is no gradient to follow.

## Output

`summary_csv_prefix` produces a CSV per stage with SMILES, total score, per-component scores, and
step number. `parse_run.py` reads it.

The score column tells you whether the objective was satisfied. It cannot tell you whether the
run collapsed — for that you need the count of distinct scaffolds, which is why
`parse_run.py summary` reports both together.
