#!/usr/bin/env python3
"""Plan a binder design campaign: pipeline choice, trajectory count, and cost.

Standard library only. No design tool is invoked; this decides what to run
before GPU time is spent.

Four things this handles that starting a campaign usually gets wrong:

* **Success rate is per campaign, not per design.** BindCraft reports 10-100%
  experimental success across targets, and the low end is common for a hard
  epitope. The number of trajectories must be chosen so that the expected
  survivor count is enough to fill a plate, not so that one design exists.
* **BindCraft and RFdiffusion fail differently.** BindCraft co-folds binder and
  target at every step, so it accounts for target flexibility; RFdiffusion
  generates a backbone against a fixed target and needs ProteinMPNN plus an
  AlphaFold2 filter afterwards. On a flexible target that difference decides
  the campaign.
* **The filter pass rate is the hidden cost.** Typically only a few percent of
  trajectories survive the interface filters, so the trajectory count must be
  set from the pass rate, not from the number of binders wanted.
* Ordering fewer than about twenty designs wastes the campaign. The in-silico
  metrics cannot pick which of them binds, so the plate is the experiment.

Commands:
    plan      trajectories and GPU time for a target survivor count
    pipelines the design pipelines and when each fits
    checklist what to have ready before starting

Examples:
    python design_manifest.py plan --want 24 --pass-rate 0.03
    python design_manifest.py plan --want 24 --pipeline rfdiffusion --gpu-hours 0.4
    python design_manifest.py pipelines
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

#: Fraction of trajectories that survive the interface filters. Highly
#: target-dependent; a few percent is typical.
DEFAULT_PASS_RATE = 0.03

#: GPU-hours per trajectory, order of magnitude.
GPU_HOURS = {"bindcraft": 0.5, "rfdiffusion": 0.4}

#: Designs below this are not worth ordering: the metrics cannot pick the
#: winner, so the plate is the experiment.
MIN_ORDER = 20

PIPELINES = {
    "bindcraft": {
        "approach": "AlphaFold2-guided hallucination with ProteinMPNN sequence redesign",
        "fits": "the default choice. Co-folds binder and target at every iteration, so it "
                "accounts for target flexibility and needs no known binding site",
        "needs": "AlphaFold2 weights, a target PDB, hotspot residues",
        "note": "Nature 2025; reported 10-100% experimental success, MIT licensed",
    },
    "rfdiffusion": {
        "approach": "diffusion backbone generation, then ProteinMPNN, then AlphaFold2 filtering",
        "fits": "rigid targets, and when you want explicit control of the binder fold or "
                "secondary-structure content",
        "needs": "RFdiffusion weights, ProteinMPNN, AlphaFold2, a target PDB, hotspots",
        "note": "generates against a FIXED target, so induced fit is invisible to it",
    },
    "rfdiffusion2": {
        "approach": "the successor, with improved motif scaffolding",
        "fits": "as RFdiffusion, with better performance on enzyme and motif problems",
        "needs": "as RFdiffusion",
        "note": "check the current licence terms before commercial use",
    },
}

CHECKLIST = (
    ("target structure", "experimental where possible; an AlphaFold model biases toward a closed apo state"),
    ("epitope chosen", "hotspot residues, surface-exposed, 3-6 of them, within ~25 A"),
    ("target trimmed", "100-200 residues around the epitope"),
    ("glycans and disorder removed", "neither is modelled, and both bias the interface"),
    ("competition defined", "if a natural ligand binds there, the binder must outcompete it"),
    ("assay ready", "BLI or SPR, plus a negative control target"),
    ("expression route", "E. coli for small helical binders; anything else is slower"),
)


class ManifestError(RuntimeError):
    """A campaign that cannot be planned as requested."""


def command_plan(args: argparse.Namespace) -> None:
    if not 0 < args.pass_rate <= 1:
        raise ManifestError("--pass-rate must be between 0 and 1")
    if args.want < 1:
        raise ManifestError("--want must be at least 1")

    pipeline = args.pipeline
    if pipeline not in PIPELINES:
        raise ManifestError(f"`{pipeline}` is not a pipeline; choose from {', '.join(PIPELINES)}")

    hours_each = args.gpu_hours or GPU_HOURS.get(pipeline, 0.5)
    trajectories = int(-(-args.want // args.pass_rate))  # ceiling division
    gpu_hours = trajectories * hours_each

    result = {
        "pipeline": pipeline,
        "designs_wanted": args.want,
        "filter_pass_rate": args.pass_rate,
        "trajectories_needed": trajectories,
        "gpu_hours_per_trajectory": hours_each,
        "total_gpu_hours": round(gpu_hours, 1),
        "gpus": args.gpus,
        "wall_clock_days": round(gpu_hours / max(args.gpus, 1) / 24.0, 2),
    }

    print(
        f"# {trajectories:,} trajectories to expect {args.want} filter survivors "
        f"at a {args.pass_rate:.0%} pass rate",
        file=sys.stderr,
    )
    print(
        f"# {result['total_gpu_hours']:,} GPU-hours -> {result['wall_clock_days']} "
        f"days on {args.gpus} GPU(s)",
        file=sys.stderr,
    )
    if args.want < MIN_ORDER:
        print(
            f"# {args.want} is below {MIN_ORDER}. The in-silico metrics cannot pick "
            "which design binds, so the plate is the experiment -- ordering fewer "
            "wastes the campaign.",
            file=sys.stderr,
        )
    print(
        "# the pass rate is the hidden cost and it is target-dependent. Reported "
        "experimental success spans 10-100% across targets, and a hard epitope "
        "sits at the bottom of that range.",
        file=sys.stderr,
    )
    emit([result], list(result), args)


def command_pipelines(args: argparse.Namespace) -> None:
    rows = [
        {
            "pipeline": name,
            "approach": spec["approach"],
            "fits": spec["fits"],
            "gpu_hours_per_trajectory": GPU_HOURS.get(name, ""),
            "note": spec["note"],
        }
        for name, spec in PIPELINES.items()
    ]
    print(
        "# BindCraft co-folds binder and target at every iteration, so target "
        "flexibility is accounted for. RFdiffusion generates against a FIXED "
        "target, so induced fit is invisible to it.",
        file=sys.stderr,
    )
    emit(rows, ["pipeline", "approach", "fits", "gpu_hours_per_trajectory", "note"], args)


def command_checklist(args: argparse.Namespace) -> None:
    rows = [{"item": item, "detail": detail} for item, detail in CHECKLIST]
    print(
        "# the epitope choice determines the campaign. Everything downstream is "
        "compute spent on that decision.",
        file=sys.stderr,
    )
    emit(rows, ["item", "detail"], args)


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

    plan = subparsers.add_parser("plan", help="trajectories and GPU time")
    plan.add_argument("--want", type=int, default=24, help="designs to order (default: 24)")
    plan.add_argument(
        "--pass-rate",
        type=float,
        default=DEFAULT_PASS_RATE,
        help=f"fraction surviving the filters (default: {DEFAULT_PASS_RATE})",
    )
    plan.add_argument(
        "--pipeline", choices=tuple(PIPELINES), default="bindcraft", help="default: bindcraft"
    )
    plan.add_argument("--gpu-hours", type=float, help="override GPU-hours per trajectory")
    plan.add_argument("--gpus", type=int, default=1, help="default: 1")
    plan.set_defaults(handler=command_plan)

    pipelines = subparsers.add_parser("pipelines", help="the design pipelines")
    pipelines.set_defaults(handler=command_pipelines)

    checklist = subparsers.add_parser("checklist", help="what to have ready first")
    checklist.set_defaults(handler=command_checklist)

    for sub in (plan, pipelines, checklist):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except ManifestError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
