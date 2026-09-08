#!/usr/bin/env python3
"""Build the final v019 Atmosphere/RomFS payload from the clean v018 baseline."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREV = ROOT / "05_build" / "v018-ui-completion"
BUILD = ROOT / "05_build" / "v019-final-complete"
TITLE_ID = "01008DC019F7A000"

OVERLAY_DIRS = (
    ROOT / "03_text" / "ui" / "rendered-v019-help",
    ROOT / "03_text" / "ui" / "rendered-v019-extra",
    ROOT / "03_text" / "ui" / "rendered-v019-menuhelp",
)

EXPECTED = {
    *(f"help{i:02d}.png" for i in range(1, 12)),
    "extrabutton.png",
    "menuhelp.png",
    "menuhelp_a.png",
}


def overlay_sources() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for folder in OVERLAY_DIRS:
        if not folder.is_dir():
            raise RuntimeError(f"missing overlay dir: {folder}")
        for p in folder.glob("*.png"):
            if p.name in out:
                raise RuntimeError(f"duplicate v019 overlay: {p.name}")
            out[p.name] = p
    if set(out) != EXPECTED:
        raise RuntimeError(
            f"unexpected v019 overlay set; missing={sorted(EXPECTED-set(out))} "
            f"extra={sorted(set(out)-EXPECTED)}"
        )
    return out


def main() -> int:
    if not (PREV / "romfs").is_dir() or not (PREV / "atmosphere").is_dir():
        raise RuntimeError(f"invalid v018 baseline: {PREV}")

    if BUILD.exists():
        shutil.rmtree(BUILD)
    shutil.copytree(PREV / "romfs", BUILD / "romfs")
    shutil.copytree(PREV / "atmosphere", BUILD / "atmosphere")

    rom_system = BUILD / "romfs" / "System"
    atm_system = BUILD / "atmosphere" / "contents" / TITLE_ID / "romfs" / "System"
    sources = overlay_sources()
    for name, src in sorted(sources.items()):
        shutil.copy2(src, rom_system / name)
        shutil.copy2(src, atm_system / name)
        print(f"overlay\tSystem/{name}\t{src.stat().st_size}")

    rom_count = sum(1 for p in (BUILD / "romfs").rglob("*") if p.is_file())
    atm_count = sum(1 for p in (BUILD / "atmosphere").rglob("*") if p.is_file())
    print(f"v019_overlays={len(sources)}")
    print(f"romfs_files={rom_count}")
    print(f"atmosphere_files={atm_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

