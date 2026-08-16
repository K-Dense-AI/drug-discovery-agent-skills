#!/usr/bin/env python3
"""Fetch sequences, annotation, and cross-references from UniProtKB.

Commands:

    entry      one accession -> summary, or full JSON with --format json
    search     a UniProt query -> table, following the Link header for all pages
    fasta      sequence(s) in FASTA, canonical or with isoforms
    features   positional annotation (domains, binding sites, PTMs, variants)
    map        UniProt <-> PDB / Ensembl / RefSeq / gene-name id mapping
    pdb        the PDB entries cross-referenced from an entry, with coverage

Two things this gets right that a hand-written request usually does not:

* **Pagination lives in the `Link` HTTP header**, not the JSON body. Read only
  the body and you silently get the first 25 rows of 12,000.
* **`reviewed:true` matters.** UniProtKB is ~0.5 % Swiss-Prot (curated) and
  ~99.5 % TrEMBL (automatic). A gene-name search without it returns fragments,
  predicted isoforms, and non-model organisms ahead of the entry you wanted.

Examples:

    python uniprot_fetch.py entry P00533
    python uniprot_fetch.py search "gene:EGFR AND organism_id:9606 AND reviewed:true"
    python uniprot_fetch.py fasta P00533 --isoforms
    python uniprot_fetch.py features P00533 --types Binding,Active,Mutagenesis
    python uniprot_fetch.py map P00533 P04637 --to PDB
    python uniprot_fetch.py pdb P00533 --max-resolution 2.5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    UNIPROT_REST,
    ServiceError,
    add_common_arguments,
    emit,
    get_json,
    request_bytes,
    uniprot_pages,
    write_table,
)

#: `fields=` shorthands that cover most needs. The full list is at
#: https://www.uniprot.org/help/return_fields
DEFAULT_SEARCH_FIELDS = (
    "accession,id,protein_name,gene_names,organism_name,length,reviewed,"
    "cc_subcellular_location,ft_binding,xref_pdb,sequence"
)

TABLE_COLUMNS = (
    "accession",
    "entryName",
    "reviewed",
    "proteinName",
    "genes",
    "organism",
    "length",
    "pdbCount",
)

#: UniProt feature `type` values are human-readable strings, not codes.
COMMON_FEATURE_TYPES = (
    "Domain", "Region", "Binding site", "Active site", "Site", "Metal binding",
    "Modified residue", "Glycosylation", "Disulfide bond", "Mutagenesis",
    "Natural variant", "Alternative sequence", "Signal", "Transmembrane",
    "Topological domain", "Chain", "Propeptide", "Helix", "Beta strand", "Turn",
)


def _reviewed(entry: dict) -> bool:
    return (entry.get("entryType") or "").startswith("UniProtKB reviewed")


def _protein_name(entry: dict) -> str:
    description = entry.get("proteinDescription") or {}
    recommended = description.get("recommendedName") or {}
    full = (recommended.get("fullName") or {}).get("value")
    if full:
        return full
    submitted = description.get("submissionNames") or []
    if submitted:
        return (submitted[0].get("fullName") or {}).get("value", "")
    return ""


def _genes(entry: dict) -> str:
    names = []
    for gene in entry.get("genes") or []:
        primary = (gene.get("geneName") or {}).get("value")
        if primary:
            names.append(primary)
    return "|".join(names)


def summarise(entry: dict) -> dict:
    sequence = entry.get("sequence") or {}
    cross_references = entry.get("uniProtKBCrossReferences") or []
    return {
        "accession": entry.get("primaryAccession"),
        "entryName": entry.get("uniProtkbId"),
        "reviewed": _reviewed(entry),
        "proteinName": _protein_name(entry),
        "genes": _genes(entry),
        "organism": (entry.get("organism") or {}).get("scientificName"),
        "length": sequence.get("length"),
        "pdbCount": sum(1 for x in cross_references if x.get("database") == "PDB"),
        "sequenceVersion": (entry.get("entryAudit") or {}).get("sequenceVersion"),
        "sequence": sequence.get("value"),
    }


def command_entry(args) -> None:
    entry = get_json(f"{UNIPROT_REST}/uniprotkb/{args.accession}.json")
    if entry is None:
        raise ServiceError(f"no UniProtKB entry {args.accession}")
    if args.output_format == "json":
        json.dump(entry, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return

    record = summarise(entry)
    print(f"# {record['accession']} ({record['entryName']}) -- {record['proteinName']}")
    print(f"# organism: {record['organism']}   length: {record['length']} aa")
    print(f"# reviewed (Swiss-Prot): {record['reviewed']}   PDB entries: {record['pdbCount']}")
    print(f"# genes: {record['genes'] or 'none listed'}")

    functions = [
        text.get("value", "")
        for comment in entry.get("comments") or []
        if comment.get("commentType") == "FUNCTION"
        for text in comment.get("texts") or []
    ]
    for text in functions[:2]:
        print(f"# function: {text[:300]}")
    locations = [
        (location.get("location") or {}).get("value")
        for comment in entry.get("comments") or []
        if comment.get("commentType") == "SUBCELLULAR LOCATION"
        for location in comment.get("subcellularLocations") or []
    ]
    if locations:
        print(f"# subcellular: {', '.join(filter(None, locations[:6]))}")
    print()
    print(record["sequence"] or "(no sequence)")


def command_search(args) -> None:
    params = {
        "query": args.query,
        "fields": args.fields or DEFAULT_SEARCH_FIELDS,
        "size": min(args.page_size, 500),
        "format": "json",
    }
    rows = []
    for page in uniprot_pages(f"{UNIPROT_REST}/uniprotkb/search", params):
        for entry in page.get("results") or []:
            rows.append(summarise(entry))
            if args.limit is not None and len(rows) >= args.limit:
                break
        if args.limit is not None and len(rows) >= args.limit:
            break

    reviewed = sum(1 for row in rows if row["reviewed"])
    print(
        f"# {len(rows)} entries ({reviewed} reviewed / {len(rows) - reviewed} unreviewed)",
        file=sys.stderr,
    )
    if rows and reviewed == 0 and "reviewed" not in args.query:
        print(
            "# note: no reviewed entries matched. Add `AND reviewed:true` unless you "
            "deliberately want TrEMBL.",
            file=sys.stderr,
        )
    columns = TABLE_COLUMNS + (("sequence",) if args.with_sequence else ())
    emit(rows, columns, args.output_format)


def command_fasta(args) -> None:
    for accession in args.accessions:
        suffix = "?includeIsoform=true" if args.isoforms else ""
        _, _, body = request_bytes(f"{UNIPROT_REST}/uniprotkb/{accession}.fasta{suffix}")
        text = body.decode("utf-8")
        if args.out:
            with open(args.out, "a", encoding="utf-8") as handle:
                handle.write(text)
        else:
            sys.stdout.write(text)
    if args.out:
        print(f"# appended {len(args.accessions)} record(s) to {args.out}", file=sys.stderr)


FEATURE_COLUMNS = ("type", "start", "end", "description", "ligand", "evidence")


def command_features(args) -> None:
    entry = get_json(f"{UNIPROT_REST}/uniprotkb/{args.accession}.json")
    if entry is None:
        raise ServiceError(f"no UniProtKB entry {args.accession}")

    wanted = [item.strip().lower() for item in (args.types or "").split(",") if item.strip()]
    rows = []
    for feature in entry.get("features") or []:
        kind = feature.get("type") or ""
        if wanted and not any(term in kind.lower() for term in wanted):
            continue
        location = feature.get("location") or {}
        ligand = (feature.get("ligand") or {}).get("name")
        rows.append(
            {
                "type": kind,
                "start": (location.get("start") or {}).get("value"),
                "end": (location.get("end") or {}).get("value"),
                "description": feature.get("description") or "",
                "ligand": ligand or "",
                # Evidence codes repeat once per supporting publication;
                # the distinct set is what tells you how well supported the
                # feature is.
                "evidence": "|".join(
                    dict.fromkeys(
                        item.get("evidenceCode", "") for item in feature.get("evidences") or []
                    )
                ),
            }
        )
    rows.sort(key=lambda row: (row["start"] is None, row["start"] or 0))
    kinds = sorted({row["type"] for row in rows})
    print(f"# {len(rows)} features: {', '.join(kinds) or 'none'}", file=sys.stderr)
    emit(rows, FEATURE_COLUMNS, args.output_format)


def command_map(args) -> None:
    """Run the asynchronous ID-mapping job and poll for its result.

    The results path depends on the target database: a UniProtKB target uses
    `/idmapping/uniprotkb/results/{job}` and returns full entries, anything
    else uses `/idmapping/results/{job}` and returns `{from, to}` pairs.
    Reading the wrong one gives rows with only a `from` key.
    """
    data = urllib.parse.urlencode(
        {"from": args.from_db, "to": args.to, "ids": ",".join(args.ids)}
    ).encode()
    _, _, body = request_bytes(f"{UNIPROT_REST}/idmapping/run", data=data, method="POST")
    job_id = json.loads(body.decode("utf-8"))["jobId"]

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        status = get_json(f"{UNIPROT_REST}/idmapping/status/{job_id}")
        if status is None:
            break
        if status.get("jobStatus") in {"RUNNING", "NEW", "QUEUED"}:
            time.sleep(1.0)
            continue
        break
    else:
        raise ServiceError(f"id-mapping job {job_id} did not finish in {args.timeout}s")

    rows = []
    seen_from = set()
    for page in uniprot_pages(f"{UNIPROT_REST}/idmapping/results/{job_id}", {"size": 500}):
        for pair in page.get("results") or []:
            source = pair.get("from")
            target = pair.get("to")
            seen_from.add(source)
            rows.append(
                {
                    "from": source,
                    "to": target if isinstance(target, str) else (target or {}).get("primaryAccession"),
                }
            )
        for failed in page.get("failedIds") or []:
            rows.append({"from": failed, "to": ""})

    unmapped = [identifier for identifier in args.ids if identifier not in seen_from]
    if unmapped:
        print(f"# unmapped: {', '.join(unmapped)}", file=sys.stderr)
    emit(rows, ("from", "to"), args.output_format)


PDB_COLUMNS = ("pdbId", "method", "resolution", "chains", "coverage")


def command_pdb(args) -> None:
    """PDB entries cross-referenced from a UniProt entry, with chain coverage.

    UniProt's own PDB cross-references carry method, resolution, and the
    chain/residue range each structure covers -- so this answers "which
    structure contains the kinase domain?" without a second service.
    """
    entry = get_json(
        f"{UNIPROT_REST}/uniprotkb/{args.accession}.json", {"fields": "xref_pdb"}
    )
    if entry is None:
        raise ServiceError(f"no UniProtKB entry {args.accession}")

    rows = []
    for reference in entry.get("uniProtKBCrossReferences") or []:
        if reference.get("database") != "PDB":
            continue
        properties = {
            item.get("key"): item.get("value") for item in reference.get("properties") or []
        }
        resolution_text = properties.get("Resolution", "")
        resolution = None
        if resolution_text and resolution_text[0].isdigit():
            try:
                resolution = float(resolution_text.split()[0])
            except ValueError:
                resolution = None
        rows.append(
            {
                "pdbId": reference.get("id"),
                "method": properties.get("Method"),
                "resolution": resolution,
                "chains": properties.get("Chains"),
                "coverage": properties.get("Chains", "").split("=")[-1],
            }
        )

    if args.max_resolution is not None:
        before = len(rows)
        rows = [
            row
            for row in rows
            if row["resolution"] is not None and row["resolution"] <= args.max_resolution
        ]
        print(
            f"# {len(rows)}/{before} entries at <= {args.max_resolution} A "
            "(NMR and predicted models have no resolution and are dropped by this filter)",
            file=sys.stderr,
        )
    rows.sort(key=lambda row: (row["resolution"] is None, row["resolution"] or 0))
    print(f"# {len(rows)} PDB entries for {args.accession}", file=sys.stderr)
    emit(rows, PDB_COLUMNS, args.output_format)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    entry = subparsers.add_parser("entry", help="one accession")
    entry.add_argument("accession")
    add_common_arguments(entry)
    entry.set_defaults(handler=command_entry)

    search = subparsers.add_parser("search", help="UniProt query syntax -> table")
    search.add_argument("query", help='e.g. "gene:EGFR AND organism_id:9606 AND reviewed:true"')
    search.add_argument("--fields", help="comma-separated UniProt return fields")
    search.add_argument("--limit", type=int, default=100, help="rows (default: 100)")
    search.add_argument("--page-size", type=int, default=100, help="rows per request (max 500)")
    search.add_argument("--with-sequence", action="store_true", help="include the sequence column")
    add_common_arguments(search)
    search.set_defaults(handler=command_search)

    fasta = subparsers.add_parser("fasta", help="sequences in FASTA")
    fasta.add_argument("accessions", nargs="+")
    fasta.add_argument("--isoforms", action="store_true", help="include isoform sequences")
    fasta.add_argument("--out", help="append to this file instead of stdout")
    add_common_arguments(fasta)
    fasta.set_defaults(handler=command_fasta)

    features = subparsers.add_parser("features", help="positional annotation")
    features.add_argument("accession")
    features.add_argument(
        "--types",
        help=f"comma-separated substrings to keep, e.g. Binding,Active. Common: "
        f"{', '.join(COMMON_FEATURE_TYPES[:10])}",
    )
    add_common_arguments(features)
    features.set_defaults(handler=command_features)

    mapping = subparsers.add_parser("map", help="cross-database id mapping")
    mapping.add_argument("ids", nargs="+")
    mapping.add_argument("--from", dest="from_db", default="UniProtKB_AC-ID", help="source database")
    mapping.add_argument("--to", default="PDB", help="target database, e.g. PDB, Ensembl, RefSeq_Protein")
    mapping.add_argument("--timeout", type=int, default=120, help="seconds to wait for the job")
    add_common_arguments(mapping)
    mapping.set_defaults(handler=command_map)

    pdb = subparsers.add_parser("pdb", help="PDB entries cross-referenced from an accession")
    pdb.add_argument("accession")
    pdb.add_argument("--max-resolution", type=float, help="keep entries at or below this resolution")
    add_common_arguments(pdb)
    pdb.set_defaults(handler=command_pdb)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except ServiceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
