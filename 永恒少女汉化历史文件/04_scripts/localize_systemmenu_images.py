from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np
from fontTools.ttLib import TTCollection
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / "02_romfs" / "merged-v1.0.3" / "System"
UI = ROOT / "03_text" / "ui"
OUT = UI / "rendered-v008-systemmenu"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")

FILES = ["systemmenu.png", "systemmenu_a.png"]

# The two paired atlases use the same six logical rows but slightly different
# vertical glyph baselines/state art. Search each row independently rather than
# copying coordinates from one image to the other.
ROW_WINDOWS = [
    (145, 220),
    (245, 320),
    (340, 420),
    (440, 520),
    (540, 620),
    (640, 710),
]

# All functional menu text lives in the left 315px sprite strip. The large
# right-side panel in systemmenu.png must never be touched.
TEXT_X0 = 0
TEXT_X1 = 315


def load_targets() -> list[str]:
    with (UI / "systemmenu-identification-v1.tsv").open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    if len(rows) != 6:
        raise RuntimeError(f"expected 6 system menu rows, got {len(rows)}")
    return [row["zh_target"] for row in rows]


def verify_font(targets: list[str]) -> None:
    if not FONT.exists():
        raise RuntimeError(f"missing baked-image font: {FONT}")
    coll = TTCollection(str(FONT))
    cmap: set[int] = set()
    for table in coll.fonts[0]["cmap"].tables:
        if table.isUnicode():
            cmap.update(table.cmap)
    chars = {ch for text in targets for ch in text if ord(ch) > 127}
    missing = sorted(ch for ch in chars if ord(ch) not in cmap)
    if missing:
        raise RuntimeError(f"system menu image font missing: {''.join(missing)}")
    print(f"systemmenu_target_chars={len(chars)} font_missing=0")


def white_mask(arr: np.ndarray, y0: int, y1: int) -> np.ndarray:
    q = arr[y0:y1, TEXT_X0:TEXT_X1]
    rgb = q[:, :, :3]
    alpha = q[:, :, 3]
    local = (
        (rgb[:, :, 0] > 225)
        & (rgb[:, :, 1] > 225)
        & (rgb[:, :, 2] > 225)
        & (alpha > 18)
    ).astype(np.uint8) * 255
    # Grow only enough to include antialiasing fringe; row windows isolate each
    # label from unrelated UI art.
    return cv2.dilate(local, np.ones((3, 3), np.uint8), iterations=1)


def mask_bbox(mask: np.ndarray, y0: int) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        raise RuntimeError(f"no system menu text found in row window starting {y0}")
    return int(xs.min()), int(ys.min() + y0), int(xs.max()), int(ys.max() + y0)


def inpaint_label(arr: np.ndarray, mask: np.ndarray, y0: int, y1: int) -> None:
    crop = arr[y0:y1, TEXT_X0:TEXT_X1]
    alpha = crop[:, :, 3].copy()
    bgr = cv2.cvtColor(crop[:, :, :3], cv2.COLOR_RGB2BGR)
    fixed = cv2.inpaint(bgr, mask, 3, cv2.INPAINT_TELEA)
    crop[:, :, :3] = cv2.cvtColor(fixed, cv2.COLOR_BGR2RGB)
    crop[:, :, 3] = alpha


def clear_alpha_label(arr: np.ndarray, y0: int, y1: int) -> None:
    """Clear one text row in the transparent alternate-state atlas.

    systemmenu_a.png contains no panel artwork inside the six row windows: its
    non-zero alpha there is the Japanese label itself (plus its antialiasing).
    Clearing the whole 315px row window therefore removes the old glyph shape
    completely and lets Pillow write a fresh Chinese alpha mask.
    """
    arr[y0:y1, TEXT_X0:TEXT_X1, 3] = 0


def fit_font(text: str, max_w: int = 230, max_h: int = 42) -> ImageFont.FreeTypeFont:
    for size in range(39, 21, -1):
        font = ImageFont.truetype(str(FONT), size=size, index=0)
        box = font.getbbox(text)
        if box[2] - box[0] <= max_w and box[3] - box[1] <= max_h:
            return font
    return ImageFont.truetype(str(FONT), size=22, index=0)


def draw_centered(arr: np.ndarray, text: str, bbox: tuple[int, int, int, int]) -> None:
    image = Image.fromarray(arr, "RGBA")
    draw = ImageDraw.Draw(image)
    font = fit_font(text)
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    # Original six labels all center around x≈158. Preserve each row's measured
    # vertical center while using a unified horizontal center and font fitting.
    cy = (bbox[1] + bbox[3]) / 2
    cx = 158
    x = round(cx - tw / 2 - tb[0])
    y = round(cy - th / 2 - tb[1])
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    arr[:] = np.array(image)


def process(name: str, targets: list[str]) -> Path:
    src = SYSTEM / name
    arr = np.array(Image.open(src).convert("RGBA"))
    original_alpha = arr[:, :, 3].copy()
    bboxes: list[tuple[int, int, int, int]] = []

    for text, (y0, y1) in zip(targets, ROW_WINDOWS):
        mask = white_mask(arr, y0, y1)
        bbox = mask_bbox(mask, y0)
        bboxes.append(bbox)
        if name == "systemmenu_a.png":
            clear_alpha_label(arr, y0, y1)
        else:
            inpaint_label(arr, mask, y0, y1)
        draw_centered(arr, text, bbox)

    # The opaque/base atlas keeps its alpha byte-for-byte. The transparent
    # alternate atlas must change alpha inside the six label windows because
    # the alpha channel is the glyph silhouette itself.
    if name != "systemmenu_a.png":
        arr[:, :, 3] = original_alpha
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / name
    Image.fromarray(arr, "RGBA").save(dst, optimize=True)
    print(name, "bboxes=", bboxes)
    return dst


def main() -> None:
    targets = load_targets()
    verify_font(targets)
    written = [process(name, targets) for name in FILES]
    print(f"systemmenu_png={len(written)}")


if __name__ == "__main__":
    main()
