#!/usr/bin/env python3
"""Write REINVENT 4 run configuration for any of its four generators.

Standard library only. REINVENT does the generation; this writes the TOML it
reads, which is where most of the mistakes happen.

Four things this handles that hand-writing the TOML usually gets wrong:

* **Each generator needs a different prior and a different input.** Reinvent
  samples de novo from nothing, LibInvent decorates a scaffold marked with
  attachment points, LinkInvent joins two warheads, and Mol2Mol transforms a
  starting molecule. Pairing the wrong prior with the wrong input fails late
  and confusingly.
* **Attachment points are `[*]` and they are mandatory.** A LibInvent scaffold
  without them, or a LinkInvent input without exactly two, is silently useless.
* **`staged_learning` optimises; `sampling` does not.** Sampling draws from the
  prior and ignores the scoring function entirely, which is the single most
  common reason a run "ignores" its objective.
* **The agent and the prior start as the same file, and must not stay so.**
  Reinforcement learning updates the agent while the prior stays fixed as the
  likelihood anchor -- pointing both at the same path across stages loses that.

Commands:
    sampling   draw molecules from a prior without optimising
    staged     reinforcement-learning optimisation against a scoring function
    generators the four generators, their priors, and what input each needs

Examples:
    python reinvent_config.py generators
    python reinvent_config.py sampling --generator reinvent --num-smiles 1000
    python reinvent_config.py staged --generator libinvent \\
        --scaffold "N1(=[*])CCN(CC1)C(=O)[*]" --scoring scoring.toml --max-steps 300
"""

from __future__ import annotations

import argparse
import sys

#: The four generators, their default priors, and the input each requires.
GENERATORS = {
    "reinvent": {
        "prior": "priors/reinvent.prior",
        "input": None,
        "purpose": "de novo generation from scratch",
        "note": "no input structure; the model samples the whole chemical space it learned",
    },
    "libinvent": {
        "prior": "priors/libinvent.prior",
        "input": "scaffold",
        "purpose": "decorate a fixed scaffold with R-groups",
        "note": "scaffold SMILES must carry one or more [*] attachment points",
    },
    "linkinvent": {
        "prior": "priors/linkinvent.prior",
        "input": "warheads",
        "purpose": "design a linker between two fragments",
        "note": "two warhead SMILES joined by |, each with exactly one [*]",
    },
    "mol2mol": {
        "prior": "priors/mol2mol_similarity.prior",
        "input": "smiles",
        "purpose": "generate analogues within a similarity radius",
        "note": "one or more starting SMILES; the prior chosen sets the similarity regime",
    },
}

#: Mol2Mol ships several priors that define how far it is allowed to travel.
MOL2MOL_PRIORS = {
    "similarity": "priors/mol2mol_similarity.prior",
    "medium-similarity": "priors/mol2mol_medium_similarity.prior",
    "high-similarity": "priors/mol2mol_high_similarity.prior",
    "mmp": "priors/mol2mol_mmp.prior",
    "scaffold": "priors/mol2mol_scaffold.prior",
    "scaffold-generic": "priors/mol2mol_scaffold_generic.prior",
}

#: Diversity filters stop the agent collapsing onto one scaffold it likes.
DIVERSITY_FILTERS = ("IdenticalMurckoScaffold", "IdenticalTopologicalScaffold", "ScaffoldSimilarity")

ATTACHMENT = "[*]"


class ConfigError(RuntimeError):
    """A generator/input combination REINVENT cannot run."""


def validate_input(generator: str, args: argparse.Namespace) -> str | None:
    spec = GENERATORS[generator]
    needs = spec["input"]
    if needs is None:
        return None

    if needs == "scaffold":
        if not args.scaffold:
            raise ConfigError("libinvent needs --scaffold")
        if ATTACHMENT not in args.scaffold:
            raise ConfigError(
                f"the scaffold has no {ATTACHMENT} attachment point. LibInvent "
                "decorates at [*]; without one there is nothing to decorate."
            )
        return args.scaffold

    if needs == "warheads":
        if not args.warheads:
            raise ConfigError("linkinvent needs --warheads 'SMILES1|SMILES2'")
        parts = args.warheads.split("|")
        if len(parts) != 2:
            raise ConfigError(
                f"--warheads needs exactly two fragments joined by |, got {len(parts)}"
            )
        for part in parts:
            if part.count(ATTACHMENT) != 1:
                raise ConfigError(
                    f"each warhead needs exactly one {ATTACHMENT}; `{part}` has "
                    f"{part.count(ATTACHMENT)}"
                )
        return args.warheads

    if not args.smiles:
        raise ConfigError("mol2mol needs --smiles")
    return args.smiles


def prior_for(generator: str, args: argparse.Namespace) -> str:
    if args.prior:
        return args.prior
    if generator == "mol2mol":
        if args.mol2mol_prior not in MOL2MOL_PRIORS:
            raise ConfigError(
                f"`{args.mol2mol_prior}` is not a Mol2Mol prior; choose from "
                f"{', '.join(MOL2MOL_PRIORS)}"
            )
        return MOL2MOL_PRIORS[args.mol2mol_prior]
    return GENERATORS[generator]["prior"]


def command_generators(args: argparse.Namespace) -> None:
    print("generator\tinput\tprior\tpurpose")
    for name, spec in GENERATORS.items():
        print(f"{name}\t{spec['input'] or '-'}\t{spec['prior']}\t{spec['purpose']}")
    print("\n# Mol2Mol priors set how far the model may travel from the input:", file=sys.stderr)
    for name, path in MOL2MOL_PRIORS.items():
        print(f"#   {name:<20} {path}", file=sys.stderr)
    print(
        "\n# sampling draws from the prior and IGNORES any scoring function. "
        "Use staged_learning to optimise.",
        file=sys.stderr,
    )


def command_sampling(args: argparse.Namespace) -> None:
    generator = args.generator
    value = validate_input(generator, args)
    prior = prior_for(generator, args)

    lines = [
        'run_type = "sampling"',
        f'device = "{args.device}"',
        "",
        "[parameters]",
        f'model_file = "{prior}"',
        f'output_file = "{args.output}"',
        f"num_smiles = {args.num_smiles}",
        'unique_molecules = true',
        'randomize_smiles = true',
    ]
    if value is not None:
        key = {"scaffold": "smiles_file", "warheads": "smiles_file", "smiles": "smiles_file"}[
            GENERATORS[generator]["input"]
        ]
        lines.append(f'# write `{value}` into {args.input_file}, one per line')
        lines.append(f'{key} = "{args.input_file}"')

    print("\n".join(lines))
    print(
        "# sampling does not optimise. Nothing here reads a scoring function -- "
        "if you want the objective honoured, use `staged`.",
        file=sys.stderr,
    )


def command_staged(args: argparse.Namespace) -> None:
    generator = args.generator
    value = validate_input(generator, args)
    prior = prior_for(generator, args)

    if args.agent == prior and args.stages > 1:
        print(
            "# note: agent and prior start as the same file, which is correct for "
            "stage 1. Later stages should load the previous stage's checkpoint as "
            "the agent while the prior stays fixed -- it is the likelihood anchor "
            "that keeps molecules realistic.",
            file=sys.stderr,
        )

    lines = [
        'run_type = "staged_learning"',
        f'device = "{args.device}"',
        f"tb_logdir = \"{args.tb_logdir}\"" if args.tb_logdir else "",
        "",
        "[parameters]",
        f'prior_file = "{prior}"',
        f'agent_file = "{args.agent or prior}"',
        f'summary_csv_prefix = "{args.prefix}"',
        f"batch_size = {args.batch_size}",
        "use_checkpoint = false",
    ]
    if value is not None:
        lines.append(f'smiles_file = "{args.input_file}"  # containing: {value}')

    lines += [
        "",
        "[learning_strategy]",
        f'type = "{args.strategy}"',
        f"sigma = {args.sigma}",
        f"rate = {args.rate}",
    ]

    if args.diversity_filter:
        if args.diversity_filter not in DIVERSITY_FILTERS:
            raise ConfigError(
                f"`{args.diversity_filter}` is not a diversity filter; choose from "
                f"{', '.join(DIVERSITY_FILTERS)}"
            )
        lines += [
            "",
            "[diversity_filter]",
            f'type = "{args.diversity_filter}"',
            f"bucket_size = {args.bucket_size}",
            "minscore = 0.4",
        ]

    for stage in range(1, args.stages + 1):
        lines += [
            "",
            "[[stage]]",
            f'chkpt_file = "{args.prefix}_stage{stage}.chkpt"',
            'termination = "simple"',
            f"max_score = {args.max_score}",
            f"min_steps = {args.min_steps}",
            f"max_steps = {args.max_steps}",
            "",
            f'# scoring for stage {stage}: paste the [stage.scoring] block from',
            f'# `scoring_profile.py`, or include {args.scoring}',
        ]

    print("\n".join(line for line in lines if line != "" or True))
    print(
        f"# {args.stages} stage(s). sigma={args.sigma} sets how hard the agent is "
        "pushed away from the prior: too high and it collapses onto degenerate "
        "high-scoring molecules, too low and it barely moves.",
        file=sys.stderr,
    )
    if not args.diversity_filter:
        print(
            "# no diversity filter set. Without one the agent will usually "
            "converge onto a single scaffold it has learned to score well.",
            file=sys.stderr,
        )


def add_generator_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--generator", choices=tuple(GENERATORS), required=True, help="which model to run"
    )
    parser.add_argument("--prior", help="override the default prior path")
    parser.add_argument(
        "--mol2mol-prior",
        default="similarity",
        help=f"for mol2mol; one of {', '.join(MOL2MOL_PRIORS)}",
    )
    parser.add_argument("--scaffold", help="libinvent scaffold SMILES with [*] points")
    parser.add_argument("--warheads", help="linkinvent 'SMILES1|SMILES2', one [*] each")
    parser.add_argument("--smiles", help="mol2mol starting SMILES")
    parser.add_argument(
        "--input-file", default="input.smi", help="path REINVENT reads input from (default: input.smi)"
    )
    parser.add_argument("--device", default="cuda:0", help="default: cuda:0")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generators = subparsers.add_parser("generators", help="the four generators and their inputs")
    generators.set_defaults(handler=command_generators)

    sampling = subparsers.add_parser("sampling", help="draw from a prior without optimising")
    add_generator_arguments(sampling)
    sampling.add_argument("--num-smiles", type=int, default=1000, help="default: 1000")
    sampling.add_argument("--output", default="sampled.csv", help="default: sampled.csv")
    sampling.set_defaults(handler=command_sampling)

    staged = subparsers.add_parser("staged", help="reinforcement-learning optimisation")
    add_generator_arguments(staged)
    staged.add_argument("--agent", help="starting agent (defaults to the prior)")
    staged.add_argument("--scoring", default="scoring.toml", help="scoring block to include")
    staged.add_argument("--prefix", default="run", help="summary CSV prefix (default: run)")
    staged.add_argument("--batch-size", type=int, default=64, help="default: 64")
    staged.add_argument(
        "--strategy", choices=("dap", "mauli", "mascof", "sdap"), default="dap", help="default: dap"
    )
    staged.add_argument("--sigma", type=int, default=128, help="default: 128")
    staged.add_argument("--rate", type=float, default=0.0001, help="learning rate (default: 1e-4)")
    staged.add_argument("--stages", type=int, default=1, help="default: 1")
    staged.add_argument("--max-score", type=float, default=0.6, help="default: 0.6")
    staged.add_argument("--min-steps", type=int, default=25, help="default: 25")
    staged.add_argument("--max-steps", type=int, default=300, help="default: 300")
    staged.add_argument(
        "--diversity-filter", help=f"one of {', '.join(DIVERSITY_FILTERS)}"
    )
    staged.add_argument("--bucket-size", type=int, default=25, help="default: 25")
    staged.add_argument("--tb-logdir", help="TensorBoard log directory")
    staged.set_defaults(handler=command_staged)

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
