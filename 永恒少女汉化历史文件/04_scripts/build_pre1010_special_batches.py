#!/usr/bin/env python3
"""Build the remaining pre-1010 special/Extra NS text batches."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALIGNMENT = ROOT / "03_text" / "matched" / "pc-ns-alignment-candidates-v2.tsv"
SUMMARY = ROOT / "03_text" / "matched" / "scene-alignment-summary-v2.tsv"
NS_EXTRACT = ROOT / "03_text" / "ns_extracted" / "ns-strings-v1.0.3.tsv"
OUT_DIR = ROOT / "03_text" / "translated" / "special-pre1010"

VOICE_RE = re.compile(r"^(@v{2,3}[A-Za-z0-9]+)")
PC_RUBY_RE = re.compile(r"\|([^\[]+)\[([^\]]+)\]")
KANA_RE = re.compile(r"[\u3040-\u30ff]")

LOCATIONS = {
    "校門": "校门",
    "礼讃祈堂": "礼赞祈堂",
    "マコーの私室": "玛可的私室",
    "パヴォーネの私室": "帕沃妮的私室",
    "礼讃祈堂地下": "礼赞祈堂地下",
    "食堂": "食堂",
    "中庭": "中庭",
    "座学室": "座学室",
    "造化室": "造化室",
    "機械室": "机械室",
    "服飾室": "服饰室",
    "図書館": "图书馆",
    "時計塔": "钟塔",
    "南の森": "南之森",
    "北の森": "北之森",
    **{f"場所{i:02d}": f"地点{i:02d}" for i in range(1, 16)},
}

EXTRA_TITLES = {
    "　無知の知　": "　无知之知　",
    "　悪夢と救済　": "　噩梦与救济　",
    "　誰がための祝祭　": "　为谁而设的庆典　",
    "　つぎはぎだらけの夢　": "　拼凑而成的梦　",
}


def convert_pc(ns_source: str, pc_translation: str) -> str:
    text = pc_translation.replace("^n", "@n")
    text = PC_RUBY_RE.sub(lambda m: f"@r{m.group(1)}@{m.group(2)}@", text)
    voice = VOICE_RE.match(ns_source)
    if voice and not text.startswith(voice.group(1)):
        text = voice.group(1) + text
    return text


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with SUMMARY.open("r", encoding="utf-8-sig", newline="") as f:
        summary = list(csv.DictReader(f, delimiter="\t"))
    targets = {
        r["scene"]: int(r["ns_story_tokens"])
        for r in summary
        if r["scene"].isdigit() and int(r["scene"]) < 1010 and int(r["ns_story_tokens"]) > 0
    }

    by_scene: dict[str, dict[int, dict[str, str]]] = defaultdict(dict)
    with ALIGNMENT.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["scene"] in targets and r["ns_filtered_index"]:
                by_scene[r["scene"]][int(r["ns_filtered_index"])] = r

    ns_meta: dict[tuple[str, str], dict[str, str]] = {}
    with NS_EXTRACT.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            ns_meta[(r["file"], r["length_offset"])] = r

    fields = [
        "file", "length_offset", "text_offset", "stored_length", "byte_length",
        "source", "translation", "scene", "ns_filtered_index", "pc_file",
        "pc_string_index", "alignment_status", "alignment_reason",
    ]

    total = 0
    reused_pc = 0
    direct_fixed = 0
    location_rows = 0
    kana_rows = 0
    voice_mismatch = 0

    for scene, expected in sorted(targets.items(), key=lambda x: int(x[0])):
        src = by_scene[scene]
        if set(src) != set(range(expected)):
            raise ValueError(f"scene {scene}: missing NS indices")
        rows = []
        for idx in range(expected):
            a = src[idx]
            source = a["ns_source"]
            pc_file = ""
            pc_string_index = ""
            if source in LOCATIONS:
                translation = LOCATIONS[source]
                status = "fixed-location-name"
                reason = "shared special-scene location dictionary"
                location_rows += 1
            elif source in EXTRA_TITLES:
                translation = EXTRA_TITLES[source]
                status = "manual-direct-extra-title"
                reason = "no reliable PC counterpart"
                direct_fixed += 1
            elif a["pc_translation"]:
                translation = convert_pc(source, a["pc_translation"])
                status = "pc-reused-special"
                reason = f"reuse PC localization from {a['status']} mapping"
                pc_file = a["pc_file"]
                pc_string_index = a["pc_string_index"]
                reused_pc += 1
            else:
                raise ValueError(f"scene {scene} index {idx}: unresolved source {source!r}")

            meta = ns_meta[(a["ns_file"], a["ns_length_offset"])]
            sv = VOICE_RE.match(source)
            tv = VOICE_RE.match(translation)
            if (sv.group(1) if sv else None) != (tv.group(1) if tv else None):
                voice_mismatch += 1
            if KANA_RE.search(translation):
                kana_rows += 1
            rows.append({
                "file": meta["file"], "length_offset": meta["length_offset"],
                "text_offset": meta["text_offset"], "stored_length": meta["stored_length"],
                "byte_length": meta["byte_length"], "source": source,
                "translation": translation, "scene": scene,
                "ns_filtered_index": str(idx), "pc_file": pc_file,
                "pc_string_index": pc_string_index, "alignment_status": status,
                "alignment_reason": reason,
            })

        output = OUT_DIR / f"scene{scene}-full-v1.tsv"
        with output.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
            w.writeheader(); w.writerows(rows)
        total += len(rows)

    print(f"scenes={len(targets)}")
    print(f"rows={total}")
    print(f"location_rows={location_rows}")
    print(f"pc_reused_rows={reused_pc}")
    print(f"manual_title_rows={direct_fixed}")
    print(f"voice_mismatch={voice_mismatch}")
    print(f"translation_kana_rows={kana_rows}")
    print(f"output_dir={OUT_DIR}")
    if total != 535 or voice_mismatch or kana_rows:
        raise SystemExit(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
