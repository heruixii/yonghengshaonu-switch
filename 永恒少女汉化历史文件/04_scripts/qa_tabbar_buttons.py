#!/usr/bin/env python3
"""Pixel/geometry QA for localized settings/Extra tab/action atlases."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import localize_tabbar_buttons as tab


ROOT = Path(__file__).resolve().parents[1]


def target_bbox(width: int, source_bbox: tuple[int, int, int, int], text: str, size: int) -> tuple[int, int, int, int]:
    font = ImageFont.truetype(str(tab.FONT), size=size, index=0)
    draw = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    _x0, y0, _x1, y1 = source_bbox
    x = round(width / 2 - tw / 2 - tb[0])
    y = round((y0 + y1) / 2 - th / 2 - tb[1])
    return x + tb[0], y + tb[1], x + tb[2] - 1, y + tb[3] - 1


def main() -> int:
    errors: list[str] = []
    localized_states = 0
    untouched_states = 0
    for name, spec in tab.SPECS.items():
        src = np.array(Image.open(tab.SYSTEM / name).convert("RGBA"))
        dst = np.array(Image.open(tab.OUT / name).convert("RGBA"))
        if src.shape != dst.shape:
            errors.append(f"dim:{name}:{src.shape}:{dst.shape}")
            continue
        if not np.array_equal(src[:, :, 3], dst[:, :, 3]):
            errors.append(f"alpha:{name}")

        state_h = int(spec["state_h"])
        size = int(spec["font_size"])
        for idx, target in enumerate(spec["targets"]):
            y0, y1 = idx * state_h, (idx + 1) * state_h
            s = src[y0:y1]
            d = dst[y0:y1]
            if not target:
                untouched_states += 1
                if not np.array_equal(s, d):
                    errors.append(f"untouched_changed:{name}:{idx}")
                continue

            localized_states += 1
            sb = tab.text_bbox(src, y0, y1)
            erased = (max(1, sb[0] - 2), max(y0, sb[1] - 2), min(src.shape[1] - 2, sb[2] + 2), min(y1 - 1, sb[3] + 2))
            tb = target_bbox(src.shape[1], erased, target, size)
            if tb[0] < 0 or tb[2] >= src.shape[1] or tb[1] < y0 or tb[3] >= y1:
                errors.append(f"clip:{name}:{idx}:{tb}")

            changed = np.any(s != d, axis=2)
            # RGB changes must remain inside the union of the erased source box
            # and the target glyph box, with a tiny anti-alias margin.
            allowed = np.zeros(changed.shape, dtype=bool)
            for x0, yy0, x1, yy1 in (erased, tb):
                lx0 = max(0, x0 - 1)
                lx1 = min(src.shape[1] - 1, x1 + 1)
                ly0 = max(y0, yy0 - 1) - y0
                ly1 = min(y1 - 1, yy1 + 1) - y0
                allowed[ly0 : ly1 + 1, lx0 : lx1 + 1] = True
            outside = int(np.count_nonzero(changed & ~allowed))
            if outside:
                errors.append(f"outside:{name}:{idx}:{outside}")

    actual = {p.name for p in tab.OUT.glob("*.png")}
    expected = set(tab.SPECS)
    if actual != expected:
        errors.append(f"png_set:missing={sorted(expected-actual)}:extra={sorted(actual-expected)}")

    print(f"localized_states={localized_states}")
    print(f"untouched_states={untouched_states}")
    print(f"png={len(actual)}")
    print(f"errors={len(errors)}")
    for error in errors[:100]:
        print(f"ERROR\t{error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
