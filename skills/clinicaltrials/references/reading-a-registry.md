# What a registry entry does and does not tell you

This file is judgement, not syntax. The API is easy; the inferences people draw from it are
usually wrong in the same handful of ways.

## A registration is a claim, not a fact

Sponsors submit their own records and update them at their own pace. Nobody verifies that the
trial described is the trial run. `statusVerifiedDate` is the only signal of how stale a record
is, and it is routinely years old.

So: a registry entry is evidence that a sponsor *said* they intended to run a study. It is not
evidence the study ran, finished, enrolled the stated number, or measured what it registered.

## `COMPLETED` is not success

This is the error that matters most. `overallStatus: COMPLETED` means the study reached its
planned end — last visit done, database locked. It carries no information about whether the
intervention worked. A trial that comprehensively failed its primary endpoint completes normally.

The three things people conflate:

| Field | Means |
|---|---|
| `overallStatus: COMPLETED` | the study finished running |
| `hasResults: true` | a results section has been posted to the registry |
| — | whether the primary endpoint was met — **not in the registry at all** |

Even `hasResults: true` gives you tabulated outcome data, not a verdict. You have to read the
numbers against the registered primary endpoint and decide yourself. For most studies the
verdict lives only in a publication, a press release, or nowhere.

## Results posting is patchy and legally complicated

FDAAA 801 and the 2016 Final Rule require results within 12 months of primary completion for most
"applicable clinical trials" of FDA-regulated products. Compliance is materially below 100%,
enforcement has been rare, and the requirement does not reach phase 1 studies, most non-US
trials, or products never submitted to the FDA.

Practical reading: **absence of posted results is weak evidence of anything.** It is most often
administrative. Presence of posted results is a genuine positive signal — someone did the work.

## Termination is the most informative status

`TERMINATED` (started, stopped early), `WITHDRAWN` (never enrolled anyone), and `SUSPENDED`
(paused) come with `whyStopped`, free text, and it is the richest field in the registry.

The reasons partition into completely different facts, and lumping them together destroys the
signal:

- **Futility / no efficacy** — "Preliminary data showed no survival benefit…" This is a real
  negative result about the biology, and often the only public record of it.
- **Toxicity / safety** — a real negative result about the molecule or the class.
- **Slow enrolment** — "recruitment prematurely stopped due to a lack of eligible patients."
  Says nothing about the drug; says a great deal about trial feasibility in that indication, and
  is a direct warning about your own recruitment assumptions.
- **Business** — reprioritisation, a partnership ending, funding. Says nothing about the science.

Checked live: phase 3 pancreatic-cancer studies show an 18.3% stopped rate across a 120-study
sample, with stated reasons spanning all four categories. Read the reasons. Do not count them.

## Registration and reporting biases

**Registration bias.** Registration became a condition of publication in ICMJE journals from
2005 and a legal requirement for many trials from 2007. Anything earlier is patchily represented,
and non-US, industry-internal, and negative studies remain underrepresented throughout.

**Outcome switching.** The registered primary endpoint and the published primary endpoint differ
more often than anyone would like. Comparing the registry record against the eventual paper is
one of the few ways to detect this, and it is a legitimate use of these data.

**Estimated enrolment is aspirational.** At registration everything is `ESTIMATED`. Comparing the
estimate against the final `ACTUAL` is a good feasibility signal in its own right.

## Counting studies is not measuring investment

A sponsor with twenty registrations may have twenty investigator-initiated phase 1s. A sponsor
with two may be running two 800-patient phase 3s. `ct_landscape.py sponsors` reports total
enrolment and the highest phase reached alongside the count for exactly this reason — and even
that misses cost, which scales with indication, duration, and endpoint far more than with
headcount.

Likewise, a rising count of registrations in an indication is as likely to reflect a fashionable
target as a tractable one.

## What to say when reporting

State the query, the sample size actually walked (not the total matched), and the data cut. Say
"N studies are registered", never "N studies show". For a stopped study, quote `whyStopped`
verbatim rather than paraphrasing it into a cause. When someone asks whether a trial succeeded,
say the registry does not record that, and point at `hasResults` and the publication.

## Where to go instead

- **EU CTR / EudraCT** (<https://euclinicaltrials.eu>) for European trials, many of which never
  appear here.
- **ISRCTN**, **ANZCTR**, **ChiCTR**, and the **WHO ICTRP** meta-registry for the rest.
- **`openfda`** in this bundle for what happened after approval.
- The publication itself for whether anything worked.
