# Running fpocket and reading what it writes

fpocket detects cavities by Voronoi tessellation: it fills the protein surface with **alpha
spheres** — spheres contacting four atoms and containing none — then clusters them. Small spheres
sit in the protein interior, large ones outside; the intermediate band is a cavity. This is
geometry, and it is fast: seconds per structure.

Open source (MIT), <https://github.com/Discngine/fpocket>. Install with
`conda install -c conda-forge fpocket` or `apt install fpocket`.

## Running it

```bash
fpocket -f receptor.pdb                    # writes receptor_out/
fpocket -f receptor.pdb -m 3.0 -M 6.0      # min / max alpha sphere radius
fpocket -f receptor.pdb -i 35              # min alpha spheres per pocket
```

**Strip waters and ligands first**, or fpocket will contour around them and report the space they
occupy as protein surface:

```bash
grep -v HOH input.pdb | grep -v HETATM > receptor.pdb
```

Deciding whether to strip a cofactor is a judgement call. A structural metal or a covalently
attached prosthetic group is part of the protein and should stay; a substrate analogue should go.

## The output tree

```
receptor_out/
├── receptor_info.txt          per-pocket scores -- what pocket_report.py reads
├── receptor_out.pdb           protein plus alpha spheres as HETATM STP records
├── receptor_pockets.pqr       all alpha sphere centres
└── pockets/
    ├── pocket1_atm.pdb        the protein atoms lining pocket 1
    ├── pocket1_vert.pqr       pocket 1's alpha sphere centres
    └── ...
```

**`_vert.pqr` and `_atm.pdb` describe different things.** The vertices are the cavity itself; the
atoms are the protein lining it, and their extent is systematically larger. `pocket_box.py`
prefers the vertices and says which it used.

## The metrics in `_info.txt`

```
Pocket 2 :
	Score :                          0.310
	Druggability Score :             0.871
	Number of Alpha Spheres :        95
	Total SASA :                     350.0
	Polar SASA :                     100.0
	Apolar SASA :                    250.0
	Volume :                         720.5
	Mean local hydrophobic density : ...
	Hydrophobicity score :           ...
	Polarity score :                 ...
	Charge score :                   ...
	Flexibility :                    ...
```

**Score and Druggability Score are different models and frequently disagree.**

- **Score** ranks cavities against each other on geometry and physicochemistry. It is what
  pocket *numbering* follows, so `pocket1` is the highest-scoring cavity — not necessarily the one
  you want.
- **Druggability Score** is a logistic model trained to separate sites with known drug-like
  ligands from sites without. It is the one that answers "is this worth a campaign".

In the worked example above, pocket 1 wins on Score (0.412 vs 0.310) while pocket 2 is far more
druggable (0.871 vs 0.183). Sorting by druggability gives a different order, which is why
`pocket_report.py rank` does exactly that and warns when the two disagree.

## Thresholds used by this skill

| Quantity | Cut | Meaning |
|---|---|---|
| Druggability | ≥ 0.5 | resembles sites with known drug-like ligands |
| Druggability | 0.2–0.5 | marginal; fragment or covalent, not a conventional lead |
| Volume | < 200 Å³ | too small for a lead-like ligand whatever the score |
| Apolar SASA / Total SASA | < 0.35 | probably a polar groove, not a pocket |

The 0.5 druggability cut is fpocket's own guidance. The others are conventions this skill applies
explicitly so they can be argued with; they are not from the fpocket paper.

**Volume alone is misleading.** A large cavity with high polar SASA is usually a surface groove or
a crystallographic artefact. The apolar fraction is what distinguishes a site that will bind a
small molecule, which is why `pocket_report.py` derives and reports it.

## Validating against reality

If a holo structure exists, the honest check is whether the top-ranked cavity contains the
crystallographic ligand:

```bash
python pocket_report.py residues --out-dir receptor_out --pocket 1
```

and compare against the residues within 4 Å of the ligand. A detector that does not recover a
known site on your protein should not be trusted on a site you cannot check. The original fpocket
paper reports the true site within the top three ranked pockets for 94% of holo and 92% of apo
structures — good, but a one-in-fifteen failure rate on apo structures is not negligible.

## Alternatives worth knowing

| Tool | Approach |
|---|---|
| **fpocket** | alpha spheres, geometric, seconds |
| **PocketFinder / LIGSITE** | grid-based energy or surface burial |
| **SiteMap** (Schrödinger) | grid-based with a well-validated SiteScore; commercial |
| **FTMap** | computational solvent mapping with organic probes; finds hot spots |
| **P2Rank** | machine-learned ligandability on the surface; fast, open source |
| **DoGSiteScorer** | descriptor-based, with a druggability model; web server |

Running two detectors that fail differently and taking cavities both agree on is a cheap and
substantial improvement over trusting one.
