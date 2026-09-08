#!/usr/bin/env python3
"""Build a fully reviewed 30/30 translation batch for NS scene 1090."""

from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALIGNMENT = ROOT / "03_text" / "matched" / "pc-ns-alignment-candidates-v2.tsv"
NS_EXTRACT = ROOT / "03_text" / "ns_extracted" / "ns-strings-v1.0.3.tsv"
PC_EXTRACT = ROOT / "03_text" / "pc_extracted" / "pc-gsc-strings.tsv"
OUTPUT = ROOT / "03_text" / "translated" / "scene1090-full-v1.tsv"

SCENE = "1090"
EXPECTED_COUNT = 30
VOICE_RE = re.compile(r"^(@v{2,3}\d+)")
PC_RUBY_RE = re.compile(r"\|([^\[]+)\[([^\]]+)\]")
UNKNOWN_PC_RUBY_RE = re.compile(r"\|[^\[]+\[[^\]]*\]")
KANA_RE = re.compile(r"[\u3040-\u30ff]")

OVERRIDES: dict[int, tuple[int, str]] = {
    4: (5, "PC 4 is standalone speaker name; NS maps directly to inner monologue PC 5"),
}

POLISH: dict[int, tuple[str, str]] = {
    0: ("阿尔艾特误打误撞走进了一栋有些眼熟的建筑。", "smooth opening narration"),
    2: ("她循着零碎的记忆，探头看向一扇觉得眼熟的门。果然，里面正是进行过适性检测的造化室。", "natural rendering of これと思う扉を覗く"),
    3: ("好奇心驱使着阿尔艾特轻轻推开门──这时，她注意到那张少女造型的椅子上已经坐着一个人。", "fix awkward review narration"),
    5: ("她轻声念出自己记住的名字。那是最排斥阿尔艾特存在的、容貌华丽的少女。", "smooth review narration"),
    9: ("看到玻璃罩内亮起一缕微弱的光，阿尔艾特停下了脚步。", "fix PC mistranslation of あえかな光が灯った"),
    15: ("如果那道视线真拥有与其中怒意同等的热度，阿尔艾特恐怕早在这一瞬间被烧成焦炭了。", "fix PC mistranslation of 視線に意思と同じだけの熱"),
    16: ("@vv20402「负责照看你的人在做什么？　怠慢也该有个限度」", "render 世話係 accurately"),
    17: ("她的怒火似乎也烧向了此刻并不在场的卡娜莉。", "fix incomplete Chinese sentence"),
    20: ("阿薇拉绽放的蔷薇实在太美，她才会忍不住发出赞叹──可阿尔艾特又不敢把这番解释说出口。", "fix first-person leakage in narration"),
    23: ("@vv20403「让那朵花枯萎的人，就是你」", "remove unsupported softening particle"),
    24: ("@vv20404「它被你那卑贱的目光玷污了，所以我至少赐予了它毁灭」", "restore literal meaning of せめてもの滅びを与えてやった"),
    26: ("她是真心想再多看一会儿那朵美丽的蔷薇，而直到现在，这份愿望仍留在胸中。", "smooth narration"),
    27: ("@vv20405「既然明白自己的罪孽有多深，就消失吧」", "keep Avela's cold tone without extra wording"),
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
    out = {}
    with NS_EXTRACT.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            out[(row["file"], row["length_offset"])] = row
    return out


def load_pc_scene() -> dict[int, str]:
    out: dict[int, str] = {}
    with PC_EXTRACT.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["file"] == "1090.gsc" and row["decode_ok"] == "1":
                out[int(row["string_index"])] = row["text"]
    return out


def load_alignment_rows() -> dict[int, dict[str, str]]:
    out = {}
    with ALIGNMENT.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["scene"] == SCENE and row["ns_filtered_index"]:
                idx = int(row["ns_filtered_index"])
                if idx in out:
                    raise ValueError(f"duplicate NS index {idx}")
                out[idx] = row
    return out


def main() -> int:
    ns_lookup = load_ns_lookup()
    pc = load_pc_scene()
    aligned = load_alignment_rows()
    expected = set(range(EXPECTED_COUNT))
    if set(aligned) != expected:
        raise ValueError(f"1090 index set mismatch: missing={sorted(expected-set(aligned))}")

    rows = []
    status_counts: dict[str, int] = {}
    for idx in range(EXPECTED_COUNT):
        a = aligned[idx]
        ns = ns_lookup[(a["ns_file"], a["ns_length_offset"])]
        if ns["text"] != a["ns_source"]:
            raise ValueError(f"NS source mismatch at 1090 index {idx}")

        if idx in OVERRIDES:
            pc_idx, reason = OVERRIDES[idx]
            translation = convert_pc_text(ns["text"], pc[pc_idx])
            status = "manual-reviewed-override"
            pc_file = "1090.gsc"
            pc_string_index = str(pc_idx)
        else:
            if a["status"] not in {"high-candidate", "review"}:
                raise ValueError(f"unhandled 1090 index {idx}: {a['status']}")
            translation = convert_pc_text(ns["text"], a["pc_translation"])
            status = a["status"]
            reason = a["reason"]
            pc_file = a["pc_file"]
            pc_string_index = a["pc_string_index"]

        if idx in POLISH:
            translation, polish_reason = POLISH[idx]
            if idx in OVERRIDES:
                status = "manual-reviewed-override+polish"
                reason = f"{reason}; {polish_reason}"
            else:
                status = "manual-reviewed-polish"
                reason = polish_reason

        sv = VOICE_RE.match(ns["text"])
        tv = VOICE_RE.match(translation)
        if (sv.group(1) if sv else None) != (tv.group(1) if tv else None):
            raise ValueError(f"voice mismatch at 1090 index {idx}")
        if KANA_RE.search(translation) or "^n" in translation or UNKNOWN_PC_RUBY_RE.search(translation):
            raise ValueError(f"translation residue at 1090 index {idx}")

        rows.append({
            "file": ns["file"], "length_offset": ns["length_offset"],
            "text_offset": ns["text_offset"], "stored_length": ns["stored_length"],
            "byte_length": ns["byte_length"], "source": ns["text"],
            "translation": translation, "scene": SCENE,
            "ns_filtered_index": str(idx), "pc_file": pc_file,
            "pc_string_index": pc_string_index, "alignment_status": status,
            "alignment_reason": reason,
        })
        status_counts[status] = status_counts.get(status, 0) + 1

    fields = list(rows[0].keys())
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)

    print(f"scene={SCENE}")
    print(f"rows_written={len(rows)}")
    print(f"voice_rows={sum(bool(VOICE_RE.match(r['source'])) for r in rows)}")
    print(f"manual_overrides={len(OVERRIDES)}")
    print(f"manual_polishes={len(POLISH)}")
    print(f"status_counts={status_counts}")
    print(f"output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
