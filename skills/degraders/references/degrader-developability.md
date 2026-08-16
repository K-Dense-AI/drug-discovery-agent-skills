# Making a degrader drug-like

Judgement, not syntax. Degraders live in beyond-rule-of-five space by construction, and almost
every conventional developability heuristic is calibrated for somewhere else.

## Lipinski rejects every PROTAC

A bifunctional degrader is two ligands and a linker: 700–1100 Da, a dozen or more rotatable bonds,
TPSA well past 140. Applying Ro5 to a degrader series discards all of it, including the molecules
that work.

The bRo5 windows this skill applies:

| Property | Window | Failure below | Failure above |
|---|---|---|---|
| MW | 700–1100 | probably not a complete bifunctional | permeability collapses |
| cLogP | 3–7 | too polar to cross a membrane at this size | aggregation, promiscuity, instability |
| TPSA | 150–250 | unusually low; check the molecule is complete | passive permeability essentially lost |
| HBD | 2–6 | soft bound | donors cost the most permeability per unit polarity |
| Rotatable bonds | 8–20 | a degrader has a linker | entropic cost of the ternary complex |
| Heavy atoms | 45–80 | small for a bifunctional | size dominates poor exposure |

**Every window is two-sided.** The failure at the top is as real as the one at the bottom, so
optimising any of these in one direction is wrong. These figures come from surveys of clinical-stage
PROTACs and are conventions to argue with, not laws — `protac_properties.py windows` prints them
with the reasoning attached.

## Permeability is the binding constraint

It is the reason most degraders are not orally available, and it is not captured by TPSA.

Successful oral degraders behave as **molecular chameleons**: polar and soluble in water,
and in a membrane they fold to form intramolecular hydrogen bonds that shield their polarity,
presenting a much smaller effective polar surface. The same molecule has two conformational
populations with very different apparent properties.

Consequences:

- **Static descriptors cannot see this.** A 3D-conformer-dependent property — such as the
  minimum-energy polar surface area computed in a low-dielectric environment — is closer, but
  still a proxy.
- **Measure it.** PAMPA and Caco-2 are the answer, and they are cheap relative to the cost of
  guessing.
- **Chameleonicity can be designed for**, mostly by placing donor–acceptor pairs where they can
  reach each other, and by rigidifying so the folded conformation is accessible.

The macrocyclic peptide field solved a version of this problem before degraders arrived, and the
same principles transfer.

## Rotatable bonds are charged twice

They cost permeability and oral exposure in the usual way. They also cost **entropy on ternary
complex formation** — a floppy linker must be ordered to hold two proteins together, and that
entropic penalty comes straight out of cooperativity.

So rigidification helps both problems at once, and it is the standard second phase of linker
optimisation. The order matters: find the length window with a flexible series first, then
rigidify at the optimum. Rigidifying early locks in a conformation before you know which one you
want.

## PK is not the usual PK

Two departures worth planning around:

**Duration is set by protein resynthesis, not by plasma half-life.** A degrader can be cleared
while its effect persists for days. The standard exposure-response framing — time above a
threshold concentration — does not apply cleanly, and a PK/PD model needs a turnover component for
the protein. See `pkpd-translation` for the machinery, and expect to add a synthesis/degradation
compartment to it.

**Catalytic action decouples exposure from effect.** Because one degrader molecule can destroy
many copies of the target, sub-stoichiometric exposure can be fully efficacious. This is genuinely
favourable, and it means an exposure that looks inadequate by inhibitor standards may be fine.

Against that, the **hook effect puts a ceiling on the useful concentration** — more drug is not
more effect past the optimum. The therapeutic window has an upper edge that is not a toxicity
edge.

## Off-target degradation

A distinctive risk with no inhibitor analogue: the degrader may recruit the E3 to proteins other
than the intended target, destroying them too.

Two sources:

- **The target ligand's own promiscuity**, amplified — an inhibitor that weakly binds ten kinases
  might meaningfully inhibit one, but a degrader might destroy several.
- **The E3 ligand's built-in neosubstrates** — IMiD scaffolds degrade IKZF1/IKZF3 regardless of
  what you attached them to.

The measurement is **global proteomics** (TMT or label-free quantitative mass spectrometry) after
treatment. It is the standard selectivity experiment for this modality and there is no
computational substitute. Run it early; a beautiful degrader that also removes three other
proteins is better discovered before the tox study.

## Formulation and route

Most clinical degraders are oral, achieved with substantial formulation work — amorphous solid
dispersions and lipid-based systems are common. The molecules are large, poorly soluble, and
usually have poor intrinsic permeability, so formulation is doing real work rather than polishing.

Budget for it, and do not read a poor early PK result as fatal before formulation has been tried.

## Reporting

Give DC50 **and** Dmax, and say whether a hook was observed and over what concentration range. Give
cooperativity if measured. State the E3 and the linker. Report permeability as measured, not as
predicted from TPSA. Report global proteomics selectivity, or say it has not been done. And when
quoting the property windows, say they are bRo5 conventions rather than rules — the molecule is
supposed to violate Lipinski.
