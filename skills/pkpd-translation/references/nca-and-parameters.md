# Non-compartmental analysis and what each parameter means

NCA reads the observed curve rather than fitting a model to it. That is its virtue: no structural
assumption to be wrong about, which is why it is the first thing done to any new profile.

## The primary parameters

| Parameter | Definition | Depends on |
|---|---|---|
| Cmax | highest observed concentration | dose, absorption, distribution |
| Tmax | time of Cmax | absorption rate |
| AUC(0–t) | area to the last measured point | dose, clearance |
| AUC(0–∞) | AUC(0–t) + Clast/λz | dose, clearance |
| λz | terminal elimination rate constant | clearance and volume |
| t½ | ln2 / λz | clearance **and** volume |
| CL | Dose / AUC(0–∞) | intrinsic clearance, binding, blood flow |
| Vz | Dose / (λz × AUC(0–∞)) | tissue partitioning |
| Vss | CL × MRT | tissue partitioning (bolus only) |
| MRT | AUMC(0–∞) / AUC(0–∞) | both |

**Clearance and volume are the two independent parameters.** Half-life is derived from them —
`t½ = ln2 · V / CL` — which is why it is a poor primary descriptor. A long half-life can mean low
clearance (good exposure) or a large volume (extensive tissue distribution and possibly low plasma
concentration). Two compounds with identical half-lives can behave completely differently.

## Linear-up / log-down, and why plain linear is wrong

Concentrations fall exponentially. A straight line drawn between two descending points sits above
the true curve, so the plain linear trapezoid **overestimates AUC** and therefore **underestimates
clearance**. The error grows with the spacing between samples and with how fast the drug falls.

The fix is to use the linear rule on ascending segments and the logarithmic rule on descending
ones:

```
ascending:   AUC += Δt · (C1 + C2) / 2
descending:  AUC += Δt · (C1 − C2) / ln(C1/C2)
```

`nca.py` uses linear-up / log-down and reports what plain linear would have given, so the size of
the difference is visible on every run.

## The terminal slope decides four other numbers

λz is fitted by log-linear regression on points after Tmax, choosing the window that maximises
adjusted R². Everything downstream inherits its error: t½, the extrapolated tail of AUC(0–∞), Vz,
and MRT.

Two quality checks that belong in every report:

- **R² and the number of points.** Three points is the minimum and is not reassuring. `nca.py`
  warns below R² 0.9.
- **Percentage extrapolated.** `Clast/λz` divided by AUC(0–∞). Above **20%**, the sampling was too
  short and AUC(0–∞) is largely a guess — as are CL and Vz, which are computed from it.

## Back-extrapolation to C0

Sampling never starts at t = 0, so the area between the dose and the first sample is missing from
the trapezoid. After an **IV bolus** that area is real and often several percent of the total;
omitting it inflates clearance by the same fraction.

The convention is to estimate C0 by log-linear back-extrapolation of the first two descending
points. `nca.py` does this automatically for `--route iv`, and reports the C0 it used.

Verified against an analytic one-compartment case — D = 100, V = 10, k = 0.1 — the script returns
CL = 1.000000, Vz = 10.000000, t½ = 6.931472, AUC(0–∞) = 100.000000, Vss = 10.000000. Without the
back-extrapolation the same profile gives AUC 97.53 and CL 1.025, a 2.5% error from a missing
first segment.

Do **not** back-extrapolate after oral dosing: the concentration at t = 0 is genuinely zero.

## Route changes what you can call things

After extravascular dosing you cannot separate clearance from bioavailability. What the arithmetic
gives is:

```
CL/F = Dose / AUC(0–∞)        Vz/F = Dose / (λz · AUC(0–∞))
```

Calling these CL and V silently assumes F = 1. For a compound with 30% oral bioavailability, the
reported "clearance" is three times the real value. `nca.py` labels them correctly and says so on
stderr.

Vss is only meaningful after an IV bolus; the script returns nothing for it after oral dosing
rather than a number that would be wrong.

## Linearity, and the assumption underneath everything

All of the above assumes **dose-proportional (linear) pharmacokinetics**: doubling the dose
doubles AUC and Cmax, and CL and V do not change with concentration. Check it by running NCA at
several dose levels and confirming dose-normalised AUC is flat.

Non-linearity has causes worth identifying, because each has a different consequence:

- **Saturable metabolism** — AUC rises faster than dose. Small dose increases produce large
  exposure jumps, and the therapeutic window narrows sharply.
- **Saturable absorption** — AUC rises more slowly than dose. Raising the dose stops working.
- **Saturable protein binding** — total AUC and free AUC diverge, so total concentrations mislead
  exactly where it matters most.
- **Time-dependent clearance** — auto-induction or auto-inhibition. Single-dose PK does not
  predict steady state at all.

If PK is non-linear, superposition fails and the accumulation arithmetic in
`pk_compartmental.py` does not apply.

## Reporting

Give AUC(0–t) alongside AUC(0–∞) and the percentage extrapolated. Give λz with its R² and point
count. Label CL/F and Vz/F correctly. State the dose levels tested and whether exposure was
dose-proportional across them. For sparse or population data, NCA is the wrong tool — use
non-linear mixed-effects modelling (NONMEM, Monolix, nlmixr2).
