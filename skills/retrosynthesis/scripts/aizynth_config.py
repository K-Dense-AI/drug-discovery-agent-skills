#!/usr/bin/env python3
"""Write AiZynthFinder configuration and check the pieces exist before a long run.

Standard library only. AiZynthFinder does the search; this writes the YAML it
reads and validates the file paths, because a missing model is discovered
after the run starts and wastes it.

Four things this handles that hand-writing the config usually gets wrong:

* **The config schema changed at version 4.** Version 3 took bare lists of
  file paths; version 4 takes typed blocks with `type:`, `model:`, and
  `template:` keys. A version-3 config fails against a version-4 install with
  an unhelpful error, and every tutorial older than 2024 shows the old form.
* **The stock file decides the answer, not the model.** A route is "solved"
  when every leaf is purchasable, so a small stock makes everything look
  unsynthesisable and an enormous one makes everything look trivial. Stock
  choice is the most consequential setting and the least discussed.
* **A filter policy is not optional in practice.** Without one the search
  proposes reactions the expansion model likes but that do not work, and the
  solved fraction becomes meaningless.
* `time_limit` and `iteration_limit` are per target. Multiply by the library
  size before starting, because the default is comfortable for ten molecules
  and impossible for ten thousand.

Commands:
    config   write an AiZynthFinder YAML configuration
    check    verify the referenced models and stock exist
    stocks   the stock options and what each implies

Examples:
    python aizynth_config.py config --model uspto_model.onnx \\
        --templates uspto_templates.csv.gz --stock zinc:zinc_stock.hdf5
    python aizynth_config.py check --config config.yml
    python aizynth_config.py stocks
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: Search algorithms AiZynthFinder 4 supports.
ALGORITHMS = ("mcts", "retrostar", "dfpn")

#: Stock back ends and what each is for.
STOCK_TYPES = {
    "inchiset": "an HDF5 or text set of InChI keys -- the usual choice",
    "mongodb": "a MongoDB collection, for a large in-house stock",
    "molbloom": "a Bloom filter over a very large catalogue; fast, approximate",
}

#: What choosing a given stock does to the reported solved fraction.
STOCK_GUIDANCE = {
    "zinc": "the default download; broad and public, a reasonable baseline",
    "emolecules": "large commercial catalogue; raises solved fraction substantially",
    "enamine-bb": "Enamine building blocks; what a REAL-space campaign should use",
    "in-house": "your own inventory; the only stock that reflects what you can start today",
}

DEFAULT_TIME_LIMIT = 120
DEFAULT_ITERATION_LIMIT = 100
DEFAULT_MAX_TRANSFORMS = 6


class ConfigError(RuntimeError):
    """A configuration AiZynthFinder cannot run."""


def parse_stock(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise ConfigError(
            f"--stock takes name:path, e.g. zinc:zinc_stock.hdf5 (got `{value}`)"
        )
    name, _, path = value.partition(":")
    if not name.strip() or not path.strip():
        raise ConfigError(f"--stock takes name:path (got `{value}`)")
    return name.strip(), path.strip()


def command_config(args: argparse.Namespace) -> None:
    stocks = [parse_stock(value) for value in args.stock]
    if not stocks:
        raise ConfigError("give at least one --stock; without one nothing can be solved")

    lines = [
        "# AiZynthFinder 4.x configuration.",
        "# Note the typed blocks -- version 3 used bare lists and is not compatible.",
        "",
        "expansion:",
        f"  {args.policy_name}:",
        "    type: template-based",
        f"    model: {args.model}",
        f"    template: {args.templates}",
    ]

    if args.filter_model:
        lines += [
            "",
            "filter:",
            f"  {args.policy_name}:",
            "    type: quick-filter",
            f"    model: {args.filter_model}",
        ]

    lines += ["", "stock:"]
    for name, path in stocks:
        lines += [f"  {name}:", f"    type: {args.stock_type}", f"    path: {path}"]

    lines += [
        "",
        "search:",
        f"  algorithm: {args.algorithm}",
        f"  time_limit: {args.time_limit}",
        f"  iteration_limit: {args.iteration_limit}",
        f"  max_transforms: {args.max_transforms}",
        "  return_first: false",
        "",
        "post_processing:",
        "  all_routes: true",
        f"  route_distance_report: {'true' if args.route_distances else 'false'}",
    ]

    print("\n".join(lines))

    if not args.filter_model:
        print(
            "# no filter policy set. Without one the search proposes reactions the "
            "expansion model likes but that do not work, and the solved fraction "
            "stops meaning anything.",
            file=sys.stderr,
        )
    per_target = args.time_limit
    print(
        f"# {per_target}s per target: {per_target / 60:.0f} min for 10 molecules, "
        f"{per_target * 1000 / 3600:.0f} h for 1000. Budget before starting.",
        file=sys.stderr,
    )
    print(
        f"# stock: {', '.join(name for name, _ in stocks)} -- this decides the "
        "answer more than the model does. A route is solved when every leaf is in "
        "stock.",
        file=sys.stderr,
    )
    print(
        "\n# run with:\n"
        "#   aizynthcli --config config.yml --smiles targets.smi --output out.json.gz",
        file=sys.stderr,
    )


def command_check(args: argparse.Namespace) -> None:
    path = Path(args.config)
    if not path.is_file():
        raise ConfigError(f"{path} does not exist")
    text = path.read_text(encoding="utf-8", errors="replace")

    if re.search(r"^\s*expansion:\s*$", text, re.MULTILINE) is None:
        raise ConfigError(f"{path} has no `expansion:` block; is this an AiZynthFinder config?")

    # Version-3 configs list bare paths under a policy name instead of typed keys.
    legacy = re.search(r"^\s+\w+:\s*\n\s+- \S+", text, re.MULTILINE)
    if legacy and "type:" not in text:
        print(
            "# this looks like a version-3 config (bare lists, no `type:` keys). "
            "AiZynthFinder 4 needs typed blocks -- `type: template-based` with "
            "`model:` and `template:`.",
            file=sys.stderr,
        )

    referenced = re.findall(r"^\s*(?:model|template|path):\s*(\S+)", text, re.MULTILINE)
    if not referenced:
        raise ConfigError("no model, template, or stock paths found in the config")

    missing = []
    print("path\texists\tsize_mb")
    for item in referenced:
        candidate = Path(item)
        if not candidate.is_absolute():
            candidate = path.parent / item
        exists = candidate.is_file()
        size = f"{candidate.stat().st_size / 1e6:.1f}" if exists else ""
        print(f"{item}\t{'true' if exists else 'false'}\t{size}")
        if not exists:
            missing.append(item)

    if missing:
        print(
            f"# {len(missing)} referenced file(s) missing. AiZynthFinder discovers "
            "this after the run starts. Download the public models with "
            "`download_public_data <dir>`.",
            file=sys.stderr,
        )
        raise ConfigError(f"missing: {', '.join(missing)}")
    print(f"# all {len(referenced)} referenced files present", file=sys.stderr)

    if "filter:" not in text:
        print("# no filter policy in this config -- see `config --filter-model`", file=sys.stderr)


def command_stocks(args: argparse.Namespace) -> None:
    print("stock\timplication")
    for name, note in STOCK_GUIDANCE.items():
        print(f"{name}\t{note}")
    print("\nbackend\tnotes")
    for name, note in STOCK_TYPES.items():
        print(f"{name}\t{note}")
    print(
        "\n# The stock is the definition of `solved`. Reporting a solved fraction "
        "without naming the stock is meaningless -- the same molecule is solved "
        "against eMolecules and unsolved against a small in-house set.",
        file=sys.stderr,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    config = subparsers.add_parser("config", help="write an AiZynthFinder YAML")
    config.add_argument("--model", required=True, help="expansion policy model file")
    config.add_argument("--templates", required=True, help="template library file")
    config.add_argument("--filter-model", help="filter policy model file (strongly recommended)")
    config.add_argument(
        "--stock", action="append", required=True, help="name:path, repeatable"
    )
    config.add_argument(
        "--stock-type", choices=tuple(STOCK_TYPES), default="inchiset", help="default: inchiset"
    )
    config.add_argument("--policy-name", default="uspto", help="default: uspto")
    config.add_argument(
        "--algorithm", choices=ALGORITHMS, default="mcts", help="default: mcts"
    )
    config.add_argument(
        "--time-limit", type=int, default=DEFAULT_TIME_LIMIT, help="seconds per target (default: 120)"
    )
    config.add_argument(
        "--iteration-limit", type=int, default=DEFAULT_ITERATION_LIMIT, help="default: 100"
    )
    config.add_argument(
        "--max-transforms", type=int, default=DEFAULT_MAX_TRANSFORMS, help="route depth (default: 6)"
    )
    config.add_argument(
        "--route-distances", action="store_true", help="cluster routes in post-processing"
    )
    config.set_defaults(handler=command_config)

    check = subparsers.add_parser("check", help="verify referenced files exist")
    check.add_argument("--config", required=True, help="path to the YAML")
    check.set_defaults(handler=command_check)

    stocks = subparsers.add_parser("stocks", help="stock options and their implications")
    stocks.set_defaults(handler=command_stocks)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except ConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
