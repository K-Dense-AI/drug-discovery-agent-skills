#!/usr/bin/env python3
"""Build a curated bioactivity table for one target — the SAR starting point.

Pulling `activity.json?target_chembl_id=...` and modelling whatever comes back
is the single most common way to build a bad QSAR set. This script applies the
curation every ChEMBL-derived dataset needs, and reports what each step
removed so the attrition is visible rather than assumed:

1. Resolve the target. A UniProt accession maps to several ChEMBL targets --
   SINGLE PROTEIN, PROTEIN FAMILY, PROTEIN COMPLEX. Mixing them mixes assays
   against the protein with assays against anything containing it.
2. Keep only `standard_relation = '='`. A `>` row means "inactive at the top
   concentration tested"; treating its value as a measurement puts a censored
   number into the middle of your dose-response range.
3. Drop rows carrying a `data_validity_comment` -- ChEMBL's own flag for
   values it considers outside the plausible range or wrongly unit-converted.
4. Keep one measurement type at a time. IC50, Ki, Kd, and EC50 are different
   physical quantities; pooling them is the second most common mistake.
5. Optionally require an assay `confidence_score` -- how confidently the assay
   was mapped to the target. 9 is a direct single-protein assignment; below 5
   the target assignment is a guess (see references/data-curation.md).
6. Aggregate replicates per molecule, reporting the median, the spread, and
   the number of independent measurements. A compound with pIC50 values of 5.1
   and 8.9 is not a compound with a pIC50 of 7.

Examples:

    python target_activities.py --uniprot P00533 --standard-type IC50 --out egfr.tsv
    python target_activities.py --target CHEMBL203 --standard-type Ki \\
        --min-confidence 8 --min-pchembl 5 --out egfr_ki.tsv
    python target_activities.py --uniprot P00533 --list-targets
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    ChemblError,
    add_common_arguments,
    as_float,
    emit,
    get,
    median,
    paged,
    total_count,
    write_table,
)

#: Binding and functional assays. `A` (ADMET) and `T` (toxicity) are excluded
#: by default because their values answer a different question.
ASSAY_TYPES = {
    "B": "binding",
    "F": "functional",
    "A": "ADMET",
    "T": "toxicity",
    "P": "physicochemical",
    "U": "unclassified",
}

#: Types that are a concentration/potency and share the pChEMBL convention.
POTENCY_TYPES = ("IC50", "Ki", "Kd", "EC50", "AC50", "XC50", "Potency", "GI50")


def resolve_targets(args) -> list[dict]:
    """ChEMBL targets for a UniProt accession, most specific first."""
    params = {"target_components__accession": args.uniprot}
    if args.organism:
        params["organism"] = args.organism
    targets = list(paged("target", params, limit=100, base_url=args.base_url))
    if not targets:
        raise ChemblError(
            f"no ChEMBL target has component {args.uniprot}"
            + (f" in {args.organism}" if args.organism else "")
        )
    order = {"SINGLE PROTEIN": 0, "PROTEIN COMPLEX": 1, "PROTEIN FAMILY": 2}
    targets.sort(key=lambda target: (order.get(target.get("target_type"), 9), target.get("pref_name") or ""))
    return targets


def command_list_targets(args) -> None:
    rows = [
        {
            "target_chembl_id": target.get("target_chembl_id"),
            "pref_name": target.get("pref_name"),
            "target_type": target.get("target_type"),
            "organism": target.get("organism"),
            "components": len(target.get("target_components") or []),
        }
        for target in resolve_targets(args)
    ]
    print(
        "# pick a SINGLE PROTEIN target unless you deliberately want family- or "
        "complex-level assays",
        file=sys.stderr,
    )
    write_table(
        rows, ("target_chembl_id", "pref_name", "target_type", "organism", "components")
    )


def fetch_activities(args, target_id: str) -> list[dict]:
    params = {
        "target_chembl_id": target_id,
        "standard_type": args.standard_type,
        "limit": 1000,
    }
    if args.require_pchembl:
        params["pchembl_value__isnull"] = "false"

    # The API takes a single value per query parameter, so several assay types
    # mean one request per type, concatenated.
    records: list[dict] = []
    assay_types = args.assay_types or [None]
    for assay_type in assay_types:
        request = dict(params)
        if assay_type:
            request["assay_type"] = assay_type
        count = total_count("activity", request, base_url=args.base_url)
        print(
            f"# {target_id} {args.standard_type}"
            + (f" assay_type={assay_type}" if assay_type else "")
            + f": {count} activity rows",
            file=sys.stderr,
        )
        records.extend(
            paged("activity", request, limit=args.max_rows, base_url=args.base_url, progress=True)
        )
    return records


def fetch_assay_confidence(args, assay_ids: set[str]) -> dict[str, int]:
    """Assay confidence scores, batched -- the activity endpoint omits them."""
    scores: dict[str, int] = {}
    ordered = sorted(assay_ids)
    batch_size = 50  # keeps the `__in` query string well under any URL limit
    for start in range(0, len(ordered), batch_size):
        batch = ordered[start : start + batch_size]
        for assay in paged(
            "assay",
            {
                "assay_chembl_id__in": ",".join(batch),
                "only": "assay_chembl_id,confidence_score,assay_organism,assay_type",
            },
            limit=len(batch),
            base_url=args.base_url,
        ):
            score = assay.get("confidence_score")
            if score is not None:
                scores[assay["assay_chembl_id"]] = int(score)
    return scores


def curate(args, records: list[dict], confidence: dict[str, int]) -> tuple[list[dict], list[str]]:
    """Apply the filters, returning kept rows and a human-readable audit trail."""
    audit: list[str] = [f"input rows: {len(records)}"]

    def drop(rows: list[dict], predicate, reason: str) -> list[dict]:
        kept = [row for row in rows if predicate(row)]
        removed = len(rows) - len(kept)
        if removed:
            audit.append(f"dropped {removed}: {reason}")
        return kept

    rows = records
    rows = drop(rows, lambda r: r.get("standard_value") is not None, "no standard_value")
    rows = drop(
        rows,
        lambda r: (r.get("standard_relation") or "=") == "=",
        "censored relation (>, <, >=, <=) -- not a measurement",
    )
    rows = drop(
        rows,
        lambda r: not r.get("data_validity_comment"),
        "flagged by ChEMBL's own data_validity_comment",
    )
    if args.units:
        rows = drop(
            rows,
            lambda r: (r.get("standard_units") or "") == args.units,
            f"standard_units != {args.units}",
        )
    if args.exclude_duplicates:
        rows = drop(rows, lambda r: not r.get("potential_duplicate"), "potential_duplicate flag")
    if args.require_pchembl:
        rows = drop(rows, lambda r: as_float(r.get("pchembl_value")) is not None, "no pchembl_value")
    if args.min_pchembl is not None:
        rows = drop(
            rows,
            lambda r: (as_float(r.get("pchembl_value")) or -99) >= args.min_pchembl,
            f"pchembl_value < {args.min_pchembl}",
        )
    if args.min_confidence is not None:
        rows = drop(
            rows,
            lambda r: confidence.get(r.get("assay_chembl_id"), -1) >= args.min_confidence,
            f"assay confidence_score < {args.min_confidence}",
        )
    if args.organism:
        rows = drop(
            rows,
            lambda r: (r.get("target_organism") or "") == args.organism,
            f"target_organism != {args.organism}",
        )
    audit.append(f"kept rows: {len(rows)}")
    return rows, audit


def aggregate(args, rows: list[dict], confidence: dict[str, int]) -> list[dict]:
    """Collapse replicate measurements to one row per molecule."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        molecule = row.get("molecule_chembl_id")
        if molecule:
            grouped[molecule].append(row)

    aggregated = []
    for molecule, measurements in grouped.items():
        pchembls = [
            value
            for value in (as_float(m.get("pchembl_value")) for m in measurements)
            if value is not None
        ]
        values = [
            value
            for value in (as_float(m.get("standard_value")) for m in measurements)
            if value is not None
        ]
        documents = {m.get("document_chembl_id") for m in measurements if m.get("document_chembl_id")}
        scores = [
            confidence[m["assay_chembl_id"]]
            for m in measurements
            if m.get("assay_chembl_id") in confidence
        ]
        spread = (max(pchembls) - min(pchembls)) if len(pchembls) > 1 else 0.0
        aggregated.append(
            {
                "molecule_chembl_id": molecule,
                "canonical_smiles": measurements[0].get("canonical_smiles"),
                "pchembl_median": median(pchembls),
                "pchembl_min": min(pchembls) if pchembls else None,
                "pchembl_max": max(pchembls) if pchembls else None,
                "pchembl_spread": round(spread, 2),
                "standard_value_median": median(values),
                "standard_units": measurements[0].get("standard_units"),
                "standard_type": measurements[0].get("standard_type"),
                "n_measurements": len(measurements),
                "n_documents": len(documents),
                "max_assay_confidence": max(scores) if scores else None,
                "inconsistent": spread >= args.spread_warning,
            }
        )

    aggregated.sort(
        key=lambda row: (row["pchembl_median"] is None, -(row["pchembl_median"] or 0))
    )
    inconsistent = sum(1 for row in aggregated if row["inconsistent"])
    if inconsistent:
        print(
            f"# warning: {inconsistent} molecule(s) have replicate pChEMBL values spanning "
            f">= {args.spread_warning} log units -- review before modelling",
            file=sys.stderr,
        )
    return aggregated


AGGREGATED_COLUMNS = (
    "molecule_chembl_id",
    "canonical_smiles",
    "pchembl_median",
    "pchembl_min",
    "pchembl_max",
    "pchembl_spread",
    "standard_value_median",
    "standard_units",
    "standard_type",
    "n_measurements",
    "n_documents",
    "max_assay_confidence",
    "inconsistent",
)

RAW_COLUMNS = (
    "molecule_chembl_id",
    "canonical_smiles",
    "standard_type",
    "standard_relation",
    "standard_value",
    "standard_units",
    "pchembl_value",
    "assay_chembl_id",
    "assay_type",
    "assay_description",
    "assay_confidence",
    "target_chembl_id",
    "target_organism",
    "document_chembl_id",
    "document_year",
    "activity_id",
)


def command_activities(args) -> None:
    if args.target:
        target_id = args.target
    else:
        targets = resolve_targets(args)
        target_id = targets[0]["target_chembl_id"]
        print(
            f"# resolved {args.uniprot} -> {target_id} "
            f"({targets[0].get('pref_name')}, {targets[0].get('target_type')})"
            + (f"; {len(targets) - 1} other ChEMBL target(s) share this component"
               if len(targets) > 1 else ""),
            file=sys.stderr,
        )

    records = fetch_activities(args, target_id)
    if not records:
        print("# no activities matched", file=sys.stderr)
        return

    assay_ids = {row["assay_chembl_id"] for row in records if row.get("assay_chembl_id")}
    confidence: dict[str, int] = {}
    if args.min_confidence is not None or args.raw:
        print(f"# fetching confidence scores for {len(assay_ids)} assays", file=sys.stderr)
        confidence = fetch_assay_confidence(args, assay_ids)

    rows, audit = curate(args, records, confidence)
    for line in audit:
        print(f"# {line}", file=sys.stderr)

    if args.raw:
        for row in rows:
            row["assay_confidence"] = confidence.get(row.get("assay_chembl_id"))
        output, columns = rows, RAW_COLUMNS
    else:
        output, columns = aggregate(args, rows, confidence), AGGREGATED_COLUMNS

    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="") as handle:
            write_table(output, columns, stream=handle)
        print(f"# wrote {len(output)} rows to {args.out}", file=sys.stderr)
    else:
        emit(output, columns, args.output_format)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument("--uniprot", help="UniProt accession, e.g. P00533")
    identity.add_argument("--target", help="ChEMBL target id, e.g. CHEMBL203")

    parser.add_argument(
        "--list-targets",
        action="store_true",
        help="list the ChEMBL targets for --uniprot and stop (requires --uniprot)",
    )
    parser.add_argument(
        "--standard-type",
        default="IC50",
        help=f"one measurement type; common: {', '.join(POTENCY_TYPES)} (default: IC50)",
    )
    parser.add_argument(
        "--assay-types",
        nargs="+",
        default=["B"],
        choices=sorted(ASSAY_TYPES),
        help="assay types to include: B binding, F functional, A ADMET, T toxicity (default: B)",
    )
    parser.add_argument("--organism", help="restrict to this target organism, e.g. 'Homo sapiens'")
    parser.add_argument("--units", help="require this standard_units value, e.g. nM")
    parser.add_argument(
        "--min-confidence",
        type=int,
        default=None,
        help="minimum assay confidence_score 0-9; 8-9 is a direct protein assignment",
    )
    parser.add_argument("--min-pchembl", type=float, default=None, help="drop weaker measurements")
    parser.add_argument(
        "--require-pchembl",
        action="store_true",
        default=True,
        help="keep only rows with a pchembl_value (default: on)",
    )
    parser.add_argument(
        "--allow-missing-pchembl",
        dest="require_pchembl",
        action="store_false",
        help="keep rows without a pchembl_value",
    )
    parser.add_argument(
        "--exclude-duplicates",
        action="store_true",
        default=True,
        help="drop rows ChEMBL flagged as potential duplicates (default: on)",
    )
    parser.add_argument(
        "--keep-duplicates", dest="exclude_duplicates", action="store_false"
    )
    parser.add_argument(
        "--spread-warning",
        type=float,
        default=1.0,
        help="flag molecules whose replicate pChEMBL values span this many log units (default: 1.0)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="emit one row per measurement instead of one row per molecule",
    )
    parser.add_argument("--max-rows", type=int, default=20000, help="safety cap on rows fetched")
    parser.add_argument("--out", help="write to this file instead of stdout")
    add_common_arguments(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.list_targets:
            if not args.uniprot:
                print("error: --list-targets requires --uniprot", file=sys.stderr)
                return 1
            command_list_targets(args)
        else:
            command_activities(args)
    except ChemblError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
