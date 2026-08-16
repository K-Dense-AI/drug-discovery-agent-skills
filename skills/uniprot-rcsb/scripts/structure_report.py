#!/usr/bin/env python3
"""Report what is actually in a structure file, before you build on it.

Resolution tells you how well the observed density was fitted. It says nothing
about what is *missing*, and the things that break a docking or simulation run
are all absence: an unresolved loop across the binding site, a ligand modelled
at half occupancy, two alternate side-chain conformations, a chain that stops
30 residues before the domain you care about, waters and cryoprotectant left in
the file, a construct with a point mutation you did not notice.

Reads PDB or mmCIF -- no parser dependency, no RDKit, no Biopython.

    python structure_report.py 1IEP.cif
    python structure_report.py 1IEP.cif --chain A --sequence
    python structure_report.py model.pdb --gaps-near 315,320

Output sections:

    CHAINS     residues observed, numbering range, and gaps in that range
    LIGANDS    non-polymer components, atom counts, occupancy
    SOLVENT    waters, ions, and crystallisation additives
    ISSUES     alternate locations, partial occupancy, insertion codes,
               multiple models, hydrogens, and unresolved regions
"""

from __future__ import annotations

import argparse
import gzip
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import add_common_arguments, emit, write_table  # noqa: E402

WATERS = frozenset({"HOH", "DOD", "WAT"})

#: Monatomic ions and the usual crystallisation, buffer, and cryoprotectant
#: components. Reported separately from ligands so "does this structure have a
#: ligand?" does not answer yes because of a sulfate.
ADDITIVES = frozenset(
    {
        "SO4", "PO4", "GOL", "EDO", "PEG", "PGE", "PG4", "1PE", "2PE", "MPD", "DMS",
        "ACT", "ACY", "FMT", "MES", "TRS", "EPE", "CIT", "TLA", "MLI", "IMD", "BME",
        "NA", "K", "MG", "CA", "ZN", "MN", "FE", "FE2", "NI", "CO", "CU", "CU1",
        "CD", "HG", "CL", "BR", "IOD", "F", "NO3", "AZI", "CO3", "NH4", "OXY",
        "UNX", "UNL", "PGO", "BU3", "P6G", "12P", "15P", "XPE", "SCN", "MLA",
    }
)

THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q",
    "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V", "SEC": "U", "PYL": "O",
    "MSE": "M", "HSD": "H", "HSE": "H", "HSP": "H", "CSO": "C", "PTR": "Y",
    "SEP": "S", "TPO": "T", "KCX": "K", "LLP": "K", "MLY": "K", "CME": "C",
    "DA": "a", "DC": "c", "DG": "g", "DT": "t", "A": "a", "C": "c", "G": "g",
    "U": "u",
}


class Atom:
    __slots__ = (
        "record", "name", "altloc", "resname", "chain", "resseq", "icode",
        "occupancy", "element", "model",
    )

    def __init__(self, record, name, altloc, resname, chain, resseq, icode,
                 occupancy, element, model):
        self.record = record
        self.name = name
        self.altloc = altloc
        self.resname = resname
        self.chain = chain
        self.resseq = resseq
        self.icode = icode
        self.occupancy = occupancy
        self.element = element
        self.model = model


def read_text(path: Path) -> str:
    data = path.read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8", "replace")


def parse_pdb(text: str) -> list[Atom]:
    """Fixed-column PDB parsing. Columns are positional by specification."""
    atoms: list[Atom] = []
    model = 1
    for line in text.splitlines():
        if line.startswith("MODEL"):
            try:
                model = int(line[10:14])
            except ValueError:
                model += 1
            continue
        if not line.startswith(("ATOM", "HETATM")):
            continue
        try:
            resseq = int(line[22:26])
        except ValueError:
            continue
        try:
            occupancy = float(line[54:60])
        except ValueError:
            occupancy = 1.0
        atoms.append(
            Atom(
                record=line[:6].strip(),
                name=line[12:16].strip(),
                altloc=line[16].strip(),
                resname=line[17:20].strip(),
                chain=line[21].strip() or "?",
                resseq=resseq,
                icode=line[26].strip(),
                occupancy=occupancy,
                element=line[76:78].strip().upper() if len(line) >= 78 else "",
                model=model,
            )
        )
    return atoms


def parse_mmcif(text: str) -> list[Atom]:
    """Minimal `_atom_site` loop reader.

    Only the atom_site category is parsed, and only the columns this report
    needs -- resolved by name from the loop header, so column order does not
    matter. Quoted values are handled; multi-line semicolon values do not
    occur inside atom_site.
    """
    atoms: list[Atom] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if line != "loop_":
            index += 1
            continue
        index += 1
        headers: list[str] = []
        while index < len(lines) and lines[index].strip().startswith("_"):
            headers.append(lines[index].strip())
            index += 1
        if not headers or not headers[0].startswith("_atom_site."):
            continue
        columns = {name.split(".", 1)[1]: position for position, name in enumerate(headers)}

        def field(values: list[str], key: str, default: str = "") -> str:
            position = columns.get(key)
            if position is None or position >= len(values):
                return default
            value = values[position]
            return "" if value in (".", "?") else value

        while index < len(lines):
            row = lines[index]
            stripped = row.strip()
            if not stripped or stripped.startswith(("#", "loop_", "_", "data_")):
                break
            values = _split_cif_row(stripped)
            index += 1
            if len(values) < len(headers) - 2:
                continue
            try:
                resseq = int(field(values, "auth_seq_id") or field(values, "label_seq_id") or "0")
            except ValueError:
                continue
            try:
                occupancy = float(field(values, "occupancy", "1.0") or 1.0)
            except ValueError:
                occupancy = 1.0
            try:
                model = int(field(values, "pdbx_PDB_model_num", "1") or 1)
            except ValueError:
                model = 1
            atoms.append(
                Atom(
                    record=field(values, "group_PDB", "ATOM"),
                    name=field(values, "auth_atom_id") or field(values, "label_atom_id"),
                    altloc=field(values, "label_alt_id"),
                    resname=field(values, "auth_comp_id") or field(values, "label_comp_id"),
                    chain=field(values, "auth_asym_id") or field(values, "label_asym_id") or "?",
                    resseq=resseq,
                    icode=field(values, "pdbx_PDB_ins_code"),
                    occupancy=occupancy,
                    element=field(values, "type_symbol").upper(),
                    model=model,
                )
            )
        continue
    return atoms


def _split_cif_row(row: str) -> list[str]:
    values: list[str] = []
    token = ""
    quote = ""
    for character in row:
        if quote:
            if character == quote:
                quote = ""
                values.append(token)
                token = ""
            else:
                token += character
        elif character in "'\"":
            quote = character
        elif character.isspace():
            if token:
                values.append(token)
                token = ""
        else:
            token += character
    if token:
        values.append(token)
    return values


def parse_unobserved(text: str, is_cif: bool) -> dict[str, list[int]]:
    """Residues the depositor declared present in the construct but not modelled.

    This is the half of "missing" that atom records cannot show: a residue
    absent from both ends of a chain leaves no gap in the numbering, so a
    report built only from ATOM records calls a truncated construct complete.
    Both formats state it outright -- mmCIF in
    `_pdbx_unobs_or_zero_occ_residues`, PDB in `REMARK 465`.
    """
    unobserved: dict[str, list[int]] = defaultdict(list)
    if is_cif:
        lines = text.splitlines()
        index = 0
        while index < len(lines):
            if lines[index].strip() != "loop_":
                index += 1
                continue
            index += 1
            headers = []
            while index < len(lines) and lines[index].strip().startswith("_"):
                headers.append(lines[index].strip())
                index += 1
            if not headers or not headers[0].startswith("_pdbx_unobs_or_zero_occ_residues."):
                continue
            columns = {name.split(".", 1)[1]: position for position, name in enumerate(headers)}
            chain_column = columns.get("auth_asym_id", columns.get("label_asym_id"))
            seq_column = columns.get("auth_seq_id", columns.get("label_seq_id"))
            while index < len(lines):
                stripped = lines[index].strip()
                if not stripped or stripped.startswith(("#", "loop_", "_", "data_")):
                    break
                values = _split_cif_row(stripped)
                index += 1
                if chain_column is None or seq_column is None or seq_column >= len(values):
                    continue
                try:
                    unobserved[values[chain_column]].append(int(values[seq_column]))
                except ValueError:
                    continue
            break
        return dict(unobserved)

    for line in text.splitlines():
        if not line.startswith("REMARK 465"):
            continue
        body = line[10:].strip()
        parts = body.split()
        # `RES C SSSEQI`, optionally preceded by a model number. Header and
        # explanatory lines never match this shape.
        if len(parts) >= 3 and parts[0].isdigit():
            parts = parts[1:]
        if len(parts) == 3 and len(parts[0]) == 3 and parts[0].isalpha() and len(parts[1]) == 1:
            try:
                unobserved[parts[1]].append(int(parts[2]))
            except ValueError:
                continue
    return dict(unobserved)


def load(path: Path) -> list[Atom]:
    text = read_text(path)
    name = path.name.lower()
    if name.endswith((".cif", ".mmcif", ".cif.gz", ".mmcif.gz")) or "_atom_site." in text:
        return parse_mmcif(text)
    return parse_pdb(text)


def analyse(
    atoms: list[Atom],
    model: int | None = None,
    unobserved: dict[str, list[int]] | None = None,
) -> dict:
    if model is None:
        models = sorted({atom.model for atom in atoms})
        model = models[0] if models else 1
    working = [atom for atom in atoms if atom.model == model]

    chains: dict[str, dict] = defaultdict(
        lambda: {"residues": {}, "atoms": 0, "hetatm": 0}
    )
    ligands: dict[tuple[str, str, int], dict] = {}
    solvent_counts: dict[str, int] = defaultdict(int)
    altloc_residues: set[tuple[str, int]] = set()
    partial_occupancy = 0
    insertion_codes: set[str] = set()
    hydrogens = 0

    for atom in working:
        if atom.element == "H" or (not atom.element and atom.name.startswith("H")):
            hydrogens += 1
        if atom.altloc:
            altloc_residues.add((atom.chain, atom.resseq))
        if atom.occupancy < 0.99:
            partial_occupancy += 1
        if atom.icode:
            insertion_codes.add(f"{atom.chain}{atom.resseq}{atom.icode}")

        if atom.resname in WATERS:
            solvent_counts["water"] += 1
            continue
        if atom.record == "HETATM" and atom.resname in ADDITIVES:
            solvent_counts[atom.resname] += 1
            continue
        if atom.record == "HETATM" and atom.resname not in THREE_TO_ONE:
            key = (atom.chain, atom.resname, atom.resseq)
            entry = ligands.setdefault(
                key,
                {
                    "chain": atom.chain,
                    "component": atom.resname,
                    "resseq": atom.resseq,
                    "atoms": 0,
                    "minOccupancy": 1.0,
                    "hasAltloc": False,
                },
            )
            entry["atoms"] += 1
            entry["minOccupancy"] = min(entry["minOccupancy"], atom.occupancy)
            entry["hasAltloc"] = entry["hasAltloc"] or bool(atom.altloc)
            continue

        chain = chains[atom.chain]
        chain["atoms"] += 1
        chain["residues"].setdefault(atom.resseq, atom.resname)

    unobserved = unobserved or {}
    chain_rows = []
    for name, data in sorted(chains.items()):
        numbers = sorted(data["residues"])
        if not numbers:
            continue
        expected = set(range(numbers[0], numbers[-1] + 1))
        internal = sorted(expected - set(numbers))
        declared = sorted(set(unobserved.get(name, [])))
        # Split the depositor's unobserved list around the modelled range:
        # a gap through a loop and 30 missing residues off the N-terminus are
        # different problems, and only the first shows up as a numbering gap.
        terminal = [number for number in declared if number < numbers[0] or number > numbers[-1]]
        internal = sorted(set(internal) | {n for n in declared if numbers[0] < n < numbers[-1]})
        chain_rows.append(
            {
                "chain": name,
                "residues": len(numbers),
                "first": numbers[0],
                "last": numbers[-1],
                "span": numbers[-1] - numbers[0] + 1,
                "gapResidues": len(internal),
                "gaps": _ranges(internal),
                "terminalMissing": len(terminal),
                "terminal": _ranges(terminal),
                "atoms": data["atoms"],
                "sequence": "".join(
                    THREE_TO_ONE.get(data["residues"][number], "X") for number in numbers
                ),
            }
        )

    return {
        "model": model,
        "models": sorted({atom.model for atom in atoms}),
        "chains": chain_rows,
        "ligands": sorted(ligands.values(), key=lambda row: -row["atoms"]),
        "solvent": dict(solvent_counts),
        "altlocResidues": len(altloc_residues),
        "partialOccupancyAtoms": partial_occupancy,
        "insertionCodes": sorted(insertion_codes),
        "hydrogens": hydrogens,
        "atoms": len(working),
    }


def _ranges(numbers: list[int]) -> str:
    """Collapse [3,4,5,9] to '3-5,9'."""
    if not numbers:
        return ""
    spans: list[str] = []
    start = previous = numbers[0]
    for number in numbers[1:]:
        if number == previous + 1:
            previous = number
            continue
        spans.append(f"{start}-{previous}" if start != previous else f"{start}")
        start = previous = number
    spans.append(f"{start}-{previous}" if start != previous else f"{start}")
    return ",".join(spans)


def _per_chain(summary: dict, key: str) -> str:
    """`A:723-725, B:867` for whichever chains have a non-empty value."""
    parts = [
        "{0}:{1}".format(row["chain"], row[key])
        for row in summary["chains"]
        if row.get(key)
    ]
    return ", ".join(parts)


def report(path: Path, summary: dict, args) -> None:
    print(f"# {path.name}: {summary['atoms']} atoms in model {summary['model']}")
    if len(summary["models"]) > 1:
        print(
            f"# {len(summary['models'])} models present (NMR ensemble or multi-state "
            f"refinement); reporting model {summary['model']} only"
        )
    print()

    print("## CHAINS")
    chain_columns = (
        "chain", "residues", "first", "last", "gapResidues", "gaps",
        "terminalMissing", "terminal", "atoms",
    )
    rows = summary["chains"]
    if args.chain:
        rows = [row for row in rows if row["chain"] in args.chain.split(",")]
    write_table(rows, chain_columns)
    print()

    print("## LIGANDS (non-polymer, excluding water/ions/additives)")
    if summary["ligands"]:
        write_table(
            summary["ligands"], ("chain", "component", "resseq", "atoms", "minOccupancy", "hasAltloc")
        )
    else:
        print("(none -- this is an apo structure, or the ligand is a modified residue)")
    print()

    print("## SOLVENT AND ADDITIVES")
    solvent = summary["solvent"]
    if solvent:
        write_table(
            [{"component": key, "atoms": value} for key, value in sorted(solvent.items())],
            ("component", "atoms"),
        )
    else:
        print("(none)")
    print()

    print("## ISSUES")
    issues = []
    total_gaps = sum(row["gapResidues"] for row in summary["chains"])
    if total_gaps:
        issues.append(
            f"{total_gaps} residues unresolved inside the modelled range "
            f"({_per_chain(summary, 'gaps')}) -- these are real atoms missing from the "
            "file, not a numbering artefact"
        )
    terminal_total = sum(row["terminalMissing"] for row in summary["chains"])
    if terminal_total:
        issues.append(
            f"{terminal_total} residues present in the construct but not modelled at the "
            f"chain termini ({_per_chain(summary, 'terminal')}) -- these leave no gap in "
            "the numbering, so they are invisible in the coordinates alone"
        )
    if summary["altlocResidues"]:
        issues.append(
            f"{summary['altlocResidues']} residues have alternate locations -- pick one "
            "conformer before preparing a receptor, or the tool will pick for you"
        )
    if summary["partialOccupancyAtoms"]:
        issues.append(
            f"{summary['partialOccupancyAtoms']} atoms at occupancy < 1.0 -- partially "
            "ordered, and a ligand at low occupancy may be barely there at all"
        )
    if summary["insertionCodes"]:
        issues.append(
            f"insertion codes present ({', '.join(summary['insertionCodes'][:6])}) -- "
            "residue numbering is not a plain integer sequence"
        )
    if len(summary["models"]) > 1:
        issues.append(f"{len(summary['models'])} models -- extract one before use")
    if not summary["hydrogens"]:
        issues.append(
            "no hydrogens (normal for X-ray) -- add them at your target pH during "
            "receptor preparation"
        )
    if summary["solvent"].get("water"):
        issues.append(
            f"{summary['solvent']['water']} water atoms present -- decide deliberately "
            "which to keep; conserved bridging waters can matter for docking"
        )
    if args.gaps_near:
        wanted = {int(item) for item in args.gaps_near.split(",") if item.strip()}
        for row in summary["chains"]:
            observed = set()
            for span in filter(None, row["gaps"].split(",")):
                if "-" in span:
                    low, high = span.split("-")
                    observed.update(range(int(low), int(high) + 1))
                else:
                    observed.add(int(span))
            hit = sorted(wanted & observed)
            if hit:
                issues.append(
                    f"chain {row['chain']}: residues of interest are UNRESOLVED: {hit}"
                )

    for issue in issues:
        print(f"- {issue}")
    if not issues:
        print("- none detected")

    if args.sequence:
        print()
        print("## SEQUENCES (observed residues only, gaps closed up)")
        for row in summary["chains"]:
            if args.chain and row["chain"] not in args.chain.split(","):
                continue
            print(f">{path.stem}_{row['chain']} {row['residues']} residues "
                  f"{row['first']}-{row['last']}")
            sequence = row["sequence"]
            for start in range(0, len(sequence), 60):
                print(sequence[start : start + 60])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", help="a .pdb, .cif, or gzipped structure file")
    parser.add_argument("--chain", help="restrict chain reporting to these (comma-separated)")
    parser.add_argument("--model", type=int, help="which model to analyse (default: the first)")
    parser.add_argument("--sequence", action="store_true", help="print observed sequences")
    parser.add_argument(
        "--gaps-near",
        help="comma-separated residue numbers to check against the unresolved list",
    )
    add_common_arguments(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.path)
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 1
    atoms = load(path)
    if not atoms:
        print(f"error: no ATOM/HETATM records found in {path}", file=sys.stderr)
        return 1
    text = read_text(path)
    unobserved = parse_unobserved(text, "_atom_site." in text)
    summary = analyse(atoms, args.model, unobserved)
    if args.output_format == "json":
        emit([summary], (), "json")
    else:
        report(path, summary, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
