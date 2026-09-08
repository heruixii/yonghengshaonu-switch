#!/usr/bin/env python3
"""QA for the localized Extra close-button sprite."""

from __future__ import annotations

import numpy as np
from PIL import Image

import localize_extra_close_button as ex


def main() -> int:
    src = np.array(Image.open(ex.SOURCE).convert("RGBA"))
    dst_path = ex.OUT / ex.SOURCE.name
    dst = np.array(Image.open(dst_path).convert("RGBA"))
    errors: list[str] = []

    if src.shape != dst.shape:
        errors.append(f"shape:{src.shape}:{dst.shape}")
    alpha_bad = int(np.count_nonzero(src[:, :, 3] != dst[:, :, 3]))
    if alpha_bad:
        errors.append(f"alpha:{alpha_bad}")

    changed = np.any(src != dst, axis=2)
    allowed = np.zeros(changed.shape, dtype=bool)
    x0, y0, x1, y1 = ex.CLEAR
    # Target glyph anti-aliasing remains inside this slightly enlarged area.
    allowed[max(0, y0 - 2) : min(src.shape[0], y1 + 3), max(0, x0 - 2) : min(src.shape[1], x1 + 3)] = True
    outside = int(np.count_nonzero(changed & ~allowed))
    if outside:
        errors.append(f"outside:{outside}")
    if int(np.count_nonzero(changed)) < 20:
        errors.append("too_few_changed_pixels")

    print(f"changed={int(np.count_nonzero(changed))}")
    print(f"alpha_changed={alpha_bad}")
    print(f"outside_allowed={outside}")
    print(f"errors={len(errors)}")
    for e in errors:
        print("ERROR\t" + e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

