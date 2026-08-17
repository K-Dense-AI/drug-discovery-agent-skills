---
name: depmap
description: Query the Cancer Dependency Map (DepMap) for cancer cell line gene dependency scores (CRISPR Chronos), RNAi DEMETER2 scores, PRISM compound sensitivity, and gene effect profiles across the cell-line panel. Use for identifying cancer-selective vulnerabilities, separating pan-essential genes from selective ones, finding synthetic lethal interactions, correlating dependency with mutation, expression and copy number, and validating oncology drug targets. Also trigger on DepMap, Chronos gene effect, CRISPRGeneEffect.csv, DEMETER2, PRISM repurposing, co-essentiality, pan-essential, or ACH- cell line identifiers.
license: MIT
compatibility: Requires Python 3.10+ with pandas, numpy, scipy and requests. Analysis is download-based — the DepMap release files (CRISPRGeneEffect.csv is roughly 500 MB) are fetched from the portal by hand and read locally. The portal gates programmatic access behind a browser verification page, so there is no usable REST API. Data is CC-BY-4.0 and requires registration to download.
allowed-tools: Read Write Edit Bash
metadata:
  version: "1.1"
  skill-author: Kuan-lin Huang
---

# DepMap — Cancer Dependency Map

## Overview

The Cancer Dependency Map (DepMap) project, run by the Broad Institute, systematically characterizes genetic dependencies across hundreds of cancer cell lines using genome-wide CRISPR knockout screens (DepMap CRISPR), RNA interference (RNAi), and compound sensitivity assays (PRISM). DepMap data is essential for:
- Identifying which genes are essential for specific cancer types
- Finding cancer-selective dependencies (therapeutic targets)
- Validating oncology drug targets
- Discovering synthetic lethal interactions

**Key resources:**
- DepMap Portal: https://depmap.org/portal/
- DepMap data downloads: https://depmap.org/portal/download/all/
- Data downloads are the supported route; see the warning below about the portal API.

**There is no DepMap Python package.** The PyPI project named `depmap` is "Dependency Mapper CLI",
an unrelated software-dependency tool — installing it will not get you cell-line data. Read the
release CSVs with pandas.

## When to Use This Skill

Use DepMap when:

- **Target validation**: Is a gene essential for survival in cancer cell lines with a specific mutation (e.g., KRAS-mutant)?
- **Biomarker discovery**: What genomic features predict sensitivity to knockout of a gene?
- **Synthetic lethality**: Find genes that are selectively essential when another gene is mutated/deleted
- **Drug sensitivity**: What cell line features predict response to a compound?
- **Pan-cancer essentiality**: Is a gene broadly essential across all cancer types (bad target) or selectively essential?
- **Correlation analysis**: Which pairs of genes have correlated dependency profiles (co-essentiality)?

## Core Concepts

### Dependency Scores

| Score | Range | Meaning |
|-------|-------|---------|
| **Chronos** (CRISPR) | ~ -3 to 0+ | More negative = more essential. Common essential threshold: −1. Pan-essential genes ~−1 to −2 |
| **RNAi DEMETER2** | ~ -3 to 0+ | Similar scale to Chronos |
| **Gene Effect** | normalized | Normalized Chronos; −1 = median effect of common essential genes |

**Key thresholds:**
- Chronos ≤ −0.5: likely dependent
- Chronos ≤ −1: strongly dependent (common essential range)

### Cell Line Annotations

Each cell line has:
- `DepMap_ID`: unique identifier (e.g., `ACH-000001`)
- `cell_line_name`: human-readable name
- `primary_disease`: cancer type
- `lineage`: broad tissue lineage
- `lineage_subtype`: specific subtype

## Core Capabilities

### 1. The portal API is not a usable data source

**Checked live, August 2026:** every path under `https://depmap.org/portal/api/` answers a
programmatic request with **HTTP 200 and an HTML browser-verification page**, not JSON. That
combination is the trap — `response.raise_for_status()` sees the 200 and passes, so the failure
surfaces later as a `JSONDecodeError`, or worse as an HTML string quietly carried forward as data.

DepMap publishes no documented, stable, public REST API. Download the release files and work
locally; that is the supported route and the one the rest of this skill uses.

### 2. Download-Based Analysis (the supported route)

For large-scale analysis, download DepMap data files and analyze locally:

```python
import pandas as pd
import requests, os

def download_depmap_data(url, output_path):
    """Download a DepMap data file."""
    response = requests.get(url, stream=True)
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

# DepMap 24Q4 data files (update version as needed)
FILES = {
    "crispr_gene_effect": "https://figshare.com/ndownloader/files/...",
    # OR download from: https://depmap.org/portal/download/all/
    # Files available:
    # CRISPRGeneEffect.csv - Chronos gene effect scores
    # OmicsExpressionProteinCodingGenesTPMLogp1.csv - mRNA expression
    # OmicsSomaticMutationsMatrixDamaging.csv - mutation binary matrix
    # OmicsCNGene.csv - copy number
    # Model.csv - cell line metadata (was sample_info.csv before 23Q2)
}

def load_depmap_gene_effect(filepath="CRISPRGeneEffect.csv"):
    """
    Load DepMap CRISPR gene effect matrix.
    Rows = cell lines (DepMap_ID), Columns = genes (Symbol (EntrezID))
    """
    df = pd.read_csv(filepath, index_col=0)
    # Rename columns to gene symbols only
    df.columns = [col.split(" ")[0] for col in df.columns]
    return df

def load_cell_line_info(filepath="Model.csv"):
    """Load cell line metadata.

    Release 23Q2 renamed this file from sample_info.csv AND renamed its columns:
    DepMap_ID -> ModelID, cell_line_name -> CellLineName,
    primary_disease -> OncotreePrimaryDisease, lineage -> OncotreeLineage.
    Code written against the old names merges to an empty frame rather than
    raising, so check the columns you actually got before trusting a join.
    """
    return pd.read_csv(filepath)
```

### 3. Identifying Selective Dependencies

```python
import numpy as np
import pandas as pd

def find_selective_dependencies(gene_effect_df, cell_line_info, target_gene,
                                 cancer_type=None, threshold=-0.5):
    """Find cell lines selectively dependent on a gene."""

    # Get scores for target gene
    if target_gene not in gene_effect_df.columns:
        return None

    scores = gene_effect_df[target_gene].dropna()
    dependent = scores[scores <= threshold]

    # Add cell line info
    result = pd.DataFrame({
        "DepMap_ID": dependent.index,
        "gene_effect": dependent.values
    }).merge(cell_line_info[["DepMap_ID", "cell_line_name", "primary_disease", "lineage"]])
    # On a 23Q2+ Model.csv these are ModelID / CellLineName /
    # OncotreePrimaryDisease / OncotreeLineage -- rename before merging.

    if cancer_type:
        result = result[result["primary_disease"].str.contains(cancer_type, case=False, na=False)]

    return result.sort_values("gene_effect")

# Example usage (after loading data)
# df_effect = load_depmap_gene_effect("CRISPRGeneEffect.csv")
# cell_info = load_cell_line_info("Model.csv")   # see the column renames in the loader
# deps = find_selective_dependencies(df_effect, cell_info, "KRAS", cancer_type="Lung")
```

### 4. Biomarker Analysis (Gene Effect vs. Mutation)

```python
import pandas as pd
from scipy import stats

def biomarker_analysis(gene_effect_df, mutation_df, target_gene, biomarker_gene):
    """
    Test if mutation in biomarker_gene predicts dependency on target_gene.

    Args:
        gene_effect_df: CRISPR gene effect DataFrame
        mutation_df: Binary mutation DataFrame (1 = mutated)
        target_gene: Gene to assess dependency of
        biomarker_gene: Gene whose mutation may predict dependency
    """
    if target_gene not in gene_effect_df.columns or biomarker_gene not in mutation_df.columns:
        return None

    # Align cell lines
    common_lines = gene_effect_df.index.intersection(mutation_df.index)
    scores = gene_effect_df.loc[common_lines, target_gene].dropna()
    mutations = mutation_df.loc[scores.index, biomarker_gene]

    mutated = scores[mutations == 1]
    wt = scores[mutations == 0]

    stat, pval = stats.mannwhitneyu(mutated, wt, alternative='less')

    return {
        "target_gene": target_gene,
        "biomarker_gene": biomarker_gene,
        "n_mutated": len(mutated),
        "n_wt": len(wt),
        "mean_effect_mutated": mutated.mean(),
        "mean_effect_wt": wt.mean(),
        "pval": pval,
        "significant": pval < 0.05
    }
```

### 5. Co-Essentiality Analysis

```python
import pandas as pd

def co_essentiality(gene_effect_df, target_gene, top_n=20):
    """Find genes with most correlated dependency profiles (co-essential partners)."""
    if target_gene not in gene_effect_df.columns:
        return None

    target_scores = gene_effect_df[target_gene].dropna()

    correlations = {}
    for gene in gene_effect_df.columns:
        if gene == target_gene:
            continue
        other_scores = gene_effect_df[gene].dropna()
        common = target_scores.index.intersection(other_scores.index)
        if len(common) < 50:
            continue
        r = target_scores[common].corr(other_scores[common])
        if not pd.isna(r):
            correlations[gene] = r

    corr_series = pd.Series(correlations).sort_values(ascending=False)
    return corr_series.head(top_n)

# Co-essential genes often share biological complexes or pathways
```

## Query Workflows

### Workflow 1: Target Validation for a Cancer Type

1. Download `CRISPRGeneEffect.csv` and `Model.csv` (cell-line metadata; this file was named
   `sample_info.csv` before release 23Q2, and older code still asks for that name)
2. Filter cell lines by cancer type
3. Compute mean gene effect for target gene in cancer vs. all others
4. Calculate selectivity: how specific is the dependency to your cancer type?
5. Cross-reference with mutation, expression, or CNA data as biomarkers

### Workflow 2: Synthetic Lethality Screen

1. Identify cell lines with mutation/deletion in gene of interest (e.g., BRCA1-mutant)
2. Compute gene effect scores for all genes in mutant vs. WT lines
3. Identify genes significantly more essential in mutant lines (synthetic lethal partners)
4. Filter by selectivity and effect size

### Workflow 3: Compound Sensitivity Analysis

1. Download PRISM compound sensitivity data (`primary-screen-replicate-treatment-info.csv`)
2. Correlate compound AUC/log2(fold-change) with genomic features
3. Identify predictive biomarkers for compound sensitivity

## DepMap Data Files Reference

| File | Description |
|------|-------------|
| `CRISPRGeneEffect.csv` | CRISPR Chronos gene effect (primary dependency data) |
| `CRISPRGeneEffectUnscaled.csv` | Unscaled CRISPR scores |
| `RNAi_merged.csv` | DEMETER2 RNAi dependency |
| `Model.csv` | Cell line metadata (lineage, disease, etc.). Called `sample_info.csv` before 23Q2 |
| `OmicsExpressionProteinCodingGenesTPMLogp1.csv` | mRNA expression |
| `OmicsSomaticMutationsMatrixDamaging.csv` | Damaging somatic mutations (binary) |
| `OmicsCNGene.csv` | Copy number per gene |
| `PRISM_Repurposing_Primary_Screens_Data.csv` | Drug sensitivity (repurposing library) |

Download all files from: https://depmap.org/portal/download/all/

Read [references/dependency_analysis.md](references/dependency_analysis.md) before acting on a
score — it covers what Chronos corrects for, the full score-band interpretation, selectivity
metrics, and the copy-number and expression confounders that produce false dependencies.

## Best Practices

- **Use Chronos scores** (not DEMETER2) for current CRISPR analyses — better controlled for cutting efficiency
- **Distinguish pan-essential from cancer-selective**: Target genes with low variance (essential in all lines) are poor drug targets
- **Validate with expression data**: A gene not expressed in a cell line will score as non-essential regardless of actual function
- **Use DepMap ID** for cell line identification — cell_line_name can be ambiguous
- **Account for copy number**: Amplified genes may appear essential due to copy number effect (junk DNA hypothesis)
- **Multiple testing correction**: When computing biomarker associations genome-wide, apply FDR correction

## Composing with the rest of the bundle

- `open-targets` → before: its `depMapEssentiality` roll-up is the summary of what is here. Come to
  this skill when the roll-up says "essential" and you need to know *in which lineages*.
- `target-safety` → alongside: cell-line essentiality is not human tolerance. A gene essential
  across the panel may still have healthy human knockouts — gnomAD LOEUF answers that, DepMap
  cannot.
- `chembl` → after: once a dependency looks selective, what has already been made against it.
- `uniprot-rcsb` → after: the structure, once the target survives triage.
- `clinicaltrials` → after: whether anyone has taken this vulnerability into patients.
- `primekg` / `ncats-arax` → alongside: mechanistic context for a co-essentiality pair that has no
  obvious pathway explanation.

**A pan-essential gene is a toxicity finding, not a target.** The whole point of the panel is the
contrast between lineages; a gene at −1 everywhere kills normal cells too.

## Additional Resources

- **DepMap Portal**: https://depmap.org/portal/
- **Data downloads**: https://depmap.org/portal/download/all/
- **DepMap paper**: Tsherniak A et al. (2017) *Defining a Cancer Dependency Map*. Cell. PMID: 28753430
- **Chronos paper**: Dempster JM et al. (2021) *Chronos: a cell population dynamics model of CRISPR
  experiments that improves inference of gene fitness effects*. Genome Biology. PMID: 34930405
- **Project Score (Sanger, complementary panel)**: Behan FM et al. (2019) Nature. PMID: 30971826
- **GitHub**: https://github.com/broadinstitute/depmap-portal
- **Figshare**: https://figshare.com/articles/dataset/DepMap_24Q4_Public/27993966
