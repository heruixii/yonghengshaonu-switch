#!/usr/bin/env python3
"""Combine clean, auto-mapped and direct-translated post-1100 rows into full scene TSVs."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "03_text" / "matched" / "scene-alignment-summary-v2.tsv"
NS_EXTRACT = ROOT / "03_text" / "ns_extracted" / "ns-strings-v1.0.3.tsv"
OUT_DIR = ROOT / "03_text" / "translated" / "bulk-post1100"
MAP_FILE = OUT_DIR / "exception-auto-map.tsv"
DIRECT_FILE = OUT_DIR / "exception-direct-translations.tsv"

VOICE_RE = re.compile(r"^(@v{2,3}[A-Za-z0-9]+)")
PC_RUBY_RE = re.compile(r"\|([^\[]+)\[([^\]]+)\]")
UNKNOWN_PC_RUBY_RE = re.compile(r"\|[^\[]+\[[^\]]*\]")
KANA_RE = re.compile(r"[\u3040-\u30ff]")

# Minimal source-side fixes for two PC strings that retain the Japanese long-vowel mark.
# These are residue fixes only, not prose polishing.
FIXED_MAPPED_TRANSLATIONS: dict[tuple[str, int], str] = {
    ("2090", 42): "@vv71207「啊……怎么了，阿薇拉。@r不@·@@r高@·@@r兴@·@@r的@·@@r样@·@子」",
    ("2090", 54): "@vv71209「知——道——了……」",
}


def convert_pc_text(ns_source: str, pc_translation: str) -> str:
    text = pc_translation.replace("^n", "@n")
    text = PC_RUBY_RE.sub(lambda m: f"@r{m.group(1)}@{m.group(2)}@", text)
    if UNKNOWN_PC_RUBY_RE.search(text):
        raise ValueError(f"unconverted PC ruby: {pc_translation!r}")
    voice = VOICE_RE.match(ns_source)
    if voice and not text.startswith(voice.group(1)):
        text = voice.group(1) + text
    return text


def main() -> int:
    with SUMMARY.open("r", encoding="utf-8-sig", newline="") as f:
        summary = list(csv.DictReader(f, delimiter="\t"))
    target_counts = {
        r["scene"]: int(r["ns_story_tokens"])
        for r in summary
        if r["scene"].isdigit() and int(r["scene"]) > 1100 and int(r["ns_story_tokens"]) > 0
    }
    exception_scenes = {
        r["scene"] for r in summary
        if r["scene"] in target_counts
        and (int(r["ns_gaps"]) or int(r["pc_gaps"]) or int(r["review"]))
    }

    ns_meta: dict[tuple[str, str], dict[str, str]] = {}
    with NS_EXTRACT.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            ns_meta[(row["file"], row["length_offset"])] = row

    mapped_by_scene: dict[str, dict[int, dict[str, str]]] = defaultdict(dict)
    with MAP_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            mapped_by_scene[row["scene"]][int(row["ns_filtered_index"])] = row

    direct_by_scene: dict[str, dict[int, dict[str, str]]] = defaultdict(dict)
    with DIRECT_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            direct_by_scene[row["scene"]][int(row["ns_filtered_index"])] = row

    fields = [
        "file", "length_offset", "text_offset", "stored_length", "byte_length",
        "source", "translation", "scene", "ns_filtered_index", "pc_file",
        "pc_string_index", "alignment_status", "alignment_reason",
    ]

    built_rows = 0
    built_exception_scenes = 0
    for scene in sorted(exception_scenes, key=int):
        expected = target_counts[scene]
        mapped = mapped_by_scene.get(scene, {})
        direct = direct_by_scene.get(scene, {})
        if set(mapped) & set(direct):
            raise ValueError(f"scene {scene}: mapped/direct overlap")
        if set(mapped) | set(direct) != set(range(expected)):
            missing = sorted(set(range(expected)) - (set(mapped) | set(direct)))
            raise ValueError(f"scene {scene}: missing indices {missing}")

        rows: list[dict[str, str]] = []
        used_pc_filtered: list[int] = []
        for idx in range(expected):
            if idx in mapped:
                m = mapped[idx]
                meta = ns_meta[(m["ns_file"], m["ns_length_offset"])]
                translation = convert_pc_text(m["ns_source"], m["pc_translation"])
                translation = FIXED_MAPPED_TRANSLATIONS.get((scene, idx), translation)
                row = {
                    "file": meta["file"], "length_offset": meta["length_offset"],
                    "text_offset": meta["text_offset"], "stored_length": meta["stored_length"],
                    "byte_length": meta["byte_length"], "source": meta["text"],
                    "translation": translation, "scene": scene,
                    "ns_filtered_index": str(idx), "pc_file": m["pc_file"],
                    "pc_string_index": m["pc_string_index"],
                    "alignment_status": m["map_status"],
                    "alignment_reason": f"post1100 structural map cost={m['cost']}",
                }
                used_pc_filtered.append(int(m["pc_filtered_index"]))
            else:
                d = direct[idx]
                meta = ns_meta[(d["ns_file"], d["ns_length_offset"])]
                row = {
                    "file": meta["file"], "length_offset": meta["length_offset"],
                    "text_offset": meta["text_offset"], "stored_length": meta["stored_length"],
                    "byte_length": meta["byte_length"], "source": meta["text"],
                    "translation": d["translation"], "scene": scene,
                    "ns_filtered_index": str(idx), "pc_file": "",
                    "pc_string_index": "",
                    "alignment_status": "manual-direct-ns-only",
                    "alignment_reason": "no reliable PC counterpart after structural realignment",
                }

            sv = VOICE_RE.match(row["source"])
            tv = VOICE_RE.match(row["translation"])
            if (sv.group(1) if sv else None) != (tv.group(1) if tv else None):
                raise ValueError(f"scene {scene} index {idx}: voice mismatch")
            if "^n" in row["translation"] or UNKNOWN_PC_RUBY_RE.search(row["translation"]):
                raise ValueError(f"scene {scene} index {idx}: PC markup residue")
            rows.append(row)

        if used_pc_filtered != sorted(used_pc_filtered) or len(used_pc_filtered) != len(set(used_pc_filtered)):
            raise ValueError(f"scene {scene}: PC mapping is not strictly monotonic/unique")

        output = OUT_DIR / f"scene{scene}-full-v1.tsv"
        with output.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
            w.writeheader(); w.writerows(rows)
        built_exception_scenes += 1
        built_rows += len(rows)

    # Verify clean TSVs and all scene files together.
    all_rows = 0
    all_scenes = 0
    kana_rows = 0
    voice_mismatch = 0
    direct_rows = 0
    for scene, expected in sorted(target_counts.items(), key=lambda x: int(x[0])):
        p = OUT_DIR / f"scene{scene}-full-v1.tsv"
        if not p.exists():
            raise FileNotFoundError(p)
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f, delimiter="\t"))
        if len(rows) != expected:
            raise ValueError(f"scene {scene}: expected {expected}, got {len(rows)}")
        if [int(r["ns_filtered_index"]) for r in rows] != list(range(expected)):
            raise ValueError(f"scene {scene}: non-contiguous NS indices")
        for r in rows:
            sv = VOICE_RE.match(r["source"])
            tv = VOICE_RE.match(r["translation"])
            if (sv.group(1) if sv else None) != (tv.group(1) if tv else None):
                voice_mismatch += 1
            if KANA_RE.search(r["translation"]):
                kana_rows += 1
            if r["alignment_status"] == "manual-direct-ns-only":
                direct_rows += 1
        all_rows += len(rows)
        all_scenes += 1

    print(f"exception_scenes_built={built_exception_scenes}")
    print(f"exception_rows_built={built_rows}")
    print(f"all_scenes={all_scenes}")
    print(f"all_rows={all_rows}")
    print(f"manual_direct_rows={direct_rows}")
    print(f"voice_mismatch={voice_mismatch}")
    print(f"translation_kana_rows={kana_rows}")
    print(f"output_dir={OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
