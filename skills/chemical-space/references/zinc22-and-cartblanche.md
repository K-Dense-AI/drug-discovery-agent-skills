# ZINC-22, CartBlanche, and the bulk tranche tree

ZINC-22 holds roughly **54.9 billion 2D** and **5.9 billion 3D** make-on-demand compounds, drawn
from Enamine, WuXi, and Mcule. CartBlanche (<https://cartblanche.docking.org>) is its web front
end. Everything below was verified live in August 2026.

## The API is one route wide

**Only `/substance/<ZINC id>.json` reliably returns JSON.** Everything else that looks like it
should work returns the React app's HTML shell:

| Route | Status | Content-Type | Body |
|---|---|---|---|
| `/substance/ZINC000000000053.json` | 200 | application/json | **JSON** |
| `/substances/ZINC000000000053.json` | 200 | application/json | HTML shell |
| `/substance.json?zinc_id=…` | 200 | application/json | HTML shell |
| `/tranches.json` | 200 | application/json | HTML shell |
| `/substance/…/catitems` | 200 | text/html | HTML shell |
| `POST /substance/search.json` | 404 | — | — |

**Neither the status code nor the content-type header can be trusted.** Three of those rows claim
`application/json` and return `<!doctype html>`. The only reliable test is parsing the body, which
is what `get_json()` in `scripts/_common.py` does — it raises a named error when the body starts
with `<`.

Treat CartBlanche as a per-identifier lookup service. For anything bulk, use the file tree.

## Identifiers

ZINC ids are `ZINC` plus digits, **zero-padded to twelve**. `ZINC53` does not resolve;
`ZINC000000000053` does. `normalise_zinc_id()` accepts either and pads.

## The substance record

```json
{"zinc_id": "ZINC000019632618",
 "smiles": "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1",
 "mol_formula": "C29H31N7O", "rings": 5, "hetero_atoms": 8, "db": "zinc20",
 "tranche_details": {"heavy_atoms": 37, "logp": 4.59, "mwt": 493.615,
                     "inchi": "InChI=1S/...", "inchikey": "KTUFNOKKBVMGRW-UHFFFAOYSA-N"},
 "catalogs": [{"catalog_name": "eMolecules Building Blocks", "price": 240,
               "purchase": 1, "quantity": 10, "shipping": "6 weeks",
               "supplier_code": "876446"}, ...]}
```

That is imatinib, with 281 catalog entries and a cheapest quote of 240.

**`catalogs` is the field that matters.** A substance existing in ZINC means it was enumerated;
having a catalog entry with `purchase: 1` means a supplier will sell it. An empty `catalogs`
block is a computationally enumerated compound nobody offers. `db` says which ZINC generation the
record came from (`zinc20`, `zinc22`).

Read `shipping` before planning: lead times of several weeks are normal for make-on-demand.

## The bulk tranche tree

<https://files.docking.org/zinc22/>, organised as:

```
zinc22/
├── zinc-22a/  zinc-22b/  zinc-22c/     three sibling partitions of the catalogue
│   └── H25/                            heavy-atom count
│       ├── H25P200/                    logP bin, P = non-negative
│       │   ├── H25P200-K.a.smi.gz      sharded by a letter code
│       │   └── H25P200-K.a.txt
│       └── H25M000/                    M = negative logP
├── 2d/  2d-all/                        (authorisation required)
├── subsets/  special/
└── vendors_zincid_map/
```

**The tree is addressed by heavy-atom count and logP, not molecular weight.** `H25P200` is
25 heavy atoms, logP 2.0; `H25M100` is logP −1.0. Bins are 0.5 wide, encoded as the absolute value
times 100. Filtering your target profile by MW will not tell you which directories to fetch —
convert to heavy-atom count first. `space_plan.py tranches` generates the paths.

Heavy-atom directories run from `H04` upward. Some paths (`2d/`, `2d-all/`) return
`Unauthorized`; the per-tranche `zinc-22{a,b,c}` trees are open.

Sizes are substantial. A single heavy-atom band across all logP bins and all three subsets is
readily tens of gigabytes compressed, so select the window before downloading, not after.

## Related resources

- **`vendors_zincid_map/`** — the mapping from supplier catalogue numbers to ZINC ids, which is
  what you need to convert a hit list into an order.
- **`subsets/`** — pre-built selections (lead-like, fragment, in-stock) that are far smaller than
  the full tranches and are usually the right starting point.
- **SmallWorld** (<https://sw.docking.org>) — NextMove's similarity search across ZINC and REAL
  Space, the practical way to ask "what near-neighbours can I buy". Web and API, separate service.
- **Arthor** (<https://arthor.docking.org>) — substructure search over the same spaces.

Both SmallWorld and Arthor answer questions CartBlanche cannot, and neither is covered by the
bundled scripts.

## Licence and citation

ZINC is free for academic and commercial use. Cite the ZINC-22 paper
(*J. Chem. Inf. Model.* 2023, 63, 1166). Supplier catalogue content belongs to the suppliers, and
prices are snapshots, not quotes.
