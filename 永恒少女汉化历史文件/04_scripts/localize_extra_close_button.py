#!/usr/bin/env python3
"""Localize System/extrabutton.png: 閉じる -> 关闭.

The sprite has a bright decorative frame/icon on the left and a small dark text
label on the right.  The Japanese label is isolated to x~93..144/y~15..28.
Only that RGB rectangle is rebuilt from its untouched horizontal neighbours;
the original alpha channel and the left-hand decoration are preserved exactly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from fontTools.ttLib import TTCollection
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "02_romfs" / "merged-v1.0.3" / "System" / "extrabutton.png"
OUT = ROOT / "03_text" / "ui" / "rendered-v019-extra"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
TARGET = "关闭"

# Conservative bounds around the OCR/connected-component-confirmed label.
CLEAR = (88, 11, 150, 31)  # x0,y0,x1,y1 inclusive


def verify_font() -> None:
    coll = TTCollection(str(FONT))
    cmap: set[int] = set()
    for table in coll.fonts[0]["cmap"].tables:
        if table.isUnicode():
            cmap.update(table.cmap)
    missing = [ch for ch in TARGET if ord(ch) not in cmap]
    if missing:
        raise RuntimeError("extra close font missing: " + "".join(missing))


def main() -> int:
    verify_font()
    arr = np.array(Image.open(SOURCE).convert("RGBA"))
    if arr.shape != (38, 180, 4):
        raise RuntimeError(f"unexpected extrabutton geometry: {arr.shape}")
    alpha = arr[:, :, 3].copy()

    x0, y0, x1, y1 = CLEAR
    # Reconstruct each source-text scanline from untouched pixels just outside
    # the label rectangle.  This preserves the original pale button gradient.
    width = x1 - x0 + 1
    for y in range(y0, y1 + 1):
        left = arr[y, x0 - 1, :3].astype(np.float32)
        right = arr[y, x1 + 1, :3].astype(np.float32)
        t = np.linspace(0.0, 1.0, width, dtype=np.float32)[:, None]
        arr[y, x0 : x1 + 1, :3] = np.rint(left * (1.0 - t) + right * t).astype(np.uint8)

    im = Image.fromarray(arr, "RGBA")
    draw = ImageDraw.Draw(im)
    f = ImageFont.truetype(str(FONT), size=17, index=0)
    tb = draw.textbbox((0, 0), TARGET, font=f)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    tx = round(cx - tw / 2 - tb[0])
    ty = round(cy - th / 2 - tb[1])
    # Source label is a dark neutral gray over the bright interior.
    draw.text((tx, ty), TARGET, font=f, fill=(92, 92, 96, 255))

    out = np.array(im)
    out[:, :, 3] = alpha
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / SOURCE.name
    Image.fromarray(out, "RGBA").save(dst, optimize=True)
    print(dst.relative_to(ROOT))
    print(f"text_bbox={tx+tb[0]},{ty+tb[1]},{tx+tb[2]-1},{ty+tb[3]-1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

