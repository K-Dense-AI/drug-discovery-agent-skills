#!/usr/bin/env python3
"""Number antibody variable domains and annotate their CDRs.

Antibody positions are only meaningful with a scheme attached. "Residue 52" is
a different residue in IMGT, Kabat, and Chothia numbering, and CDR definitions
differ again -- Kabat CDR-H1 is 31-35B, Chothia CDR-H1 is 26-32, and they
overlap only partially. Reporting a position without its scheme is the most
common source of confusion in antibody work.

Wraps ANARCI (HMM alignment to germline V and J genes) and reports:

    summary     chain type, species, germline hit, CDR sequences and lengths
    regions     a table of region start/end over the input sequence, for
                `scan_liabilities.py --regions`
    numbering   every position with its scheme number and insertion code

Requires `pip install anarci` and HMMER (`hmmscan`) on PATH. ANARCI is
alignment-based, so it identifies chain type reliably; its species call is
the closest germline, which the authors themselves say is not a species
annotation tool.

Examples:

    python number_antibody.py antibody.fasta
    python number_antibody.py antibody.fasta --scheme kabat --format regions --out regions.tsv
    python number_antibody.py --sequence EVQLVESGG... --format numbering
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

SCHEMES = ("imgt", "kabat", "chothia", "martin", "aho", "wolfguy", "hmm")

#: CDR boundaries per scheme, as (start, end) inclusive in that scheme's own
#: numbering. Heavy and light differ in Kabat/Chothia/Martin and do not in
#: IMGT or AHo -- which is the main practical argument for IMGT.
CDR_DEFINITIONS: dict[str, dict[str, tuple[tuple[int, int], ...]]] = {
    "imgt": {
        "H": ((27, 38), (56, 65), (105, 117)),
        "L": ((27, 38), (56, 65), (105, 117)),
    },
    "kabat": {
        "H": ((31, 35), (50, 65), (95, 102)),
        "L": ((24, 34), (50, 56), (89, 97)),
    },
    "chothia": {
        "H": ((26, 32), (52, 56), (95, 102)),
        "L": ((24, 34), (50, 56), (89, 97)),
    },
    "martin": {
        "H": ((26, 32), (52, 56), (95, 102)),
        "L": ((24, 34), (50, 56), (89, 97)),
    },
    "aho": {
        "H": ((27, 42), (57, 76), (109, 137)),
        "L": ((27, 42), (57, 76), (109, 137)),
    },
}


def load_anarci():
    try:
        from anarci import run_anarci  # noqa: PLC0415
    except ImportError:
        print(
            "error: anarci is not installed. `pip install anarci` and make sure HMMER "
            "is available (`hmmscan` on PATH; conda install -c bioconda hmmer, or "
            "brew install hmmer).",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    return run_anarci


def read_sequences(args) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    for index, sequence in enumerate(args.sequence or [], start=1):
        records.append((f"sequence{index}", sequence.strip().upper()))
    for item in args.paths or []:
        path = Path(item)
        if not path.is_file():
            print(f"# warning: no such file: {path}", file=sys.stderr)
            continue
        name = ""
        chunks: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(">"):
                if chunks:
                    records.append((name, "".join(chunks).upper()))
                name = line[1:].strip().split()[0] if line[1:].strip() else "unnamed"
                chunks = []
            elif line.strip():
                chunks.append(line.strip())
        if chunks:
            records.append((name, "".join(chunks).upper()))
    return records


def region_of(position: int, chain_type: str, scheme: str) -> str:
    """Which region a scheme position falls in."""
    key = "H" if chain_type == "H" else "L"
    definitions = CDR_DEFINITIONS.get(scheme, CDR_DEFINITIONS["imgt"])[key]
    for index, (start, end) in enumerate(definitions, start=1):
        if start <= position <= end:
            return f"CDR{chain_type}{index}" if chain_type in ("H",) else f"CDR{key}{index}"
    boundaries = [definitions[0][0], definitions[0][1], definitions[1][0],
                  definitions[1][1], definitions[2][0], definitions[2][1]]
    if position < boundaries[0]:
        return "FR1"
    if position < boundaries[2]:
        return "FR2"
    if position < boundaries[4]:
        return "FR3"
    return "FR4"


def analyse(name: str, sequence: str, numbering, details, scheme: str) -> list[dict]:
    """One record per detected variable domain."""
    domains: list[dict] = []
    if not numbering:
        return domains

    for domain_index, (positions, start, end) in enumerate(numbering):
        detail = details[domain_index] if domain_index < len(details) else {}
        chain_type = detail.get("chain_type", "?")
        # ANARCI reports light chains as K (kappa) or L (lambda); the region
        # tables key on H vs L, so normalise here rather than at each use.
        region_key = "H" if chain_type == "H" else "L"

        offset = start  # 0-based index into the input sequence
        residues: list[tuple[int, str, str, str]] = []
        consumed = 0
        for (position, insertion), residue in positions:
            if residue == "-":
                continue
            index_in_input = offset + consumed
            consumed += 1
            residues.append(
                (
                    index_in_input + 1,  # 1-based over the input sequence
                    residue,
                    f"{position}{insertion.strip()}",
                    region_of(position, region_key, scheme),
                )
            )

        regions: dict[str, list[int]] = {}
        for input_position, _, _, region in residues:
            regions.setdefault(region, []).append(input_position)

        cdrs = {}
        for region, indices in regions.items():
            if region.startswith("CDR"):
                cdrs[region] = "".join(
                    residue for input_position, residue, _, _ in residues
                    if input_position in set(indices)
                )

        domains.append(
            {
                "name": name if len(numbering) == 1 else f"{name}_domain{domain_index + 1}",
                "chain_type": chain_type,
                "species": detail.get("species", ""),
                "germline": detail.get("id", ""),
                "evalue": detail.get("evalue"),
                "domain_start": start + 1,
                "domain_end": end + 1,
                "scheme": scheme,
                "residues": residues,
                "regions": regions,
                "cdrs": cdrs,
                "tail": sequence[end + 1 :],
            }
        )
    return domains


def emit_summary(domains: list[dict], stream) -> None:
    for domain in domains:
        stream.write(
            f"# {domain['name']}: chain {domain['chain_type']}, closest germline "
            f"{domain['germline']} ({domain['species']}), E={domain['evalue']:.1g}\n"
            if domain.get("evalue") is not None
            else f"# {domain['name']}: chain {domain['chain_type']}\n"
        )
        stream.write(
            f"#   variable domain spans input residues "
            f"{domain['domain_start']}-{domain['domain_end']}"
            + (f", tail of {len(domain['tail'])} residues follows\n" if domain["tail"] else "\n")
        )
        for region in sorted(domain["cdrs"]):
            sequence = domain["cdrs"][region]
            stream.write(f"  {region}\t{len(sequence)}\t{sequence}\n")
        stream.write("\n")


def emit_regions(domains: list[dict], stream, delimiter: str = "\t") -> None:
    writer = csv.writer(stream, delimiter=delimiter, lineterminator="\n")
    writer.writerow(("name", "chain_type", "scheme", "region", "start", "end", "sequence"))
    for domain in domains:
        for region, indices in sorted(
            domain["regions"].items(), key=lambda item: min(item[1])
        ):
            residues = {
                input_position: residue
                for input_position, residue, _, _ in domain["residues"]
            }
            writer.writerow(
                (
                    domain["name"],
                    domain["chain_type"],
                    domain["scheme"],
                    region,
                    min(indices),
                    max(indices),
                    "".join(residues[index] for index in sorted(indices)),
                )
            )


def emit_numbering(domains: list[dict], stream, delimiter: str = "\t") -> None:
    writer = csv.writer(stream, delimiter=delimiter, lineterminator="\n")
    writer.writerow(("name", "chain_type", "scheme", "input_position", "scheme_position",
                     "residue", "region"))
    for domain in domains:
        for input_position, residue, scheme_position, region in domain["residues"]:
            writer.writerow(
                (
                    domain["name"],
                    domain["chain_type"],
                    domain["scheme"],
                    input_position,
                    scheme_position,
                    residue,
                    region,
                )
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("paths", nargs="*", help="FASTA file(s)")
    parser.add_argument("--sequence", action="append", help="an inline sequence, repeatable")
    parser.add_argument(
        "--scheme",
        choices=SCHEMES,
        default="imgt",
        help="numbering scheme (default: imgt, the only one with a consistent "
        "definition across heavy and light chains)",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("summary", "regions", "numbering", "csv"),
        default="summary",
    )
    parser.add_argument("--out", help="write here instead of stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = read_sequences(args)
    if not records:
        print("error: no sequences given", file=sys.stderr)
        return 1

    run_anarci = load_anarci()
    payload = [(name, sequence) for name, sequence in records]
    _, numbering, details, _ = run_anarci(payload, scheme=args.scheme)

    domains: list[dict] = []
    for index, (name, sequence) in enumerate(records):
        if numbering[index] is None:
            print(
                f"# warning: {name} did not align to any antibody germline -- not a "
                "variable domain, or too divergent for the HMMs",
                file=sys.stderr,
            )
            continue
        domains.extend(
            analyse(name, sequence, numbering[index], details[index] or [], args.scheme)
        )

    if not domains:
        print("error: no variable domains identified", file=sys.stderr)
        return 1

    stream = open(args.out, "w", encoding="utf-8", newline="") if args.out else sys.stdout
    try:
        if args.output_format == "summary":
            emit_summary(domains, stream)
        elif args.output_format == "regions":
            emit_regions(domains, stream)
        elif args.output_format == "csv":
            emit_regions(domains, stream, delimiter=",")
        else:
            emit_numbering(domains, stream)
    finally:
        if args.out:
            stream.close()
            print(f"# wrote {args.out}", file=sys.stderr)

    heavy = sum(1 for domain in domains if domain["chain_type"] == "H")
    light = len(domains) - heavy
    print(f"# {len(domains)} variable domain(s): {heavy} heavy, {light} light", file=sys.stderr)
    print(
        f"# positions are {args.scheme.upper()} numbering -- always state the scheme "
        "when quoting a residue number",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
