#!/usr/bin/env python3
"""Inventory likely player-visible UI strings and System PNG resources.

This is deliberately conservative: it creates review candidates and never
modifies game data. Internal identifiers may still appear and must be marked
before translation/writeback.
"""

from __future__ import annotations

import argparse
import csv
import re
import struct
from pathlib import Path


JP_RE = re.compile(r"[\u3040-\u30ff]")
RESOURCE_RE = re.compile(
    r"^(?:[A-Za-z0-9_@.\-]+|[A-Za-z0-9_@.\-]+\.(?:dat|spm|png|mp4|opus|fnt|ttc|bin))$",
    re.IGNORECASE,
)

EXPLICIT_TEXT_FILES = {
    "Config/button.datu8",
    "Config/char.datu8",
    "Config/system.datu8",
    "Script/system.binu8",
    "Script/title.binu8",
    "Script/replaymode.binu8",
    "Script/eventmode.binu8",
}

IMAGE_PATTERNS = (
    "title",
    "config",
    "menu",
    "button",
    "save",
    "load",
    "extra",
    "replay",
    "caution",
    "help",
    "systembar",
    "controlbar",
    "automode",
    "quickconfig",
    "tabbar",
    "bgmtitle",
    "cgthumbnail",
)


def category_for_text(path: str) -> str:
    if path == "Config/button.datu8":
        return "button-help"
    if path == "Config/char.datu8":
        return "character-name"
    if path == "Script/title.binu8":
        return "title-script"
    if path == "Script/system.binu8":
        return "system-script"
    if "replay" in path.lower() or "eventmode" in path.lower():
        return "extra-script"
    if path == "Config/system.datu8":
        return "system-config"
    return "config-other"


def looks_candidate(path: str, text: str) -> tuple[bool, str]:
    if not JP_RE.search(text):
        return False, "no-kana"
    if RESOURCE_RE.fullmatch(text.strip()):
        return False, "resource-id"
    if "@関数内ローカル変数" in text:
        return False, "local-variable"
    if path in EXPLICIT_TEXT_FILES:
        return True, "explicit-ui-file"
    if path.startswith("Config/"):
        return True, "config-japanese-candidate"
    return False, "out-of-scope"


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return 0, 0
    return struct.unpack(">II", data[16:24])


def image_category(name: str) -> str:
    low = name.lower()
    if "title" in low or "caution" in low:
        return "title"
    if "config" in low or "tabbar" in low or "quickconfig" in low:
        return "settings"
    if "save" in low or "load" in low:
        return "save-load"
    if "extra" in low or "replay" in low or "cgthumbnail" in low or "bgmtitle" in low:
        return "extra"
    if "menu" in low or "help" in low or "button" in low or "bar" in low:
        return "system-controls"
    return "other-ui"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ns_extract", type=Path)
    ap.add_argument("romfs", type=Path)
    ap.add_argument("--text-output", type=Path, required=True)
    ap.add_argument("--image-output", type=Path, required=True)
    args = ap.parse_args()

    text_rows: list[dict[str, str]] = []
    with args.ns_extract.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            keep, reason = looks_candidate(row["file"], row["text"])
            if not keep:
                continue
            text_rows.append(
                {
                    "category": category_for_text(row["file"]),
                    "file": row["file"],
                    "length_offset": row["length_offset"],
                    "stored_length": row["stored_length"],
                    "source": row["text"],
                    "translation": "",
                    "visibility": "needs-review",
                    "status": "todo",
                    "reason": reason,
                    "notes": "",
                }
            )

    args.text_output.parent.mkdir(parents=True, exist_ok=True)
    with args.text_output.open("w", encoding="utf-8-sig", newline="") as f:
        fields = [
            "category",
            "file",
            "length_offset",
            "stored_length",
            "source",
            "translation",
            "visibility",
            "status",
            "reason",
            "notes",
        ]
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(text_rows)

    image_rows: list[dict[str, str | int]] = []
    system = args.romfs / "System"
    for path in sorted(system.glob("*.png")):
        low = path.name.lower()
        if not any(pattern in low for pattern in IMAGE_PATTERNS):
            continue
        width, height = png_dimensions(path)
        image_rows.append(
            {
                "category": image_category(path.name),
                "file": path.relative_to(args.romfs).as_posix(),
                "width": width,
                "height": height,
                "bytes": path.stat().st_size,
                "contains_japanese": "needs-visual-review",
                "status": "todo",
                "pc_reference": "",
                "notes": "",
            }
        )

    args.image_output.parent.mkdir(parents=True, exist_ok=True)
    with args.image_output.open("w", encoding="utf-8-sig", newline="") as f:
        fields = [
            "category",
            "file",
            "width",
            "height",
            "bytes",
            "contains_japanese",
            "status",
            "pc_reference",
            "notes",
        ]
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(image_rows)

    print(f"ui_text_candidates={len(text_rows)}")
    print(f"ui_image_candidates={len(image_rows)}")
    print(f"text_output={args.text_output.resolve()}")
    print(f"image_output={args.image_output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
