#!/usr/bin/env python3
"""Release-gate QA and ZIP builder for the final v019 localization payload."""

from __future__ import annotations

import csv
from pathlib import Path

import build_v019_final_complete as build
import qa_build_v016_all_text as base


ROOT = Path(__file__).resolve().parents[1]
BUILD = build.BUILD
PREV = build.PREV
FONT_BASE = ROOT / "05_build" / "v015-scene1100"
CUMULATIVE = ROOT / "03_text" / "translated" / "final-all-text-v3-cumulative.tsv"
ZIP_PATH = BUILD / "v019-final-complete.zip"
QA_PATH = BUILD / "qa-final.tsv"
TITLE_ID = build.TITLE_ID

DANGEROUS_SUFFIXES = {".nsp", ".nsz", ".nca"}
DANGEROUS_NAMES = {"prod.keys", "title.keys"}


def sha(path: Path) -> str:
    return base.sha(path)


def verify_v019_overlays(errors: list[str]) -> tuple[int, int, int, int]:
    rom = BUILD / "romfs"
    atm = BUILD / "atmosphere" / "contents" / TITLE_ID / "romfs"
    sources = build.overlay_sources()

    overlay_ok = 0
    for name, src in sorted(sources.items()):
        rel = Path("System") / name
        a, b = rom / rel, atm / rel
        if a.is_file() and b.is_file() and sha(src) == sha(a) == sha(b):
            overlay_ok += 1
        else:
            errors.append(f"overlay:{rel.as_posix()}")

    overlay_rels = {f"System/{name}" for name in sources}
    inherited_ok = 0
    for old in (PREV / "romfs").rglob("*"):
        if not old.is_file():
            continue
        rel = old.relative_to(PREV / "romfs").as_posix()
        if rel in overlay_rels:
            continue
        cur = rom / rel
        if not cur.is_file():
            errors.append(f"missing_inherited:{rel}")
        elif sha(old) != sha(cur):
            errors.append(f"unexpected_inherited_change:{rel}")
        else:
            inherited_ok += 1

    mirror_bad = 0
    for p in rom.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(rom)
        q = atm / rel
        if not q.is_file() or sha(p) != sha(q):
            mirror_bad += 1
            errors.append(f"mirror:{rel.as_posix()}")
    return len(sources), overlay_ok, inherited_ok, mirror_bad


def scan_dangerous(errors: list[str]) -> int:
    bad: list[str] = []
    for root in (BUILD / "romfs", BUILD / "atmosphere"):
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() in DANGEROUS_SUFFIXES or p.name.lower() in DANGEROUS_NAMES:
                bad.append(p.relative_to(BUILD).as_posix())
    if bad:
        errors.append(f"dangerous_payload:{bad[:20]}")
    return len(bad)


def main() -> int:
    with CUMULATIVE.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    errors: list[str] = []
    if len(rows) != 14178:
        errors.append(f"cumulative_rows:{len(rows)}")

    base.BUILD = BUILD
    base.CLEAN = ROOT / "02_romfs" / "merged-v1.0.3"
    base.PREV = FONT_BASE
    base.ZIP_PATH = ZIP_PATH

    overlay = verify_v019_overlays(errors)
    reext = base.verify_reextract(rows, errors)
    story = base.verify_story_coverage(rows, errors)
    fonts = base.verify_fonts(rows, errors)
    dangerous = scan_dangerous(errors)

    prev_rels = {
        p.relative_to(PREV / "romfs").as_posix()
        for p in (PREV / "romfs").rglob("*")
        if p.is_file()
    }
    overlay_rels = {f"System/{name}" for name in build.overlay_sources()}
    expected_payload = len(prev_rels | overlay_rels)

    romfs_files = [p for p in (BUILD / "romfs").rglob("*") if p.is_file()]
    atmosphere_files = [p for p in (BUILD / "atmosphere").rglob("*") if p.is_file()]
    if len(romfs_files) != expected_payload or len(atmosphere_files) != expected_payload:
        errors.append(f"payload_file_count:{len(romfs_files)}:{len(atmosphere_files)}")

    zip_stats = base.build_zip(errors)
    if zip_stats[0] != expected_payload:
        errors.append(f"zip_file_count:{zip_stats[0]}")

    with QA_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["check", "value"])
        w.writerow(["cumulative_rows", len(rows)])
        w.writerow(["v019_overlay", f"{overlay[1]}/{overlay[0]}"])
        w.writerow(["inherited_unchanged", overlay[2]])
        w.writerow(["mirror_bad", overlay[3]])
        w.writerow(["reextract_match", f"{reext[1]}/{len(rows)}"])
        w.writerow(["story_coverage", f"{story[2]}/{story[1]}"])
        w.writerow(["font_target_codepoints", fonts[0]])
        w.writerow(["dangerous_payload", dangerous])
        w.writerow(["expected_payload_files", expected_payload])
        w.writerow(["romfs_files", len(romfs_files)])
        w.writerow(["atmosphere_files", len(atmosphere_files)])
        w.writerow(["zip_files", zip_stats[0]])
        w.writerow(["zip_size", zip_stats[2]])
        w.writerow(["sha256", zip_stats[3]])
        w.writerow(["zip_bad", zip_stats[4]])
        w.writerow(["errors", len(errors)])

    print(f"cumulative_rows={len(rows)}")
    print(f"v019_overlay={overlay[1]}/{overlay[0]} inherited_unchanged={overlay[2]} mirror_bad={overlay[3]}")
    print(f"resource_files={reext[0]} reextract_match={reext[1]}/{len(rows)}")
    print(f"source_bad={reext[2]} voice_bad={reext[3]} strict_bad={reext[4]} kana_bad={reext[5]} markup_bad={reext[6]}")
    print(f"story_scenes={story[0]} story_rows={story[1]} covered={story[2]} coverage_errors={story[3]}")
    print(f"font_target_codepoints={fonts[0]} font_coverage={fonts[1]}")
    print(f"dangerous_payload={dangerous}")
    print(f"expected_payload_files={expected_payload} romfs_files={len(romfs_files)} atmosphere_files={len(atmosphere_files)}")
    print(f"zip_files={zip_stats[0]} zip_size={zip_stats[2]} sha256={zip_stats[3]} zip_bad={zip_stats[4]}")
    print(f"errors={len(errors)}")
    for error in errors[:100]:
        print(f"ERROR\t{error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

