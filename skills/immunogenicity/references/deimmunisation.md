# Deimmunisation in practice

Judgement, not syntax. Removing a predicted epitope is easy; removing it without breaking the
molecule is the actual problem.

## Decide whether it is worth doing

Not every flagged epitope needs fixing. Work through, in order:

1. **Is it in germline framework?** Then it is probably tolerised and probably noise. Leave it.
2. **Is it in a CDR?** Mutating a CDR risks affinity, and affinity is usually worth more than a
   marginal immunogenicity improvement. Treat as a last resort.
3. **Is it promiscuous?** A core binding one rare allele affects few patients. Prioritise cores
   binding many common alleles.
4. **Is it in an engineered junction?** Fusion joints, linkers, and humanisation back-mutations
   are the highest-yield targets — non-germline by construction, and usually not affinity-critical.

Most of the value comes from step 4.

## The 9-mer register

Class II binding is determined by a 9-residue core sitting in the groove, with anchor pockets at
**P1, P4, P6, and P9**. P1 is the deepest and most restrictive — it strongly prefers large
hydrophobics (F, W, Y, L, I, V, M).

So the highest-leverage single substitution is usually **at P1, replacing a large hydrophobic with
a charged or small polar residue** (D, E, K, R, N, S). That one change frequently drops a core
below the binding threshold for most alleles at once.

Substitutions at P4, P6, and P9 are more allele-specific: they may remove binding for one allele
and leave it for another, which is why a re-scan across the full panel is mandatory.

## The failure mode: register shift

**A substitution that breaks one core routinely creates a new one shifted by a few residues.** The
class II groove is open-ended, so the same 15-mer contains several possible registers, and
suppressing the best one simply promotes the next.

This is why the workflow is a loop, not a step:

```
scan -> pick a core -> substitute an anchor -> RE-SCAN THE WHOLE MOLECULE -> repeat
```

Re-scanning only the mutated peptide misses the new register in its neighbours. Re-scan everything.

## Do not break the protein

Every substitution risks:

- **Affinity**, if the position contacts the antigen.
- **Stability**, if it is buried or structurally important. Buried hydrophobics are exactly the
  residues that make good P1 anchors, which is an unfortunate coincidence and the main reason
  deimmunisation is hard.
- **New liabilities**: introducing N-X-S/T creates a glycosylation sequon (`glycoengineering`);
  introducing NG or DG creates deamidation and isomerisation hotspots (`antibody-engineering`).
- **New aggregation propensity**, which given how much aggregation matters can easily be a net loss.

Rescreen for all of these after each round, and measure affinity and thermostability
experimentally on the final candidates. A variant with two fewer epitopes and a 5 °C lower Tm is
usually worse.

## Germline reversion is the reliable route

For a humanised antibody, the safest deimmunisation is **reverting framework positions to the
nearest human germline**. It reduces epitope content and increases humanness simultaneously, and
the germline sequence is by definition tolerised.

The constraint is **Vernier residues** — framework positions that support CDR conformation.
Reverting those costs affinity. `antibody-engineering` identifies them, and they should be excluded
from the reversion set before you start.

## Tregitopes

Some peptides from IgG constant regions are **regulatory T-cell epitopes**: they activate Tregs and
actively *suppress* responses rather than provoking them. A naive scan counts them as risk when
they may be protective.

EpiVax's JanusMatrix is the tool built around this idea, comparing predicted epitopes against the
human self-proteome to distinguish tolerising from activating. It is commercial, and worth knowing
about because it explains why raw epitope counts overstate risk for human-derived sequence.

## Confirm experimentally

In-silico deimmunisation is a hypothesis. Before committing:

- **MAPPs** — MHC-associated peptide proteomics, showing what dendritic cells actually present.
  The best-characterised in-vitro method and the one that correlates with clinical ADA.
- **T-cell proliferation assays** against a donor panel covering common HLA types.
- **DC-T cell co-culture** for a more physiological readout.

These cost real money and time, and they answer the question. The scan decides which variants are
worth putting into them.

## A workable sequence

1. Compute germline identity — `antibody-engineering`.
2. Scan for class II epitopes — `epitope_scan.py`.
3. Score and locate the promiscuous cores — `ada_risk.py`.
4. Discard flagged cores in germline framework.
5. Prioritise engineered junctions, then non-germline framework, then CDRs last.
6. Substitute at P1 where possible.
7. **Re-scan the entire molecule.**
8. Rescreen for glycosylation sequons, deamidation, isomerisation, and aggregation.
9. Measure affinity and Tm on survivors.
10. MAPPs or a T-cell assay on the final one or two.
