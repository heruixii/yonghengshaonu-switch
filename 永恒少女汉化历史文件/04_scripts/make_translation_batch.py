#!/usr/bin/env python3
"""Create a small, reviewable NS translation batch from alignment candidates.

This script does not edit game data.  It converts PC-engine markup to the
Switch script markup used by this project and emits the exact BINU8 record
coordinates required by the writer.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


VOICE_RE = re.compile(r"^(@v{2,3}\d+)")
PC_RUBY_RE = re.compile(r"\|([^\[]+)\[([^\]]+)\]")
UNKNOWN_PC_RUBY_RE = re.compile(r"\|[^\[]+\[[^\]]*\]")


def convert_pc_text(ns_source: str, pc_translation: str) -> str:
    text = pc_translation.replace("^n", "@n")
    text = PC_RUBY_RE.sub(lambda m: f"@r{m.group(1)}@{m.group(2)}@", text)
    if UNKNOWN_PC_RUBY_RE.search(text):
        raise ValueError(f"unconverted PC ruby markup: {pc_translation!r}")

    voice = VOICE_RE.match(ns_source)
    if voice:
        text = voice.group(1) + text
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("alignment", type=Path)
    ap.add_argument("ns_extract", type=Path)
    ap.add_argument("--scene", required=True)
    ap.add_argument("--start", type=int, required=True, help="inclusive NS filtered index")
    ap.add_argument("--end", type=int, required=True, help="inclusive NS filtered index")
    ap.add_argument("--include-review", action="store_true")
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    ns_lookup: dict[tuple[str, str], dict[str, str]] = {}
    with args.ns_extract.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            ns_lookup[(row["file"], row["length_offset"])] = row

    allowed = {"high-candidate"}
    if args.include_review:
        allowed.add("review")

    selected: list[dict[str, str]] = []
    with args.alignment.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["scene"] != args.scene or row["status"] not in allowed:
                continue
            if not row["ns_filtered_index"] or not row["pc_translation"]:
                continue
            index = int(row["ns_filtered_index"])
            if not (args.start <= index <= args.end):
                continue

            key = (row["ns_file"], row["ns_length_offset"])
            ns = ns_lookup.get(key)
            if ns is None:
                raise ValueError(f"NS extraction row not found: {key}")
            if ns["text"] != row["ns_source"]:
                raise ValueError(f"NS source mismatch: {key}")

            selected.append(
                {
                    "file": ns["file"],
                    "length_offset": ns["length_offset"],
                    "text_offset": ns["text_offset"],
                    "stored_length": ns["stored_length"],
                    "byte_length": ns["byte_length"],
                    "source": ns["text"],
                    "translation": convert_pc_text(ns["text"], row["pc_translation"]),
                    "scene": row["scene"],
                    "ns_filtered_index": row["ns_filtered_index"],
                    "pc_file": row["pc_file"],
                    "pc_string_index": row["pc_string_index"],
                    "alignment_status": row["status"],
                    "alignment_reason": row["reason"],
                }
            )

    selected.sort(key=lambda r: int(r["length_offset"]))
    if not selected:
        raise SystemExit("no rows selected")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "file",
        "length_offset",
        "text_offset",
        "stored_length",
        "byte_length",
        "source",
        "translation",
        "scene",
        "ns_filtered_index",
        "pc_file",
        "pc_string_index",
        "alignment_status",
        "alignment_reason",
    ]
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)

    print(f"rows_written={len(selected)}")
    print(f"scene={args.scene}")
    print(f"range={args.start}-{args.end}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
