---
name: retrosynthesis
description: Plan synthetic routes and judge whether a proposed molecule can actually be made, using AiZynthFinder's Monte-Carlo tree search over template-derived reactions and a purchasable building-block stock. Use this skill to configure expansion and filter policies, choose a stock file, run route search over a candidate set, and read the returned trees — solved fraction, route depth, and which building blocks a route bottoms out in. Also trigger on AiZynthFinder, retrosynthetic tree search, synthetic accessibility, SAscore, RAscore, building-block stock, reaction template, or route scoring.
license: MIT
allowed-tools: Read Write Edit Bash
compatibility: Requires Python 3.10+. The bundled scripts write AiZynthFinder YAML configuration and parse its route JSON using only the standard library. Running a search needs aizynthfinder 4.4+ (pip, Python >=3.10 and <3.13, MIT) plus its downloaded policy models and a stock file; CPU is sufficient, though a GPU speeds up the expansion policy.
metadata:
  version: "1.0"
  skill-author: K-Dense Inc.
  openclaw:
    emoji: "⚗️"
    homepage: https://github.com/MolecularAI/aizynthfinder
  hermes:
    category: research
---

# Retrosynthetic Planning

The Make half of design-make-test-analyse, and the check that a proposed molecule is more than a
picture. AiZynthFinder runs Monte Carlo tree search over reaction templates until every leaf of a
route is something you can buy.

**Tool:** [AiZynthFinder](https://github.com/MolecularAI/aizynthfinder) 4.4.1, MIT.
`pip install aizynthfinder` — **Python 3.10–3.12 only, it will not install on 3.13**. Then
`download_public_data <dir>` for models and a ZINC stock (several GB). CPU is sufficient.
**Checked against:** 4.4.1, December 2025.

Read [references/aizynthfinder-setup.md](references/aizynthfinder-setup.md) before your first run,
[references/synthesizability-scores.md](references/synthesizability-scores.md) when triaging more
molecules than you can search, and [references/route-quality.md](references/route-quality.md)
before acting on a route — **that one is judgement, not syntax.**

## The two scripts

| Script | Answers |
|---|---|
| `aizynth_config.py` | What does the config look like, and are the model files really there? |
| `route_report.py` | What fraction is makeable, in how many steps, from what? |

## The stock file is the answer

This is the thing to get right. A target is **solved** when every leaf of a route is in your stock
file — so "solved" is a statement about the stock at least as much as about the molecule.

| Stock | Solved fraction |
|---|---|
| small in-house inventory | low; reflects what you can start today |
| ZINC (the default download) | moderate; a public baseline |
| eMolecules / commercial | high |
| Enamine building blocks | high; what a REAL-space campaign should use |

**A solved fraction quoted without naming the stock is meaningless** — the same molecule is solved
against eMolecules and unsolved against a cupboard. `route_report.py` says so on every run.

## Configuration changed at version 4

Version 3 took bare lists of file paths; version 4 takes typed blocks. Every tutorial older than
2024 shows the incompatible form, and the resulting error is unhelpful.

```bash
python skills/retrosynthesis/scripts/aizynth_config.py config \
    --model uspto_model.onnx --templates uspto_templates.csv.gz \
    --filter-model uspto_filter_model.onnx --stock zinc:zinc_stock.hdf5 > config.yml
python skills/retrosynthesis/scripts/aizynth_config.py check --config config.yml
```

```yaml
expansion:
  uspto:
    type: template-based
    model: uspto_model.onnx
    template: uspto_templates.csv.gz
```

`check` verifies every referenced file exists, because AiZynthFinder discovers a missing model
*after* the run starts. It also warns when a config looks like the version-3 form.

**Always set a filter policy.** Without one the search proposes reactions the expansion model
likes but that do not work, and the solved fraction stops measuring anything.

## Budget before you start

`time_limit` is **per target**. At the 120 s default, ten molecules is twenty minutes and ten
thousand is nearly two weeks. Use `aizynthcli --nproc 8` to parallelise across targets.

## Reading the result

```bash
python skills/retrosynthesis/scripts/route_report.py summary --output out.json.gz
python skills/retrosynthesis/scripts/route_report.py routes --output out.json.gz
```

```
# 1/1 solved (100.0%)
targets       1
solved        1
median_steps  2

target  route  steps  starting_materials  leaves_in_stock  score
TARGET  0      2      3                   3                0.95
```

Step count matters more than existence — yields multiply, so five steps at 70% is 17% overall, and
past about six steps a route is rarely run as written. `route_report.py` flags those.

`blocks` counts how many routes share each starting material. If twenty targets converge on three
intermediates, the campaign is cheap; that is a different and more useful fact than the solved
fraction.

## Unsolved does not mean unmakeable

It means no route was found within the time and depth limits, using these templates, terminating
in this stock. Four distinct fixes, and working out which applies is the useful step: raise the
time limit, raise `max_transforms`, broaden the stock — or accept that the chemistry is not in
USPTO templates.

That last case is systematic. Template models only know reactions in their training corpus, so
novel methodology, photoredox, electrochemistry, and enzymatic steps are largely invisible.

## Four ways this misleads

1. **A solved route is a proposal, not a validated synthesis.** The templates come from reactions
   that worked on *other* substrates; nothing here knows your chemoselectivity or protecting-group
   needs.
2. **Convergent beats linear at equal step count.** Overall yield depends on the longest linear
   sequence, so read the tree shape, not just its depth.
3. **Where the disconnections sit matters more than step count for a series.** A route that
   decorates late gives analogues from a common intermediate; one that installs the variable group
   first needs a full resynthesis each time.
4. **Pre-filtering with RAscore inflates the solved fraction**, because RAscore is trained to
   predict AiZynthFinder's own verdict. Fine as a pipeline, misleading as a statistic — report the
   pre-filter.

## Triage at scale

Route search is seconds to minutes per molecule; scores are microseconds. For a generated library:
SAscore or RAscore across everything, full search on the survivors, and a chemist reading the
routes for the handful you will actually order. The honest hierarchy is
`SAscore < RAscore < route search < a chemist's opinion < the compound in a vial`, and each step
right is more expensive and more real.

## Composing with the rest of the bundle

- `generative-design` → here: the essential check, since nothing in a REINVENT objective knows
  what can be made. Better still, add SAscore as a scoring component during the run.
- `chemical-space` → alongside: if it is already purchasable, you do not need a route.
- `medchem` → before: no point routing molecules that fail structural alerts.
- `admet-prediction` → alongside: makeable and developable are different filters.

## Reporting results honestly

Name the stock, always. Give solved fraction **and** median step count — 90% solved at nine steps
is worse than 60% at three. State the time and depth limits, since unsolved is partly a statement
about them. And say plainly that a proposed route is a hypothesis no chemist has yet reviewed.
