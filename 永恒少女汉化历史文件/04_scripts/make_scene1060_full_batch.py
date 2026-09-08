#!/usr/bin/env python3
"""Generate scene 1060 with reviewed alignments and durable wording fixes."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERIC = ROOT / "04_scripts" / "make_translation_batch.py"
ALIGNMENT = ROOT / "03_text" / "matched" / "pc-ns-alignment-candidates-v2.tsv"
NS_EXTRACT = ROOT / "03_text" / "ns_extracted" / "ns-strings-v1.0.3.tsv"
OUTPUT = ROOT / "03_text" / "translated" / "scene1060-full-v1.tsv"

POLISH: dict[int, tuple[str, str]] = {
    5: ("玛可嘴上说得若无其事，却仍低着头。“只是多了点课题”究竟给她增加了多大负担，实在难以估量。", "smooth narration around the extra assignments"),
    12: ("@vv70405「就因为这种事啊。托它的福，我都快从特进班掉到普通班了」", "natural spoken rendering of 特進から一般に落ちそう"),
    28: ("@vv70411「说到底，不管怎样都会寂寞。根本没什么努力的意义嘛」", "fix awkward 努什么力 wording"),
    43: ("@vv50414「……我可在意」", "natural contrast for 私は構うわ"),
    49: ("@vv50415「……！」", "render caught-breath interjection without invented 呜"),
    56: ("@vv50416「……没、没什么」", "fix broken PC wording for hesitant べつ、に"),
    64: ("@vv00507「这样啊……」", "natural rendering of そう……"),
    70: ("@vv70419「哎呀，你已经知道啦。是谁告诉你我的名字的？」", "fix typo and smooth question"),
    71: ("@vv00510「也不算是谁教我的……之前听别人叫过你好几次了」", "natural rendering of 今までに何度か呼ばれていた"),
    72: ("@vv70420「这样就记住了？　只听一次就能记住？　挺厉害的嘛」", "smooth colloquial praise"),
    80: ("@vv70422「你肚子饿了吧？　去食堂的话应该还有东西吃」", "fix awkward 应该能有什么吃的"),
    87: ("@vv70424「你现在也是这里的学生了，要说能不能到处走，当然可以吧。虽然可能会被嫌弃就是了」", "restore いいか悪いか nuance"),
    89: ("@vv50425「下午特进班是自习，普通班则会在校舍的讲堂里上课」", "remove unsupported 一般来说 and keep schedule explicit"),
    101: ("@vv70429「去吧，回头见」", "distinguish いってらっしゃい from following 気をつけてね"),
    105: ("@vv70430「……真是个不可思议的孩子」", "avoid overly negative 奇怪 for 不思議"),
}


def main() -> int:
    subprocess.run(
        [
            sys.executable,
            str(GENERIC),
            str(ALIGNMENT),
            str(NS_EXTRACT),
            "--scene", "1060",
            "--start", "0",
            "--end", "106",
            "--include-review",
            "--output", str(OUTPUT),
        ],
        check=True,
    )

    with OUTPUT.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    if len(rows) != 107 or [int(r["ns_filtered_index"]) for r in rows] != list(range(107)):
        raise ValueError("scene 1060 generic batch is not contiguous 0..106")

    for idx, (translation, note) in POLISH.items():
        row = rows[idx]
        if int(row["ns_filtered_index"]) != idx:
            raise AssertionError(idx)
        # All polished dialogue strings already contain their exact NS voice
        # prefix. Narration fixes intentionally contain no voice control.
        row["translation"] = translation
        row["alignment_status"] = "manual-reviewed-polish"
        row["alignment_reason"] = note

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"scene=1060")
    print(f"rows_written={len(rows)}")
    print(f"manual_polishes={len(POLISH)}")
    print(f"review_rows={sum(r['alignment_status']=='review' for r in rows)}")
    print(f"output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
