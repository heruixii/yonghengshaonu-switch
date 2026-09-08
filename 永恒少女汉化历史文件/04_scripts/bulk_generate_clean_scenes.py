#!/usr/bin/env python3
"""Generate all post-1100 scenes whose v2 alignment is fully clean."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "03_text" / "matched" / "scene-alignment-summary-v2.tsv"
ALIGNMENT = ROOT / "03_text" / "matched" / "pc-ns-alignment-candidates-v2.tsv"
NS_EXTRACT = ROOT / "03_text" / "ns_extracted" / "ns-strings-v1.0.3.tsv"
GENERIC = ROOT / "04_scripts" / "make_translation_batch.py"
OUT_DIR = ROOT / "03_text" / "translated" / "bulk-post1100"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with SUMMARY.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    clean = [
        r for r in rows
        if r["scene"].isdigit()
        and int(r["scene"]) > 1100
        and int(r["ns_story_tokens"]) > 0
        and int(r["ns_gaps"]) == 0
        and int(r["pc_gaps"]) == 0
        and int(r["review"]) == 0
    ]

    total = 0
    for r in clean:
        scene = r["scene"]
        count = int(r["ns_story_tokens"])
        output = OUT_DIR / f"scene{scene}-full-v1.tsv"
        subprocess.run(
            [
                sys.executable, str(GENERIC), str(ALIGNMENT), str(NS_EXTRACT),
                "--scene", scene, "--start", "0", "--end", str(count - 1),
                "--output", str(output),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        with output.open("r", encoding="utf-8-sig", newline="") as f:
            generated = list(csv.DictReader(f, delimiter="\t"))
        if len(generated) != count:
            raise ValueError(f"scene {scene}: expected {count}, got {len(generated)}")
        total += count
        print(f"{scene}\t{count}")

    print(f"clean_scenes={len(clean)}")
    print(f"clean_rows={total}")
    print(f"output_dir={OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
