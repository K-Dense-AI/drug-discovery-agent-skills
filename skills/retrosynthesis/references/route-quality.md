# Reading a route

Judgement, not syntax. "Solved" is a binary flag over a stock file. Whether a route is worth
running is a different question and the software does not answer it.

## Solved is not the same as makeable

Three separate things:

| | Means |
|---|---|
| **Solved** | a complete tree exists whose leaves are all in your stock file |
| **Feasible** | the proposed reactions would actually work on *these* substrates |
| **Practical** | a chemist would run it, at the scale and timeline you need |

AiZynthFinder answers the first. It approximates the second with a filter policy trained on
reactions that did and did not work. It says nothing about the third.

The templates come from reactions that worked on *other* substrates. Nothing in the search knows
about your molecule's chemoselectivity, its need for protecting groups, whether the amine you are
acylating is the one you meant, or whether the sequence survives scale-up.

## What a chemist reads

**Step count.** Yield compounds multiplicatively — five steps at 70% is 17% overall. Anything past
about six steps is rarely run as proposed. `route_report.py` flags these.

**Convergent versus linear.** A convergent route builds two halves separately and joins them late;
a linear route carries every atom through every step. For the same step count, convergent is
dramatically better: overall yield depends on the longest linear sequence, not the total. Read the
tree shape, not just its depth.

**Number of distinct starting materials.** Fewer is better — fewer orders, fewer lead times, fewer
things to go wrong. `route_report.py routes` reports it beside step count.

**Where the disconnections are.** A route that disconnects the scaffold early and decorates late
allows analogues from a common intermediate. A route that installs the variable group first
requires a full resynthesis per analogue. **For a lead-optimisation series this matters more than
the step count**, because you are not making one molecule, you are making forty.

**Shared intermediates across the series.** If twenty targets converge on three intermediates, the
campaign is cheap. `route_report.py blocks` counts how many routes use each starting material for
exactly this reason.

## What unsolved means

Not "unmakeable". It means no route was found **within the time and depth limits, using these
templates, terminating in this stock**. Four distinct fixes, and identifying which applies is the
useful step:

1. **Raise `time_limit` or `iteration_limit`** — the search ran out of budget.
2. **Raise `max_transforms`** — a route exists but is deeper than allowed.
3. **Broaden the stock** — the route exists but its leaves are not in your file.
4. **Accept the model's blind spot** — the chemistry is not in USPTO templates.

The last case is real and systematic. Template-based models only know reactions that appear in
their training corpus, so genuinely novel chemistry, recently developed methodology, and
specialist transformations (photoredox, electrochemistry, enzymatic steps) are largely invisible.
An unsolved target may need a chemist, not a bigger budget.

## Where these tools are strong and weak

**Strong**: ordinary medicinal-chemistry scaffolds assembled from common reactions — amide
couplings, Suzukis, SNAr, reductive aminations, sulfonamides. This is most of what a discovery
programme makes, which is why the tools are useful.

**Weak**: complex natural products, dense stereochemistry, unusual ring systems, macrocycles,
organometallics, and anything requiring a strategic insight rather than a template lookup.

## Using it on a generated library

The main use for this skill: filtering `generative-design` output, where nothing in the objective
knew whether a molecule could be made.

A workable protocol:

1. **Cheap pre-filter** with SA-score or RAscore across everything — milliseconds per molecule.
2. **Full route search** on the survivors, with `--nproc` and a modest `time_limit`. At 60 s per
   target on 8 processes, a thousand molecules is about two hours.
3. **Read the routes** for the handful you intend to make. Solved fraction is a triage statistic;
   the individual route is what gets run.

Do not skip step 3. A solved fraction of 80% across a library says the library is reasonable; it
says nothing about the specific compound you are about to order.

## Reporting

Always name the stock. Give solved fraction *and* median step count — a library that is 90% solved
at nine steps each is worse than one 60% solved at three. Say what the time and depth limits were,
since unsolved is partly a statement about them. And say plainly that a proposed route is a
hypothesis a chemist has not yet reviewed.
