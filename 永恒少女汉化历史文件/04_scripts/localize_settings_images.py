from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTCollection, TTFont
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ROMFS = ROOT / "02_romfs" / "merged-v1.0.3" / "System"
UI = ROOT / "03_text" / "ui"
OUT = UI / "rendered-v017-settings-polish"

FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path(r"C:\Windows\Fonts\simsun.ttc"),
]

# Logical row -> actual y range. These were measured from the Switch v1.0.3
# baked UI layer. Separator-rule bands are deliberately excluded.
ROW_BANDS: dict[int, dict[int, tuple[int, int]]] = {
    1: {
        1: (220, 262), 2: (310, 340), 3: (378, 412), 4: (448, 482),
        5: (520, 553), 6: (608, 652), 7: (706, 740), 8: (776, 808),
        9: (846, 878), 10: (920, 951),
    },
    2: {
        1: (220, 262), 2: (308, 347), 3: (384, 422), 4: (490, 531),
        5: (578, 617), 6: (654, 692), 7: (759, 802), 8: (849, 887),
        9: (924, 982), 10: (924, 982),
    },
    3: {
        1: (220, 262), 2: (310, 345), 3: (384, 420), 4: (458, 497),
        5: (534, 572), 6: (608, 647), 7: (684, 721), 8: (764, 799),
        9: (849, 887), 10: (923, 962),
    },
    4: {
        1: (220, 262), 2: (308, 346), 3: (377, 427), 4: (609, 648),
        5: (680, 722), 6: (769, 807), 7: (843, 882), 8: (919, 956),
    },
    5: {
        1: (220, 262), 2: (335, 374), 3: (413, 452), 4: (492, 531),
        5: (570, 609), 6: (649, 688), 7: (727, 766), 8: (806, 845),
        9: (882, 921), 10: (961, 1000),
    },
    6: {
        1: (220, 262), 2: (317, 351), 3: (395, 427), 4: (468, 499),
        5: (542, 578), 6: (617, 652), 7: (821, 860), 8: (894, 933),
    },
    7: {
        1: (220, 260), 2: (306, 345), 3: (375, 414), 4: (444, 483),
    },
}

PAGE_TITLE_BAND = (120, 180)


def white_mask(arr: np.ndarray) -> np.ndarray:
    return (
        (arr[:, :, 0] > 248)
        & (arr[:, :, 1] > 248)
        & (arr[:, :, 2] > 248)
        & (arr[:, :, 3] > 12)
    )


def x_runs(arr: np.ndarray, y0: int, y1: int, gap: int = 18) -> list[tuple[int, int, int]]:
    q = arr[y0:y1]
    mask = white_mask(q)
    occupied = mask.any(axis=0)
    spans: list[list[int]] = []
    start = None
    for x, on in enumerate(list(occupied) + [False]):
        if on and start is None:
            start = x
        elif not on and start is not None:
            spans.append([start, x - 1])
            start = None

    groups: list[list[int]] = []
    for x0, x1 in spans:
        if not groups or x0 - groups[-1][1] > gap:
            groups.append([x0, x1])
        else:
            groups[-1][1] = x1

    out: list[tuple[int, int, int]] = []
    for x0, x1 in groups:
        pixels = int(mask[:, x0 : x1 + 1].sum())
        if pixels >= 20:
            out.append((x0, x1, pixels))
    return out


def pick_run(runs: list[tuple[int, int, int]], column: str) -> tuple[int, int, int]:
    if not runs:
        raise RuntimeError("no white-text run found")
    if column == "left":
        candidates = [r for r in runs if r[0] < 950]
        if candidates:
            return candidates[0]
    elif column == "right":
        candidates = [r for r in runs if r[0] >= 950]
        if candidates:
            return candidates[0]
    elif column == "center":
        # 'center' in the source table means centered inside its local block, not
        # necessarily centered on the 1920px canvas. Prefer the run whose center
        # is closest to the screen center, but keep a single obvious run as-is.
        if len(runs) == 1:
            return runs[0]
        return min(runs, key=lambda r: abs(((r[0] + r[1]) / 2) - 960))
    return runs[0]


def run_bbox(arr: np.ndarray, run: tuple[int, int, int], y0: int, y1: int) -> tuple[int, int, int, int]:
    x0, x1, _ = run
    q = arr[y0:y1, x0 : x1 + 1]
    mask = white_mask(q)
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return x0, y0, x1, y1 - 1
    return x0 + int(xs.min()), y0 + int(ys.min()), x0 + int(xs.max()), y0 + int(ys.max())


def erase_white_pixels(arr: np.ndarray, bbox: tuple[int, int, int, int], pad: int = 2) -> None:
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(arr.shape[1] - 1, x1 + pad)
    y1 = min(arr.shape[0] - 1, y1 + pad)
    q = arr[y0 : y1 + 1, x0 : x1 + 1]
    mask = white_mask(q)
    q[mask, 3] = 0


def inpaint_rect_from_edges(arr: np.ndarray, bbox: tuple[int, int, int, int], pad: int = 2) -> tuple[int, int, int, int]:
    """Rebuild an opaque button background under baked white text.

    The config button sprites use a mostly horizontal/vertical smooth fill.  For
    each scanline we interpolate between untouched pixels immediately left and
    right of the text bbox.  This is much safer than making white glyph pixels
    transparent on an otherwise opaque sprite.
    """
    x0, y0, x1, y1 = bbox
    x0 = max(1, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(arr.shape[1] - 2, x1 + pad)
    y1 = min(arr.shape[0] - 1, y1 + pad)
    width = x1 - x0 + 1
    if width <= 0:
        return x0, y0, x1, y1
    for y in range(y0, y1 + 1):
        left = arr[y, x0 - 1].astype(np.float32)
        right = arr[y, x1 + 1].astype(np.float32)
        t = np.linspace(0.0, 1.0, width, dtype=np.float32)[:, None]
        arr[y, x0 : x1 + 1] = np.rint(left * (1.0 - t) + right * t).astype(np.uint8)
    return x0, y0, x1, y1


def load_font(size: int) -> ImageFont.FreeTypeFont:
    last_error = None
    for path in FONT_CANDIDATES:
        if not path.exists():
            continue
        try:
            return ImageFont.truetype(str(path), size=size, index=0)
        except Exception as exc:  # pragma: no cover - fallback only
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError("No complete Windows Chinese font found for baked UI rendering")


def selected_font_path() -> Path:
    for path in FONT_CANDIDATES:
        if path.exists():
            return path
    raise RuntimeError("No Windows Chinese font candidate exists")


def font_unicode_cmap(path: Path, index: int = 0) -> set[int]:
    if path.suffix.lower() == ".ttc":
        collection = TTCollection(str(path))
        font = collection.fonts[index]
    else:
        font = TTFont(str(path))
    cmap: set[int] = set()
    for table in font["cmap"].tables:
        if table.isUnicode():
            cmap.update(table.cmap.keys())
    return cmap


def verify_target_font_coverage() -> tuple[Path, int]:
    chars: set[str] = set()
    with (UI / "configmenu-identification-v1.tsv").open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            chars.update(ch for ch in row["zh_target"] if ord(ch) > 127)
    with (UI / "configmenubutton-identification-v1.tsv").open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            chars.update(ch for ch in row["zh_states"] if ord(ch) > 127)

    path = selected_font_path()
    cmap = font_unicode_cmap(path, index=0)
    missing = sorted(ch for ch in chars if ord(ch) not in cmap)
    if missing:
        codes = " ".join(f"U+{ord(ch):04X}" for ch in missing)
        raise RuntimeError(f"Selected image font is missing {len(missing)} target glyphs: {codes}")
    return path, len(chars)


def draw_fixed_on_bbox(
    img: Image.Image,
    text: str,
    bbox: tuple[int, int, int, int],
    size: int,
    align: str = "center",
    anchor_x: float | None = None,
    fill: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> None:
    """Draw with an explicit visual hierarchy instead of per-label auto fitting.

    The old v006a renderer resized every Chinese label against the width of the
    Japanese source glyphs.  That made short labels much larger than long labels
    and also shifted left/right-column starts because everything was re-centered
    on a source bbox of different width.  The Switch source UI itself uses a
    small set of stable type sizes, so keep those sizes stable and only reuse the
    source bbox as the vertical/column anchor.
    """
    x0, y0, x1, y1 = bbox
    font = load_font(size)
    draw = ImageDraw.Draw(img)
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    cy = (y0 + y1) / 2
    if align == "left":
        left = x0 if anchor_x is None else anchor_x
        x = round(left - tb[0])
    elif align == "right":
        right = x1 if anchor_x is None else anchor_x
        x = round(right - tw - tb[0])
    else:
        cx = (x0 + x1) / 2 if anchor_x is None else anchor_x
        x = round(cx - tw / 2 - tb[0])
    y = round(cy - th / 2 - tb[1])
    draw.text((x, y), text, font=font, fill=fill)


BODY_X_ANCHORS: dict[tuple[int, str], int] = {
    (1, "left"): 86,
    (1, "right"): 1079,
    (2, "left"): 87,
    (2, "right"): 972,
    (3, "left"): 87,
    (3, "right"): 1007,
    (4, "left"): 87,
    (4, "right"): 1007,
    (4, "center"): 516,
    (5, "center"): 376,
    (6, "left"): 258,
    (6, "center"): 345,
    (7, "center"): 247,
}


def menu_text_style(row: dict[str, str]) -> tuple[int, str, float | None]:
    """Return fixed size, alignment and x anchor for a menu label."""
    page = int(row["page"])
    logical_row = int(row["row"])
    column = row["column"].strip()
    jp = row["jp_identified"].strip()
    section = row["section"].strip()

    if section == "page-title":
        return 58, "center", 960

    # Group headings are the rows whose displayed Japanese label is also the
    # section name (表示 / 機能 / オートセーブ / メニュー / ...).  They are
    # visually left-aligned even when the identification table calls the local
    # source run "center".
    if section == jp:
        return 34, "left", 104

    if section == "note":
        return 28, "center", None

    # Page 1's sample-area heading is the same typographic level as the left
    # group heading even though it is a separate label.
    if page == 1 and logical_row == 1:
        return 34, "left", BODY_X_ANCHORS[(1, column)]

    # Page 1 uses the compact ADV settings typography; the other settings pages
    # use the regular body size.  These sizes reproduce the measured source text
    # heights (~24-25 px and ~30-32 px respectively) with Microsoft YaHei.
    size = 26 if page == 1 and logical_row >= 2 else 30
    anchor = BODY_X_ANCHORS.get((page, column))
    # The source UI's paragraph-style rows are left aligned inside their local
    # region even when the identification table says "center" (the latter only
    # means there is no left/right split).  Reuse the measured region start.
    if anchor is not None:
        return size, "left", anchor
    return size, "left", None


def load_menu_rows() -> list[dict[str, str]]:
    with (UI / "configmenu-identification-v1.tsv").open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def localize_menu_pages() -> list[Path]:
    rows = load_menu_rows()
    by_page: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        by_page.setdefault(int(row["page"]), []).append(row)

    OUT.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for page in range(1, 8):
        src = ROMFS / f"configmenu_{page:04d}.png"
        image = Image.open(src).convert("RGBA")
        arr = np.array(image)

        for row in by_page.get(page, []):
            text = row["zh_target"].strip()
            if not text or text == row["jp_identified"].strip():
                continue
            logical_row = int(row["row"])
            column = row["column"].strip()

            if row["section"] == "page-title":
                y0, y1 = PAGE_TITLE_BAND
                runs = x_runs(arr, y0, y1)
                # Page titles are the central white run(s). Merge adjacent title
                # fragments such as メッセージ + digit into one logical bbox.
                central = [r for r in runs if 700 <= r[0] <= 1200 or 700 <= r[1] <= 1200]
                if not central:
                    central = runs
                x0 = min(r[0] for r in central)
                x1 = max(r[1] for r in central)
                fake = (x0, x1, sum(r[2] for r in central))
                bbox = run_bbox(arr, fake, y0, y1)
                erase_white_pixels(arr, bbox, pad=3)
                image = Image.fromarray(arr, "RGBA")
                size, align, anchor_x = menu_text_style(row)
                draw_fixed_on_bbox(image, text, bbox, size=size, align=align, anchor_x=anchor_x)
                arr = np.array(image)
                continue

            band = ROW_BANDS.get(page, {}).get(logical_row)
            if not band:
                raise RuntimeError(f"missing row band for page={page}, row={logical_row}, text={text}")
            y0, y1 = band
            runs = x_runs(arr, y0, y1)

            # Page 2 row 9 contains the left row-9 label and the centered row-10
            # explanatory note in the same y band. The column rule separates them.
            run = pick_run(runs, column)
            bbox = run_bbox(arr, run, y0, y1)
            erase_white_pixels(arr, bbox, pad=2)
            image = Image.fromarray(arr, "RGBA")
            size, align, anchor_x = menu_text_style(row)
            draw_fixed_on_bbox(image, text, bbox, size=size, align=align, anchor_x=anchor_x)
            arr = np.array(image)

        dst = OUT / src.name
        Image.fromarray(arr, "RGBA").save(dst, optimize=True)
        written.append(dst)
    return written


def parse_state_count(layout: str) -> int:
    # e.g. "4 vertical states"
    return int(layout.split()[0])


def localize_button_sprites() -> list[Path]:
    table = UI / "configmenubutton-identification-v1.tsv"
    with table.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    OUT.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for row in rows:
        if row["confidence"] == "unresolved":
            continue
        jp_states = [s.strip() for s in row["jp_states"].split("/")]
        zh_states = [s.strip() for s in row["zh_states"].split("/")]
        if not jp_states or not zh_states or jp_states == zh_states:
            continue
        count = parse_state_count(row["state_layout"])
        src = ROMFS / Path(row["file"]).name
        image = Image.open(src).convert("RGBA")
        arr = np.array(image)
        h, w = arr.shape[:2]
        if h % count != 0:
            raise RuntimeError(f"sprite height not divisible by state count: {src}")
        state_h = h // count

        if src.name == "configmenubutton_0008.png":
            # Brown/red alternate button family.  Comparing states 0↔2 and 1↔3
            # shows that all label changes are confined to x≈52..198, y≈8..35
            # inside each 43px state.  Rebuild that local background and render
            # with the source family's own normal/selected text colors.
            if state_h != 43 or count != 4:
                raise RuntimeError(f"unexpected 0008 geometry: {src} {w}x{h}/{count}")
            colors = [
                (61, 40, 22, 255),
                (168, 78, 50, 255),
                (61, 40, 22, 255),
                (168, 78, 50, 255),
            ]
            for idx in range(count):
                bbox = (50, idx * state_h + 6, 200, idx * state_h + 37)
                bbox = inpaint_rect_from_edges(arr, bbox, pad=0)
                image = Image.fromarray(arr, "RGBA")
                target = zh_states[min(idx, len(zh_states) - 1)]
                draw_fixed_on_bbox(image, target, bbox, size=22, align="center", fill=colors[idx])
                arr = np.array(image)
            dst = OUT / src.name
            Image.fromarray(arr, "RGBA").save(dst, optimize=True)
            written.append(dst)
            continue

        localized_any = False
        for idx in range(count):
            y0, y1 = idx * state_h, (idx + 1) * state_h
            runs = x_runs(arr, y0, y1, gap=12)
            # Sprite text is the widest meaningful white run in each state; tiny
            # arrow/highlight fragments are ignored.
            candidates = [r for r in runs if r[1] - r[0] >= 12]
            if not candidates:
                # 0008 is a separate brown/red sprite family whose baked labels
                # are not white.  Keep the original untouched until it gets a
                # dedicated color-aware rule instead of risking background damage.
                localized_any = False
                break
            run = max(candidates, key=lambda r: (r[1] - r[0], r[2]))
            bbox = run_bbox(arr, run, y0, y1)
            bbox = inpaint_rect_from_edges(arr, bbox, pad=2)
            image = Image.fromarray(arr, "RGBA")
            target = zh_states[min(idx, len(zh_states) - 1)]
            draw_fixed_on_bbox(image, target, bbox, size=28, align="center")
            arr = np.array(image)
            localized_any = True

        if localized_any:
            dst = OUT / src.name
            Image.fromarray(arr, "RGBA").save(dst, optimize=True)
            written.append(dst)
        else:
            stale = OUT / src.name
            if stale.exists():
                stale.unlink()
    return written


def main() -> None:
    font_path, target_chars = verify_target_font_coverage()
    print(f"image_font={font_path}")
    print(f"target_nonascii_chars={target_chars}")
    print("font_missing=0")
    menu = localize_menu_pages()
    buttons = localize_button_sprites()
    print(f"menu_pages={len(menu)}")
    print(f"button_sprites={len(buttons)}")
    for p in menu + buttons:
        print(p.relative_to(ROOT))


if __name__ == "__main__":
    main()
