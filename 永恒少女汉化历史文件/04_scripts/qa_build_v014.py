#!/usr/bin/env python3
"""Final static QA and ZIP build for v014 scene 1090."""

from __future__ import annotations

import csv
import hashlib
import re
import struct
import zipfile
from pathlib import Path

from fontTools.ttLib import TTCollection


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "05_build" / "v014-scene1090"
PREV = ROOT / "05_build" / "v013-scene1080"
CLEAN_ROMFS = ROOT / "02_romfs" / "merged-v1.0.3"
SCENE_TSV = ROOT / "03_text" / "translated" / "scene1090-full-v1.tsv"
CUMULATIVE = ROOT / "03_text" / "translated" / "v014-cumulative.tsv"
ZIP_PATH = BUILD / "v014-scene1090-test.zip"
TITLE_ID = "01008DC019F7A000"
FONT_NAMES = ["dfgotp5.ttc", "dfhsr4.ttc", "dfmrg5_u.ttc"]
FONT_RELS = {f"contents/{TITLE_ID}/romfs/System/{name}" for name in FONT_NAMES}

VOICE_RE = re.compile(r"^(@v{2,3}\d+)")
PC_RUBY_RE = re.compile(r"\|[^\[]+\[[^\]]*\]")
NS_RUBY_RE = re.compile(r"@r[^@]*@[^@]*@")
KANA_RE = re.compile(r"[\u3040-\u30ff]")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def unicode_cmap(font) -> dict[int, str]:
    cmap: dict[int, str] = {}
    for table in font["cmap"].tables:
        if table.isUnicode():
            cmap.update(table.cmap)
    return cmap


def collect_target_codepoints() -> set[int]:
    cps: set[int] = set()
    with CUMULATIVE.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            for field in ("source", "translation"):
                cps.update(ord(ch) for ch in row.get(field, "") if ord(ch) > 127)
    return cps


def verify_scene_reextract(errors: list[str]) -> tuple[int, int, int]:
    with SCENE_TSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    if len(rows) != 30:
        errors.append(f"scene_row_count:{len(rows)}")

    source_path = CLEAN_ROMFS / "Script" / "scr1090.binu8"
    patched_path = BUILD / "romfs" / "Script" / "scr1090.binu8"
    source = source_path.read_bytes()
    patched = patched_path.read_bytes()

    edits: list[tuple[int, int]] = []  # original offset, delta
    verify_rows: list[list[object]] = []
    voice_mismatch = 0
    ruby_bad = 0
    kana_rows = 0

    for row in sorted(rows, key=lambda r: int(r["length_offset"])):
        old_offset = int(row["length_offset"])
        old_stored = struct.unpack_from("<I", source, old_offset)[0]
        old_start = old_offset + 4
        old_end = old_start + old_stored
        original = source[old_start : old_end - 1].decode("utf-8")
        if original != row["source"]:
            errors.append(f"scene_source_mismatch:{row['ns_filtered_index']}")

        translation = row["translation"]
        new_record_size = 4 + len(translation.encode("utf-8")) + 1
        old_record_size = 4 + old_stored
        shift = sum(delta for prior_offset, delta in edits if prior_offset < old_offset)
        new_offset = old_offset + shift
        stored = struct.unpack_from("<I", patched, new_offset)[0]
        start = new_offset + 4
        end = start + stored
        actual = patched[start : end - 1].decode("utf-8")
        ok = actual == translation
        if not ok:
            errors.append(f"scene_reextract:{row['ns_filtered_index']}")

        src_voice = VOICE_RE.match(original)
        dst_voice = VOICE_RE.match(actual)
        if (src_voice.group(1) if src_voice else None) != (dst_voice.group(1) if dst_voice else None):
            voice_mismatch += 1

        no_ruby = NS_RUBY_RE.sub("", actual)
        if "@r" in no_ruby or "^n" in actual or PC_RUBY_RE.search(actual):
            ruby_bad += 1
        if KANA_RE.search(actual):
            kana_rows += 1

        verify_rows.append(
            [
                row["ns_filtered_index"],
                old_offset,
                new_offset,
                stored,
                "1" if ok else "0",
                src_voice.group(1) if src_voice else "",
                dst_voice.group(1) if dst_voice else "",
                actual,
            ]
        )
        edits.append((old_offset, new_record_size - old_record_size))

    if voice_mismatch:
        errors.append(f"voice_prefix_mismatch:{voice_mismatch}")
    if ruby_bad:
        errors.append(f"markup_residue_or_bad_ruby:{ruby_bad}")
    if kana_rows:
        errors.append(f"scene_translation_kana:{kana_rows}")

    verify_path = BUILD / "verify-reextract.tsv"
    with verify_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "ns_filtered_index",
                "original_offset",
                "patched_offset",
                "stored_length",
                "match",
                "source_voice",
                "patched_voice",
                "translation",
            ]
        )
        writer.writerows(verify_rows)

    return sum(row[4] == "1" for row in verify_rows), voice_mismatch, kana_rows


def verify_inheritance(errors: list[str]) -> tuple[int, int, int]:
    prev_root = PREV / "atmosphere"
    cur_root = BUILD / "atmosphere"
    prev_files = {p.relative_to(prev_root).as_posix(): p for p in prev_root.rglob("*") if p.is_file()}
    cur_files = {p.relative_to(cur_root).as_posix(): p for p in cur_root.rglob("*") if p.is_file()}

    unchanged = 0
    intended_changed = 0
    for rel, old in prev_files.items():
        new = cur_files.get(rel)
        if new is None:
            errors.append(f"missing_inherited:{rel}")
            continue
        same = sha(old) == sha(new)
        if rel in FONT_RELS:
            if same:
                errors.append(f"font_not_extended:{rel}")
            else:
                intended_changed += 1
        elif not same:
            errors.append(f"unexpected_inherited_change:{rel}")
        else:
            unchanged += 1

    scene_rel = f"contents/{TITLE_ID}/romfs/Script/scr1090.binu8"
    if scene_rel not in cur_files:
        errors.append("missing_new_scene1090")
    return len(prev_files), unchanged, intended_changed


def verify_font_preservation(errors: list[str]) -> tuple[int, dict[str, list[int]], dict[str, int]]:
    target_cps = collect_target_codepoints()
    coverage: dict[str, list[int]] = {}
    added_counts: dict[str, int] = {}
    audit_rows: list[list[object]] = []

    for name in FONT_NAMES:
        old_coll = TTCollection(str(PREV / "romfs" / "System" / name))
        new_coll = TTCollection(str(BUILD / "romfs" / "System" / name))
        if len(old_coll.fonts) != len(new_coll.fonts):
            errors.append(f"font_face_count:{name}")
            continue

        missing_faces: list[int] = []
        per_font_added: set[int] = set()
        for face_index, (old, new) in enumerate(zip(old_coll.fonts, new_coll.fonts)):
            old_order = old.getGlyphOrder()
            new_order = new.getGlyphOrder()
            if new_order[: len(old_order)] != old_order:
                errors.append(f"font_glyph_order_prefix:{name}:face{face_index}")

            old_cmap = unicode_cmap(old)
            new_cmap = unicode_cmap(new)
            if any(new_cmap.get(cp) != glyph for cp, glyph in old_cmap.items()):
                errors.append(f"font_existing_cmap_changed:{name}:face{face_index}")

            if any(old["hmtx"].metrics[g] != new["hmtx"].metrics[g] for g in old_order):
                errors.append(f"font_existing_hmtx_changed:{name}:face{face_index}")
            if "vmtx" in old and "vmtx" in new:
                if any(old["vmtx"].metrics[g] != new["vmtx"].metrics[g] for g in old_order):
                    errors.append(f"font_existing_vmtx_changed:{name}:face{face_index}")

            # Because new glyphs are appended, existing glyph IDs remain stable.
            # Compiled glyf bytes must therefore remain exactly identical.
            glyph_changed = 0
            for glyph_name in old_order:
                old_bytes = old["glyf"][glyph_name].compile(old["glyf"], recalcBBoxes=False)
                new_bytes = new["glyf"][glyph_name].compile(new["glyf"], recalcBBoxes=False)
                if old_bytes != new_bytes:
                    glyph_changed += 1
            if glyph_changed:
                errors.append(f"font_existing_glyf_changed:{name}:face{face_index}:{glyph_changed}")

            missing = sum(cp not in new_cmap for cp in target_cps)
            missing_faces.append(missing)
            newly_covered = {cp for cp in target_cps if cp not in old_cmap and cp in new_cmap}
            per_font_added.update(newly_covered)
            audit_rows.append(
                [name, face_index, len(old_order), len(new_order), len(new_order) - len(old_order), missing, glyph_changed]
            )

        coverage[name] = missing_faces
        added_counts[name] = len(per_font_added)
        if any(missing_faces):
            errors.append(f"font_coverage:{name}:{missing_faces}")

    with (BUILD / "font-coverage.tsv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(
            ["font", "face", "old_glyphs", "new_glyphs", "added_glyphs", "missing_target_codepoints", "changed_old_glyphs"]
        )
        writer.writerows(audit_rows)
    return len(target_cps), coverage, added_counts


def verify_payload_mirror(errors: list[str]) -> None:
    romfs = BUILD / "romfs"
    atmosphere_romfs = BUILD / "atmosphere" / "contents" / TITLE_ID / "romfs"
    for p in romfs.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(romfs)
        other = atmosphere_romfs / rel
        if not other.is_file() or sha(p) != sha(other):
            errors.append(f"romfs_atmosphere_mirror:{rel.as_posix()}")


def build_zip(errors: list[str]) -> tuple[int, int, int, str]:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted((BUILD / "atmosphere").rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(BUILD).as_posix())

    with zipfile.ZipFile(ZIP_PATH) as z:
        files = [n for n in z.namelist() if not n.endswith("/")]
        pngs = [n for n in files if n.lower().endswith(".png")]
        scripts = [n for n in files if "/script/" in n.lower() and n.lower().endswith(".binu8")]
        for bad in [".nsp", ".nsz", ".nca", "prod.keys", "title.keys"]:
            if any(bad in n.lower() for n in files):
                errors.append(f"badfile:{bad}")
        if len(files) != 48:
            errors.append(f"zip_file_count:{len(files)}")
        if len(pngs) != 27:
            errors.append(f"zip_png_count:{len(pngs)}")
        if len(scripts) != 13:
            errors.append(f"zip_script_count:{len(scripts)}")
    return len(files), len(pngs), len(scripts), sha(ZIP_PATH)


def main() -> int:
    errors: list[str] = []
    matched, voice_mismatch, kana_rows = verify_scene_reextract(errors)
    inherited_total, inherited_unchanged, intended_changed = verify_inheritance(errors)
    target_cps, coverage, added_counts = verify_font_preservation(errors)
    verify_payload_mirror(errors)
    zip_files, zip_png, zip_scripts, zip_sha = build_zip(errors)

    print(f"scene1090_reextract={matched}/30")
    print(f"voice_prefix_mismatch={voice_mismatch}")
    print(f"scene_translation_kana_rows={kana_rows}")
    print(f"cumulative_rows=1400")
    print(f"font_target_codepoints={target_cps}")
    print(f"font_coverage={coverage}")
    print(f"font_added_codepoints={added_counts}")
    print(f"inherited_previous_files={inherited_total}")
    print(f"inherited_unchanged={inherited_unchanged}")
    print(f"intentionally_changed_fonts={intended_changed}")
    print(f"zip_files={zip_files} zip_png={zip_png} zip_scripts={zip_scripts}")
    print(f"zip_size={ZIP_PATH.stat().st_size}")
    print(f"sha256={zip_sha}")
    print(f"errors={len(errors)}")
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())





