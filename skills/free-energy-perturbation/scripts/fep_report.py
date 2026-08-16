#!/usr/bin/env python3
"""Analyse FEP results: cycle closure, per-ligand free energies, and error against experiment.

Standard library only. OpenFE produces per-edge free energy differences; this
turns them into the three numbers that decide whether to believe the run.

Four things this handles that reading the edges usually gets wrong:

* **Cycle closure is the only internal error check FEP has.** Free energy is a
  state function, so the sum around any closed loop must be zero. It never is,
  and the deviation -- the hysteresis -- is a direct, assumption-free measure
  of the calculation's error. A network with no cycles cannot be checked.
* **Per-edge uncertainty understates the real error.** It reports how well the
  sampling converged, not whether the force field is right. Cycle closure
  catches what the repeat-to-repeat scatter does not.
* **Comparing to experiment needs the right quantity.** FEP gives relative
  free energies; converting IC50 to a free energy assumes the assay is at
  equilibrium and that IC50 tracks Kd. Both are frequently untrue.
* Only differences are computed, so absolute per-ligand values are anchored to
  one reference and are meaningful only within the network.

Commands:
    edges    per-edge results, worst-converged first
    cycles   cycle closure errors -- the internal consistency check
    rank     per-ligand free energies, propagated from a reference

Examples:
    python fep_report.py edges --results ddg.tsv
    python fep_report.py cycles --results ddg.tsv
    python fep_report.py rank --results ddg.tsv --reference lig1 --experimental exp.tsv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict

#: kcal/mol. Above this an edge's uncertainty makes it unusable for ranking.
HIGH_UNCERTAINTY = 1.0

#: kcal/mol. Cycle closure worse than this indicates a real problem.
POOR_CYCLE_CLOSURE = 1.0

#: RT at 298 K, kcal/mol -- for converting IC50 to a free energy.
RT_KCAL = 0.5924


class ReportError(RuntimeError):
    """Results that cannot support the analysis being asked for."""


def read_edges(path: str) -> list[dict]:
    """Read a ligand_a / ligand_b / ddg / uncertainty table (TSV or CSV)."""
    stream = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8")
    with stream as handle:
        text = handle.read()
    delimiter = "," if text.count(",") > text.count("\t") else "\t"
    rows = list(csv.DictReader(text.splitlines(), delimiter=delimiter))
    if not rows:
        raise ReportError(f"{path} has no rows")

    fields = {name.lower().strip(): name for name in rows[0]}
    a = _need(fields, ("ligand_a", "liganda", "ligand1", "from"), path)
    b = _need(fields, ("ligand_b", "ligandb", "ligand2", "to"), path)
    ddg = _need(fields, ("ddg", "ddg_kcal", "estimate", "dg"), path)
    unc = fields.get("uncertainty") or fields.get("error") or fields.get("ddg_error")

    edges = []
    for row in rows:
        try:
            value = float(row[ddg])
        except (TypeError, ValueError):
            continue
        edges.append(
            {
                "ligand_a": (row[a] or "").strip(),
                "ligand_b": (row[b] or "").strip(),
                "ddg": value,
                "uncertainty": _as_float(row.get(unc)) if unc else None,
            }
        )
    if not edges:
        raise ReportError(f"no usable rows in {path}")
    return edges


def _need(fields: dict, candidates, path: str) -> str:
    for name in candidates:
        if name in fields:
            return fields[name]
    raise ReportError(
        f"{path} has no column matching {candidates}. Expected a table with "
        "ligand_a, ligand_b, ddg, and optionally uncertainty -- "
        "`openfe gather` produces this."
    )


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def find_cycles(edges: list[dict], limit: int = 200) -> list[list[str]]:
    """Enumerate simple cycles up to length 6 by depth-first search.

    Longer cycles accumulate error from more edges and are less diagnostic, so
    the search is deliberately shallow.
    """
    graph: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        graph[edge["ligand_a"]].append(edge["ligand_b"])
        graph[edge["ligand_b"]].append(edge["ligand_a"])

    seen: set[frozenset] = set()
    cycles: list[list[str]] = []

    def walk(start: str, node: str, path: list[str]) -> None:
        if len(cycles) >= limit or len(path) > 6:
            return
        for neighbour in graph[node]:
            if neighbour == start and len(path) >= 3:
                key = frozenset(path)
                if key not in seen:
                    seen.add(key)
                    cycles.append(list(path))
            elif neighbour not in path and neighbour > start:
                walk(start, neighbour, path + [neighbour])

    for node in sorted(graph):
        walk(node, node, [node])
    return cycles


def edge_lookup(edges: list[dict]) -> dict[tuple[str, str], float]:
    """Directed lookup: (a, b) -> ddg, with the reverse negated."""
    table: dict[tuple[str, str], float] = {}
    for edge in edges:
        table[(edge["ligand_a"], edge["ligand_b"])] = edge["ddg"]
        table[(edge["ligand_b"], edge["ligand_a"])] = -edge["ddg"]
    return table


def cycle_closure(cycle: list[str], table: dict) -> float | None:
    """Sum of ddG around a closed loop. Should be zero; the deviation is error."""
    total = 0.0
    for first, second in zip(cycle, cycle[1:] + cycle[:1]):
        if (first, second) not in table:
            return None
        total += table[(first, second)]
    return total


def command_edges(args: argparse.Namespace) -> None:
    edges = read_edges(args.results)
    rows = sorted(
        edges, key=lambda edge: -(edge["uncertainty"] if edge["uncertainty"] is not None else 0.0)
    )
    for row in rows:
        row["usable"] = (
            row["uncertainty"] is None or row["uncertainty"] <= HIGH_UNCERTAINTY
        )

    unusable = [row for row in rows if not row["usable"]]
    print(f"# {len(edges)} edges", file=sys.stderr)
    if unusable:
        print(
            f"# {len(unusable)} edge(s) with uncertainty above "
            f"{HIGH_UNCERTAINTY:g} kcal/mol -- too noisy to rank with",
            file=sys.stderr,
        )
    print(
        "# per-edge uncertainty measures sampling convergence, not force-field "
        "accuracy. Cycle closure catches what it cannot.",
        file=sys.stderr,
    )
    emit(rows, ["ligand_a", "ligand_b", "ddg", "uncertainty", "usable"], args)


def command_cycles(args: argparse.Namespace) -> None:
    edges = read_edges(args.results)
    table = edge_lookup(edges)
    cycles = find_cycles(edges)

    if not cycles:
        print(
            "# no cycles in this network, so there is no internal consistency "
            "check available. A star map cannot be validated from its own "
            "results -- plan a cyclic network next time.",
            file=sys.stderr,
        )
        return

    rows = []
    for cycle in cycles:
        closure = cycle_closure(cycle, table)
        if closure is None:
            continue
        rows.append(
            {
                "cycle": " -> ".join(cycle + [cycle[0]]),
                "length": len(cycle),
                "closure_kcal": round(closure, 3),
                "abs_closure": round(abs(closure), 3),
                "acceptable": abs(closure) <= POOR_CYCLE_CLOSURE,
            }
        )
    rows.sort(key=lambda row: -row["abs_closure"])

    values = [row["abs_closure"] for row in rows]
    rmse = math.sqrt(sum(value ** 2 for value in values) / len(values)) if values else 0.0
    bad = sum(1 for row in rows if not row["acceptable"])

    print(
        f"# {len(rows)} cycle(s); RMS closure {rmse:.3f} kcal/mol, "
        f"{bad} above {POOR_CYCLE_CLOSURE:g}",
        file=sys.stderr,
    )
    print(
        "# free energy is a state function, so a loop must sum to zero. The "
        "deviation is a direct, assumption-free measure of the error.",
        file=sys.stderr,
    )
    if bad:
        print(
            "# poor closure usually means insufficient sampling on one edge, a bad "
            "atom mapping, or a perturbation that changes net charge",
            file=sys.stderr,
        )
    emit(rows, ["cycle", "length", "closure_kcal", "abs_closure", "acceptable"], args)


def command_rank(args: argparse.Namespace) -> None:
    edges = read_edges(args.results)
    table = edge_lookup(edges)
    nodes = sorted({edge["ligand_a"] for edge in edges} | {edge["ligand_b"] for edge in edges})

    reference = args.reference or nodes[0]
    if reference not in nodes:
        raise ReportError(f"reference `{reference}` is not in the results")

    # Breadth-first propagation from the reference, which is all a relative
    # calculation supports: values are meaningful only within this network.
    relative = {reference: 0.0}
    frontier = [reference]
    while frontier:
        current = frontier.pop(0)
        for node in nodes:
            if node in relative or (current, node) not in table:
                continue
            relative[node] = relative[current] + table[(current, node)]
            frontier.append(node)

    unreachable = [node for node in nodes if node not in relative]
    experimental = read_experimental(args.experimental) if args.experimental else {}

    rows = []
    for node in nodes:
        if node not in relative:
            continue
        row = {"ligand": node, "relative_dg": round(relative[node], 3)}
        if node in experimental:
            row["experimental_dg"] = round(experimental[node], 3)
        rows.append(row)

    if experimental:
        paired = [row for row in rows if "experimental_dg" in row]
        if len(paired) >= 2:
            offset = sum(row["experimental_dg"] - row["relative_dg"] for row in paired) / len(paired)
            errors = []
            for row in paired:
                predicted = row["relative_dg"] + offset
                row["predicted_dg"] = round(predicted, 3)
                row["error"] = round(predicted - row["experimental_dg"], 3)
                errors.append(abs(row["error"]))
            mue = sum(errors) / len(errors)
            rmse = math.sqrt(sum(error ** 2 for error in errors) / len(errors))
            print(
                f"# against {len(paired)} experimental values: MUE {mue:.2f}, "
                f"RMSE {rmse:.2f} kcal/mol",
                file=sys.stderr,
            )
            print(
                "# offset-corrected, because relative FEP has no absolute anchor. "
                "1 kcal/mol is roughly a 5-fold error in affinity.",
                file=sys.stderr,
            )

    rows.sort(key=lambda row: row["relative_dg"])
    if unreachable:
        print(
            f"# {len(unreachable)} ligand(s) not connected to {reference}: "
            f"{', '.join(unreachable)}",
            file=sys.stderr,
        )
    print(
        f"# values are relative to `{reference}` and meaningful only within this "
        "network. Lower is tighter binding.",
        file=sys.stderr,
    )
    print(
        "# each value follows ONE path from the reference. In a cyclic network "
        "different paths disagree by exactly the cycle closure error -- run "
        "`cycles` to see it. For a maximum-likelihood estimate that uses every "
        "path and weights by uncertainty, use cinnabar (`openfe gather` feeds it).",
        file=sys.stderr,
    )
    columns = ["ligand", "relative_dg"]
    if experimental:
        columns += ["predicted_dg", "experimental_dg", "error"]
    emit(rows, columns, args)


def read_experimental(path: str) -> dict[str, float]:
    """A ligand / value table. Accepts dG in kcal/mol, or IC50/Ki in molar."""
    with open(path, newline="", encoding="utf-8") as handle:
        text = handle.read()
    delimiter = "," if text.count(",") > text.count("\t") else "\t"
    rows = list(csv.DictReader(text.splitlines(), delimiter=delimiter))
    if not rows:
        raise ReportError(f"{path} has no rows")

    fields = {name.lower().strip(): name for name in rows[0]}
    ligand = fields.get("ligand") or fields.get("name") or fields.get("id")
    if ligand is None:
        raise ReportError(f"{path} needs a `ligand` column")

    values: dict[str, float] = {}
    for row in rows:
        name = (row[ligand] or "").strip()
        if not name:
            continue
        if "dg" in fields:
            value = _as_float(row[fields["dg"]])
            if value is not None:
                values[name] = value
            continue
        for key in ("ic50", "ki", "kd"):
            if key in fields:
                measured = _as_float(row[fields[key]])
                if measured and measured > 0:
                    values[name] = RT_KCAL * math.log(measured)
                break
    if not values:
        raise ReportError(f"no usable values in {path}; give a dg, ic50, ki, or kd column")
    return values


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
                "" if row.get(c) is None
                else "true" if row[c] is True
                else "false" if row[c] is False
                else row[c]
                for c in columns
            ]
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler, help_text in (
        ("edges", command_edges, "per-edge results, worst-converged first"),
        ("cycles", command_cycles, "cycle closure errors"),
        ("rank", command_rank, "per-ligand free energies"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--results", required=True, help="edge table, or - for stdin")
        if name == "rank":
            sub.add_argument("--reference", help="anchor ligand (defaults to the first)")
            sub.add_argument("--experimental", help="ligand/value table to compare against")
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
        sub.set_defaults(handler=handler)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except ReportError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
