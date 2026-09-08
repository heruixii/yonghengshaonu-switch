from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from fontTools.ttLib import TTCollection
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / "02_romfs" / "merged-v1.0.3" / "System"
OUT = ROOT / "03_text" / "ui" / "rendered-v007-title"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")

LABELS = {
    "title_btn0001.png": "从头开始",
    "title_btn0002.png": "继续",
    "title_btn0003.png": "环境设置",
    "title_btn0004.png": "鉴赏",
    "title_btn0005.png": "CG鉴赏",
    "title_btn0006.png": "场景鉴赏",
    "title_btn0007.png": "音乐鉴赏",
    "title_btn0008.png": "EX剧情",
    "title_btn0009.png": "返回标题",
    "title_btn0101.png": "从头开始",
    "title_btn0102.png": "继续",
    "title_btn0103.png": "环境设置",
    "title_btn0104.png": "鉴赏",
    "title_btn0105.png": "CG鉴赏",
    "title_btn0106.png": "场景鉴赏",
    "title_btn0107.png": "音乐鉴赏",
    "title_btn0108.png": "EX剧情",
    "title_btn0109.png": "返回标题",
    # Disabled/locked EX-scenario state.  Its glyphs are dark gray rather than
    # white, so the normal source-image text detector cannot see them directly.
    "title_btn0208.png": "EX剧情",
}

MASK_REFERENCE = {
    "title_btn0208.png": "title_btn0008.png",
}

TEXT_FILL = {
    "title_btn0208.png": (89, 89, 89, 255),
}

# title_btn0003 is a 672x672 atlas, but title_menu.spm uses only its top-left
# button-sized region. All localization work is constrained to this box.
BUTTON_BOX = (0, 0, 284, 84)
TEXT_SEARCH_BOX = (34, 14, 250, 66)


def verify_font() -> None:
    if not FONT.exists():
        raise RuntimeError(f"missing image font: {FONT}")
    coll = TTCollection(str(FONT))
    cmap: set[int] = set()
    for table in coll.fonts[0]["cmap"].tables:
        if table.isUnicode():
            cmap.update(table.cmap)
    chars = {ch for text in LABELS.values() for ch in text if ord(ch) > 127}
    missing = sorted(ch for ch in chars if ord(ch) not in cmap)
    if missing:
        raise RuntimeError(f"title image font missing: {''.join(missing)}")
    print(f"title_target_chars={len(chars)} font_missing=0")


def white_text_mask(crop: np.ndarray) -> np.ndarray:
    x0, y0, x1, y1 = TEXT_SEARCH_BOX
    rgb = crop[:, :, :3]
    alpha = crop[:, :, 3]
    mask = np.zeros(alpha.shape, dtype=np.uint8)
    local = (
        (rgb[y0:y1, x0:x1, 0] > 225)
        & (rgb[y0:y1, x0:x1, 1] > 225)
        & (rgb[y0:y1, x0:x1, 2] > 225)
        & (alpha[y0:y1, x0:x1] > 20)
    )
    mask[y0:y1, x0:x1][local] = 255
    # Include antialiased fringes while keeping the ornate border untouched.
    kernel = np.ones((3, 3), np.uint8)
    return cv2.dilate(mask, kernel, iterations=1)


def mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        raise RuntimeError("no title label pixels found")
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def clear_label(crop: np.ndarray, mask: np.ndarray) -> np.ndarray:
    # Inpaint only RGB beneath the label. Alpha is preserved byte-for-byte so
    # button geometry and transparent edge pixels cannot be damaged.
    bgr = cv2.cvtColor(crop[:, :, :3], cv2.COLOR_RGB2BGR)
    fixed = cv2.inpaint(bgr, mask, 3, cv2.INPAINT_TELEA)
    rgb = cv2.cvtColor(fixed, cv2.COLOR_BGR2RGB)
    out = crop.copy()
    out[:, :, :3] = rgb
    return out


def fit_font(text: str, max_w: int, max_h: int) -> ImageFont.FreeTypeFont:
    for size in range(35, 19, -1):
        font = ImageFont.truetype(str(FONT), size=size, index=0)
        box = font.getbbox(text)
        if box[2] - box[0] <= max_w and box[3] - box[1] <= max_h:
            return font
    return ImageFont.truetype(str(FONT), size=20, index=0)


def draw_label(
    crop: np.ndarray,
    text: str,
    old_bbox: tuple[int, int, int, int],
    fill: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> np.ndarray:
    image = Image.fromarray(crop, "RGBA")
    draw = ImageDraw.Draw(image)
    # Keep all four title items visually consistent rather than preserving the
    # varying Japanese glyph widths. The original bbox determines only the line
    # center and maximum height.
    x0, y0, x1, y1 = old_bbox
    max_w = 188
    max_h = max(26, (y1 - y0 + 1) + 4)
    font = fit_font(text, max_w, max_h)
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    cx = 142
    cy = (y0 + y1) / 2
    tx = round(cx - tw / 2 - tb[0])
    ty = round(cy - th / 2 - tb[1])
    draw.text((tx, ty), text, font=font, fill=fill)
    return np.array(image)


def process_one(name: str, text: str) -> Path:
    src = SYSTEM / name
    full = np.array(Image.open(src).convert("RGBA"))
    bx0, by0, bx1, by1 = BUTTON_BOX
    crop = full[by0:by1, bx0:bx1].copy()
    original_alpha = crop[:, :, 3].copy()
    ref_name = MASK_REFERENCE.get(name)
    if ref_name:
        ref_full = np.array(Image.open(SYSTEM / ref_name).convert("RGBA"))
        ref_crop = ref_full[by0:by1, bx0:bx1]
        mask = white_text_mask(ref_crop)
    else:
        mask = white_text_mask(crop)
    bbox = mask_bbox(mask)
    crop = clear_label(crop, mask)
    crop = draw_label(crop, text, bbox, fill=TEXT_FILL.get(name, (255, 255, 255, 255)))
    crop[:, :, 3] = original_alpha
    full[by0:by1, bx0:bx1] = crop

    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / name
    Image.fromarray(full, "RGBA").save(dst, optimize=True)
    print(f"{name}\t{text}\told_bbox={bbox}")
    return dst


def main() -> None:
    verify_font()
    written = [process_one(name, text) for name, text in LABELS.items()]
    print(f"title_png={len(written)}")


if __name__ == "__main__":
    main()
