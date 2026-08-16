# The scoring function is the experiment

Everything a generative run produces is a consequence of what you asked for. The model does not
know what you meant.

## Components must be transformed to [0, 1]

REINVENT combines component scores on a common scale, so every raw property needs a transform.
Omitting one lets molecular weight — a number in the hundreds — swamp QED, which is in [0, 1].

| Transform | Shape | Use when |
|---|---|---|
| `sigmoid` | rises to 1 above `high` | more is better |
| `reverse_sigmoid` | falls to 0 above `high` | less is better |
| `double_sigmoid` | peaks between `low` and `high` | a target window |
| `left_step` / `right_step` | hard 0/1 | genuinely binary |
| `step` | hard 0/1 at a threshold | rarely — see below |
| `value_mapping` | explicit table | categorical output |

**`double_sigmoid` is the workhorse.** Most physicochemical properties have a desirable *window*,
not a direction: molecular weight should be 250–500, not "as low as possible". A `reverse_sigmoid`
on molecular weight optimises toward methane.

**Avoid `step`.** It gives the optimiser no gradient — a near-miss and a far-miss score identically
— so the agent wanders instead of improving. Use a sigmoid unless the requirement is truly binary.

## Aggregation changes the meaning

```toml
[stage.scoring]
type = "geometric_mean"   # or "arithmetic_mean"
```

- **Geometric mean** — a single zero component zeroes the total. Use when a component is a
  *requirement*: structural alerts, a mandatory substructure, a hard property ceiling.
- **Arithmetic mean** — components trade off. A strong docking score can paper over a failed
  property filter.

Geometric is the safer default. Choose arithmetic deliberately, when you genuinely want trade-offs.

## Reward hacking is the norm, not the exception

A reinforcement-learning agent optimises the literal objective. Every unbounded reward gets
exploited, and the results are often absurd in ways that are obvious afterwards:

- Reward high logP without a ceiling → long greasy alkyl chains.
- Reward molecular weight upward → 900 Da molecules that satisfy nothing else.
- Reward a similarity score to one reference → the reference itself, regenerated forever.
- Reward "number of aromatic rings" → fused polycyclics no one can make.
- Reward a docking score → molecules exploiting the scoring function's known blind spots,
  which giga-scale docking already showed us are high-molecular-weight hydrophobic burial.

Countermeasures, in order of importance:

1. **Bound every component on both sides.** `double_sigmoid` rather than `sigmoid` wherever a
   window exists. `scoring_profile.py` does this by construction.
2. **Include `custom_alerts`.** Without a substructure veto, the agent rediscovers reactive and
   PAINS-like chemistry, because those substructures often score well on everything else.
3. **Add a synthesisability term** — or at minimum check the output with `retrosynthesis`
   afterwards. Nothing in the default components knows whether a molecule can be made.
4. **Use a diversity filter**, so exploitation of one trick is capped.
5. **Look at the molecules.** Fifty structures, by eye, will reveal a hack that no metric does.

## Components worth knowing

**Property components:** `MolecularWeight`, `SlogP`, `TPSA`, `NumHBD`, `NumHBA`, `NumRotBond`,
`NumRings`, `NumAromaticRings`, `NumAtomStereoCenters`, `GraphLength`, `QED`.

**Structure components:** `MatchingSubstructure` (require a SMARTS), `custom_alerts` (veto a list
of SMARTS), `GroupCount`, `TanimotoSimilarity`, `MMP` similarity.

**Model components:** `Qptuna` and `ChemProp` load your own trained models — this is how a real
project brings its own potency or ADMET predictor into the objective. A model trained on your
project's data is far more useful here than any generic property.

**Docking components:** `DockStream` and `Icolos` bridge to docking engines. Powerful and slow:
docking every molecule at every step dominates run time, and it exposes the agent to the scoring
function's artefacts. Common practice is to optimise cheap properties first and dock afterwards, or
dock only in a later stage.

## Weights

Weights are relative within the aggregation. What matters is their ratio, not that they sum to 1.

A useful discipline: give the components you actually care about — potency, the hard safety veto —
most of the weight, and treat physicochemistry as a small set of guardrails. A scoring function
where twelve components each carry weight 1 optimises nothing in particular.

## Profiles in this skill

`scoring_profile.py profile` emits three ready-made objectives:

- **`lead-like`** — MW 250–400, logP 1–3.5, TPSA 40–110, HBD ≤ 3, QED, alerts.
- **`cns`** — tighter: MW 200–380, logP 1.5–3.5, TPSA 20–70, HBD ≤ 2. Reflects the well-known
  CNS-penetration property window.
- **`fragment`** — MW 140–250, logP 0–2.5, few rotatable bonds. For fragment-based starts.

These are starting points to edit, not recommendations. The right scoring function encodes what
your project actually needs, which nobody else can know.

## The honest framing

A scoring function is a hypothesis about what makes a good molecule. The generative model will
satisfy it exactly. If the hypothesis is wrong — if it omits synthesisability, or selectivity, or
the specific liability that kills your series — the output will be confidently, efficiently wrong.

Time spent on the scoring function has a far better return than time spent on the model.
