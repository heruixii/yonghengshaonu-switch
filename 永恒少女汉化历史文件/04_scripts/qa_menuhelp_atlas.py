#!/usr/bin/env python3
"""Pixel safety QA for localized MenuHelp atlases."""

from __future__ import annotations

import numpy as np
from PIL import Image

import localize_menuhelp_atlas as mh


def main() -> int:
    errors: list[str] = []
    for name in ("menuhelp.png", "menuhelp_a.png"):
        src = np.array(Image.open(mh.SYSTEM / name).convert("RGBA"))
        dst = np.array(Image.open(mh.OUT / name).convert("RGBA"))
        if src.shape != dst.shape:
            errors.append(f"shape:{name}:{src.shape}:{dst.shape}")
            continue
        sy, sx = src.shape[0] / 633, src.shape[1] / 950
        allowed = np.zeros(src.shape[:2], dtype=bool)
        for y0, y1 in mh.ROW_RECTS:
            for x0, x1 in mh.COL_RECTS:
                rx0, ry0, rx1, ry1 = mh.scaled_rect((x0, y0, x1, y1), sx, sy)
                allowed[max(0, ry0 - 1) : min(src.shape[0], ry1 + 2), max(0, rx0 - 1) : min(src.shape[1], rx1 + 2)] = True
        changed = np.any(src != dst, axis=2)
        outside = int(np.count_nonzero(changed & ~allowed))
        if outside:
            errors.append(f"outside:{name}:{outside}")

        # Controller/icon marker zones must remain byte-identical.  These are
        # the repeated left-edge regions preceding each text column.
        icon_ranges_full = [(0, 44), (286, 334), (573, 624)]
        icon_bad = 0
        for x0, x1 in icon_ranges_full:
            ax0, ax1 = round(x0 * sx), round(x1 * sx)
            icon_bad += int(np.count_nonzero(np.any(src[:, ax0 : ax1 + 1] != dst[:, ax0 : ax1 + 1], axis=2)))
        if icon_bad:
            errors.append(f"icons:{name}:{icon_bad}")

        # Top two icon-only bands are not part of text localization.
        top_bad = int(np.count_nonzero(np.any(src[: round(150 * sy)] != dst[: round(150 * sy)], axis=2)))
        if top_bad:
            errors.append(f"top_icons:{name}:{top_bad}")
        print(f"{name}\tchanged={int(np.count_nonzero(changed))}\toutside={outside}\ticons={icon_bad}\ttop={top_bad}")

    chars = mh.verify_font()
    print(f"target_nonascii={chars}")
    print(f"errors={len(errors)}")
    for e in errors:
        print("ERROR\t" + e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

