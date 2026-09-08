#!/usr/bin/env python3
"""Build a fully reviewed 57/57 translation batch for NS scene 1080."""

from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALIGNMENT = ROOT / "03_text" / "matched" / "pc-ns-alignment-candidates-v2.tsv"
NS_EXTRACT = ROOT / "03_text" / "ns_extracted" / "ns-strings-v1.0.3.tsv"
PC_EXTRACT = ROOT / "03_text" / "pc_extracted" / "pc-gsc-strings.tsv"
OUTPUT = ROOT / "03_text" / "translated" / "scene1080-full-v1.tsv"

SCENE = "1080"
EXPECTED_COUNT = 57
VOICE_RE = re.compile(r"^(@v{2,3}\d+)")
PC_RUBY_RE = re.compile(r"\|([^\[]+)\[([^\]]+)\]")
UNKNOWN_PC_RUBY_RE = re.compile(r"\|[^\[]+\[[^\]]*\]")
KANA_RE = re.compile(r"[\u3040-\u30ff]")

OVERRIDES: dict[int, tuple[int, str]] = {
    7: (8, "PC 7 is standalone speaker name; NS maps directly to inner monologue PC 8"),
    8: (10, "PC 9 is standalone speaker name; NS maps directly to inner monologue PC 10"),
    9: (11, "v2 false match: narration belongs to PC 11, not inner monologue PC 8"),
}

POLISH: dict[int, tuple[str, str]] = {
    0: ("实际上，在外面漫无目的走着的阿尔艾特，最先注意到的是钟塔。", "smooth opening narration"),
    4: ("从下面看时显得小巧，可真正爬上来后才发现，这是一座宽敞而气派的钟楼。", "natural rendering of 辿りついてみると"),
    6: ("但它确实响过。就在阿尔艾特报上名字的瞬间，仿佛是在斥责那串音节一般──", "restore 音韻 nuance"),
    7: ("@vv00701（……那声音好可怕。简直像悲鸣一样……）", "natural inner monologue"),
    8: ("@vv00702（你为什么会响？　是因为我吗？　因为我是个不祥的存在吗？）", "natural inner monologue"),
    9: ("她一边在心里对钟说着这些，一边探出身子观察──", "clarify implicit addressee"),
    16: ("@vv00705「这样啊……」", "fix そう as 是的"),
    19: ("@vv00707「我不知道它为什么会响，只是那声音实在太猛烈了」", "fix causal structure of 激しい音だったから"),
    22: ("@vv10403「据说这口钟一旦鸣响，普埃拉利姆就会毁灭」", "remove unnecessary PC Latin ruby"),
    23: ("@vv00709「普埃拉利姆？」", "standardize school name without PC Latin ruby"),
    24: ("@vv10404「这是这所学园的名字」", "natural dialogue"),
    25: ("@vv00710「这样啊。『普埃拉利姆』……」", "standardize school name without PC Latin ruby"),
    26: ("离开时，卡娜莉好像说过这个名字。阿尔艾特像要将它刻进心里一样，一遍遍默念着。", "natural rendering of 反芻"),
    29: ("@vv00712「所以大家才会那么……」", "remove dangling 的"),
    32: ("露珂用毫无起伏的语气断言后，转身离开。", "natural narration"),
    37: ("@vv00715「而且，这里是只有被选中的人才能进入的特别学园吧。一般人也不会觉得，一个倒在路边的人会有这种资格」", "fix 行き倒れ mistranslation"),
    46: ("这张白皙的脸比她在学园里遇到的任何人都更缺乏感情。阿尔艾特忽然发现，自己正睁大眼睛，生怕错过她脸上哪怕一丝变化。", "smooth narration"),
    52: ("“花”是指适性检测时绽放的那些花吗？　无论是什么，露珂最终都把想问的话咽了回去。", "natural rendering of 問いかけを呑む"),
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
    out: dict[tuple[str, str], dict[str, str]] = {}
    with NS_EXTRACT.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            out[(row["file"], row["length_offset"])] = row
    return out


def load_pc_scene() -> dict[int, str]:
    out: dict[int, str] = {}
    with PC_EXTRACT.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["file"] == "1080.gsc" and row["decode_ok"] == "1":
                out[int(row["string_index"])] = row["text"]
    return out


def load_alignment_rows() -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
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
        raise ValueError(f"1080 index set mismatch: missing={sorted(expected-set(aligned))}")

    rows: list[dict[str, str]] = []
    status_counts: dict[str, int] = {}
    for idx in range(EXPECTED_COUNT):
        a = aligned[idx]
        ns = ns_lookup[(a["ns_file"], a["ns_length_offset"])]
        if ns["text"] != a["ns_source"]:
            raise ValueError(f"NS source mismatch at 1080 index {idx}")

        if idx in OVERRIDES:
            pc_idx, reason = OVERRIDES[idx]
            translation = convert_pc_text(ns["text"], pc[pc_idx])
            status = "manual-reviewed-override"
            pc_file = "1080.gsc"
            pc_string_index = str(pc_idx)
        else:
            if a["status"] not in {"high-candidate", "review"}:
                raise ValueError(f"unhandled 1080 index {idx}: {a['status']}")
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
            raise ValueError(f"voice mismatch at 1080 index {idx}")
        if KANA_RE.search(translation) or "^n" in translation or UNKNOWN_PC_RUBY_RE.search(translation):
            raise ValueError(f"translation residue at 1080 index {idx}")

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
