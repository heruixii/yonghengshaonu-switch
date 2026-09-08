#!/usr/bin/env python3
"""Final build QA + ZIP builder for v017 settings typography polish."""

from __future__ import annotations

import csv
from pathlib import Path

import qa_build_v016_all_text as base


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "05_build" / "v017-settings-polish"
PREV_BUILD = ROOT / "05_build" / "v016-all-text"
FONT_BASE = ROOT / "05_build" / "v015-scene1100"
TEXT = ROOT / "03_text" / "rendered-final-v3"
FONTS = ROOT / "03_text" / "runtime-fonts-final-v3"
SETTINGS = ROOT / "03_text" / "ui" / "rendered-v017-settings-polish"
CUMULATIVE = ROOT / "03_text" / "translated" / "final-all-text-v3-cumulative.tsv"
ZIP_PATH = BUILD / "v017-settings-polish-test.zip"
QA_PATH = BUILD / "qa-final.tsv"
TITLE_ID = "01008DC019F7A000"
FONT_NAMES = ["dfgotp5.ttc", "dfhsr4.ttc", "dfmrg5_u.ttc"]


def verify_payload(errors: list[str]) -> tuple[int, int, int, int, int, int]:
    romfs = BUILD / "romfs"
    atm = BUILD / "atmosphere" / "contents" / TITLE_ID / "romfs"
    text_rels = {p.relative_to(TEXT).as_posix() for p in TEXT.rglob("*") if p.is_file()}
    settings_rels = {f"System/{p.name}" for p in SETTINGS.glob("*.png")}
    font_rels = {f"System/{name}" for name in FONT_NAMES}

    if len(text_rels) != 197:
        errors.append(f"text_overlay_count:{len(text_rels)}")
    if len(settings_rels) != 17:
        errors.append(f"settings_overlay_count:{len(settings_rels)}")

    text_ok = 0
    for rel in sorted(text_rels):
        src = TEXT / rel
        a, b = romfs / rel, atm / rel
        if a.is_file() and b.is_file() and base.sha(src) == base.sha(a) == base.sha(b):
            text_ok += 1
        else:
            errors.append(f"text_payload:{rel}")

    settings_ok = 0
    for rel in sorted(settings_rels):
        src = SETTINGS / Path(rel).name
        a, b = romfs / rel, atm / rel
        if a.is_file() and b.is_file() and base.sha(src) == base.sha(a) == base.sha(b):
            settings_ok += 1
        else:
            errors.append(f"settings_payload:{rel}")

    font_ok = 0
    for name in FONT_NAMES:
        src = FONTS / name
        a, b = romfs / "System" / name, atm / "System" / name
        if a.is_file() and b.is_file() and base.sha(src) == base.sha(a) == base.sha(b):
            font_ok += 1
        else:
            errors.append(f"font_payload:{name}")

    intended = text_rels | settings_rels | font_rels
    unchanged = 0
    for old in (PREV_BUILD / "romfs").rglob("*"):
        if not old.is_file():
            continue
        rel = old.relative_to(PREV_BUILD / "romfs").as_posix()
        if rel in intended:
            continue
        cur = romfs / rel
        if not cur.is_file():
            errors.append(f"missing_inherited:{rel}")
        elif base.sha(old) != base.sha(cur):
            errors.append(f"unexpected_inherited_change:{rel}")
        else:
            unchanged += 1

    mirror_bad = 0
    for p in romfs.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(romfs)
        q = atm / rel
        if not q.is_file() or base.sha(p) != base.sha(q):
            mirror_bad += 1
            errors.append(f"mirror:{rel.as_posix()}")

    return len(text_rels), text_ok, settings_ok, font_ok, unchanged, mirror_bad


def main() -> int:
    with CUMULATIVE.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    errors: list[str] = []
    if len(rows) != 14178:
        errors.append(f"cumulative_rows:{len(rows)}")

    # Reuse the proven v016 deep checks, but point them at the v017 tree while
    # keeping v015 as the old-glyph baseline for font-preservation verification.
    base.BUILD = BUILD
    base.CLEAN = ROOT / "02_romfs" / "merged-v1.0.3"
    base.PREV = FONT_BASE
    base.ZIP_PATH = ZIP_PATH

    payload = verify_payload(errors)
    reext = base.verify_reextract(rows, errors)
    story = base.verify_story_coverage(rows, errors)
    fonts = base.verify_fonts(rows, errors)

    romfs_files = [p for p in (BUILD / "romfs").rglob("*") if p.is_file()]
    atmosphere_files = [p for p in (BUILD / "atmosphere").rglob("*") if p.is_file()]
    if len(romfs_files) != 227 or len(atmosphere_files) != 227:
        errors.append(f"payload_file_count:{len(romfs_files)}:{len(atmosphere_files)}")

    zip_stats = base.build_zip(errors)
    with QA_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["check", "value"])
        w.writerow(["cumulative_rows", len(rows)])
        w.writerow(["text_overlay", f"{payload[1]}/{payload[0]}"])
        w.writerow(["settings_overlay", f"{payload[2]}/17"])
        w.writerow(["font_payload", f"{payload[3]}/3"])
        w.writerow(["inherited_unchanged", payload[4]])
        w.writerow(["mirror_bad", payload[5]])
        w.writerow(["reextract_match", f"{reext[1]}/{len(rows)}"])
        w.writerow(["story_coverage", f"{story[2]}/{story[1]}"])
        w.writerow(["font_target_codepoints", fonts[0]])
        w.writerow(["zip_files", zip_stats[0]])
        w.writerow(["zip_size", zip_stats[2]])
        w.writerow(["sha256", zip_stats[3]])
        w.writerow(["errors", len(errors)])

    print(f"cumulative_rows={len(rows)}")
    print(f"text_overlay={payload[1]}/{payload[0]} settings_overlay={payload[2]}/17 font_payload={payload[3]}/3")
    print(f"inherited_unchanged={payload[4]} mirror_bad={payload[5]}")
    print(f"resource_files={reext[0]} reextract_match={reext[1]}/{len(rows)}")
    print(f"source_bad={reext[2]} voice_bad={reext[3]} strict_bad={reext[4]} kana_bad={reext[5]} markup_bad={reext[6]}")
    print(f"story_scenes={story[0]} story_rows={story[1]} covered={story[2]} coverage_errors={story[3]}")
    print(f"font_target_codepoints={fonts[0]} font_coverage={fonts[1]}")
    print(f"romfs_files={len(romfs_files)} atmosphere_files={len(atmosphere_files)}")
    print(f"zip_files={zip_stats[0]} zip_size={zip_stats[2]} sha256={zip_stats[3]} zip_bad={zip_stats[4]}")
    print(f"errors={len(errors)}")
    for e in errors[:100]:
        print(f"ERROR\t{e}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
