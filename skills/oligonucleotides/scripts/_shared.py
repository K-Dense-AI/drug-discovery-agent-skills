"""Sequence handling shared by the oligonucleotide scripts.

Standard library only. Nothing here touches the network; the transcriptome
FASTA used for off-target scanning is supplied by the caller.

Two conventions are fixed here because every script depends on them agreeing:

* **U is mapped to T on input.** Design rules, nearest-neighbour parameters,
  and FASTA files are all written in DNA alphabet, and silently mixing the two
  produces sequences that match nothing.
* **The seed is antisense positions 2-8**, zero-indexed `[1:8]`. It drives
  microRNA-like off-target silencing and is the single most important
  specificity determinant for an siRNA.
"""

from __future__ import annotations

import re
import sys

VALID_BASES = frozenset("ACGT")

#: Antisense positions 2-8 (zero-indexed 1..7). The microRNA-like seed.
SEED_START = 1
SEED_END = 8

COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}


class OligoError(RuntimeError):
    """Input that cannot be handled as a nucleotide sequence."""


def clean_sequence(text: str) -> str:
    """Uppercase, strip FASTA headers and whitespace, and map U to T."""
    lines = [line for line in text.splitlines() if not line.startswith(">")]
    sequence = re.sub(r"\s+", "", "".join(lines)).upper().replace("U", "T")
    if not sequence:
        raise OligoError("no sequence found")
    unknown = set(sequence) - VALID_BASES
    if unknown:
        raise OligoError(
            f"unexpected characters in the sequence: {', '.join(sorted(unknown))}. "
            "Only A, C, G, T, and U are handled -- degenerate codes and gaps are not."
        )
    return sequence


def reverse_complement(sequence: str) -> str:
    return "".join(COMPLEMENT[base] for base in reversed(sequence))


def read_fasta(path: str) -> dict[str, str]:
    """Read a FASTA into {name: sequence}, mapping U to T.

    Records with unexpected characters are skipped rather than fatal -- a real
    transcriptome contains N runs and the occasional ambiguity code, and one
    bad record should not stop an off-target scan.
    """
    stream = sys.stdin if path == "-" else open(path, encoding="utf-8", errors="replace")
    records: dict[str, str] = {}
    name: str | None = None
    chunks: list[str] = []

    def flush() -> None:
        if name is None:
            return
        sequence = "".join(chunks).upper().replace("U", "T")
        sequence = "".join(base for base in sequence if base in VALID_BASES)
        if sequence:
            records[name] = sequence

    with stream as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                flush()
                name = line[1:].split()[0] if len(line) > 1 else "unnamed"
                chunks = []
            else:
                chunks.append(line)
    flush()

    if not records:
        raise OligoError(f"no sequences read from {path}")
    return records
