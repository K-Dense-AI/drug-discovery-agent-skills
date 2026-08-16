# Running NetMHCIIpan

The standard MHC class II binding predictor, from DTU Health Tech.
<https://services.healthtech.dtu.dk/services/NetMHCIIpan-4.3/>

**Free for academic use under a signed licence, and not redistributable.** Download requires
registration; commercial use needs a separate agreement. This is why the bundled scripts prepare
input and parse output rather than wrapping the tool.

A web server exists for small jobs. Do not paste proprietary sequences into it.

## Class II, not class I

Anti-drug antibody formation requires **CD4 T-cell help**, and CD4 T cells see peptides presented
on **MHC class II**. Scanning a biologic against MHC-I predicts CD8 recognition, which is a
question about cytotoxic T cells and rarely the one being asked about a therapeutic protein.

Use **NetMHCIIpan** for ADA risk. NetMHCpan (class I) matters for vaccine and neoantigen work,
which is a different problem.

## Running it

```bash
# peptide list (what epitope_scan.py peptides produces)
netMHCIIpan -f peptides.txt -inptype 1 \
    -a DRB1_0101,DRB1_0301,DRB1_0401,DRB1_0701,DRB1_0801,DRB1_1101,DRB1_1501 \
    -xls -xlsfile out.txt

# or a FASTA, letting the tool do the tiling
netMHCIIpan -f protein.fa -length 15 -a DRB1_0101,DRB1_0401 -xls -xlsfile out.txt
```

`-inptype 1` means the input is a peptide list rather than FASTA. `-xls` writes the tabular output
`epitope_scan.py parse` reads.

Class II peptides are conventionally **15-mers**, because the class II groove is open at both ends
and accommodates a longer peptide than class I. The actual binding **core is 9 residues**, which
matters for interpretation — see below.

## Use %Rank, not affinity

This is the thing to get right. The predictor reports both a score/affinity and a **%Rank**, and
they are not interchangeable.

**Predicted IC50 is not comparable between alleles.** Each allele has its own affinity
distribution — some bind everything tightly, some bind nothing tightly — so a 100 nM prediction
means something different for DRB1\*0101 than for DRB1\*1501. Ranking peptides by nM across alleles
is a standard and serious error.

**%Rank normalises against a background of random natural peptides**, so it is comparable across
alleles and can be thresholded uniformly:

| %Rank | Conventional interpretation |
|---|---|
| ≤ 2 | strong binder |
| ≤ 10 | weak binder |
| > 10 | not a binder |

`epitope_scan.py parse` defaults to a 2% threshold and takes `--rank-threshold`.

## Collapse to binding cores

Consecutive 15-mers overlap by 14 residues, so the same 9-mer core appears in up to seven
peptides. Counting peptide hits therefore overcounts epitopes by roughly that factor.

`epitope_scan.py parse` groups by the `Core` column and reports distinct cores. In the worked
example, three predictions across three alleles collapse to **one** epitope — which is the honest
count.

## Promiscuity is the useful number

A peptide binding one allele is a problem for the fraction of patients carrying it. A peptide
binding eight common alleles is a problem for nearly everyone.

So the metric that matters is **how many alleles a core binds**, not how strongly it binds the
best one. The scripts report `alleles_bound` and `allele_coverage_pct`, and sort by promiscuity
before rank.

## The allele panel

A conventional DRB1 screening set giving broad population coverage:

| Allele | Note |
|---|---|
| DRB1\*01:01 | common in European populations |
| DRB1\*03:01 | common in European and African populations |
| DRB1\*04:01 | common in European populations; RA-associated |
| DRB1\*07:01 | broadly common |
| DRB1\*08:01 | common in Native American and European populations |
| DRB1\*11:01 | common in European and African populations |
| DRB1\*15:01 | broadly common; MS-associated |

Two caveats. **DP and DQ also present peptides**, are less well predicted, and are not in this
panel — a clean DRB1 scan is necessary rather than sufficient. And **allele frequencies vary
enormously between populations**, so a panel chosen for European coverage misrepresents risk
elsewhere; use the allele frequencies for your intended population.

The **IEDB population coverage tool** does this properly and is worth using when the trial
population is known.

## Alternatives and complements

| Tool | Notes |
|---|---|
| **NetMHCIIpan** | the standard; free academic licence |
| **IEDB consensus** | ensemble of several predictors, free web API |
| **EpiMatrix** (EpiVax) | commercial, with a large clinical validation set and JanusMatrix for tolerance |
| **iTope / TCED** (Abzena) | commercial, paired with in-vitro T-cell assays |
| **MAPPs** | **experimental**, not predictive: MHC-associated peptide proteomics identifies what dendritic cells actually present |

**MAPPs is the best-characterised in-vitro tool** and correlates with clinical ADA better than any
sequence method. The number of drug-derived peptides presented, and the number of distinct regions
they come from, track observed ADA incidence approximately. If the decision matters, run MAPPs and
a T-cell proliferation assay rather than trusting a prediction.
