#!/usr/bin/env python3
"""Prepare inputs for ternary complex prediction and reason about linker geometry.

Standard library only. The prediction tools themselves are external and mostly
need a GPU; this assembles what they ask for and checks the parts are coherent.

Four things this handles that setting up by hand usually gets wrong:

* **The E3 and target structures must both be the right constructs.** VHL
  needs Elongin B/C to fold; CRBN needs DDB1. Predicting against the isolated
  domain gives a complex that cannot exist, and benchmarking work has shown
  AlphaFold3's apparent performance on PROTAC ternaries is inflated by exactly
  these accessory proteins contributing interface area.
* **The exit vector is not the attachment atom.** The linker must leave each
  ligand from a solvent-exposed position that points toward the partner. A
  vector buried in the pocket cannot be linked from, whatever the docking says.
* **Linker length has a window per pair.** Too short and the proteins clash;
  too long and the entropic cost of ordering the complex swamps the enthalpy.
  Scanning a length series is the standard first experiment.
* Tool choice matters more here than for most modelling. PRosettaC outperforms
  AlphaFold3 on curated PROTAC ternary benchmarks once accessory-protein
  interface area is discounted.

Commands:
    manifest   an input manifest for a ternary prediction run
    linkers    a linker length series to synthesise
    tools      the prediction tools and what each needs

Examples:
    python ternary_setup.py manifest --target 6BOY --e3 vhl --warhead-vector "C12"
    python ternary_setup.py linkers --min 4 --max 16 --chemistry peg
    python ternary_setup.py tools
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

#: E3 complexes and the accessory subunits a valid model must include.
E3_COMPLEXES = {
    "vhl": {
        "core": "VHL",
        "accessory": ["Elongin B", "Elongin C"],
        "example_pdb": "5T35",
        "note": "VHL does not fold without Elongin B/C; model the trimer, not the domain",
    },
    "crbn": {
        "core": "CRBN",
        "accessory": ["DDB1"],
        "example_pdb": "4TZ4",
        "note": "DDB1 contributes substantial interface area that is not degrader-specific",
    },
    "iap": {
        "core": "cIAP1 / XIAP BIR3",
        "accessory": [],
        "example_pdb": "3UW5",
        "note": "the BIR domain alone is usually sufficient",
    },
    "mdm2": {
        "core": "MDM2",
        "accessory": [],
        "example_pdb": "4HG7",
        "note": "the p53-binding domain alone is usually sufficient",
    },
}

#: Linker chemistries and what each is for.
LINKER_CHEMISTRY = {
    "peg": "flexible, soluble; the default first series. Costs rotatable bonds and entropy",
    "alkyl": "flexible, lipophilic; better permeability than PEG, worse solubility",
    "rigid": "piperazine, piperidine, spiro, alkyne; fewer rotatable bonds, better exposure, "
             "but the geometry must already be right",
    "triazole": "click chemistry; fast to make a series, adds polarity and rigidity",
}

#: Ternary prediction tools.
TOOLS = {
    "PRosettaC": {
        "approach": "Rosetta protein-protein docking constrained by the two anchored ligands",
        "needs": "both structures, both ligand poses, the linker",
        "note": "outperforms AlphaFold3 on curated PROTAC ternary benchmarks",
    },
    "DeepTernary": {
        "approach": "SE(3)-equivariant encoder with a query-based decoder, trained on TernaryDB",
        "needs": "both structures and the degrader",
        "note": "state of the art on PROTAC benchmarks, and fast",
    },
    "AlphaFold3": {
        "approach": "end-to-end structure prediction with ligands",
        "needs": "sequences and the ligand",
        "note": "apparent performance is inflated by accessory proteins such as Elongin B/C "
                "and DDB1 contributing interface area that is not degrader-specific",
    },
    "SILCS-xTAC": {
        "approach": "site-identification by ligand competitive saturation, ensemble-based",
        "needs": "both structures plus precomputed SILCS maps",
        "note": "models the complex as an ensemble rather than a single pose",
    },
    "PROTAC-Model": {
        "approach": "FRODOCK protein-protein docking plus RosettaDock refinement",
        "needs": "both structures and ligand poses",
        "note": "open and scriptable",
    },
}

#: Typical usable linker length in heavy atoms between attachment points.
LINKER_WINDOW = (4, 20)


class TernaryError(RuntimeError):
    """An input combination that cannot describe a ternary complex."""


def command_manifest(args: argparse.Namespace) -> None:
    e3 = args.e3.lower()
    if e3 not in E3_COMPLEXES:
        raise TernaryError(f"`{args.e3}` is not a known E3; choose from {', '.join(E3_COMPLEXES)}")
    spec = E3_COMPLEXES[e3]

    manifest = {
        "target_structure": args.target,
        "target_ligand_vector": args.warhead_vector,
        "e3": spec["core"],
        "e3_accessory_subunits": spec["accessory"],
        "e3_reference_pdb": args.e3_pdb or spec["example_pdb"],
        "e3_ligand_vector": args.e3_vector,
        "linker_length_range": list(LINKER_WINDOW),
        "notes": [spec["note"]],
    }

    if spec["accessory"]:
        print(
            f"# {spec['core']} needs {', '.join(spec['accessory'])} in the model. "
            f"{spec['note']}.",
            file=sys.stderr,
        )
    if not args.warhead_vector or not args.e3_vector:
        print(
            "# exit vectors not fully specified. The linker must leave each ligand "
            "from a solvent-exposed atom pointing toward the partner -- an atom "
            "buried in the pocket cannot be linked from, whatever a docking pose "
            "suggests.",
            file=sys.stderr,
        )
        manifest["notes"].append("exit vectors incomplete")

    print(json.dumps(manifest, indent=2))


def command_linkers(args: argparse.Namespace) -> None:
    if args.chemistry not in LINKER_CHEMISTRY:
        raise TernaryError(
            f"`{args.chemistry}` is not a linker chemistry; choose from "
            f"{', '.join(LINKER_CHEMISTRY)}"
        )
    if args.min < 1 or args.max < args.min:
        raise TernaryError("--min must be at least 1 and no greater than --max")

    rows = []
    for length in range(args.min, args.max + 1, args.step):
        # A PEG unit is three heavy atoms (C-C-O); alkyl is one per carbon.
        units = length / 3.0 if args.chemistry == "peg" else float(length)
        rows.append(
            {
                "heavy_atoms": length,
                "approx_units": round(units, 1),
                "approx_extension_A": round(length * 1.25, 1),
                "in_typical_window": LINKER_WINDOW[0] <= length <= LINKER_WINDOW[1],
            }
        )

    print(f"# {len(rows)} linker lengths, {args.chemistry} chemistry", file=sys.stderr)
    print(f"# {LINKER_CHEMISTRY[args.chemistry]}", file=sys.stderr)
    print(
        "# scanning a length series is the standard first experiment, because "
        "the window is pair-specific: too short and the proteins clash, too long "
        "and the entropic cost of ordering the complex swamps the enthalpy.",
        file=sys.stderr,
    )
    print(
        "# extension is a rough 1.25 A per heavy atom for an extended chain; a "
        "real linker is not extended, so treat it as an upper bound.",
        file=sys.stderr,
    )
    emit(rows, ["heavy_atoms", "approx_units", "approx_extension_A", "in_typical_window"], args)


def command_tools(args: argparse.Namespace) -> None:
    rows = [
        {"tool": name, "approach": spec["approach"], "needs": spec["needs"], "note": spec["note"]}
        for name, spec in TOOLS.items()
    ]
    print(
        "# tool choice matters more here than for most modelling, and the "
        "benchmark literature disagrees with the obvious default.",
        file=sys.stderr,
    )
    emit(rows, ["tool", "approach", "needs", "note"], args)


def emit(rows: list[dict], columns: list[str], args: argparse.Namespace) -> None:
    if args.output_format == "json":
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    writer = csv.writer(
        sys.stdout, delimiter="," if args.output_format == "csv" else "\t", lineterminator="\n"
    )
    writer.writerow(columns)
    for row in rows:
        writer.writerow(
            [
                "true" if row.get(c) is True else "false" if row.get(c) is False else row.get(c, "")
                for c in columns
            ]
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser("manifest", help="input manifest for a ternary prediction")
    manifest.add_argument("--target", required=True, help="target PDB id or file")
    manifest.add_argument(
        "--e3", required=True, help=f"one of {', '.join(E3_COMPLEXES)}"
    )
    manifest.add_argument("--e3-pdb", help="override the reference E3 structure")
    manifest.add_argument("--warhead-vector", help="atom name the linker leaves the warhead from")
    manifest.add_argument("--e3-vector", help="atom name the linker leaves the E3 ligand from")
    manifest.set_defaults(handler=command_manifest)

    linkers = subparsers.add_parser("linkers", help="a linker length series")
    linkers.add_argument("--min", type=int, default=4, help="heavy atoms (default: 4)")
    linkers.add_argument("--max", type=int, default=16, help="heavy atoms (default: 16)")
    linkers.add_argument("--step", type=int, default=2, help="default: 2")
    linkers.add_argument(
        "--chemistry", choices=tuple(LINKER_CHEMISTRY), default="peg", help="default: peg"
    )
    linkers.set_defaults(handler=command_linkers)

    tools = subparsers.add_parser("tools", help="ternary complex prediction tools")
    tools.set_defaults(handler=command_tools)

    for sub in (manifest, linkers, tools):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except TernaryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
