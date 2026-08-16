# Interspecies scaling and first-in-human dose selection

Primary source: FDA, *Estimating the Maximum Safe Starting Dose in Initial Clinical Trials for
Therapeutics in Adult Healthy Volunteers* (2005). The Km factors below are its Table 1.

## Never transfer mg/kg directly

A dose of 50 mg/kg in a rat is **not** 50 mg/kg in a human. Metabolic rate scales with body
surface area rather than mass, so the conversion is:

```
HED (mg/kg) = animal dose (mg/kg) × Km_animal / Km_human
```

where `Km = body weight (kg) / body surface area (m²)`. Human Km is 37.

| Species | Km | Reference weight (kg) | Divide animal mg/kg by |
|---|---|---|---|
| Human | 37 | 60 | 1 |
| Child | 25 | 20 | 1.5 |
| Mouse | 3 | 0.020 | 12.3 |
| Hamster | 5 | 0.080 | 7.4 |
| Rat | 6 | 0.150 | 6.2 |
| Ferret | 7 | 0.300 | 5.3 |
| Guinea pig | 8 | 0.400 | 4.6 |
| Rabbit | 12 | 1.8 | 3.1 |
| Monkey (cynomolgus) | 12 | 3.0 | 3.1 |
| Squirrel monkey | 12 | 0.600 | 3.1 |
| Marmoset | 6 | 0.350 | 6.2 |
| Dog | 20 | 10 | 1.8 |
| Baboon | 20 | 12 | 1.8 |
| Micro-pig | 27 | 20 | 1.4 |
| Mini-pig | 35 | 40 | 1.1 |

Worked, from `allometry.py hed --dose 50`:

```
species  km  divide_by  hed_mg_kg  hed_total_mg_60kg
rat      6   6.167      8.10811    486.486
dog      20  1.85       27.027     1621.62
mouse    3   12.333     4.05405    243.243
```

Skipping the conversion would give a first human cohort six times the intended rat-equivalent
dose.

**The exception that matters:** for most therapeutic proteins and monoclonal antibodies, mg/kg
scaling is more appropriate than body-surface-area scaling, because clearance is receptor- or
FcRn-mediated rather than metabolic. The 2005 guidance applies to small molecules; for biologics
the minimum anticipated biological effect level (MABEL) approach usually governs instead.

## Allometric scaling of parameters

```
P_human = a × W_human^b
```

Conventional exponents:

| Parameter | b | Reasoning |
|---|---|---|
| Clearance | 0.75 | metabolic rate scaling |
| Volume of distribution | 1.0 | body composition is roughly constant |
| Half-life | 0.25 | follows from t½ = ln2·V/CL |

`allometry.py scale` fits the exponent from your data by least squares on log–log axes and reports
it alongside the conventional prediction. With three or four species the fitted exponent is
noisy: an R² near 1 across three points is not evidence of much, and a fitted exponent far from
0.75 is more often sparse data than real biology. Report both.

## Where simple allometry fails

- **Renally cleared drugs** scale better on glomerular filtration rate than on body weight.
- **Drugs cleared by a polymorphic or species-divergent enzyme** — CYP2D6, CYP3A4, aldehyde
  oxidase — do not scale at all. Aldehyde oxidase activity is high in primates and low in rodents,
  and has caused clinical surprises.
- **Protein binding differs between species.** Scaling total clearance when free fractions differ
  compounds the error; scale unbound clearance where fu is known.
- **Transporter-mediated clearance** has species-specific expression.

The modern alternative is **in vitro–in vivo extrapolation (IVIVE)**: measure intrinsic clearance
in human hepatocytes or microsomes, scale by hepatocellularity and liver weight, and correct for
binding. Better mechanistic grounding than allometry, and the basis of PBPK models in
Simcyp, GastroPlus, and open-source PK-Sim.

## First-in-human starting dose

The NOAEL route from the 2005 guidance, in order:

1. Determine the **NOAEL** in each toxicology species, in mg/kg.
2. Convert each to an **HED** using the Km factors.
3. Take the **lowest** HED — the most sensitive species sets the dose, not the average.
4. Divide by a **safety factor**, default **10**.
5. That is the **MRSD**, the maximum recommended starting dose.

```bash
python allometry.py fih --noael rat:50 --noael dog:12 --safety-factor 10
```

Raise the safety factor above 10 when: the dose–response is steep, the toxicity is irreversible or
not monitorable, the target is novel or widely expressed, there is no antidote, the animal models
are of doubtful relevance, or the drug is an agonist of an immune receptor. TGN1412 in 2006 is the
standing lesson — the starting dose was 500-fold below the NOAEL HED and still caused
life-threatening cytokine release, because the animal models did not predict human receptor
biology at all.

Lower it below 10 only with strong justification, typically in oncology where patients rather than
healthy volunteers are dosed and a different risk balance applies.

## MABEL, and when it governs instead

For agonists, immunomodulators, and most biologics, the **minimum anticipated biological effect
level** is the appropriate anchor. It is derived from *in vitro* human receptor occupancy and
concentration–response data rather than animal toxicology, and it usually gives a far lower
starting dose than the NOAEL route. EMA guidance (EMEA/CHMP/SWP/28367/07 Rev. 1) requires the
lowest of the available approaches be used where the risk is high.

Neither `allometry.py` nor anything else in this skill computes MABEL — it needs receptor
occupancy modelling against human target expression, which is compound-specific.

## Reporting

State the species, the NOAEL in each, the Km factor applied, the resulting HED, the safety factor
and its justification, and the MRSD in both mg/kg and total mg at a stated body weight. Say which
species was limiting. If the compound is a biologic or an agonist, say explicitly why the NOAEL
route was chosen over MABEL, or use MABEL.
