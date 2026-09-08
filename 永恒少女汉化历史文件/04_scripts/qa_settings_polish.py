#!/usr/bin/env python3
"""Static geometry/pixel QA for the v017 settings typography polish."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import localize_settings_images as ui


ROOT = Path(__file__).resolve().parents[1]
OUT = ui.OUT
QA_OUT = ROOT / "03_text" / "ui" / "qa-settings-polish.tsv"


def rect_mask(shape: tuple[int, int], rects: list[tuple[int, int, int, int]]) -> np.ndarray:
    h, w = shape
    mask = np.zeros((h, w), dtype=bool)
    for x0, y0, x1, y1 in rects:
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(w - 1, x1)
        y1 = min(h - 1, y1)
        if x0 <= x1 and y0 <= y1:
            mask[y0 : y1 + 1, x0 : x1 + 1] = True
    return mask


def pad(rect: tuple[int, int, int, int], n: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = rect
    return x0 - n, y0 - n, x1 + n, y1 + n


def source_bbox(arr: np.ndarray, row: dict[str, str]) -> tuple[int, int, int, int]:
    page = int(row["page"])
    logical_row = int(row["row"])
    column = row["column"].strip()
    if row["section"] == "page-title":
        y0, y1 = ui.PAGE_TITLE_BAND
        runs = ui.x_runs(arr, y0, y1)
        central = [r for r in runs if 700 <= r[0] <= 1200 or 700 <= r[1] <= 1200] or runs
        fake = (
            min(r[0] for r in central),
            max(r[1] for r in central),
            sum(r[2] for r in central),
        )
        return ui.run_bbox(arr, fake, y0, y1)
    y0, y1 = ui.ROW_BANDS[page][logical_row]
    return ui.run_bbox(arr, ui.pick_run(ui.x_runs(arr, y0, y1), column), y0, y1)


def theoretical_text_bbox(
    text: str,
    source: tuple[int, int, int, int],
    size: int,
    align: str,
    anchor_x: float | None,
) -> tuple[int, int, int, int]:
    font = ui.load_font(size)
    draw = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    x0, y0, x1, y1 = source
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
    return x + tb[0], y + tb[1], x + tb[2] - 1, y + tb[3] - 1


def band_for(row: dict[str, str]) -> tuple[int, int]:
    if row["section"] == "page-title":
        return ui.PAGE_TITLE_BAND
    return ui.ROW_BANDS[int(row["page"])][int(row["row"])]


def verify_menu(errors: list[str], audit: list[list[str]]) -> None:
    rows = ui.load_menu_rows()
    by_page: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        if row["zh_target"].strip() and row["zh_target"].strip() != row["jp_identified"].strip():
            by_page.setdefault(int(row["page"]), []).append(row)

    for page in range(1, 8):
        src_path = ui.ROMFS / f"configmenu_{page:04d}.png"
        dst_path = OUT / src_path.name
        src = np.array(Image.open(src_path).convert("RGBA"))
        dst = np.array(Image.open(dst_path).convert("RGBA"))
        if src.shape != dst.shape:
            errors.append(f"menu_dim:{src_path.name}:{src.shape}:{dst.shape}")
            continue

        allowed_rects: list[tuple[int, int, int, int]] = []
        for row in by_page.get(page, []):
            sb = source_bbox(src, row)
            size, align, anchor_x = ui.menu_text_style(row)
            tb = theoretical_text_bbox(row["zh_target"].strip(), sb, size, align, anchor_x)
            y0, y1 = band_for(row)
            cy_source = (sb[1] + sb[3]) / 2
            cy_target = (tb[1] + tb[3]) / 2
            if tb[1] < y0 - 1 or tb[3] > y1 + 1:
                errors.append(f"menu_y_clip:p{page}:r{row['row']}:{row['column']}:{tb}:{y0}-{y1}")
            if abs(cy_source - cy_target) > 2.0:
                errors.append(f"menu_baseline:p{page}:r{row['row']}:{row['column']}:{cy_source}:{cy_target}")
            if tb[0] < 0 or tb[2] >= src.shape[1]:
                errors.append(f"menu_x_clip:p{page}:r{row['row']}:{row['column']}:{tb}")

            section = row["section"].strip()
            column = row["column"].strip()
            if section == "page-title":
                if not (700 <= tb[0] and tb[2] <= 1220):
                    errors.append(f"title_region:p{page}:{tb}")
                if abs(((tb[0] + tb[2]) / 2) - 960) > 2:
                    errors.append(f"title_center:p{page}:{tb}")
            elif section == row["jp_identified"].strip():
                if abs(tb[0] - 104) > 4:
                    errors.append(f"section_x:p{page}:r{row['row']}:{tb[0]}")
            elif section == "note":
                if tb[0] < 950 or tb[2] >= 1900:
                    errors.append(f"note_region:p{page}:{tb}")
            else:
                expected = ui.BODY_X_ANCHORS.get((page, column))
                if expected is not None and abs(tb[0] - expected) > 4:
                    errors.append(f"body_x:p{page}:r{row['row']}:{column}:{tb[0]}:{expected}")
                if column == "left" and tb[2] >= 950:
                    errors.append(f"left_cross:p{page}:r{row['row']}:{tb}")
                if column == "right" and tb[0] < 950:
                    errors.append(f"right_cross:p{page}:r{row['row']}:{tb}")

            allowed_rects.append(pad(sb, 4 if section == "page-title" else 3))
            allowed_rects.append(pad(tb, 2))
            audit.append([
                "menu", src_path.name, row["row"], column, row["zh_target"],
                str(size), align, str(anchor_x or ""), str(sb), str(tb),
            ])

        changed = np.any(src != dst, axis=2)
        allowed = rect_mask(src.shape[:2], allowed_rects)
        outside = int(np.count_nonzero(changed & ~allowed))
        if outside:
            errors.append(f"menu_pixels_outside:{src_path.name}:{outside}")


def verify_buttons(errors: list[str], audit: list[list[str]]) -> None:
    table = ui.UI / "configmenubutton-identification-v1.tsv"
    rows = list(csv.DictReader(table.open("r", encoding="utf-8-sig", newline=""), delimiter="\t"))
    for row in rows:
        if row["confidence"] == "unresolved":
            continue
        jp_states = [s.strip() for s in row["jp_states"].split("/")]
        zh_states = [s.strip() for s in row["zh_states"].split("/")]
        if not jp_states or not zh_states or jp_states == zh_states:
            continue
        count = ui.parse_state_count(row["state_layout"])
        name = Path(row["file"]).name
        src = np.array(Image.open(ui.ROMFS / name).convert("RGBA"))
        dst = np.array(Image.open(OUT / name).convert("RGBA"))
        if src.shape != dst.shape:
            errors.append(f"button_dim:{name}:{src.shape}:{dst.shape}")
            continue
        state_h = src.shape[0] // count
        allowed_rects: list[tuple[int, int, int, int]] = []
        for idx in range(count):
            y0, y1 = idx * state_h, (idx + 1) * state_h
            target = zh_states[min(idx, len(zh_states) - 1)]
            if name == "configmenubutton_0008.png":
                erased = (50, y0 + 6, 200, y0 + 37)
                tb = theoretical_text_bbox(target, erased, 22, "center", None)
                size = 22
            else:
                runs = [r for r in ui.x_runs(src, y0, y1, gap=12) if r[1] - r[0] >= 12]
                if not runs:
                    errors.append(f"button_source_run:{name}:{idx}")
                    continue
                run = max(runs, key=lambda r: (r[1] - r[0], r[2]))
                sb = ui.run_bbox(src, run, y0, y1)
                erased = pad(sb, 2)
                tb = theoretical_text_bbox(target, erased, 28, "center", None)
                size = 28
            if tb[0] < 0 or tb[2] >= src.shape[1] or tb[1] < y0 or tb[3] >= y1:
                errors.append(f"button_clip:{name}:{idx}:{tb}:{src.shape[1]}x{state_h}")
            allowed_rects.append(pad(erased, 1))
            allowed_rects.append(pad(tb, 1))
            audit.append(["button", name, str(idx), "", target, str(size), "center", "", str(erased), str(tb)])

        changed = np.any(src != dst, axis=2)
        allowed = rect_mask(src.shape[:2], allowed_rects)
        outside = int(np.count_nonzero(changed & ~allowed))
        if outside:
            errors.append(f"button_pixels_outside:{name}:{outside}")


def main() -> int:
    errors: list[str] = []
    audit: list[list[str]] = []
    font_path, target_chars = ui.verify_target_font_coverage()
    verify_menu(errors, audit)
    verify_buttons(errors, audit)

    expected_names = {f"configmenu_{i:04d}.png" for i in range(1, 8)}
    expected_names |= {
        "configmenubutton_0001.png", "configmenubutton_0002.png", "configmenubutton_0002_2.png",
        "configmenubutton_0003.png", "configmenubutton_0004.png", "configmenubutton_0005.png",
        "configmenubutton_0006.png", "configmenubutton_0007.png", "configmenubutton_0008.png",
        "configmenubutton_0009.png",
    }
    actual_names = {p.name for p in OUT.glob("*.png")}
    if actual_names != expected_names:
        errors.append(f"png_set:missing={sorted(expected_names-actual_names)}:extra={sorted(actual_names-expected_names)}")

    with QA_OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(["kind", "file", "row_or_state", "column", "text", "font_size", "align", "anchor_x", "source_or_erased_bbox", "target_bbox"])
        writer.writerows(audit)

    print(f"image_font={font_path}")
    print(f"target_nonascii_chars={target_chars}")
    print(f"rendered_png={len(actual_names)}")
    print(f"audit_items={len(audit)}")
    print(f"errors={len(errors)}")
    for error in errors[:100]:
        print(f"ERROR\t{error}")
    print(QA_OUT.relative_to(ROOT))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
