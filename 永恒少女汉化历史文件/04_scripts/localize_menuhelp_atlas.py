#!/usr/bin/env python3
"""Localize the final MenuHelp prompt atlases.

menuhelp.png and menuhelp_a.png contain the same 21 action labels at two UI
scales, plus controller/button icons.  The icon pixels are deliberately kept
byte-identical; only the transparent text rectangles to their right are cleared
and redrawn in Simplified Chinese.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from fontTools.ttLib import TTCollection
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / "02_romfs" / "merged-v1.0.3" / "System"
OUT = ROOT / "03_text" / "ui" / "rendered-v019-menuhelp"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")

# Rows/columns recovered from alpha projection and individually OCR-verified on
# both atlases.  Japanese source labels are included here as an audit trail.
LABELS = [
    [("決定", "确定"), ("クイックジャンプ", "快速跳转"), ("デフォルトへ戻す", "恢复默认")],
    [("閉じる", "关闭"), ("ボイス再生", "播放语音"), ("全てデフォルトへ戻す", "全部恢复默认")],
    [("データ保護", "数据保护"), ("１画面戻る", "上一页"), ("次へ進む", "下一步")],
    [("データ保護解除", "解除数据保护"), ("１画面進む", "下一页"), ("前へ戻る", "返回")],
    [("編集", "编辑"), ("戦闘", "战斗"), ("キャラクタ切り替え", "切换角色")],
    [("移動", "移动"), ("末尾", "末尾"), ("モード切り替え", "切换模式")],
    [("削除", "删除"), ("高速のスクロール", "高速滚动"), ("フォーカス移動", "移动焦点")],
]

# Full-resolution text-only rectangles.  Repeated button/icon markers at
# x~35/321/608 stay outside these bounds and are therefore untouched.
ROW_RECTS = [(185, 222), (245, 282), (304, 342), (364, 403), (425, 463), (485, 524), (546, 594)]
# Keep the boundary columns immediately before the 2nd/3rd icon groups out of
# the clear rectangles.  Those columns belong to the repeated controller/icon
# markers (x=286 and x=573 at full resolution), so touching them trips the
# byte-identical icon safety gate, especially after scaling menuhelp_a.png.
COL_RECTS = [(45, 285), (335, 572), (625, 949)]


def target_chars() -> set[str]:
    return {ch for row in LABELS for _jp, zh in row for ch in zh if ord(ch) > 127}


def verify_font() -> int:
    coll = TTCollection(str(FONT))
    cmap: set[int] = set()
    for table in coll.fonts[0]["cmap"].tables:
        if table.isUnicode():
            cmap.update(table.cmap)
    chars = target_chars()
    missing = sorted(ch for ch in chars if ord(ch) not in cmap)
    if missing:
        raise RuntimeError("menuhelp font missing: " + " ".join(f"U+{ord(ch):04X}" for ch in missing))
    return len(chars)


def scaled_rect(rect: tuple[int, int, int, int], sx: float, sy: float) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = rect
    return round(x0 * sx), round(y0 * sy), round(x1 * sx), round(y1 * sy)


def fit_font(text: str, max_w: int, max_h: int, preferred: int) -> ImageFont.FreeTypeFont:
    for size in range(preferred, 10, -1):
        f = ImageFont.truetype(str(FONT), size=size, index=0)
        b = f.getbbox(text)
        if b[2] - b[0] <= max_w and b[3] - b[1] <= max_h:
            return f
    raise RuntimeError(f"cannot fit menuhelp label: {text}")


def process(name: str) -> Path:
    src = Image.open(SYSTEM / name).convert("RGBA")
    arr = np.array(src)
    full_w, full_h = 950, 633
    sx, sy = src.width / full_w, src.height / full_h
    preferred = 25 if name == "menuhelp.png" else 19

    im = Image.fromarray(arr, "RGBA")
    draw = ImageDraw.Draw(im)
    for ri, (y0, y1) in enumerate(ROW_RECTS):
        for ci, (x0, x1) in enumerate(COL_RECTS):
            rect = scaled_rect((x0, y0, x1, y1), sx, sy)
            rx0, ry0, rx1, ry1 = rect
            # Text lives on transparent atlas space.  Clearing the rectangle is
            # safer than trying to inpaint anti-aliased Japanese glyphs.
            draw.rectangle((rx0, ry0, rx1, ry1), fill=(0, 0, 0, 0))
            text = LABELS[ri][ci][1]
            f = fit_font(text, rx1 - rx0 - 8, ry1 - ry0 - 4, preferred)
            tb = draw.textbbox((0, 0), text, font=f)
            th = tb[3] - tb[1]
            tx = rx0 + 4 - tb[0]
            ty = round((ry0 + ry1) / 2 - th / 2 - tb[1])
            draw.text((tx, ty), text, font=f, fill=(255, 255, 255, 255))

    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / name
    im.save(dst, optimize=True)
    return dst


def main() -> int:
    chars = verify_font()
    for name in ("menuhelp.png", "menuhelp_a.png"):
        dst = process(name)
        print(f"{dst.relative_to(ROOT)}\t{dst.stat().st_size}")
    print(f"menuhelp_target_nonascii={chars}")
    print("menuhelp_labels=21")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

