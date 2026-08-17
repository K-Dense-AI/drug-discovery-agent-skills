#!/usr/bin/env python3
"""Scan antibody sequences for chemical and manufacturability liabilities.

These are the sequence motifs that turn into problems months later: a
deamidation site in CDR-H2 that loses potency on storage, an N-glycosylation
sequon in a CDR that makes the product heterogeneous, an unpaired cysteine that
drives aggregation, a Met that oxidises and takes affinity with it.

Nothing here needs a structure or a model — it is motif matching plus the
context rules that decide whether a match matters. What it cannot do is tell
you about conformational or aggregation liabilities, which need structure
(see references/developability.md).

**Position matters more than presence.** The same NG in a framework region is
usually tolerated and in CDR-H3 is usually not, because framework residues are
buried and paratope residues are exposed and load-bearing. Pass `--regions`
(from `number_antibody.py --format regions`) and the severity is adjusted
accordingly; without it, everything is reported as unknown-region.

Examples:

    python scan_liabilities.py antibody.fasta
    python scan_liabilities.py antibody.fasta --regions regions.tsv --format tsv
    python scan_liabilities.py --sequence EVQLVESGGGLVQPGG... --min-severity high
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

#: (name, regex, base severity, why it matters). Motifs are the ones with
#: consistent experimental support in the developability literature; the
#: severity is the *framework* baseline and is raised inside a CDR.
LIABILITY_MOTIFS: tuple[tuple[str, str, str, str], ...] = (
    (
        "N-glycosylation sequon",
        r"N[^P][ST]",
        "high",
        "N-X-S/T with X != P is a substrate for N-linked glycosylation; in a variable "
        "domain it produces glycoform heterogeneity and can block the paratope",
    ),
    (
        "deamidation (NG)",
        r"NG",
        "high",
        "the fastest-deamidating motif; Asn -> iso-Asp/Asp changes charge and can "
        "abolish binding, and it is the usual cause of potency loss on storage",
    ),
    (
        "deamidation (NS/NT/NN/NA/ND/NH)",
        r"N[STNADH]",
        "medium",
        "slower deamidation than NG but still a stability-indicating attribute",
    ),
    (
        "isomerisation (DG)",
        r"DG",
        "high",
        "Asp-Gly isomerises to iso-Asp through a succinimide intermediate; in a CDR "
        "this typically costs affinity",
    ),
    (
        "isomerisation (DS/DT/DD/DH)",
        r"D[STDH]",
        "medium",
        "slower Asp isomerisation; monitor if it sits in a binding loop",
    ),
    (
        "fragmentation (DP)",
        r"DP",
        "medium",
        "the Asp-Pro bond is acid-labile and clips during low-pH viral inactivation "
        "and elution steps",
    ),
    (
        "Met oxidation",
        r"M",
        "low",
        "surface-exposed Met oxidises to the sulfoxide; the concern is CDR and "
        "Fc positions, not buried framework Met",
    ),
    (
        "Trp oxidation",
        r"W",
        "low",
        "Trp oxidises under light and metal stress; in a CDR it is often a key "
        "contact residue, so oxidation is directly potency-relevant",
    ),
    (
        "free cysteine",
        r"C",
        "low",
        "counted per chain -- an odd number means an unpaired thiol, which drives "
        "disulfide scrambling and aggregation",
    ),
    (
        "N-terminal pyroglutamate",
        r"^[QE]",
        "low",
        "N-terminal Gln or Glu cyclises to pyroglutamate, producing a charge-variant "
        "peak; usually accepted as a product attribute rather than fixed",
    ),
    (
        "integrin-binding motif (RGD)",
        r"RGD",
        "medium",
        "RGD and RYD bind integrins and can cause off-target cell adhesion",
    ),
    (
        "integrin-binding motif (RYD)",
        r"RYD",
        "medium",
        "as RGD; RYD is the motif in the anti-integrin literature",
    ),
)

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

#: In-CDR promotion. Solvent exposure and functional load are both higher, so
#: the same motif is a bigger risk there.
CDR_PROMOTION = {"low": "medium", "medium": "high", "high": "critical"}

#: Motifs whose severity does not depend on position.
POSITION_INDEPENDENT = frozenset({"free cysteine", "N-terminal pyroglutamate"})


def read_sequences(args) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    for sequence in args.sequence or []:
        records.append(("sequence", sequence.strip().upper()))
    for item in args.paths or []:
        path = Path(item)
        if not path.is_file():
            print(f"# warning: no such file: {path}", file=sys.stderr)
            continue
        text = path.read_text(encoding="utf-8")
        if text.lstrip().startswith(">"):
            records.extend(_parse_fasta(text))
        else:
            records.extend(_parse_table(text, path))
    return records


def _parse_fasta(text: str) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    name = ""
    chunks: list[str] = []
    for line in text.splitlines():
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


def _parse_table(text: str, path: Path) -> list[tuple[str, str]]:
    """A CSV/TSV with a sequence column, and a name column if one is present."""
    delimiter = "\t" if "\t" in text.splitlines()[0] else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    if not reader.fieldnames:
        return []
    lowered = {name.lower(): name for name in reader.fieldnames}
    sequence_field = next(
        (lowered[key] for key in ("sequence", "seq", "aa", "protein_sequence") if key in lowered),
        None,
    )
    if sequence_field is None:
        print(
            f"# warning: {path} has no sequence column (looked for sequence/seq/aa)",
            file=sys.stderr,
        )
        return []
    name_field = next(
        (lowered[key] for key in ("name", "id", "chain", "label") if key in lowered), None
    )
    records = []
    for index, row in enumerate(reader, start=1):
        sequence = (row.get(sequence_field) or "").strip().upper()
        if not sequence:
            continue
        name = (row.get(name_field) or "").strip() if name_field else ""
        records.append((name or f"row{index}", sequence))
    return records


def load_regions(path: Path) -> dict[str, list[tuple[int, int, str]]]:
    """Region ranges per chain, as written by `number_antibody.py --format regions`.

    Expected columns: name, region, start, end (1-based, inclusive, over the
    input sequence).
    """
    regions: dict[str, list[tuple[int, int, str]]] = {}
    text = path.read_text(encoding="utf-8")
    delimiter = "\t" if "\t" in text.splitlines()[0] else ","
    for row in csv.DictReader(text.splitlines(), delimiter=delimiter):
        try:
            start = int(row["start"])
            end = int(row["end"])
        except (KeyError, TypeError, ValueError):
            continue
        regions.setdefault(row.get("name", ""), []).append((start, end, row.get("region", "")))
    return regions


def region_at(regions: list[tuple[int, int, str]], position: int) -> str:
    for start, end, name in regions:
        if start <= position <= end:
            return name
    return ""


def scan(name: str, sequence: str, regions: list[tuple[int, int, str]]) -> list[dict]:
    findings: list[dict] = []

    for label, pattern, base_severity, rationale in LIABILITY_MOTIFS:
        if label == "free cysteine":
            continue  # counted separately, below
        # Lookahead so overlapping motifs are all reported. re.finditer resumes
        # after each match, so in NNTS it would find the N1 sequon and never
        # look at N2 -- a real liability, silently absent from the report. The
        # same applies to the NG/N[STNADH] deamidation motifs in a run of Asn.
        for match in re.finditer(f"(?=({pattern}))", sequence):
            position = match.start() + 1
            region = region_at(regions, position)
            severity = base_severity
            if (
                label not in POSITION_INDEPENDENT
                and region.upper().startswith("CDR")
            ):
                severity = CDR_PROMOTION.get(base_severity, base_severity)
            findings.append(
                {
                    "name": name,
                    "liability": label,
                    "motif": match.group(1),
                    "position": position,
                    "region": region or "unknown",
                    "severity": severity,
                    "rationale": rationale,
                }
            )

    cysteines = [index + 1 for index, residue in enumerate(sequence) if residue == "C"]
    if len(cysteines) % 2 == 1:
        findings.append(
            {
                "name": name,
                "liability": "unpaired cysteine",
                "motif": "C",
                "position": cysteines[-1],
                "region": region_at(regions, cysteines[-1]) or "unknown",
                "severity": "critical",
                "rationale": (
                    f"{len(cysteines)} cysteines is an odd count, so at least one thiol is "
                    "unpaired -- a driver of disulfide scrambling, dimerisation, and "
                    "aggregation. Verify against the expected disulfide pattern."
                ),
            }
        )
    elif len(cysteines) > 2:
        findings.append(
            {
                "name": name,
                "liability": "extra cysteine pair",
                "motif": "C",
                "position": cysteines[-1],
                "region": region_at(regions, cysteines[-1]) or "unknown",
                "severity": "medium",
                "rationale": (
                    f"{len(cysteines)} cysteines: a variable domain normally carries two "
                    "(one intradomain disulfide). Extra pairs may be intentional, but "
                    "confirm they are not an unintended CDR cysteine."
                ),
            }
        )

    findings.sort(key=lambda item: (-SEVERITY_ORDER[item["severity"]], item["position"]))
    return findings


COLUMNS = ("name", "liability", "motif", "position", "region", "severity")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("paths", nargs="*", help="FASTA, CSV, or TSV files")
    parser.add_argument("--sequence", action="append", help="an inline sequence, repeatable")
    parser.add_argument(
        "--regions",
        help="region table from `number_antibody.py --format regions`, to weight CDR hits",
    )
    parser.add_argument(
        "--min-severity",
        choices=tuple(SEVERITY_ORDER),
        default="low",
        help="drop findings below this severity (default: low)",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "tsv", "csv"),
        default="text",
        help="text adds the rationale for each finding",
    )
    parser.add_argument("--out", help="write here instead of stdout")
    args = parser.parse_args(argv)

    records = read_sequences(args)
    if not records:
        print("error: no sequences given", file=sys.stderr)
        return 1

    regions_by_name: dict[str, list[tuple[int, int, str]]] = {}
    if args.regions:
        path = Path(args.regions)
        if not path.is_file():
            print(f"error: no such regions file: {path}", file=sys.stderr)
            return 1
        regions_by_name = load_regions(path)
    else:
        print(
            "# note: no --regions given, so CDR context is unknown and severities are "
            "the framework baseline. A liability in a CDR is materially worse; run "
            "number_antibody.py --format regions first.",
            file=sys.stderr,
        )

    threshold = SEVERITY_ORDER[args.min_severity]
    all_findings: list[dict] = []
    for name, sequence in records:
        unknown = set(sequence) - set("ACDEFGHIKLMNPQRSTVWYXBZUO")
        if unknown:
            print(
                f"# warning: {name} contains non-amino-acid characters "
                f"({''.join(sorted(unknown))}); is this a nucleotide sequence?",
                file=sys.stderr,
            )
        findings = scan(name, sequence, regions_by_name.get(name, []))
        all_findings.extend(
            item for item in findings if SEVERITY_ORDER[item["severity"]] >= threshold
        )

    stream = open(args.out, "w", encoding="utf-8", newline="") if args.out else sys.stdout
    try:
        if args.output_format in ("tsv", "csv"):
            writer = csv.writer(
                stream, delimiter="," if args.output_format == "csv" else "\t",
                lineterminator="\n",
            )
            writer.writerow(COLUMNS)
            for finding in all_findings:
                writer.writerow([finding[column] for column in COLUMNS])
        else:
            for name, sequence in records:
                findings = [item for item in all_findings if item["name"] == name]
                stream.write(f"# {name}: {len(sequence)} residues, {len(findings)} finding(s)\n")
                if not findings:
                    stream.write("  (none at this severity)\n\n")
                    continue
                for finding in findings:
                    stream.write(
                        f"  [{finding['severity']:8s}] {finding['liability']} "
                        f"'{finding['motif']}' at {finding['position']} "
                        f"({finding['region']})\n"
                        f"             {finding['rationale']}\n"
                    )
                stream.write("\n")
    finally:
        if args.out:
            stream.close()
            print(f"# wrote {len(all_findings)} finding(s) to {args.out}", file=sys.stderr)

    counts: dict[str, int] = {}
    for finding in all_findings:
        counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1
    summary = ", ".join(
        f"{counts[level]} {level}" for level in ("critical", "high", "medium", "low")
        if counts.get(level)
    )
    print(f"# {len(all_findings)} finding(s) across {len(records)} sequence(s): {summary or 'none'}",
          file=sys.stderr)
    print(
        "# these are sequence liabilities only. Aggregation, viscosity, and "
        "polyspecificity need structure or experiment -- see references/developability.md",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
