# The two design pipelines

De novo binder design became practical in the last few years. Two approaches dominate, and they
fail differently enough that the choice matters.

## BindCraft

AlphaFold2-guided hallucination with ProteinMPNN sequence redesign. Published in *Nature* (2025),
MIT licensed, <https://github.com/martinpacesa/BindCraft>. Reported experimental success rates of
**10–100%** depending on target, without high-throughput screening.

```bash
git clone https://github.com/martinpacesa/BindCraft.git
cd BindCraft && bash install_bindcraft.sh --cuda 12.4
python bindcraft.py --settings target.json --filters filters.json --advanced advanced.json
```

Needs AlphaFold2 weights and an NVIDIA GPU. A single trajectory is roughly half an hour.

**The distinguishing feature: it co-folds binder and target at every iteration.** Target
flexibility is therefore accounted for, and no known binding site is required — the hotspots guide
it rather than constraining it geometrically.

## RFdiffusion (+ ProteinMPNN + AlphaFold2)

The earlier and still widely used route, in three stages:

1. **RFdiffusion** generates a binder backbone against a fixed target, guided by hotspots.
2. **ProteinMPNN** designs a sequence for that backbone.
3. **AlphaFold2** predicts the complex, and the interface metrics filter the result.

```bash
./scripts/run_inference.py \
  inference.output_prefix=out/binder inference.input_pdb=target.pdb \
  'ppi.hotspot_res=[A45,A47,A52]' \
  'contigmap.contigs=[A1-150/0 70-100]' \
  inference.num_designs=1000
```

The `contigs` string is the design brief: `A1-150` is the fixed target chain, `/0` a chain break,
and `70-100` a binder of that length range to generate.

**The distinguishing weakness: the target is fixed.** Induced fit is invisible to it, so on a
flexible epitope BindCraft usually does better. RFdiffusion in exchange gives explicit control over
binder length, fold, and secondary-structure content.

**RFdiffusion2** improves motif scaffolding; check its current licence terms before commercial use.

## Choosing

| Situation | Pipeline |
|---|---|
| Default, and flexible targets | BindCraft |
| Rigid target, or you want a specific fold | RFdiffusion |
| Scaffolding a known functional motif | RFdiffusion / RFdiffusion2 |
| No GPU | `tamarind` in this bundle runs both in the cloud |

Running both on a hard target is defensible — they fail differently, and designs that survive both
are the most interesting ones.

## Cost, honestly

The number that matters is not GPU-hours per trajectory but **trajectories per ordered design**.
Typically a few percent of trajectories survive the interface filters, so:

```
trajectories = designs_wanted / filter_pass_rate
```

`design_manifest.py plan` does this. Wanting 24 designs at a 3% pass rate means about 800
trajectories — roughly 400 GPU-hours, or four days on four GPUs.

The pass rate is target-dependent and is the hidden cost of the campaign.

## Expression matters more than it should

Small helical binders (50–100 residues, mostly helix) express well in *E. coli*, are soluble, and
are cheap to make. That is why both pipelines produce them by default, and it is a real practical
advantage rather than an aesthetic one.

Designs with long loops, unusual topologies, or many cysteines are harder to express and slower to
test. If a filter survivor looks structurally exotic, budget more time for it.

## What these tools do not do

- **Predict affinity.** The metrics are self-consistency measures.
- **Guarantee specificity.** A binder designed against one target may bind its paralogues; test a
  counter-screen.
- **Design catalysis or allostery.** Binding is the achievement.
- **Handle glycans, membranes, or disorder.** All three are outside the model.
