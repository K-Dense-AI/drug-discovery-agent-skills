# Installing and running AiZynthFinder

AstraZeneca's retrosynthetic planner. MIT, <https://github.com/MolecularAI/aizynthfinder>.
Version 4.4.1 (December 2025), `requires-python >=3.10,<3.13` — **it will not install on 3.13**.

```bash
pip install aizynthfinder
download_public_data /path/to/models     # models + a ZINC stock, several GB
```

CPU is sufficient. A GPU speeds up the expansion policy but the search itself is the bottleneck.

## How it works

Monte Carlo tree search over retrosynthetic disconnections:

1. An **expansion policy** — a neural network over reaction templates extracted from USPTO —
   proposes disconnections for a molecule.
2. A **filter policy** scores whether each proposed reaction is plausible.
3. The search recurses on the precursors.
4. A branch **terminates** when every leaf is in the **stock**.

A target is **solved** when a complete tree exists whose every leaf is purchasable.

Those four pieces are the whole system, and the stock matters more than any of the others.

## The version 4 config schema

Version 3 took bare lists of paths; version 4 takes typed blocks. **Every tutorial older than 2024
shows the incompatible form**, and the error when you use it is unhelpful.

```yaml
expansion:
  uspto:
    type: template-based
    model: uspto_model.onnx
    template: uspto_templates.csv.gz

filter:
  uspto:
    type: quick-filter
    model: uspto_filter_model.onnx

stock:
  zinc:
    type: inchiset
    path: zinc_stock.hdf5

search:
  algorithm: mcts
  time_limit: 120
  iteration_limit: 100
  max_transforms: 6
  return_first: false

post_processing:
  all_routes: true
```

`aizynth_config.py config` writes this, and `aizynth_config.py check` verifies every referenced
file exists — worth doing, because AiZynthFinder discovers a missing model *after* the run starts.

## Search settings that matter

| Setting | Effect |
|---|---|
| `time_limit` | seconds **per target**. Multiply by library size before starting. |
| `iteration_limit` | MCTS iterations per target; the other stopping condition |
| `max_transforms` | maximum route depth. 6 is a reasonable default; higher finds more and mostly finds long routes |
| `return_first` | stop at the first solution. Fast, and gives up route quality |
| `algorithm` | `mcts` (default), `retrostar`, or `dfpn` |

The per-target budget is the thing people get wrong. At the 120 s default, ten molecules is
twenty minutes and ten thousand is nearly two weeks.

## Running

```bash
aizynthcli --config config.yml --smiles targets.smi --output out.json.gz
aizynthcli --config config.yml --smiles targets.smi --output out.json.gz --nproc 8
```

`--nproc` parallelises across targets and is the correct way to scale a library.

## Output

`out.json.gz` holds a `data` block, column-major, one entry per target:

| Column | Meaning |
|---|---|
| `target` | input SMILES |
| `is_solved` | a complete in-stock route was found |
| `search_time` | seconds spent |
| `first_solution_time` | when the first route appeared |
| `number_of_nodes` | tree size explored |
| `top_score` | best route score |
| `number_of_solved_routes` | distinct complete routes |
| `number_of_precursors` / `..._in_stock` | leaf counts |
| `trees` | the route trees themselves |

A route tree alternates `mol` and `reaction` nodes:

```json
{"type": "mol", "smiles": "TARGET", "in_stock": false,
 "children": [{"type": "reaction",
   "children": [{"type": "mol", "smiles": "A", "in_stock": true}, ...]}]}
```

`route_report.py` walks this to get step count, depth, and the leaves.

## The stock is the answer

This is the most consequential setting and the least discussed. "Solved" is defined by the stock
file, so:

| Stock | Effect on solved fraction |
|---|---|
| small in-house inventory | low; reflects what you can start **today** |
| ZINC (the default download) | moderate; a reasonable public baseline |
| eMolecules / commercial | high |
| Enamine building blocks | high; what a REAL-space campaign should use |

**A solved fraction quoted without naming the stock is meaningless.** The same molecule is solved
against eMolecules and unsolved against a cupboard.

## Run a filter policy

Without one, the search proposes reactions the expansion model likes but that do not work, and the
solved fraction stops measuring anything. It is nominally optional and practically required.

## Alternatives

| Tool | Notes |
|---|---|
| **AiZynthFinder** | open source, template-based, fast, well documented |
| **ASKCOS** (MIT) | open source; also predicts forward reactions, so it can prune infeasible routes AiZynthFinder would keep |
| **IBM RXN** | transformer-based, free web API, no templates |
| **Chemical.AI, Spaya, SYNTHIA** | commercial, with expert-curated rules |

AiZynthFinder and ASKCOS are the two open options and they fail differently — running both on your
hard cases is worthwhile. SYNTHIA's hand-coded rules remain notably strong on complex molecules.
