#!/usr/bin/env python3
"""Read a REINVENT run's output and judge whether it produced anything useful.

Standard library only. A generative run always produces molecules; the question
is whether they are distinct, realistic, and actually optimised.

Four things this handles that reading the CSV usually gets wrong:

* **Mode collapse is the default failure and it looks like success.** Score
  climbs, and the agent has found one scaffold it can decorate endlessly. The
  score curve cannot show this; the count of distinct scaffolds can.
* **Duplicates inflate every count.** The same SMILES is regenerated many times
  across steps, so "50 000 molecules generated" is usually a few thousand.
* **A high score is not a good molecule.** It means the scoring function was
  satisfied, which is a statement about the scoring function. Score against
  scaffold diversity is the diagnostic pair.
* Scaffold extraction here is a **crude ring-system approximation**, not a
  Bemis-Murcko decomposition, because that needs a chemistry toolkit. It is
  good enough to detect collapse and no more; use `rdkit` for real scaffolds.

Commands:
    summary   distinct molecules, score progression, and collapse warning
    top       the best-scoring distinct molecules

Examples:
    python parse_run.py summary --csv run_1.csv
    python parse_run.py top --csv run_1.csv --n 25 --min-score 0.7
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter

#: Fewer distinct ring systems than this across a large run means collapse.
COLLAPSE_SCAFFOLD_FRACTION = 0.05

#: Column names REINVENT uses, in the order it prefers them.
SMILES_COLUMNS = ("SMILES", "Smiles", "smiles")
SCORE_COLUMNS = ("Score", "total_score", "score")
STEP_COLUMNS = ("step", "Step")

#: Ring-system approximation: strip everything outside ring atoms.
RING_TOKEN = re.compile(r"[A-Za-z][a-z]?\d|[a-z]|\d")


class RunError(RuntimeError):
    """Output that is not a REINVENT run summary."""


def pick(row: dict, candidates) -> str | None:
    for name in candidates:
        if name in row:
            return name
    return None


def read_run(path: str) -> tuple[list[dict], str, str | None, str | None]:
    stream = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8")
    with stream as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RunError(f"{path} has no rows")

    smiles_column = pick(rows[0], SMILES_COLUMNS)
    if smiles_column is None:
        raise RunError(
            f"no SMILES column in {path}; columns are {sorted(rows[0])[:10]}. "
            "Pass the run's summary CSV (summary_csv_prefix in the config)."
        )
    return rows, smiles_column, pick(rows[0], SCORE_COLUMNS), pick(rows[0], STEP_COLUMNS)


def ring_signature(smiles: str) -> str:
    """A crude ring-system fingerprint, enough to detect mode collapse.

    Not a Bemis-Murcko scaffold -- that needs a chemistry toolkit. This counts
    ring-closure digits and aromatic atoms, which distinguishes genuinely
    different cores from decorations of one core well enough to see collapse.
    """
    aromatic = "".join(sorted(character for character in smiles if character.islower()))
    closures = len(re.findall(r"[0-9]", smiles)) // 2
    branches = smiles.count("(")
    return f"{aromatic}|r{closures}|b{min(branches, 6)}"


def as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def command_summary(args: argparse.Namespace) -> None:
    rows, smiles_column, score_column, step_column = read_run(args.csv)

    seen: dict[str, float | None] = {}
    for row in rows:
        smiles = (row.get(smiles_column) or "").strip()
        if not smiles:
            continue
        score = as_float(row.get(score_column)) if score_column else None
        if smiles not in seen or (score is not None and (seen[smiles] is None or score > seen[smiles])):
            seen[smiles] = score

    if not seen:
        raise RunError("no SMILES found in the run output")

    scaffolds = Counter(ring_signature(smiles) for smiles in seen)
    distinct_fraction = len(scaffolds) / len(seen)

    scores = [score for score in seen.values() if score is not None]
    result = {
        "rows": len(rows),
        "distinct_molecules": len(seen),
        "duplicate_rows": len(rows) - len(seen),
        "distinct_ring_systems": len(scaffolds),
        "ring_system_fraction": round(distinct_fraction, 4),
        "largest_ring_system_share": round(scaffolds.most_common(1)[0][1] / len(seen), 4),
        "mean_score": round(sum(scores) / len(scores), 4) if scores else None,
        "max_score": round(max(scores), 4) if scores else None,
        "scored": len(scores),
    }

    if step_column:
        by_step: dict[int, list[float]] = {}
        for row in rows:
            step = as_float(row.get(step_column))
            score = as_float(row.get(score_column)) if score_column else None
            if step is None or score is None:
                continue
            by_step.setdefault(int(step), []).append(score)
        if len(by_step) >= 2:
            steps = sorted(by_step)
            first = sum(by_step[steps[0]]) / len(by_step[steps[0]])
            last = sum(by_step[steps[-1]]) / len(by_step[steps[-1]])
            result["first_step_mean_score"] = round(first, 4)
            result["last_step_mean_score"] = round(last, 4)
            result["score_improvement"] = round(last - first, 4)

    print(
        f"# {result['rows']} rows -> {result['distinct_molecules']} distinct "
        f"({result['duplicate_rows']} duplicates)",
        file=sys.stderr,
    )
    if distinct_fraction < COLLAPSE_SCAFFOLD_FRACTION:
        print(
            f"# MODE COLLAPSE: only {len(scaffolds)} ring systems across "
            f"{len(seen)} molecules ({distinct_fraction:.1%}). The agent has found "
            "one core it can decorate. Add a diversity filter, lower sigma, or "
            "shorten the run.",
            file=sys.stderr,
        )
    if result.get("score_improvement") is not None and result["score_improvement"] <= 0:
        print(
            "# score did not improve from the first step to the last. Check the run "
            "is `staged_learning` and not `sampling` -- sampling ignores the "
            "scoring function entirely.",
            file=sys.stderr,
        )
    print(
        "# ring systems are a crude approximation, not Bemis-Murcko scaffolds. "
        "Use `rdkit` for real scaffold analysis.",
        file=sys.stderr,
    )

    if args.output_format == "json":
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    for key, value in result.items():
        print(f"{key}\t{'' if value is None else value}")


def command_top(args: argparse.Namespace) -> None:
    rows, smiles_column, score_column, _ = read_run(args.csv)
    if score_column is None:
        raise RunError("no score column in this file, so there is nothing to rank")

    best: dict[str, float] = {}
    for row in rows:
        smiles = (row.get(smiles_column) or "").strip()
        score = as_float(row.get(score_column))
        if not smiles or score is None:
            continue
        if smiles not in best or score > best[smiles]:
            best[smiles] = score

    ranked = sorted(best.items(), key=lambda pair: -pair[1])
    if args.min_score is not None:
        ranked = [(smiles, score) for smiles, score in ranked if score >= args.min_score]

    seen_scaffolds: set[str] = set()
    out = []
    for smiles, score in ranked:
        signature = ring_signature(smiles)
        novel = signature not in seen_scaffolds
        seen_scaffolds.add(signature)
        if args.diverse and not novel:
            continue
        out.append(
            {"smiles": smiles, "score": round(score, 4), "new_ring_system": novel}
        )
        if len(out) >= args.n:
            break

    print(f"# {len(out)} of {len(ranked)} distinct molecules shown", file=sys.stderr)
    if args.diverse:
        print("# one molecule per ring system", file=sys.stderr)
    print(
        "# a high score means the scoring function was satisfied. That is a "
        "statement about the scoring function.",
        file=sys.stderr,
    )

    if args.output_format == "json":
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    writer = csv.writer(
        sys.stdout, delimiter="," if args.output_format == "csv" else "\t", lineterminator="\n"
    )
    writer.writerow(["smiles", "score", "new_ring_system"])
    for item in out:
        writer.writerow([item["smiles"], item["score"], str(item["new_ring_system"]).lower()])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary = subparsers.add_parser("summary", help="distinct molecules and collapse check")
    summary.add_argument("--csv", required=True, help="REINVENT summary CSV, or - for stdin")
    summary.set_defaults(handler=command_summary)

    top = subparsers.add_parser("top", help="best-scoring distinct molecules")
    top.add_argument("--csv", required=True, help="REINVENT summary CSV, or - for stdin")
    top.add_argument("--n", type=int, default=25, help="default: 25")
    top.add_argument("--min-score", type=float, help="drop anything below this")
    top.add_argument(
        "--diverse", action="store_true", help="one molecule per ring system"
    )
    top.set_defaults(handler=command_top)

    for sub in (summary, top):
        sub.add_argument(
            "--format", dest="output_format", choices=("tsv", "csv", "json"), default="tsv"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except RunError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
