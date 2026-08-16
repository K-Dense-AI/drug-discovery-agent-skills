#!/usr/bin/env python3
"""Plan a relative free energy perturbation network and cost it before running.

Standard library only. OpenFE plans and runs the calculations; this reasons
about the network shape, which decides both the cost and whether the result
can be validated.

Four things this handles that planning by hand usually gets wrong:

* **A star map has no cycles, so it cannot be checked.** Cycle closure -- the
  requirement that free energy summed around a loop is zero -- is the only
  internal error estimate FEP has. A network with no cycles gives numbers with
  no way to tell whether they are wrong.
* **Cost is edges, not ligands.** A star map over N ligands is N-1 edges; a
  well-connected map is closer to 2N. At GPU-hours per edge, the difference
  between those decides whether the calculation happens.
* **The reference ligand carries the whole map.** In a star map every result
  is relative to one compound, so a bad reference -- poor pose, unusual
  chemistry, weak experimental value -- corrupts every edge.
* Perturbations that change net charge or transform large fragments are much
  less reliable. Flagging them at planning time is cheaper than discovering it
  in the results.

Commands:
    plan     build a network over a ligand set and report its shape
    cost     GPU-hours and wall-clock for a given edge count
    shapes   the network topologies and what each trades away

Examples:
    python fep_network.py plan --ligands lig1,lig2,lig3,lig4,lig5 --shape star --reference lig1
    python fep_network.py plan --ligands-file names.txt --shape cyclic
    python fep_network.py cost --edges 24 --gpus 4
    python fep_network.py shapes
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

#: Hours of GPU time for one edge at typical settings: 12 lambda windows,
#: 5 ns per window, complex and solvent legs, three repeats.
DEFAULT_HOURS_PER_EDGE = 24.0

#: Below three repeats an edge has no usable uncertainty of its own.
DEFAULT_REPEATS = 3

NETWORK_SHAPES = {
    "star": "every ligand connected to one reference; N-1 edges, no cycles, no validation",
    "cyclic": "star plus a ring through the periphery; ~2N-1 edges, every ligand in a cycle",
    "complete": "every pair connected; N(N-1)/2 edges, maximal redundancy, rarely affordable",
}


class NetworkError(RuntimeError):
    """A network that cannot be planned as requested."""


def read_ligands(args: argparse.Namespace) -> list[str]:
    names: list[str] = []
    if args.ligands:
        names += [item.strip() for item in args.ligands.split(",") if item.strip()]
    if args.ligands_file:
        stream = sys.stdin if args.ligands_file == "-" else open(args.ligands_file, encoding="utf-8")
        with stream as handle:
            names += [line.strip() for line in handle if line.strip() and not line.startswith("#")]
    if len(names) < 2:
        raise NetworkError("at least two ligands are needed for a relative calculation")
    if len(set(names)) != len(names):
        raise NetworkError("ligand names must be unique")
    return names


def star_edges(names: list[str], reference: str) -> list[tuple[str, str]]:
    if reference not in names:
        raise NetworkError(f"reference `{reference}` is not in the ligand list")
    return [(reference, name) for name in names if name != reference]


def cyclic_edges(names: list[str], reference: str) -> list[tuple[str, str]]:
    """Star plus a ring through the periphery, so every ligand sits in a cycle."""
    edges = star_edges(names, reference)
    periphery = [name for name in names if name != reference]
    if len(periphery) < 2:
        return edges
    for first, second in zip(periphery, periphery[1:]):
        edges.append((first, second))
    if len(periphery) > 2:
        edges.append((periphery[-1], periphery[0]))
    return edges


def complete_edges(names: list[str], reference: str) -> list[tuple[str, str]]:
    edges = []
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            edges.append((first, second))
    return edges


BUILDERS = {"star": star_edges, "cyclic": cyclic_edges, "complete": complete_edges}


def count_independent_cycles(names: list[str], edges: list[tuple[str, str]]) -> int:
    """Circuit rank: edges - nodes + connected components.

    This is the number of independent loops, and therefore the number of
    independent cycle-closure checks the network supports.
    """
    parent = {name: name for name in names}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    for first, second in edges:
        root_first, root_second = find(first), find(second)
        if root_first != root_second:
            parent[root_second] = root_first

    components = len({find(name) for name in names})
    return len(edges) - len(names) + components


def command_plan(args: argparse.Namespace) -> None:
    names = read_ligands(args)
    reference = args.reference or names[0]
    if args.shape not in BUILDERS:
        raise NetworkError(f"`{args.shape}` is not a shape; choose from {', '.join(BUILDERS)}")

    edges = BUILDERS[args.shape](names, reference)
    cycles = count_independent_cycles(names, edges)
    hours = len(edges) * args.hours_per_edge * args.repeats

    print(
        f"# {len(names)} ligands, {len(edges)} edges, {cycles} independent cycle(s)",
        file=sys.stderr,
    )
    if cycles == 0:
        print(
            "# no cycles: this network has NO internal error check. Cycle closure "
            "is the only self-consistency test FEP offers -- consider --shape cyclic.",
            file=sys.stderr,
        )
    if args.shape == "star":
        print(
            f"# every result is relative to `{reference}`. A bad reference -- poor "
            "pose, unusual chemistry, weak experimental value -- corrupts the whole map.",
            file=sys.stderr,
        )
    print(
        f"# {hours:,.0f} GPU-hours at {args.hours_per_edge:g} h/edge x {args.repeats} repeats",
        file=sys.stderr,
    )

    rows = [
        {"edge": index, "ligand_a": a, "ligand_b": b, "in_cycle": args.shape != "star"}
        for index, (a, b) in enumerate(edges)
    ]
    emit(rows, ["edge", "ligand_a", "ligand_b", "in_cycle"], args)


def command_cost(args: argparse.Namespace) -> None:
    total = args.edges * args.hours_per_edge * args.repeats
    wall = total / max(args.gpus, 1)
    result = {
        "edges": args.edges,
        "repeats": args.repeats,
        "hours_per_edge": args.hours_per_edge,
        "total_gpu_hours": round(total, 1),
        "gpus": args.gpus,
        "wall_clock_hours": round(wall, 1),
        "wall_clock_days": round(wall / 24.0, 2),
    }
    print(
        f"# {result['total_gpu_hours']:,} GPU-hours -> {result['wall_clock_days']} days "
        f"on {args.gpus} GPU(s)",
        file=sys.stderr,
    )
    print(
        "# FEP costs GPU-days for tens of compounds where docking costs seconds for "
        "millions. It buys accuracy on a congeneric series, not throughput.",
        file=sys.stderr,
    )
    emit([result], list(result), args)


def command_shapes(args: argparse.Namespace) -> None:
    print("shape\tedges for N ligands\ttrade-off")
    print("star\tN-1\t" + NETWORK_SHAPES["star"])
    print("cyclic\t~2N-1\t" + NETWORK_SHAPES["cyclic"])
    print("complete\tN(N-1)/2\t" + NETWORK_SHAPES["complete"])
    print(
        "\n# OpenFE's own planners (LOMAP scorer, minimal spanning network) choose "
        "edges by chemical similarity, which matters more than topology: a "
        "perturbation between similar ligands converges, one between dissimilar "
        "ligands may not converge at all.",
        file=sys.stderr,
    )


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

    plan = subparsers.add_parser("plan", help="build and describe a perturbation network")
    plan.add_argument("--ligands", help="comma-separated ligand names")
    plan.add_argument("--ligands-file", help="one name per line, or - for stdin")
    plan.add_argument(
        "--shape", choices=tuple(BUILDERS), default="cyclic", help="default: cyclic"
    )
    plan.add_argument("--reference", help="hub ligand (defaults to the first)")
    plan.set_defaults(handler=command_plan)

    cost = subparsers.add_parser("cost", help="GPU-hours for an edge count")
    cost.add_argument("--edges", type=int, required=True)
    cost.add_argument("--gpus", type=int, default=1, help="default: 1")
    cost.set_defaults(handler=command_cost)

    shapes = subparsers.add_parser("shapes", help="network topologies and their trade-offs")
    shapes.set_defaults(handler=command_shapes)

    for sub in (plan, cost):
        sub.add_argument(
            "--hours-per-edge",
            type=float,
            default=DEFAULT_HOURS_PER_EDGE,
            help=f"default: {DEFAULT_HOURS_PER_EDGE:g}",
        )
        sub.add_argument(
            "--repeats", type=int, default=DEFAULT_REPEATS, help=f"default: {DEFAULT_REPEATS}"
        )
    for sub in (plan, cost, shapes):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except NetworkError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
