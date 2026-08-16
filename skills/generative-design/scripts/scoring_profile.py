#!/usr/bin/env python3
"""Compose a REINVENT 4 multi-parameter scoring function.

Standard library only. The scoring function is the whole experiment: the model
will optimise exactly what you asked for, including the parts you did not mean.

Four things this handles that hand-writing the scoring block usually gets wrong:

* **A raw property is not a score.** REINVENT combines values in [0, 1], so
  every component needs a transform mapping its natural units onto that range.
  Omitting the transform silently lets molecular weight, in daltons, dominate
  everything else.
* **Geometric mean and arithmetic mean behave completely differently.** With
  the geometric mean a single zero component zeroes the total, which is what
  you want for a hard requirement. Arithmetic lets a strong component paper
  over a failed one.
* **Unbounded components get exploited.** Optimise molecular weight upward with
  no ceiling and the agent will happily produce a 900 Da molecule. Every
  transform here is bounded on both sides.
* Without a `custom_alerts` component the agent will rediscover reactive and
  PAINS-like chemistry, because those substructures often score well on
  everything else.

Commands:
    profile     a ready-made scoring block for a common objective
    component   one component's TOML, to paste into a stage
    transforms  the transforms and when each is right

Examples:
    python scoring_profile.py profile --objective lead-like
    python scoring_profile.py profile --objective cns --weight QED=0.4
    python scoring_profile.py component --name SlogP --low 1 --high 4
    python scoring_profile.py transforms
"""

from __future__ import annotations

import argparse
import sys

#: REINVENT transforms, and the shape each imposes on a raw value.
TRANSFORMS = {
    "sigmoid": "rises to 1 above `high`; use when more is better",
    "reverse_sigmoid": "falls to 0 above `high`; use when less is better",
    "double_sigmoid": "peaks between `low` and `high`; use for a target window",
    "step": "hard 0/1 at a threshold; brittle, gives the optimiser no gradient",
    "value_mapping": "explicit value-to-score table for categorical output",
    "left_step": "1 below the threshold, 0 above",
    "right_step": "0 below the threshold, 1 above",
}

#: Components this script can emit, with the transform that suits each and a
#: sensible window. Windows are conventions, not REINVENT defaults.
COMPONENTS = {
    "QED": {"transform": None, "window": None, "note": "already 0-1; no transform needed"},
    "MolecularWeight": {"transform": "double_sigmoid", "window": (250.0, 500.0)},
    "SlogP": {"transform": "double_sigmoid", "window": (1.0, 4.0)},
    "TPSA": {"transform": "double_sigmoid", "window": (40.0, 120.0)},
    "NumHBD": {"transform": "reverse_sigmoid", "window": (0.0, 5.0)},
    "NumRotBond": {"transform": "reverse_sigmoid", "window": (0.0, 8.0)},
    "NumAtomStereoCenters": {"transform": "reverse_sigmoid", "window": (0.0, 2.0)},
    "GraphLength": {"transform": "reverse_sigmoid", "window": (0.0, 20.0)},
    "custom_alerts": {"transform": None, "window": None, "note": "substructure veto; no transform"},
    "TanimotoSimilarity": {"transform": None, "window": None, "note": "already 0-1"},
    "MatchingSubstructure": {"transform": None, "window": None, "note": "0 or 1"},
}

#: Common objectives as weighted component sets.
PROFILES = {
    "lead-like": {
        "MolecularWeight": (0.15, (250.0, 400.0)),
        "SlogP": (0.15, (1.0, 3.5)),
        "TPSA": (0.10, (40.0, 110.0)),
        "NumHBD": (0.10, (0.0, 3.0)),
        "NumRotBond": (0.10, (0.0, 7.0)),
        "QED": (0.20, None),
        "custom_alerts": (0.20, None),
    },
    "cns": {
        "MolecularWeight": (0.15, (200.0, 380.0)),
        "SlogP": (0.20, (1.5, 3.5)),
        "TPSA": (0.25, (20.0, 70.0)),
        "NumHBD": (0.15, (0.0, 2.0)),
        "QED": (0.10, None),
        "custom_alerts": (0.15, None),
    },
    "fragment": {
        "MolecularWeight": (0.25, (140.0, 250.0)),
        "SlogP": (0.20, (0.0, 2.5)),
        "NumHBD": (0.15, (0.0, 3.0)),
        "NumRotBond": (0.15, (0.0, 3.0)),
        "custom_alerts": (0.25, None),
    },
}

#: The default set of structural alerts to veto. Extend for your project.
DEFAULT_ALERTS = (
    "[*;r8]",
    "[*;r9]",
    "[*;r10]",
    "[#8][#8]",
    "[#16][#16]",
    "[#7;!n][S;!$(S(=O)=O)]",
    "[#7;!n][#7;!n]",
    "C(=[O,S])[O,S]",
    "[#7;!n][C;!$(C(=[O,N])[N,O])][#16;!s]",
    "[#16][C;!$(C(=[O,N])[N,O])][#16]",
)


class ScoringError(RuntimeError):
    """A component or transform REINVENT will not accept."""


def component_toml(name: str, weight: float, window: tuple[float, float] | None) -> list[str]:
    if name not in COMPONENTS:
        raise ScoringError(
            f"`{name}` is not a component this script knows. Known: "
            f"{', '.join(sorted(COMPONENTS))}"
        )
    spec = COMPONENTS[name]
    lines = ["[[stage.scoring.component]]", f"[stage.scoring.component.{name}]"]

    if name == "custom_alerts":
        lines.append("[[stage.scoring.component.custom_alerts.endpoint]]")
        lines.append(f'name = "structural alerts"')
        lines.append(f"weight = {weight}")
        lines.append("params.smarts = [")
        for smarts in DEFAULT_ALERTS:
            lines.append(f'    "{smarts}",')
        lines.append("]")
        return lines

    lines.append(f"[[stage.scoring.component.{name}.endpoint]]")
    lines.append(f'name = "{name}"')
    lines.append(f"weight = {weight}")

    transform = spec["transform"]
    if transform is None:
        lines.append(f"# {spec.get('note', 'no transform needed')}")
        return lines

    bounds = window or spec["window"]
    if bounds is None:
        raise ScoringError(f"{name} needs a window; pass --low and --high")
    low, high = bounds
    if low >= high:
        raise ScoringError(f"--low ({low}) must be below --high ({high})")

    lines.append(f'transform.type = "{transform}"')
    if transform == "double_sigmoid":
        lines.append(f"transform.high = {high}")
        lines.append(f"transform.low = {low}")
        lines.append("transform.coef_div = 100.0")
        lines.append("transform.coef_si = 20.0")
        lines.append("transform.coef_se = 20.0")
    else:
        lines.append(f"transform.high = {high}")
        lines.append(f"transform.low = {low}")
        lines.append("transform.k = 0.5")
    return lines


def command_profile(args: argparse.Namespace) -> None:
    if args.objective not in PROFILES:
        raise ScoringError(
            f"`{args.objective}` is not a profile; choose from {', '.join(PROFILES)}"
        )
    profile = dict(PROFILES[args.objective])

    for override in args.weight or []:
        if "=" not in override:
            raise ScoringError(f"--weight takes NAME=VALUE, got `{override}`")
        name, _, value = override.partition("=")
        name = name.strip()
        if name not in profile:
            raise ScoringError(
                f"`{name}` is not in the {args.objective} profile; it has "
                f"{', '.join(profile)}"
            )
        try:
            profile[name] = (float(value), profile[name][1])
        except ValueError as error:
            raise ScoringError(f"`{value}` is not a number") from error

    total = sum(weight for weight, _ in profile.values())

    print("[stage.scoring]")
    print(f'type = "{args.aggregation}"')
    print()
    for name, (weight, window) in profile.items():
        for line in component_toml(name, weight, window):
            print(line)
        print()

    print(f"# profile `{args.objective}`, weights sum to {total:.2f}", file=sys.stderr)
    if args.aggregation == "geometric_mean":
        print(
            "# geometric mean: any component scoring 0 zeroes the total. That is "
            "what you want for a hard requirement such as custom_alerts.",
            file=sys.stderr,
        )
    else:
        print(
            "# arithmetic mean: a strong component can paper over a failed one. "
            "Use geometric_mean when a component is a requirement, not a preference.",
            file=sys.stderr,
        )
    print(
        "# every numeric component is bounded on both sides. An unbounded reward "
        "gets exploited -- optimise molecular weight upward with no ceiling and "
        "the agent will return 900 Da molecules that score beautifully.",
        file=sys.stderr,
    )


def command_component(args: argparse.Namespace) -> None:
    window = None
    if args.low is not None or args.high is not None:
        if args.low is None or args.high is None:
            raise ScoringError("give both --low and --high, or neither")
        window = (args.low, args.high)
    for line in component_toml(args.name, args.weight, window):
        print(line)


def command_transforms(args: argparse.Namespace) -> None:
    print("transform\twhen to use")
    for name, note in TRANSFORMS.items():
        print(f"{name}\t{note}")
    print(
        "\n# `step` gives the optimiser no gradient -- it cannot tell a near-miss "
        "from a far one, so it wanders. Prefer a sigmoid unless the requirement "
        "is genuinely binary.",
        file=sys.stderr,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    profile = subparsers.add_parser("profile", help="a ready-made scoring block")
    profile.add_argument(
        "--objective", choices=tuple(PROFILES), default="lead-like", help="default: lead-like"
    )
    profile.add_argument(
        "--aggregation",
        choices=("geometric_mean", "arithmetic_mean"),
        default="geometric_mean",
        help="default: geometric_mean",
    )
    profile.add_argument("--weight", action="append", help="override, e.g. QED=0.4")
    profile.set_defaults(handler=command_profile)

    component = subparsers.add_parser("component", help="one component's TOML")
    component.add_argument("--name", required=True, help=f"one of {', '.join(sorted(COMPONENTS))}")
    component.add_argument("--weight", type=float, default=1.0, help="default: 1.0")
    component.add_argument("--low", type=float, help="lower bound of the desirable window")
    component.add_argument("--high", type=float, help="upper bound of the desirable window")
    component.set_defaults(handler=command_component)

    transforms = subparsers.add_parser("transforms", help="the transforms and when each is right")
    transforms.set_defaults(handler=command_transforms)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except ScoringError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
