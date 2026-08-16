#!/usr/bin/env python3
"""Read AiZynthFinder output and report what is actually makeable.

Standard library only. Handles both the plain and gzipped JSON that
`aizynthcli --output` produces.

Four things this handles that reading the JSON usually gets wrong:

* **"Solved" means every leaf is in your stock.** It is a statement about the
  stock file as much as the molecule, so the stock is reported alongside the
  fraction and a solved fraction quoted without one is meaningless.
* **A solved route is a proposal, not a validated synthesis.** The templates
  come from reactions that worked on *other* substrates. Nothing here knows
  about your substrate's chemoselectivity, protecting groups, or scale.
* **Route depth matters more than existence.** A nine-step linear route and a
  two-step route are both "solved". Depth, and the number of distinct starting
  materials, are what a chemist actually reads.
* **Unsolved does not mean unmakeable.** It means the search did not find a
  route within its time and depth limits using its templates. Novel chemistry
  is systematically invisible to a template-based model.

Commands:
    summary    solved fraction and route statistics across a run
    routes     the routes found for one target, shallowest first
    blocks     the starting materials the routes bottom out in

Examples:
    python route_report.py summary --output out.json.gz
    python route_report.py routes --output out.json.gz --target "CCOc1ccccc1"
    python route_report.py blocks --output out.json.gz --top 30
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter

#: Beyond this many steps a linear route is rarely worth pursuing as written.
DEEP_ROUTE = 6


class RouteError(RuntimeError):
    """Output that is not an AiZynthFinder result file."""


def load(path: str) -> list[dict]:
    """Read plain or gzipped AiZynthFinder JSON into a list of target records."""
    opener = gzip.open if path.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8") as handle:
            document = json.load(handle)
    except OSError as error:
        raise RouteError(f"cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise RouteError(f"{path} is not JSON: {error}") from error

    # aizynthcli writes {"data": {column: {row_index: value}}}; older and
    # hand-assembled files sometimes hold a plain list of records.
    if isinstance(document, dict) and "data" in document:
        data = document["data"]
        if not isinstance(data, dict) or not data:
            raise RouteError(f"{path} has an empty `data` block")
        columns = list(data)
        indices = sorted(data[columns[0]], key=lambda key: int(key))
        return [{column: data[column].get(index) for column in columns} for index in indices]
    if isinstance(document, list):
        return document
    raise RouteError(
        f"{path} does not look like aizynthcli output -- expected a `data` block "
        f"or a list, got keys {sorted(document)[:6]}"
    )


def walk(node: dict, depth: int = 0) -> tuple[int, list[str], int]:
    """Return (max depth in reactions, leaf SMILES, reaction count)."""
    if not isinstance(node, dict):
        return (depth, [], 0)
    kind = node.get("type")
    children = node.get("children") or []
    if not children:
        return (depth, [node["smiles"]] if kind == "mol" and node.get("smiles") else [], 0)

    reactions = 1 if kind == "reaction" else 0
    deepest = depth
    leaves: list[str] = []
    for child in children:
        child_depth, child_leaves, child_reactions = walk(
            child, depth + (1 if kind == "reaction" else 0)
        )
        deepest = max(deepest, child_depth)
        leaves += child_leaves
        reactions += child_reactions
    return (deepest, leaves, reactions)


def route_stats(tree: dict) -> dict:
    depth, leaves, reactions = walk(tree)
    in_stock = _count_in_stock(tree)
    return {
        "steps": reactions,
        "depth": depth,
        "starting_materials": len(leaves),
        "distinct_starting_materials": len(set(leaves)),
        "leaves_in_stock": in_stock,
        "leaves": sorted(set(leaves)),
    }


def _count_in_stock(node: dict) -> int:
    if not isinstance(node, dict):
        return 0
    children = node.get("children") or []
    if not children:
        return 1 if node.get("in_stock") else 0
    return sum(_count_in_stock(child) for child in children)


def as_bool(value) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes")


def trees_of(record: dict) -> list[dict]:
    trees = record.get("trees") or record.get("top_score_routes") or []
    return [tree for tree in trees if isinstance(tree, dict)]


def command_summary(args: argparse.Namespace) -> None:
    records = load(args.output)
    solved = [record for record in records if as_bool(record.get("is_solved"))]

    depths, steps = [], []
    for record in solved:
        for tree in trees_of(record)[:1]:
            stats = route_stats(tree)
            depths.append(stats["depth"])
            steps.append(stats["steps"])

    result = {
        "targets": len(records),
        "solved": len(solved),
        "solved_pct": round(100.0 * len(solved) / len(records), 1) if records else 0.0,
        "median_steps": _median(steps),
        "max_steps": max(steps) if steps else None,
        "deep_routes": sum(1 for value in steps if value > DEEP_ROUTE),
        "mean_search_time_s": _mean(
            [float(record["search_time"]) for record in records if record.get("search_time")]
        ),
    }

    print(
        f"# {result['solved']}/{result['targets']} solved ({result['solved_pct']}%)",
        file=sys.stderr,
    )
    print(
        "# `solved` means every leaf is in the stock file you configured. Quote "
        "the stock alongside this number or it means nothing.",
        file=sys.stderr,
    )
    if result["deep_routes"]:
        print(
            f"# {result['deep_routes']} route(s) longer than {DEEP_ROUTE} steps -- "
            "solved, but rarely worth running as written",
            file=sys.stderr,
        )
    unsolved = result["targets"] - result["solved"]
    if unsolved:
        print(
            f"# {unsolved} unsolved. That means no route was found within the time "
            "and depth limits using these templates -- not that the molecule "
            "cannot be made.",
            file=sys.stderr,
        )

    if args.output_format == "json":
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    for key, value in result.items():
        print(f"{key}\t{'' if value is None else value}")


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def command_routes(args: argparse.Namespace) -> None:
    records = load(args.output)
    if args.target:
        records = [r for r in records if (r.get("target") or "").strip() == args.target.strip()]
        if not records:
            raise RouteError(f"no target matching `{args.target}` in {args.output}")

    rows = []
    for record in records:
        target = record.get("target")
        for index, tree in enumerate(trees_of(record)[: args.n]):
            stats = route_stats(tree)
            rows.append(
                {
                    "target": target,
                    "route": index,
                    "steps": stats["steps"],
                    "starting_materials": stats["distinct_starting_materials"],
                    "leaves_in_stock": stats["leaves_in_stock"],
                    "score": record.get("top_score"),
                }
            )
    if not rows:
        print("# no routes in this output", file=sys.stderr)
        return
    rows.sort(key=lambda row: (row["steps"], -(row["leaves_in_stock"] or 0)))
    print(
        "# shallowest first. A short route with few distinct starting materials "
        "is what a chemist will actually run.",
        file=sys.stderr,
    )
    emit(rows, ["target", "route", "steps", "starting_materials", "leaves_in_stock", "score"], args)


def command_blocks(args: argparse.Namespace) -> None:
    records = load(args.output)
    counter: Counter[str] = Counter()
    for record in records:
        for tree in trees_of(record)[:1]:
            counter.update(route_stats(tree)["leaves"])
    if not counter:
        print("# no starting materials found -- were any targets solved?", file=sys.stderr)
        return
    rows = [
        {"starting_material": smiles, "routes_using_it": count}
        for smiles, count in counter.most_common(args.top)
    ]
    print(
        f"# {len(counter)} distinct starting materials across the best route per "
        "target. Materials shared by many routes are worth stocking.",
        file=sys.stderr,
    )
    emit(rows, ["starting_material", "routes_using_it"], args)


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
        writer.writerow(["" if row.get(c) is None else row[c] for c in columns])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary = subparsers.add_parser("summary", help="solved fraction and route statistics")
    summary.add_argument("--output", required=True, help="aizynthcli output .json or .json.gz")
    summary.set_defaults(handler=command_summary)

    routes = subparsers.add_parser("routes", help="routes for one target")
    routes.add_argument("--output", required=True)
    routes.add_argument("--target", help="target SMILES; omit for all")
    routes.add_argument("--n", type=int, default=5, help="routes per target (default: 5)")
    routes.set_defaults(handler=command_routes)

    blocks = subparsers.add_parser("blocks", help="starting materials the routes need")
    blocks.add_argument("--output", required=True)
    blocks.add_argument("--top", type=int, default=25, help="default: 25")
    blocks.set_defaults(handler=command_blocks)

    for sub in (summary, routes, blocks):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except RouteError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
