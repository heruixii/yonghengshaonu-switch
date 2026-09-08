#!/usr/bin/env python3
"""Build a fully reviewed 76/76 translation batch for NS scene 1050."""

from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALIGNMENT = ROOT / "03_text" / "matched" / "pc-ns-alignment-candidates-v2.tsv"
NS_EXTRACT = ROOT / "03_text" / "ns_extracted" / "ns-strings-v1.0.3.tsv"
PC_EXTRACT = ROOT / "03_text" / "pc_extracted" / "pc-gsc-strings.tsv"
OUTPUT = ROOT / "03_text" / "translated" / "scene1050-full-v1.tsv"

SCENE = "1050"
EXPECTED_COUNT = 76
VOICE_RE = re.compile(r"^(@v{2,3}\d+)")
PC_RUBY_RE = re.compile(r"\|([^\[]+)\[([^\]]+)\]")
UNKNOWN_PC_RUBY_RE = re.compile(r"\|[^\[]+\[[^\]]*\]")
KANA_RE = re.compile(r"[\u3040-\u30ff]")

# PC stores the speaker name as a separate record at each of these three
# inner-monologue points. Switch omits that name record and keeps only the
# voiced inner-monologue string.
OVERRIDES: dict[int, tuple[int, str]] = {
    66: (101, "PC 100 is standalone speaker name; NS maps directly to inner monologue PC 101"),
    70: (106, "PC 105 is standalone speaker name; NS maps directly to inner monologue PC 106"),
    73: (111, "PC 110 is standalone speaker name; PC 109 transition line has no independent NS record"),
}

# Keep these small wording fixes durable instead of inheriting a handful of
# visibly awkward / over-compressed lines from the old PC translation.
POLISH: dict[int, tuple[str, str]] = {
    5: ("卡娜莉打开走廊上一扇门，将阿尔艾特领进房内。", "manual polish: make the room-entry narration natural in Chinese"),
    14: ("「你问为什么……」", "manual polish: preserve the hesitant echo in どうして、って"),
    19: ("「裸露身体会带来不好的影响……？」", "manual polish: remove unnatural punctuation and clarify 裸"),
    25: ("「旅行者的心得？」", "manual polish: concise rendering of 旅人の心得"),
    32: ("可这件睡衣领口敞开，衣袖和下摆还用了透光的布料。大概是因为只会在自己的房间里穿，不会有给别人看到的机会吧。", "manual polish: restore the open-neckline detail and smooth the narration"),
    41: ("「有资格进入这所学园的人比你想象的少得多。即使在大城市里，也未必能有一个。大家都以能来到这里为荣」", "manual polish: remove unsupported '幸运儿' wording"),
    42: ("「门槛很高呢。我这种人不该进来的……」", "manual polish: idiomatic rendering of 狭き門"),
    61: ("那是一场仿佛饥渴已久、贪婪吞噬睡眠般的沉睡。甚至无暇做梦，只是在虚无的世界中漂浮。", "manual polish: restore imagery omitted by the PC translation"),
    64: ("附近的桌上放着面包和已经开始变凉的汤。唤醒阿尔艾特的，似乎正是那股香味。", "manual polish: natural narration for 冷えはじめたスープ"),
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
            if row["file"] == "1050.gsc" and row["decode_ok"] == "1":
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

    expected = set(range(EXPECTED_COUNT))
    if set(aligned) != expected:
        raise ValueError(
            f"1050 NS index set mismatch: missing={sorted(expected-set(aligned))}, "
            f"extra={sorted(set(aligned)-expected)}"
        )

    output_rows: list[dict[str, str]] = []
    status_counts: dict[str, int] = {}

    for idx in range(EXPECTED_COUNT):
        a = aligned[idx]
        key = (a["ns_file"], a["ns_length_offset"])
        ns = ns_lookup.get(key)
        if ns is None or ns["text"] != a["ns_source"]:
            raise ValueError(f"NS source lookup mismatch at 1050 index {idx}: {key}")

        if idx in POLISH:
            polished, note = POLISH[idx]
            translation = convert_pc_text(ns["text"], polished)
            status = "manual-reviewed-polish"
            reason = note
            pc_file = a["pc_file"]
            pc_string_index = a["pc_string_index"]
        elif idx in OVERRIDES:
            pc_idx, note = OVERRIDES[idx]
            translation = convert_pc_text(ns["text"], pc[pc_idx])
            status = "manual-reviewed-override"
            reason = note
            pc_file = "1050.gsc"
            pc_string_index = str(pc_idx)
        else:
            if a["status"] not in {"high-candidate", "review"}:
                raise ValueError(f"unhandled 1050 index {idx}: {a['status']}")
            if not a["pc_translation"]:
                raise ValueError(f"missing PC translation at 1050 index {idx}")
            translation = convert_pc_text(ns["text"], a["pc_translation"])
            status = a["status"]
            reason = a["reason"]
            pc_file = a["pc_file"]
            pc_string_index = a["pc_string_index"]

        src_voice = VOICE_RE.match(ns["text"])
        dst_voice = VOICE_RE.match(translation)
        if (src_voice.group(1) if src_voice else None) != (dst_voice.group(1) if dst_voice else None):
            raise ValueError(f"voice prefix mismatch at 1050 index {idx}")
        if "^n" in translation or UNKNOWN_PC_RUBY_RE.search(translation):
            raise ValueError(f"PC markup residue at 1050 index {idx}")
        if KANA_RE.search(translation):
            raise ValueError(f"Japanese kana remain at 1050 index {idx}: {translation!r}")

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
                "alignment_status": status,
                "alignment_reason": reason,
            }
        )
        status_counts[status] = status_counts.get(status, 0) + 1

    fields = [
        "file", "length_offset", "text_offset", "stored_length", "byte_length",
        "source", "translation", "scene", "ns_filtered_index", "pc_file",
        "pc_string_index", "alignment_status", "alignment_reason",
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"scene={SCENE}")
    print(f"rows_written={len(output_rows)}")
    print(f"voice_rows={sum(bool(VOICE_RE.match(r['source'])) for r in output_rows)}")
    print(f"manual_overrides={len(OVERRIDES)}")
    print(f"manual_polishes={len(POLISH)}")
    print(f"status_counts={status_counts}")
    print("index_contiguous=True")
    print("voice_prefix_mismatch=0")
    print("pc_markup_residue=0")
    print("translation_kana_rows=0")
    print(f"output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
