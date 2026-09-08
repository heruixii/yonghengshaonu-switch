#!/usr/bin/env python3
"""Localize remaining baked settings/Extra tab and action button labels.

Four atlases contain confirmed functional Japanese text:

* tabbarbutton_0001.png: ADV / 系统 / 显示 / 消息1 / 消息2 / 声音 / 语音
* tabbarbutton_0002.png: 恢复默认设置 / 全部恢复默认
* tabbarbutton_0005.png: 移动 / 删除 / 编辑
* extramodebarbutton.png: CG / 音乐 / 场景

The original alpha channel is preserved byte-for-byte.  Source glyph rectangles
are rebuilt from untouched pixels at each scanline's left/right edges before the
Chinese text is drawn, so button/state geometry is not changed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from fontTools.ttLib import TTCollection
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / "02_romfs" / "merged-v1.0.3" / "System"
OUT = ROOT / "03_text" / "ui" / "rendered-v018-tabbar"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")


SPECS = {
    "tabbarbutton_0001.png": {
        "state_h": 58,
        "font_size": 28,
        "targets": [
            None, None,          # ADV: deliberately unchanged
            "系统", "系统",
            "显示", "显示",
            "消息1", "消息1",
            "消息2", "消息2",
            "声音", "声音",
            "语音", "语音",
        ],
    },
    "tabbarbutton_0002.png": {
        "state_h": 58,
        "font_size": 24,
        "targets": [
            "恢复默认设置", "恢复默认设置",
            "全部恢复默认", "全部恢复默认",
        ],
    },
    "tabbarbutton_0005.png": {
        "state_h": 47,
        "font_size": 26,
        "targets": [
            "移动", "移动",
            "删除", "删除",
            "编辑", "编辑",
        ],
    },
    "extramodebarbutton.png": {
        "state_h": 58,
        "font_size": 28,
        "targets": [
            None, None,          # CG: established Latin label, unchanged
            "音乐", "音乐",
            "场景", "场景",
        ],
    },
}


def unicode_cmap() -> set[int]:
    coll = TTCollection(str(FONT))
    out: set[int] = set()
    for table in coll.fonts[0]["cmap"].tables:
        if table.isUnicode():
            out.update(table.cmap.keys())
    return out


def verify_font() -> int:
    chars = {ch for spec in SPECS.values() for text in spec["targets"] if text for ch in text if ord(ch) > 127}
    cmap = unicode_cmap()
    missing = sorted(ch for ch in chars if ord(ch) not in cmap)
    if missing:
        raise RuntimeError("tabbar image font missing: " + " ".join(f"U+{ord(ch):04X}" for ch in missing))
    return len(chars)


def white_mask(q: np.ndarray) -> np.ndarray:
    return (
        (q[:, :, 3] > 16)
        & (q[:, :, 0] > 160)
        & (q[:, :, 1] > 160)
        & (q[:, :, 2] > 160)
    )


def text_bbox(arr: np.ndarray, y0: int, y1: int) -> tuple[int, int, int, int]:
    q = arr[y0:y1]
    mask = white_mask(q)
    ys, xs = np.where(mask)
    if not len(xs):
        raise RuntimeError(f"no tabbar text pixels at y={y0}:{y1}")
    return int(xs.min()), y0 + int(ys.min()), int(xs.max()), y0 + int(ys.max())


def inpaint_rgb(arr: np.ndarray, bbox: tuple[int, int, int, int], pad: int = 2) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    x0 = max(1, x0 - pad)
    x1 = min(arr.shape[1] - 2, x1 + pad)
    y0 = max(0, y0 - pad)
    y1 = min(arr.shape[0] - 1, y1 + pad)
    width = x1 - x0 + 1
    for y in range(y0, y1 + 1):
        left = arr[y, x0 - 1, :3].astype(np.float32)
        right = arr[y, x1 + 1, :3].astype(np.float32)
        t = np.linspace(0.0, 1.0, width, dtype=np.float32)[:, None]
        arr[y, x0 : x1 + 1, :3] = np.rint(left * (1.0 - t) + right * t).astype(np.uint8)
    return x0, y0, x1, y1


def draw_centered(arr: np.ndarray, text: str, bbox: tuple[int, int, int, int], size: int) -> None:
    alpha = arr[:, :, 3].copy()
    image = Image.fromarray(arr, "RGBA")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(FONT), size=size, index=0)
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    _x0, y0, _x1, y1 = bbox
    cx = arr.shape[1] / 2
    cy = (y0 + y1) / 2
    x = round(cx - tw / 2 - tb[0])
    y = round(cy - th / 2 - tb[1])
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    arr[:] = np.array(image)
    arr[:, :, 3] = alpha


def process(name: str, spec: dict) -> Path:
    src = SYSTEM / name
    arr = np.array(Image.open(src).convert("RGBA"))
    state_h = int(spec["state_h"])
    targets = list(spec["targets"])
    size = int(spec["font_size"])
    if arr.shape[0] != state_h * len(targets):
        raise RuntimeError(f"unexpected tabbar geometry: {name} {arr.shape[1]}x{arr.shape[0]} / {state_h}")

    for idx, target in enumerate(targets):
        if not target:
            continue
        y0, y1 = idx * state_h, (idx + 1) * state_h
        bbox = text_bbox(arr, y0, y1)
        rebuilt = inpaint_rgb(arr, bbox, pad=2)
        draw_centered(arr, target, rebuilt, size)

    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / name
    Image.fromarray(arr, "RGBA").save(dst, optimize=True)
    return dst


def main() -> int:
    chars = verify_font()
    written = [process(name, spec) for name, spec in SPECS.items()]
    print(f"font={FONT}")
    print(f"target_nonascii_chars={chars}")
    print(f"tabbar_png={len(written)}")
    for path in written:
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
