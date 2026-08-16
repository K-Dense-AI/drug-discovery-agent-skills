#!/usr/bin/env python3
"""Generic access to any ChEMBL web-service endpoint, with paging handled.

Use this for the endpoints the purpose-built scripts do not cover -- documents,
drug indications, drug warnings, cell lines, protein classifications, ATC
classes, tissues, binding sites, metabolism.

    fetch     page an endpoint with filters, into TSV/CSV/JSON
    count     how many records a filter matches, without downloading them
    record    one record by id
    status    database version and row counts
    endpoints what endpoints exist and which filters they take

Filters use Django-style double-underscore lookups:

    field=value                 exact
    field__in=A,B,C             any of
    field__gte=8 / __lte / __gt / __lt
    field__isnull=false
    field__icontains=kinase     case-insensitive substring
    field__startswith=CHEMBL2
    related__field=value        traverse a relation

A **single** underscore before a lookup name is read as part of the field name,
so `pchembl_value_gte=8` filters nothing and returns the whole table. This
script rejects that spelling rather than letting it through.

Examples:

    python chembl_query.py count activity --filter target_chembl_id=CHEMBL203
    python chembl_query.py fetch drug_indication \\
        --filter molecule_chembl_id=CHEMBL941 --only mesh_heading,max_phase_for_ind
    python chembl_query.py fetch molecule \\
        --filter molecule_properties__full_mwt__lte=300 \\
        --filter max_phase=4 --limit 200 --out small_approved.tsv
    python chembl_query.py record target CHEMBL203
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    MAX_LIMIT,
    ChemblError,
    add_common_arguments,
    get,
    paged,
    parse_filters,
    payload_key,
    total_count,
    write_table,
)

#: Endpoint -> (what it holds, filters that are actually useful on it).
ENDPOINTS: dict[str, tuple[str, str]] = {
    "activity": (
        "one measured value per assay/compound pair",
        "target_chembl_id, molecule_chembl_id, assay_chembl_id, standard_type, "
        "standard_relation, standard_units, pchembl_value__gte, assay_type, "
        "target_organism, document_chembl_id",
    ),
    "assay": (
        "assay descriptions and target-assignment confidence",
        "assay_chembl_id, target_chembl_id, assay_type, confidence_score__gte, "
        "assay_organism, bao_format, document_chembl_id",
    ),
    "molecule": (
        "compound records, structures, and calculated properties",
        "molecule_chembl_id, pref_name__icontains, max_phase, molecule_type, "
        "molecule_properties__full_mwt__lte, molecule_structures__canonical_smiles__flexmatch, "
        "molecule_structures__standard_inchi_key, withdrawn_flag, natural_product",
    ),
    "target": (
        "targets and their protein components",
        "target_chembl_id, target_type, organism, pref_name__icontains, "
        "target_components__accession",
    ),
    "mechanism": (
        "curated mechanism of action for approved and clinical drugs",
        "molecule_chembl_id, target_chembl_id, action_type, max_phase",
    ),
    "drug_indication": (
        "indications with the highest phase reached",
        "molecule_chembl_id, mesh_id, efo_id, max_phase_for_ind__gte",
    ),
    "drug_warning": (
        "withdrawal and black-box warnings",
        "molecule_chembl_id, warning_type, warning_class, warning_country",
    ),
    "drug": ("approved drugs with development and administration flags", "molecule_chembl_id, first_approval, usan_stem"),
    "document": ("source publications", "document_chembl_id, doi, year, journal, pubmed_id"),
    "cell_line": ("cell lines used in assays", "cell_chembl_id, cell_name, cell_source_organism"),
    "tissue": ("tissue terms", "tissue_chembl_id, pref_name"),
    "binding_site": ("binding-site definitions on targets", "site_id, site_name"),
    "protein_classification": ("the ChEMBL protein family tree", "protein_class_id, pref_name, class_level"),
    "atc_class": ("WHO ATC codes", "level5, level1, who_name__icontains"),
    "molecule_form": ("salt/parent relationships", "molecule_chembl_id, parent_chembl_id"),
    "metabolism": ("curated metabolic conversions", "drug_chembl_id, metabolite_chembl_id, enzyme_name"),
    "compound_structural_alert": ("structural alert hits per compound", "molecule_chembl_id, alert__alert_name"),
    "target_component": ("protein components with sequence and cross-references", "accession, component_type"),
    "target_relation": ("subset/superset relations between targets", "target_chembl_id, relationship"),
    "chembl_id_lookup": ("what kind of entity an id is, and whether it is still active", "chembl_id, entity_type, status"),
}


def command_endpoints(args) -> None:
    rows = [
        {"endpoint": name, "holds": description, "useful_filters": filters}
        for name, (description, filters) in sorted(ENDPOINTS.items())
    ]
    write_table(rows, ("endpoint", "holds", "useful_filters"))
    print(
        "\n# full list and per-endpoint schema: "
        "https://www.ebi.ac.uk/chembl/api/data/docs",
        file=sys.stderr,
    )


def command_count(args) -> None:
    params = parse_filters(args.filters)
    count = total_count(args.endpoint, params, base_url=args.base_url)
    print(count)


def command_fetch(args) -> None:
    params = parse_filters(args.filters)
    if args.only:
        params["only"] = args.only
    if args.order_by:
        params["order_by"] = args.order_by

    matched = total_count(args.endpoint, params, base_url=args.base_url)
    print(f"# {matched} records match; fetching up to {args.limit}", file=sys.stderr)
    if matched > args.limit:
        print(
            f"# note: truncated to {args.limit} of {matched} -- raise --limit or "
            "narrow the filters if you need the whole set",
            file=sys.stderr,
        )

    records = list(
        paged(
            args.endpoint,
            params,
            limit=args.limit,
            page_size=min(args.page_size, MAX_LIMIT),
            base_url=args.base_url,
            progress=True,
        )
    )
    _emit(records, args)


def command_record(args) -> None:
    document = get(f"{args.endpoint}/{args.record_id}", base_url=args.base_url)
    json.dump(document, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def command_status(args) -> None:
    document = get("status", base_url=args.base_url)
    for key in sorted(document):
        print(f"{key}\t{document[key]}")


def _emit(records: list[dict], args) -> None:
    if not records:
        print("# no records matched", file=sys.stderr)
        return
    if args.output_format == "json":
        stream = open(args.out, "w", encoding="utf-8") if args.out else sys.stdout
        try:
            json.dump(records, stream, indent=2)
            stream.write("\n")
        finally:
            if args.out:
                stream.close()
        return

    # Union of keys, in first-seen order, so a sparse field is not dropped
    # just because the first record lacks it.
    columns: list[str] = []
    for record in records:
        for key, value in record.items():
            if key not in columns and not isinstance(value, (list, dict)):
                columns.append(key)
    delimiter = "," if args.output_format == "csv" else "\t"
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="") as handle:
            write_table(records, columns, stream=handle, delimiter=delimiter)
        print(f"# wrote {len(records)} rows to {args.out}", file=sys.stderr)
    else:
        write_table(records, columns, delimiter=delimiter)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    endpoints = subparsers.add_parser("endpoints", help="list endpoints and their useful filters")
    add_common_arguments(endpoints)
    endpoints.set_defaults(handler=command_endpoints)

    fetch = subparsers.add_parser("fetch", help="page an endpoint into a table")
    fetch.add_argument("endpoint", help="e.g. activity, molecule, drug_indication")
    fetch.add_argument(
        "--filter",
        dest="filters",
        action="append",
        default=[],
        metavar="FIELD=VALUE",
        help="repeatable; Django-style lookups with double underscores",
    )
    fetch.add_argument("--only", help="comma-separated fields to return")
    fetch.add_argument("--order-by", help="field to sort by; prefix with - for descending")
    fetch.add_argument("--limit", type=int, default=1000, help="total records (default: 1000)")
    fetch.add_argument(
        "--page-size", type=int, default=MAX_LIMIT, help=f"records per request (max {MAX_LIMIT})"
    )
    fetch.add_argument("--out", help="write to this file instead of stdout")
    add_common_arguments(fetch)
    fetch.set_defaults(handler=command_fetch)

    count = subparsers.add_parser("count", help="how many records match, without fetching")
    count.add_argument("endpoint")
    count.add_argument(
        "--filter", dest="filters", action="append", default=[], metavar="FIELD=VALUE"
    )
    add_common_arguments(count)
    count.set_defaults(handler=command_count)

    record = subparsers.add_parser("record", help="one record by id, as raw JSON")
    record.add_argument("endpoint")
    record.add_argument("record_id")
    add_common_arguments(record)
    record.set_defaults(handler=command_record)

    status = subparsers.add_parser("status", help="database release and row counts")
    add_common_arguments(status)
    status.set_defaults(handler=command_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except ChemblError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
