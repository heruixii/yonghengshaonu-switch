#!/usr/bin/env python3
"""Geometry/content QA for rebuilt v019 Chinese help pages."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

import localize_help_pages as hp


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors: list[str] = []
    files = sorted(hp.OUT.glob("help??.png"))
    expected = {f"help{i:02d}.png" for i in range(1, 12)}
    actual = {p.name for p in files}
    if actual != expected:
        errors.append(f"file_set missing={sorted(expected-actual)} extra={sorted(actual-expected)}")

    hashes: set[bytes] = set()
    for p in files:
        im = Image.open(p)
        if im.size != (1920, 1080):
            errors.append(f"size:{p.name}:{im.size}")
        if im.mode != "RGB":
            errors.append(f"mode:{p.name}:{im.mode}")
        a = np.array(im.convert("RGB"))
        # Page may not be blank/near-solid; header/cards/text create variance.
        if float(a.std()) < 8.0:
            errors.append(f"low_variance:{p.name}:{float(a.std()):.3f}")
        hashes.add(a.tobytes())

    if len(hashes) != 11:
        errors.append(f"duplicate_pages:{len(hashes)}")

    # Renderer itself performs font coverage and per-card overflow hard-fails.
    target_chars = hp.verify_font()
    print(f"png={len(files)}")
    print(f"unique_pages={len(hashes)}")
    print(f"target_nonascii={target_chars}")
    print(f"errors={len(errors)}")
    for error in errors:
        print("ERROR\t" + error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

