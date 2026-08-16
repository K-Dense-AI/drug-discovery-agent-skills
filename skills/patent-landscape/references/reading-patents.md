# Reading a chemical patent

Judgement, not syntax. **Nothing in this skill is legal advice**, and the gap between what a
structure search can tell you and what a freedom-to-operate opinion requires is very wide.

## Claims are the patent

A patent document has a description, examples, figures, and claims. **Only the claims define the
legal monopoly.** The description supports and enables them; it does not itself exclude anyone
from anything.

This is why the `field` column in SureChEMBL's mapping table matters so much. A compound extracted
from the claims is claimed. A compound extracted from the description may be:

- prior art the applicant is distinguishing themselves from,
- a comparator from a competitor,
- a starting material or reagent,
- an intermediate,
- or a compound they chose not to claim.

Treating every extracted compound as "covered by this patent" is the most common misreading of
patent-derived chemical data.

## Markush structures, and why structure search under-reports

Chemical patents claim **genus** structures — a scaffold with variable positions defined by lists
or classes:

> A compound of formula (I), wherein R¹ is C₁–C₆ alkyl, halogen, or CN; R² is …

A single Markush claim can cover billions of specific compounds. SureChEMBL extracts the **specific
examples**, not the enumerated genus.

So a structure search returning no hits means *this exact structure was not disclosed as an
example*. It does not mean the structure falls outside every claim, and for a novel analogue of a
known series the opposite is usually true — that is exactly what a Markush claim is for.

**Markush search is a specialist capability.** Reaxys, SciFinder, and Derwent implement it and it
is a substantial reason those subscriptions exist. No free source does.

## Two different questions

**Novelty** — "has this been disclosed before?" — determines whether *you* can patent it. Prior
art is anything published anywhere, including papers, posters, and your own abstract. A structure
search over SureChEMBL genuinely helps here.

**Freedom to operate** — "can I sell this without infringing?" — determines whether you can
commercialise. It requires reading the claims of every in-force patent in every jurisdiction you
intend to sell in, and construing them against your product. A structure search does not answer
this and cannot.

The two are independent. A compound can be novel and infringing (it falls inside someone's genus
claim while being a new specific compound), or old and non-infringing (disclosed long ago, all
patents expired).

## Dates that matter

**Priority date** — the earliest filing establishing the invention date. This is the date that
matters for prior art, and what a patent is measured against.

**Publication date** — 18 months after priority. Before this the application is secret, so the
last 18 months are invisible in every database.

**Grant date** — when the claims become enforceable. Grant claims are frequently narrower than
filed claims, so reading the application and assuming its scope was granted overestimates the
monopoly.

**Expiry** — nominally 20 years from filing, adjusted by term extensions (patent term
adjustment/extension, SPCs in Europe) and by whether renewal fees were paid. A patent can lapse
early. **Legal status is not in SureChEMBL and must be checked in EPO OPS or a national register.**

## Families

One invention filed in fifteen countries is one **family** with fifteen members. Counting members
as separate patents inflates a landscape by an order of magnitude, and it is the commonest error
in a naive assignee count.

Conversely, a family's *geographic* spread is a real signal: filing in twenty countries is
expensive, and companies do it for assets they believe in.

## The patent-thicket picture

Around a successful drug there is rarely one patent. There is a composition-of-matter patent, then
patents on salts, polymorphs, formulations, methods of use for each indication, manufacturing
processes, and combinations. Each has its own expiry.

For competitive work this means "the compound patent expires in 2029" is usually not when generics
arrive. And for your own programme it means composition of matter is necessary but not the whole
strategy.

## What to say when reporting

State the source and its coverage explicitly — "SureChEMBL, US/EP/WO/JP structure extraction,
release 2026-08-04". Say which document field a compound was found in. Say that Markush claims are
not enumerated and that the search therefore under-reports coverage. Note the 18-month publication
lag. Give family counts rather than document counts where you can.

Never write "this compound is free to use" or "this is not patented". Write "no exact structure
match in SureChEMBL release X; this does not address Markush claims, unpublished applications, or
claim construction, and is not a freedom-to-operate assessment."

## When to stop and get help

Any decision with money attached. A structure search is a screening step to decide whether to ask
a patent attorney, and the cost asymmetry is stark: an FTO opinion costs a few tens of thousands;
launching into an infringement costs the programme.

Use this skill to find out whether there is something to worry about. Use a professional to find
out whether you should worry.
