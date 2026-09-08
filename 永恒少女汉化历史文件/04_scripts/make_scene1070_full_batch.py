#!/usr/bin/env python3
"""Generate scene 1070 from the clean generic alignment plus durable polish."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERIC = ROOT / "04_scripts" / "make_translation_batch.py"
ALIGNMENT = ROOT / "03_text" / "matched" / "pc-ns-alignment-candidates-v2.tsv"
NS_EXTRACT = ROOT / "03_text" / "ns_extracted" / "ns-strings-v1.0.3.tsv"
OUTPUT = ROOT / "03_text" / "translated" / "scene1070-full-v1.tsv"


POLISH: dict[int, tuple[str, str]] = {
    4: ("阿尔艾特在外侧墙壁内凹般的通道里发现了人影，于是停下脚步。", "fix PC spatial mistranslation of 外辺に抉りこむような通路"),
    12: ("@vv00604「这样啊……」", "natural rendering of そう……"),
    14: ("@vv30403「明明都被安排暂时照顾你了，那家伙这么快就把你丢着不管了吗」", "smooth rough Robin dialogue"),
    17: ("@vv30404「也许吧。那家伙就喜欢自己忙这些事的样子」", "clarify そういう自分が好き"),
    18: ("@vv00606「……温柔的人会讨人喜欢。自己也会喜欢那样的自己」", "restore reflexive meaning of その人自身にも"),
    20: ("阿尔艾特替卡娜莉说的每一句好话，都被萝宾毫不留情地挡了回来。", "natural rendering of 擁護は悉く弾き返された"),
    30: ("@vv00609「不、不用了。还是留到那个‘早晚’再看吧」", "preserve joke referring back to いずれ"),
    34: ("@vv00610「没有」", "natural full reply for いいえ"),
    36: ("@vv00611「什么都不记得。……什么都不知道」", "distinguish 憶え and わからない"),
    40: ("阿尔艾特自认为已经拼命寻找合适的说法来回答了，可似乎仍没达到萝宾的期待，得到的只有一句冷淡的回应。", "fix awkward PC narration wording"),
    44: ("阿尔艾特没能理解萝宾这句话的意思，疑惑地歪了歪头。", "fix typo/awkward 话中意"),
}


def main() -> int:
    subprocess.run(
        [
            sys.executable,
            str(GENERIC),
            str(ALIGNMENT),
            str(NS_EXTRACT),
            "--scene", "1070",
            "--start", "0",
            "--end", "47",
            "--output", str(OUTPUT),
        ],
        check=True,
    )

    with OUTPUT.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    if len(rows) != 48 or [int(r["ns_filtered_index"]) for r in rows] != list(range(48)):
        raise ValueError("scene 1070 generic batch is not contiguous 0..47")

    for idx, (translation, note) in POLISH.items():
        row = rows[idx]
        row["translation"] = translation
        row["alignment_status"] = "manual-reviewed-polish"
        row["alignment_reason"] = note

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print("scene=1070")
    print(f"rows_written={len(rows)}")
    print(f"manual_polishes={len(POLISH)}")
    print(f"output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
