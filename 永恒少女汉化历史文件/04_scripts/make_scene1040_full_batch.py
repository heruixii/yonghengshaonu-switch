#!/usr/bin/env python3
"""Build a fully reviewed 150/150 translation batch for NS scene 1040.

The generic v2 aligner is already correct for most of this scene, but the PC
script sometimes stores a speaker name and an inner-monologue line as separate
strings while the Switch script merges/omits those records.  This generator
keeps all high/review mappings that were semantically checked and applies a
small explicit override table at the known split points.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALIGNMENT = ROOT / "03_text" / "matched" / "pc-ns-alignment-candidates-v2.tsv"
NS_EXTRACT = ROOT / "03_text" / "ns_extracted" / "ns-strings-v1.0.3.tsv"
PC_EXTRACT = ROOT / "03_text" / "pc_extracted" / "pc-gsc-strings.tsv"
OUTPUT = ROOT / "03_text" / "translated" / "scene1040-full-v1.tsv"

SCENE = "1040"
NS_FILE = "Script/scr1040.binu8"
EXPECTED_COUNT = 150

VOICE_RE = re.compile(r"^(@v{2,3}\d+)")
PC_RUBY_RE = re.compile(r"\|([^\[]+)\[([^\]]+)\]")
UNKNOWN_PC_RUBY_RE = re.compile(r"\|[^\[]+\[[^\]]*\]")
KANA_RE = re.compile(r"[\u3040-\u30ff]")


# ns_filtered_index -> (PC string index, optional replacement translation,
# review note).  replacement=None means use that PC string verbatim.
OVERRIDES: dict[int, tuple[int | None, str | None, str]] = {
    37: (49, None, "PC speaker-name record; NS has standalone Mako name"),
    38: (50, None, "PC Mako dialogue split from speaker name; NS uses @vvv voice prefix"),
    51: (70, None, "v2 false match: narration belongs to PC 70, not inner monologue PC 72"),
    52: (72, None, "PC speaker name 71 is omitted on NS; dialogue maps directly"),
    55: (76, None, "PC speaker name 75 is omitted on NS; inner monologue maps directly"),
    58: (80, None, "PC speaker name 79 is omitted on NS; inner monologue maps directly"),
    59: (82, None, "PC speaker name 81 is omitted on NS; inner monologue maps directly"),
    114: (168, "「特进班……？」", "manual polish: replace legacy PC 'ＴＥＪＩＮ班' mistranslation"),
}


def convert_pc_text(ns_source: str, pc_translation: str) -> str:
    text = pc_translation.replace("^n", "@n")
    text = PC_RUBY_RE.sub(lambda m: f"@r{m.group(1)}@{m.group(2)}@", text)
    if UNKNOWN_PC_RUBY_RE.search(text):
        raise ValueError(f"unconverted PC ruby markup: {pc_translation!r}")
    voice = VOICE_RE.match(ns_source)
    if voice and not text.startswith(voice.group(1)):
        text = voice.group(1) + text
    return text


def load_ns_lookup() -> dict[tuple[str, str], dict[str, str]]:
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    with NS_EXTRACT.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            lookup[(row["file"], row["length_offset"])] = row
    return lookup


def load_pc_scene() -> dict[int, str]:
    out: dict[int, str] = {}
    with PC_EXTRACT.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["file"] == "1040.gsc" and row["decode_ok"] == "1":
                out[int(row["string_index"])] = row["text"]
    return out


def load_alignment_rows() -> dict[int, dict[str, str]]:
    rows: dict[int, dict[str, str]] = {}
    with ALIGNMENT.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["scene"] != SCENE or not row["ns_filtered_index"]:
                continue
            idx = int(row["ns_filtered_index"])
            if idx in rows:
                raise ValueError(f"duplicate NS alignment index {idx}")
            rows[idx] = row
    return rows


def main() -> int:
    ns_lookup = load_ns_lookup()
    pc = load_pc_scene()
    aligned = load_alignment_rows()

    expected_indices = set(range(EXPECTED_COUNT))
    if set(aligned) != expected_indices:
        missing = sorted(expected_indices - set(aligned))
        extra = sorted(set(aligned) - expected_indices)
        raise ValueError(f"1040 NS index set mismatch: missing={missing}, extra={extra}")

    output_rows: list[dict[str, str]] = []
    status_counts: dict[str, int] = {}
    override_count = 0

    for idx in range(EXPECTED_COUNT):
        a = aligned[idx]
        key = (a["ns_file"], a["ns_length_offset"])
        ns = ns_lookup.get(key)
        if ns is None:
            raise ValueError(f"NS extraction row not found: {key}")
        if ns["text"] != a["ns_source"]:
            raise ValueError(f"NS source mismatch at index {idx}: {key}")

        if idx in OVERRIDES:
            pc_idx, replacement, note = OVERRIDES[idx]
            if replacement is not None:
                raw_translation = replacement
            elif pc_idx is not None:
                raw_translation = pc[pc_idx]
            else:
                raise AssertionError(idx)
            translation = convert_pc_text(ns["text"], raw_translation)
            alignment_status = "manual-reviewed-override"
            alignment_reason = note
            pc_file = "1040.gsc" if pc_idx is not None else ""
            pc_string_index = str(pc_idx) if pc_idx is not None else ""
            override_count += 1
        else:
            if a["status"] not in {"high-candidate", "review"}:
                raise ValueError(f"unhandled non-aligned 1040 index {idx}: {a['status']}")
            if not a["pc_translation"]:
                raise ValueError(f"missing PC translation at 1040 index {idx}")
            translation = convert_pc_text(ns["text"], a["pc_translation"])
            alignment_status = a["status"]
            alignment_reason = a["reason"]
            pc_file = a["pc_file"]
            pc_string_index = a["pc_string_index"]

        src_voice = VOICE_RE.match(ns["text"])
        dst_voice = VOICE_RE.match(translation)
        if bool(src_voice) != bool(dst_voice):
            raise ValueError(f"voice presence mismatch at 1040 index {idx}")
        if src_voice and dst_voice and src_voice.group(1) != dst_voice.group(1):
            raise ValueError(
                f"voice prefix mismatch at 1040 index {idx}: "
                f"{src_voice.group(1)} != {dst_voice.group(1)}"
            )
        if "^n" in translation or UNKNOWN_PC_RUBY_RE.search(translation):
            raise ValueError(f"PC markup residue at 1040 index {idx}: {translation!r}")

        output_rows.append(
            {
                "file": ns["file"],
                "length_offset": ns["length_offset"],
                "text_offset": ns["text_offset"],
                "stored_length": ns["stored_length"],
                "byte_length": ns["byte_length"],
                "source": ns["text"],
                "translation": translation,
                "scene": SCENE,
                "ns_filtered_index": str(idx),
                "pc_file": pc_file,
                "pc_string_index": pc_string_index,
                "alignment_status": alignment_status,
                "alignment_reason": alignment_reason,
            }
        )
        status_counts[alignment_status] = status_counts.get(alignment_status, 0) + 1

    if len(output_rows) != EXPECTED_COUNT:
        raise AssertionError(len(output_rows))

    # The finalized scene should contain no Japanese kana in the translated
    # payload. Control codes and CJK ideographs are intentionally allowed.
    kana_rows = [
        (int(r["ns_filtered_index"]), r["translation"])
        for r in output_rows
        if KANA_RE.search(r["translation"])
    ]
    if kana_rows:
        raise ValueError(f"Japanese kana remain in translations: {kana_rows[:5]}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
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
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    voice_count = sum(bool(VOICE_RE.match(r["source"])) for r in output_rows)
    print(f"scene={SCENE}")
    print(f"rows_written={len(output_rows)}")
    print(f"voice_rows={voice_count}")
    print(f"manual_overrides={override_count}")
    print(f"status_counts={status_counts}")
    print("index_contiguous=True")
    print("voice_prefix_mismatch=0")
    print("pc_markup_residue=0")
    print("translation_kana_rows=0")
    print(f"output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
