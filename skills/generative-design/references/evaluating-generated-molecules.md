# Judging what a generative run produced

Judgement, not syntax. A run always produces molecules. Whether they are worth anything is a
separate question, and the score column cannot answer it.

## The four metrics, and what each hides

**Validity** — the fraction of outputs that parse as molecules. Modern chemical language models
sit above 95%, so this is a smoke test rather than a result. A sudden drop means something is
wrong with the run, not with the chemistry.

**Uniqueness** — distinct SMILES over total generated. Routinely far below 1: the same molecule is
regenerated many times across steps. "50 000 molecules generated" is usually a few thousand.

**Novelty** — the fraction not present in the training set. Here the framing matters: **novelty is
not automatically good.** A molecule absent from ChEMBL may be absent because nobody wanted it. And
for a `mol2mol` similarity run, low novelty is the *intent*.

**Diversity** — usually the count of distinct Bemis-Murcko scaffolds, or mean pairwise Tanimoto
distance. This is the one that detects the characteristic failure.

## Mode collapse looks exactly like success

The default failure mode of reinforcement learning on molecules: the agent finds one scaffold that
scores well and decorates it forever. The score curve rises smoothly. The run looks like it
worked. What you have is a thousand analogues of one compound.

The score cannot show this. The scaffold count can:

```bash
python parse_run.py summary --csv run_1.csv
```

```
# MODE COLLAPSE: only 2 ring systems across 60 molecules (3.3%).
```

Below roughly 5% distinct ring systems, collapse has happened. Fixes, in order: add or tighten a
**diversity filter**, **lower sigma**, **shorten the run** (collapse gets worse with steps), or
**stage the objective** so the agent is not rewarded for over-exploiting one trick early.

The ring-system signature in `parse_run.py` is a crude approximation, not a real Bemis-Murcko
decomposition — that needs a chemistry toolkit. It is sensitive enough to catch collapse and
nothing more; use `rdkit` for proper scaffold analysis.

## The things generative models are actually good at

Being specific about this saves disappointment:

- **Enumerating a design space you have already defined.** LibInvent decorating a scaffold, or
  LinkInvent joining two fragments you know bind, is genuinely useful and reliable.
- **Scaffold hopping** from a known active, via Mol2Mol with a scaffold prior.
- **Multi-parameter optimisation within a series**, where the objective is well specified and the
  chemistry is bounded.
- **Generating ideas at volume** for a human chemist to filter.

## And what they are not

- **Inventing biology.** The model knows nothing about your target beyond what your scoring
  function encodes.
- **Knowing what can be made.** Nothing in a default REINVENT objective is aware of synthetic
  accessibility. This is the single largest practical gap.
- **Predicting potency.** Only as well as the model you plugged into the scoring function.
- **Replacing a chemist.** Output needs filtering by someone who can see that a molecule is
  absurd, and absurdity is not a computable property.

## Synthesisability is the gap that matters most

A generative model will happily produce molecules no one can make. Nothing in the default
components prevents it, and the more aggressively you optimise, the further into
difficult-to-synthesise space the agent goes.

Two options, and doing both is better:

1. **Score it during generation.** Add an SA-score or RAscore component so synthesisability is
   part of the objective rather than an afterthought.
2. **Filter afterwards** with real retrosynthetic planning — `retrosynthesis` in this bundle runs
   AiZynthFinder over the output and reports the solved fraction.

The second is more honest and much slower. A common compromise: cheap SA-score during the run,
full route search on the final few hundred.

## A workable triage of the output

1. **Deduplicate**, then count distinct scaffolds. If collapsed, fix the run rather than the list.
2. **Filter structural alerts and PAINS** — `medchem`.
3. **Check synthesisability** — `retrosynthesis`.
4. **Check purchasability** for anything close to a known compound — `chemical-space`.
5. **Predict ADMET** across the survivors — `admet-prediction`.
6. **Dock or rescore** with a method that was *not* in the scoring function. Optimising against a
   docking score and then validating with the same score is circular.
7. **Look at fifty structures.** This step is not optional and finds things no filter does.

## The circularity trap

If a docking score was in the scoring function, the output will score well on that docking score.
That is not validation, it is a tautology. Any post-hoc assessment must use a method the optimiser
never saw — a different scoring function, a different program, or ideally an assay.

The same applies to a property model. Optimise against your own ADMET model and the output will
satisfy your ADMET model, including wherever it is wrong.

## Reporting

Give the number generated, distinct, and distinct-by-scaffold — not just the first. State the
scoring function in full, because the output is a function of it. Say whether a diversity filter
was used. Report the assessment method and confirm it was not part of the objective. And say how
many were checked by a human, because that number is usually the one that matters.
