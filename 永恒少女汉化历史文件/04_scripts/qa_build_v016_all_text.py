#!/usr/bin/env python3
"""Final static QA + ZIP builder for v016 all-text milestone."""

from __future__ import annotations

import csv
import hashlib
import re
import struct
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from fontTools.ttLib import TTCollection


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "05_build" / "v016-all-text"
PREV = ROOT / "05_build" / "v015-scene1100"
CLEAN = ROOT / "02_romfs" / "merged-v1.0.3"
RENDERED = ROOT / "03_text" / "rendered-final-v3"
FONTS = ROOT / "03_text" / "runtime-fonts-final-v3"
CUMULATIVE = ROOT / "03_text" / "translated" / "final-all-text-v3-cumulative.tsv"
SUMMARY = ROOT / "03_text" / "matched" / "scene-alignment-summary-v2.tsv"
ZIP_PATH = BUILD / "v016-all-text-test.zip"
QA_PATH = BUILD / "qa-final.tsv"
TITLE_ID = "01008DC019F7A000"
FONT_NAMES = ["dfgotp5.ttc", "dfhsr4.ttc", "dfmrg5_u.ttc"]

VOICE_RE = re.compile(r"@v{2,3}\d+")
GENERIC_CONTROL_RE = re.compile(r"@[A-Za-z][A-Za-z0-9_]*")
RUBY_RE = re.compile(r"@r[^@]*@[^@]*@")
PC_RUBY_RE = re.compile(r"\|[^\[]+\[[^\]]*\]")
KANA_RE = re.compile(r"[\u3040-\u30ff]")
DANGEROUS_SUFFIXES = {".nsp", ".nsz", ".nca"}
DANGEROUS_NAMES = {"prod.keys", "title.keys"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def strict_controls(text: str) -> list[str]:
    text = RUBY_RE.sub("", text)
    return [c for c in GENERIC_CONTROL_RE.findall(text) if c not in {"@n", "@r"}]


def unicode_cmap(font) -> dict[int, str]:
    out = {}
    for table in font["cmap"].tables:
        if table.isUnicode():
            out.update(table.cmap)
    return out


def collect_target_cps(rows: list[dict[str, str]]) -> set[int]:
    out = set()
    for r in rows:
        for field in ("source", "translation"):
            out.update(ord(ch) for ch in r.get(field, "") if ord(ch) > 127)
    return out


def verify_overlay_and_inheritance(errors: list[str]):
    romfs = BUILD / "romfs"
    atm = BUILD / "atmosphere" / "contents" / TITLE_ID / "romfs"
    overlay_rels = {p.relative_to(RENDERED).as_posix() for p in RENDERED.rglob("*") if p.is_file()}
    if len(overlay_rels) != 197:
        errors.append(f"overlay_count:{len(overlay_rels)}")

    overlay_ok = 0
    for rel in sorted(overlay_rels):
        src = RENDERED / rel
        a = romfs / rel
        b = atm / rel
        if a.is_file() and b.is_file() and sha(src) == sha(a) == sha(b):
            overlay_ok += 1
        else:
            errors.append(f"overlay_mismatch:{rel}")

    font_ok = 0
    for name in FONT_NAMES:
        src = FONTS / name
        a = romfs / "System" / name
        b = atm / "System" / name
        if a.is_file() and b.is_file() and sha(src) == sha(a) == sha(b):
            font_ok += 1
        else:
            errors.append(f"font_payload_mismatch:{name}")

    prev_root = PREV / "romfs"
    unchanged = 0
    skipped_intended = 0
    font_rel = {f"System/{n}" for n in FONT_NAMES}
    for old in prev_root.rglob("*"):
        if not old.is_file():
            continue
        rel = old.relative_to(prev_root).as_posix()
        if rel in overlay_rels or rel in font_rel:
            skipped_intended += 1
            continue
        cur = romfs / rel
        if not cur.is_file():
            errors.append(f"missing_inherited:{rel}")
        elif sha(old) != sha(cur):
            errors.append(f"unexpected_inherited_change:{rel}")
        else:
            unchanged += 1

    # Every RomFS payload file must mirror exactly into Atmosphere.
    mirror_bad = 0
    for p in romfs.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(romfs)
        q = atm / rel
        if not q.is_file() or sha(p) != sha(q):
            mirror_bad += 1
            errors.append(f"mirror:{rel.as_posix()}")

    return len(overlay_rels), overlay_ok, font_ok, unchanged, skipped_intended, mirror_bad


def verify_reextract(rows: list[dict[str, str]], errors: list[str]):
    by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        by_file[r["file"]].append(r)

    matched = source_bad = voice_bad = strict_bad = kana_bad = markup_bad = 0
    for rel, file_rows in sorted(by_file.items()):
        src = (CLEAN / rel).read_bytes()
        dst = (BUILD / "romfs" / rel).read_bytes()
        shift = 0
        for r in sorted(file_rows, key=lambda x: int(x["length_offset"])):
            old_off = int(r["length_offset"])
            old_stored = struct.unpack_from("<I", src, old_off)[0]
            original = src[old_off + 4 : old_off + 4 + old_stored - 1].decode("utf-8")
            if original != r["source"]:
                source_bad += 1
            new_off = old_off + shift
            new_stored = struct.unpack_from("<I", dst, new_off)[0]
            actual = dst[new_off + 4 : new_off + 4 + new_stored - 1].decode("utf-8")
            if actual == r["translation"]:
                matched += 1
            else:
                errors.append(f"reextract:{rel}:{old_off}")
            if VOICE_RE.findall(original) != VOICE_RE.findall(actual):
                voice_bad += 1
            if strict_controls(original) != strict_controls(actual):
                strict_bad += 1
            no_ruby = RUBY_RE.sub("", actual)
            if "@r" in no_ruby or "^n" in actual or PC_RUBY_RE.search(actual):
                markup_bad += 1
            if KANA_RE.search(actual):
                kana_bad += 1
            shift += (4 + new_stored) - (4 + old_stored)

    if source_bad: errors.append(f"source_bad:{source_bad}")
    if voice_bad: errors.append(f"voice_bad:{voice_bad}")
    if strict_bad: errors.append(f"strict_bad:{strict_bad}")
    if kana_bad: errors.append(f"kana_bad:{kana_bad}")
    if markup_bad: errors.append(f"markup_bad:{markup_bad}")
    return len(by_file), matched, source_bad, voice_bad, strict_bad, kana_bad, markup_bad


def verify_story_coverage(rows: list[dict[str, str]], errors: list[str]):
    targets = {}
    with SUMMARY.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["scene"].isdigit() and int(r["ns_story_tokens"]) > 0:
                targets[r["scene"]] = int(r["ns_story_tokens"])

    indices: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        scene = r.get("scene", "")
        idx = r.get("ns_filtered_index", "")
        # Non-story dynamic/UI records may reuse a numeric scene label while
        # carrying descriptive indices such as "speaker-before-9".  Only the
        # authoritative story batches use contiguous decimal NS indices.
        if scene in targets and idx.isdigit():
            indices[scene].append(int(idx))
    bad = 0
    for scene, expected in targets.items():
        if sorted(indices[scene]) != list(range(expected)):
            bad += 1
            errors.append(f"story_coverage:{scene}:{len(indices[scene])}/{expected}")
    return len(targets), sum(targets.values()), sum(len(v) for v in indices.values()), bad


def verify_fonts(rows: list[dict[str, str]], errors: list[str]):
    cps = collect_target_cps(rows)
    coverage = {}
    added = {}
    for name in FONT_NAMES:
        old_coll = TTCollection(str(PREV / "romfs" / "System" / name))
        new_coll = TTCollection(str(BUILD / "romfs" / "System" / name))
        if len(old_coll.fonts) != len(new_coll.fonts):
            errors.append(f"font_face_count:{name}")
            continue
        misses = []
        added_set = set()
        for face, (old, new) in enumerate(zip(old_coll.fonts, new_coll.fonts)):
            old_order, new_order = old.getGlyphOrder(), new.getGlyphOrder()
            if new_order[:len(old_order)] != old_order:
                errors.append(f"glyph_order:{name}:{face}")
            oc, nc = unicode_cmap(old), unicode_cmap(new)
            cmap_bad = sum(nc.get(cp) != glyph for cp, glyph in oc.items())
            hmtx_bad = sum(old["hmtx"].metrics[g] != new["hmtx"].metrics[g] for g in old_order)
            vmtx_bad = 0
            if "vmtx" in old and "vmtx" in new:
                vmtx_bad = sum(old["vmtx"].metrics[g] != new["vmtx"].metrics[g] for g in old_order)
            glyf_bad = 0
            for g in old_order:
                ob = old["glyf"][g].compile(old["glyf"], recalcBBoxes=False)
                nb = new["glyf"][g].compile(new["glyf"], recalcBBoxes=False)
                glyf_bad += ob != nb
            if cmap_bad or hmtx_bad or vmtx_bad or glyf_bad:
                errors.append(f"font_old_changed:{name}:{face}:c{cmap_bad}:h{hmtx_bad}:v{vmtx_bad}:g{glyf_bad}")
            miss = sum(cp not in nc for cp in cps)
            misses.append(miss)
            added_set.update(cp for cp in cps if cp not in oc and cp in nc)
        coverage[name] = misses
        added[name] = len(added_set)
        if any(misses):
            errors.append(f"font_coverage:{name}:{misses}")
    return len(cps), coverage, added


def build_zip(errors: list[str]):
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted((BUILD / "atmosphere").rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(BUILD).as_posix())

    with zipfile.ZipFile(ZIP_PATH) as z:
        names = z.namelist()
        bad = []
        for n in names:
            p = Path(n)
            if p.suffix.lower() in DANGEROUS_SUFFIXES or p.name.lower() in DANGEROUS_NAMES:
                bad.append(n)
            if not n.startswith("atmosphere/"):
                bad.append(n)
        if bad:
            errors.append(f"dangerous_or_non_atmosphere_zip:{bad[:20]}")
        ext = Counter(Path(n).suffix.lower() for n in names)
        return len(names), ext, ZIP_PATH.stat().st_size, sha(ZIP_PATH), len(bad)


def main() -> int:
    with CUMULATIVE.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    errors = []
    if len(rows) != 14178:
        errors.append(f"cumulative_rows:{len(rows)}")

    overlay = verify_overlay_and_inheritance(errors)
    reext = verify_reextract(rows, errors)
    story = verify_story_coverage(rows, errors)
    fonts = verify_fonts(rows, errors)

    romfs_files = [p for p in (BUILD / "romfs").rglob("*") if p.is_file()]
    atmosphere_files = [p for p in (BUILD / "atmosphere").rglob("*") if p.is_file()]
    if len(romfs_files) != 227 or len(atmosphere_files) != 227:
        errors.append(f"payload_file_count:{len(romfs_files)}:{len(atmosphere_files)}")

    zip_stats = build_zip(errors)
    with QA_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["check", "value"])
        w.writerow(["cumulative_rows", len(rows)])
        w.writerow(["overlay_files", overlay[0]])
        w.writerow(["overlay_ok", overlay[1]])
        w.writerow(["font_payload_ok", overlay[2]])
        w.writerow(["inherited_unchanged", overlay[3]])
        w.writerow(["mirror_bad", overlay[5]])
        w.writerow(["reextract_match", f"{reext[1]}/{len(rows)}"])
        w.writerow(["story_coverage", f"{story[2]}/{story[1]}"])
        w.writerow(["font_target_codepoints", fonts[0]])
        w.writerow(["zip_files", zip_stats[0]])
        w.writerow(["zip_size", zip_stats[2]])
        w.writerow(["sha256", zip_stats[3]])
        w.writerow(["errors", len(errors)])

    print(f"cumulative_rows={len(rows)}")
    print(f"overlay_files={overlay[0]} overlay_ok={overlay[1]} font_payload_ok={overlay[2]}")
    print(f"inherited_unchanged={overlay[3]} intended_prev_overlays={overlay[4]} mirror_bad={overlay[5]}")
    print(f"resource_files={reext[0]} reextract_match={reext[1]}/{len(rows)}")
    print(f"source_bad={reext[2]} voice_bad={reext[3]} strict_bad={reext[4]} kana_bad={reext[5]} markup_bad={reext[6]}")
    print(f"story_scenes={story[0]} story_rows={story[1]} covered={story[2]} coverage_errors={story[3]}")
    print(f"font_target_codepoints={fonts[0]}")
    print(f"font_coverage={fonts[1]}")
    print(f"font_added_codepoints={fonts[2]}")
    print(f"romfs_files={len(romfs_files)} atmosphere_files={len(atmosphere_files)}")
    print(f"zip_files={zip_stats[0]} zip_ext={dict(zip_stats[1])} zip_size={zip_stats[2]}")
    print(f"sha256={zip_stats[3]} zip_bad={zip_stats[4]}")
    print(f"errors={len(errors)}")
    for e in errors[:100]:
        print(f"ERROR\t{e}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
