#!/usr/bin/env python3
"""Build conservative final batches for 5000/5010 (no PC original JP available)."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "03_text" / "matched" / "pc-ns-alignment-candidates-v2.tsv"
SUMMARY = ROOT / "03_text" / "matched" / "scene-alignment-summary-v2.tsv"
NS_EXTRACT = ROOT / "03_text" / "ns_extracted" / "ns-strings-v1.0.3.tsv"
OLD_DIRECT = ROOT / "03_text" / "translated" / "bulk-post1100" / "exception-direct-translations.tsv"
NEW_DIRECT = ROOT / "03_text" / "translated" / "scenes5000-5010-direct-translations.tsv"
OUT_DIR = ROOT / "03_text" / "translated" / "v3-final-scenes"

VOICE_RE = re.compile(r"^(@v{2,3}[A-Za-z0-9]+)")
PC_RUBY_RE = re.compile(r"\|([^\[]+)\[([^\]]+)\]")
KANA_RE = re.compile(r"[\u3040-\u30ff]")

FIXED_HIGH_FALLBACK: dict[tuple[str, int], str] = {
    # v2 high candidate was structurally aligned, but the PC Chinese source
    # mistranslated 幸いする as the noun “幸福”.
    ("5000", 212): "@vv19226「……真不知道什么事情反而会带来好运呢」",
}


def convert_pc(source: str, text: str) -> str:
    text = text.replace("^n", "@n")
    text = PC_RUBY_RE.sub(lambda m: f"@r{m.group(1)}@{m.group(2)}@", text)
    v = VOICE_RE.match(source)
    if v and not text.startswith(v.group(1)):
        text = v.group(1) + text
    return text


def load_direct(path: Path) -> dict[tuple[str, int], str]:
    out = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            out[(r["scene"], int(r["ns_filtered_index"]))] = r["translation"]
    return out


def main() -> int:
    targets = {}
    with SUMMARY.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["scene"] in {"5000", "5010"}:
                targets[r["scene"]] = int(r["ns_story_tokens"])

    rows_by: dict[str, dict[int, dict[str, str]]] = defaultdict(dict)
    with V2.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["scene"] in targets and r["ns_filtered_index"]:
                rows_by[r["scene"]][int(r["ns_filtered_index"])] = r

    meta = {}
    with NS_EXTRACT.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            meta[(r["file"], r["length_offset"])] = r

    direct = load_direct(OLD_DIRECT)
    direct.update(load_direct(NEW_DIRECT))
    fields = [
        "file", "length_offset", "text_offset", "stored_length", "byte_length",
        "source", "translation", "scene", "ns_filtered_index", "pc_file",
        "pc_string_index", "alignment_status", "alignment_reason",
    ]
    total = high = direct_count = kana = voice_bad = 0
    for scene, expected in sorted(targets.items()):
        src = rows_by[scene]
        if set(src) != set(range(expected)):
            raise ValueError(f"scene {scene} index coverage mismatch")
        out = []
        for idx in range(expected):
            r = src[idx]
            source = r["ns_source"]
            key = (scene, idx)
            if r["status"] == "high-candidate":
                translation = convert_pc(source, r["pc_translation"])
                translation = FIXED_HIGH_FALLBACK.get(key, translation)
                status = "v2-high-fallback"
                reason = "PC original JP unavailable; v2 high candidate retained"
                pc_file, pc_index = r["pc_file"], r["pc_string_index"]
                high += 1
            else:
                if key not in direct:
                    raise ValueError(f"missing direct fallback {key}")
                translation = direct[key]
                status = "manual-direct-no-pc-jp"
                reason = f"PC original JP unavailable; v2 status={r['status']} not trusted"
                pc_file = pc_index = ""
                direct_count += 1
            m = meta[(r["ns_file"], r["ns_length_offset"])]
            sv, tv = VOICE_RE.match(source), VOICE_RE.match(translation)
            if (sv.group(1) if sv else None) != (tv.group(1) if tv else None):
                voice_bad += 1
            if KANA_RE.search(translation):
                kana += 1
            out.append({
                "file": m["file"], "length_offset": m["length_offset"],
                "text_offset": m["text_offset"], "stored_length": m["stored_length"],
                "byte_length": m["byte_length"], "source": source,
                "translation": translation, "scene": scene, "ns_filtered_index": str(idx),
                "pc_file": pc_file, "pc_string_index": pc_index,
                "alignment_status": status, "alignment_reason": reason,
            })
        p = OUT_DIR / f"scene{scene}-full-v3.tsv"
        with p.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
            w.writeheader(); w.writerows(out)
        total += len(out)
    print(f"rows={total} high_fallback={high} direct={direct_count}")
    print(f"voice_mismatch={voice_bad} kana_rows={kana}")
    if voice_bad or kana:
        raise SystemExit(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
