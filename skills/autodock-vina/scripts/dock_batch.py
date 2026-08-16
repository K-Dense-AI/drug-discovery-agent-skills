#!/usr/bin/env python3
"""Prepare ligands, dock them, and collect the scores — the whole loop.

Wraps the Meeko + Vina command-line tools rather than reimplementing them, so
what runs is exactly what the AutoDock documentation describes. Every command
is printed, and `--dry-run` prints them without running anything.

    check     verify the toolchain is installed and report versions
    run       prepare and dock a set of ligands against one receptor

Ligand input may be a directory of SDF files, one multi-molecule SDF, a list of
SDF paths, or a SMILES file (which needs `scrub.py` from Molscrub to build 3D
coordinates and protonation states).

Examples:

    python dock_batch.py check
    python dock_batch.py run --receptor rec.pdbqt --config box.txt \\
        --ligands ligands/ --out-dir docking/ --exhaustiveness 32 --workers 8
    python dock_batch.py run --receptor rec.pdbqt --config box.txt \\
        --smiles library.smi --out-dir docking/ --dry-run

The scoring function is chosen with `--scoring vina|vinardo|ad4`. `ad4` needs
precomputed affinity maps from `autogrid4` and takes `--maps` instead of a
receptor; this script supports vina and vinardo, and tells you what to run for
ad4 rather than pretending to handle it.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import shutil
import subprocess
import sys
import time
from pathlib import Path

REQUIRED = {
    "vina": "AutoDock Vina -- conda install -c conda-forge vina, or a release binary",
    "mk_prepare_ligand.py": "Meeko -- pip install meeko",
}
OPTIONAL = {
    "mk_prepare_receptor.py": "Meeko, for preparing the receptor PDBQT",
    "mk_export.py": "Meeko, to convert docked poses back to SDF with correct bond orders",
    "scrub.py": "Molscrub -- pip install molscrub; needed only for SMILES input",
    "obabel": "Open Babel, a fallback for format conversion",
}


def which(name: str) -> str | None:
    return shutil.which(name)


def command_check(args) -> int:
    missing = []
    print("tool\tstatus\tpath")
    for name, hint in {**REQUIRED, **OPTIONAL}.items():
        path = which(name)
        status = "found" if path else ("MISSING" if name in REQUIRED else "optional, absent")
        print(f"{name}\t{status}\t{path or hint}")
        if not path and name in REQUIRED:
            missing.append(name)

    vina = which("vina")
    if vina:
        try:
            result = subprocess.run([vina, "--version"], capture_output=True, text=True, timeout=30)
            print(f"\n# {result.stdout.strip().splitlines()[0] if result.stdout.strip() else 'vina --version gave no output'}")
        except (subprocess.SubprocessError, OSError) as error:
            print(f"\n# vina present but not runnable: {error}", file=sys.stderr)

    if missing:
        print(f"\n# missing required tools: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


def run_command(command: list[str], *, dry_run: bool, timeout: int) -> tuple[int, str]:
    printable = " ".join(command)
    if dry_run:
        print(f"$ {printable}")
        return 0, ""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s: {printable}"
    except OSError as error:
        return 127, f"{error}: {printable}"
    if result.returncode != 0:
        return result.returncode, (result.stderr or result.stdout or "").strip()[:800]
    return 0, result.stdout


def collect_ligands(args) -> list[Path]:
    paths: list[Path] = []
    for item in args.ligands or []:
        path = Path(item)
        if path.is_dir():
            paths.extend(sorted(path.glob("*.sdf")))
            paths.extend(sorted(path.glob("*.mol2")))
            paths.extend(sorted(path.glob("*.pdbqt")))
        elif path.is_file():
            paths.append(path)
        else:
            print(f"# warning: no such ligand path: {path}", file=sys.stderr)
    return paths


def prepare_from_smiles(args, work_dir: Path) -> list[Path]:
    """Build 3D, protonated ligands from a SMILES file using scrub.py.

    Docking a structure straight from SMILES without a protonation step is a
    common and expensive mistake: the charge state at pH 7.4 changes hydrogen
    bonding and therefore the pose, and an amine docked neutral rarely finds
    the salt bridge it makes in reality.
    """
    if not which("scrub.py"):
        raise SystemExit(
            "error: SMILES input needs scrub.py (pip install molscrub) to generate 3D "
            "coordinates, protonation, and tautomers. Alternatively pre-build SDF files "
            "with the `rdkit` or `datamol` skill and pass them with --ligands."
        )
    source = Path(args.smiles)
    sdf = work_dir / f"{source.stem}_scrubbed.sdf"
    code, message = run_command(
        ["scrub.py", str(source), "-o", str(sdf), "--ph", str(args.ph)],
        dry_run=args.dry_run,
        timeout=args.timeout,
    )
    if code != 0:
        raise SystemExit(f"error: scrub.py failed: {message}")
    if args.dry_run:
        return [sdf]
    if not sdf.is_file():
        raise SystemExit(f"error: scrub.py produced no output at {sdf}")
    return [sdf]


def dock_one(ligand: Path, args, out_dir: Path) -> dict:
    """Prepare one ligand and dock it. Returns a status record."""
    started = time.monotonic()
    stem = ligand.stem
    prepared = out_dir / f"{stem}.pdbqt"
    docked = out_dir / f"{stem}_out.pdbqt"
    record = {"ligand": stem, "status": "ok", "detail": "", "seconds": 0.0,
              "prepared": str(prepared), "docked": str(docked)}

    if ligand.suffix.lower() == ".pdbqt":
        prepared = ligand
        record["prepared"] = str(prepared)
    else:
        code, message = run_command(
            ["mk_prepare_ligand.py", "-i", str(ligand), "-o", str(prepared)],
            dry_run=args.dry_run,
            timeout=args.timeout,
        )
        if code != 0:
            record.update(status="prepare_failed", detail=message)
            return record

    command = [
        "vina",
        "--receptor", str(args.receptor),
        "--ligand", str(prepared),
        "--config", str(args.config),
        "--exhaustiveness", str(args.exhaustiveness),
        "--num_modes", str(args.num_modes),
        "--cpu", str(args.cpu_per_job),
        "--out", str(docked),
    ]
    if args.scoring != "vina":
        command += ["--scoring", args.scoring]
    if args.seed is not None:
        command += ["--seed", str(args.seed)]

    code, message = run_command(command, dry_run=args.dry_run, timeout=args.timeout)
    if code != 0:
        record.update(status="dock_failed", detail=message)
        return record

    if args.export_sdf and which("mk_export.py") and not args.dry_run:
        run_command(
            ["mk_export.py", str(docked), "-s", str(out_dir / f"{stem}_out.sdf")],
            dry_run=False,
            timeout=args.timeout,
        )
    record["seconds"] = round(time.monotonic() - started, 1)
    return record


def command_run(args) -> int:
    if args.scoring == "ad4":
        print(
            "error: the ad4 scoring function needs precomputed affinity maps. Run\n"
            "  mk_prepare_receptor.py -i rec.pdb -o rec -p -v -g --box_center ... --box_size ...\n"
            "  autogrid4 -p rec.gpf -l rec.glg\n"
            "  vina --ligand lig.pdbqt --maps rec --scoring ad4 --exhaustiveness 32 --out out.pdbqt\n"
            "and note that ad4 and vina scores are not comparable with each other.",
            file=sys.stderr,
        )
        return 1

    for name in REQUIRED:
        if not which(name) and not args.dry_run:
            print(f"error: {name} is not on PATH. Run `dock_batch.py check`.", file=sys.stderr)
            return 1

    receptor = Path(args.receptor)
    if receptor.suffix.lower() != ".pdbqt":
        print(
            f"error: --receptor must be a PDBQT file. Prepare one with\n"
            f"  mk_prepare_receptor.py -i {receptor} -o receptor -p -v "
            "--box_center X Y Z --box_size SX SY SZ",
            file=sys.stderr,
        )
        return 1
    if not receptor.is_file() and not args.dry_run:
        print(f"error: no such receptor: {receptor}", file=sys.stderr)
        return 1
    if not Path(args.config).is_file() and not args.dry_run:
        print(
            f"error: no such config: {args.config}. Generate one with make_box.py.",
            file=sys.stderr,
        )
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ligands = collect_ligands(args)
    if args.smiles:
        ligands.extend(prepare_from_smiles(args, out_dir))
    if not ligands:
        print("error: no ligands found", file=sys.stderr)
        return 1

    print(
        f"# {len(ligands)} ligand file(s), scoring={args.scoring}, "
        f"exhaustiveness={args.exhaustiveness}, workers={args.workers}",
        file=sys.stderr,
    )
    if args.seed is None:
        print(
            "# note: no --seed given, so this run is not reproducible. Vina's search is "
            "stochastic; fix a seed when a result matters.",
            file=sys.stderr,
        )

    records: list[dict] = []
    if args.workers > 1 and not args.dry_run:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(dock_one, ligand, args, out_dir): ligand for ligand in ligands}
            for future in concurrent.futures.as_completed(futures):
                records.append(future.result())
    else:
        for ligand in ligands:
            records.append(dock_one(ligand, args, out_dir))

    records.sort(key=lambda record: record["ligand"])
    failures = [record for record in records if record["status"] != "ok"]

    manifest = out_dir / "run_manifest.tsv"
    if not args.dry_run:
        with open(manifest, "w", encoding="utf-8") as handle:
            handle.write("ligand\tstatus\tseconds\tdocked\tdetail\n")
            for record in records:
                handle.write(
                    f"{record['ligand']}\t{record['status']}\t{record['seconds']}\t"
                    f"{record['docked']}\t{record['detail'][:200]}\n"
                )
        print(f"# wrote {manifest}", file=sys.stderr)

    print(f"# {len(records) - len(failures)}/{len(records)} succeeded", file=sys.stderr)
    for record in failures[:10]:
        print(f"# {record['ligand']}: {record['status']}: {record['detail'][:200]}", file=sys.stderr)

    if not args.dry_run and len(failures) < len(records):
        print(
            f"# next: python parse_vina_output.py {out_dir}/*_out.pdbqt "
            f"--config {args.config} --summary",
            file=sys.stderr,
        )
    return 1 if failures and len(failures) == len(records) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="verify the toolchain")
    check.set_defaults(handler=command_check)

    run = subparsers.add_parser("run", help="prepare and dock a set of ligands")
    run.add_argument("--receptor", required=True, help="receptor PDBQT")
    run.add_argument("--config", required=True, help="Vina config from make_box.py")
    run.add_argument("--ligands", nargs="+", help="SDF/MOL2/PDBQT files or a directory")
    run.add_argument("--smiles", help="a .smi file; needs scrub.py for 3D and protonation")
    run.add_argument("--out-dir", default="docking", help="output directory (default: docking)")
    run.add_argument(
        "--scoring",
        choices=("vina", "vinardo", "ad4"),
        default="vina",
        help="scoring function; vina and vinardo scores are not comparable",
    )
    run.add_argument(
        "--exhaustiveness",
        type=int,
        default=32,
        help="search effort (default: 32; Vina's own default of 8 is often too low)",
    )
    run.add_argument("--num-modes", dest="num_modes", type=int, default=9, help="poses to write")
    run.add_argument("--cpu-per-job", type=int, default=1, help="Vina threads per ligand")
    run.add_argument("--workers", type=int, default=4, help="ligands docked in parallel")
    run.add_argument("--seed", type=int, help="fix the random seed for reproducibility")
    run.add_argument("--ph", type=float, default=7.4, help="pH for scrub.py protonation")
    run.add_argument("--timeout", type=int, default=3600, help="seconds per subprocess")
    run.add_argument(
        "--export-sdf",
        action="store_true",
        help="convert poses back to SDF with mk_export.py (correct bond orders)",
    )
    run.add_argument("--dry-run", action="store_true", help="print commands without running them")
    run.set_defaults(handler=command_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
