---
name: generative-design
description: Generate and optimise novel small molecules with REINVENT 4 — de novo sampling from a chemical language model, scaffold decoration with LibInvent, fragment linking with LinkInvent, and similarity-constrained analogue generation with Mol2Mol. Use this skill to set up reinforcement-learning or curriculum runs, compose a multi-parameter scoring function from docking scores, predictive models, and physicochemical desirability, and read the resulting sampled sets. Also trigger on REINVENT, LibInvent, LinkInvent, Mol2Mol, scaffold hopping, R-group replacement, linker design, chemical language model, or reinforcement-learning molecule optimisation.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+. The bundled scripts build REINVENT TOML configuration and parse sampled CSV output using only the standard library. Running a generation job needs REINVENT 4 installed from github.com/MolecularAI/REINVENT4 (not on PyPI, Apache-2.0) with its model priors, and an NVIDIA GPU for practical reinforcement-learning throughput.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "🧪"
    homepage: https://github.com/MolecularAI/REINVENT4
  hermes:
    category: research
---

# Generative Molecular Design

The Design half of design-make-test-analyse. REINVENT 4 turns a scoring function into molecules —
de novo, or by decorating a scaffold, linking two fragments, or transforming a known active. It is
the most capable open-source generative framework in medicinal chemistry, and it will optimise
exactly what you ask for, including the parts you did not mean.

**Tool:** [REINVENT 4](https://github.com/MolecularAI/REINVENT4) v4.8, Apache-2.0.
**Not on PyPI** — `git clone` and `pip install -e .`. Priors ship with the repository. An NVIDIA
GPU is effectively required for reinforcement learning.
**Checked against:** v4.8, June 2026.

Read [references/reinvent-configuration.md](references/reinvent-configuration.md) before writing a
run file, [references/scoring-functions.md](references/scoring-functions.md) before defining an
objective, and
[references/evaluating-generated-molecules.md](references/evaluating-generated-molecules.md)
before believing the output — **that one is judgement, not syntax.**

## The three scripts

| Script | Answers |
|---|---|
| `reinvent_config.py` | Which generator, which prior, and what does the run file look like? |
| `scoring_profile.py` | What am I actually asking the model to optimise? |
| `parse_run.py` | Did the run produce distinct, useful molecules — or one scaffold a thousand times? |

## The scoring function is the experiment

The model does not know what you meant. Everything it produces is a literal consequence of the
objective, and unbounded rewards get exploited without exception:

| Reward | What the agent returns |
|---|---|
| logP, unbounded | long greasy alkyl chains |
| molecular weight upward | 900 Da molecules that satisfy nothing else |
| similarity to one reference | the reference, regenerated forever |
| a docking score | molecules exploiting that scoring function's blind spots |

So every numeric component gets a **window**, not a direction. Most properties have a desirable
range — molecular weight should be 250–500, not "as low as possible" — which is what
`double_sigmoid` is for. A `reverse_sigmoid` on molecular weight optimises toward methane.

```bash
python skills/generative-design/scripts/scoring_profile.py profile --objective cns
```

```toml
[stage.scoring]
type = "geometric_mean"

[[stage.scoring.component]]
[stage.scoring.component.MolecularWeight]
[[stage.scoring.component.MolecularWeight.endpoint]]
name = "MolecularWeight"
weight = 0.15
transform.type = "double_sigmoid"
transform.high = 380.0
transform.low = 200.0
```

**Geometric mean, not arithmetic**, wherever a component is a requirement rather than a
preference: a single zero zeroes the total, which is exactly what you want from `custom_alerts`.
Without that alerts component the agent rediscovers reactive and PAINS-like chemistry, because
those substructures score well on everything else.

## Four generators, and matching the input to the prior

```bash
python skills/generative-design/scripts/reinvent_config.py generators
```

| Generator | Input | Job |
|---|---|---|
| Reinvent | none | de novo from scratch |
| LibInvent | scaffold with `[*]` | decorate a core with R-groups |
| LinkInvent | two warheads, one `[*]` each | design a linker |
| Mol2Mol | starting SMILES | analogues, at a similarity set by the prior |

Attachment points are mandatory and the script refuses without them:

```
$ reinvent_config.py staged --generator libinvent --scaffold "c1ccccc1"
error: the scaffold has no [*] attachment point. LibInvent decorates at [*];
without one there is nothing to decorate.
```

**`sampling` ignores the scoring function entirely** — it draws from the prior. If a run seems to
ignore its objective, check `run_type` before anything else. Optimisation is `staged_learning`.

Mol2Mol's choice of prior *is* the novelty dial: `mol2mol_similarity` gives conservative
analogues, `mol2mol_scaffold_generic` hops aggressively. There is no separate setting.

## Mode collapse looks exactly like success

The default failure. The agent finds one scaffold that scores well and decorates it forever; the
score curve rises smoothly and the run looks like it worked.

```bash
python skills/generative-design/scripts/parse_run.py summary --csv run_1.csv
```

```
# 60 rows -> 60 distinct (0 duplicates)
# MODE COLLAPSE: only 2 ring systems across 60 molecules (3.3%). The agent has
# found one core it can decorate. Add a diversity filter, lower sigma, or shorten the run.
```

The score column cannot show this; the scaffold count can. **Always set a diversity filter** —
without one, having found something that scores well, decorating it is the cheapest way to keep
scoring well.

`sigma` is the other dial: too high and the agent collapses onto degenerate high scorers, too low
and it barely moves from the prior. If output stops looking like chemistry, lower sigma first.

## Four ways generative runs mislead

1. **Nothing in the default objective knows what can be made.** The harder you optimise, the
   further into unsynthesisable space the agent goes. Add an SA-score component, and check the
   output with `retrosynthesis`.
2. **Validating with the scoring function is circular.** If a docking score was in the objective,
   the output scores well on it by construction. Assess with something the optimiser never saw.
3. **Novelty is not automatically good.** A molecule absent from ChEMBL may be absent because
   nobody wanted it.
4. **Uniqueness is far below the generated count.** "50 000 generated" is usually a few thousand
   distinct.

## When to stop and look

Fifty structures, by eye, will reveal a reward hack that no metric does. Absurdity is not a
computable property, and this step is not optional.

## Composing with the rest of the bundle

- `chembl` → before: actives to seed Mol2Mol or to fit a potency model for the objective.
- `binding-site-analysis` → before: is there a pocket worth designing into?
- `medchem` → after: alerts and PAINS on the output, as a check on the alerts component.
- `retrosynthesis` → after: can any of these actually be made?
- `admet-prediction` → after: developability across the survivors.
- `autodock-vina` / `free-energy-perturbation` → after: an orthogonal score the agent never saw.

## Reporting results honestly

Give the number generated, distinct, and distinct-by-scaffold — not just the first. Quote the
scoring function in full, because the output is a function of it, and say whether a diversity
filter was used. Confirm that any post-hoc assessment used a method absent from the objective. And
report how many molecules a human actually looked at.
