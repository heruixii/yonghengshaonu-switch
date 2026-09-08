#!/usr/bin/env python3
"""Full re-extraction and font-preservation QA for the final v3 text payload."""

from __future__ import annotations

import csv
import re
import struct
from collections import defaultdict
from pathlib import Path

from fontTools.ttLib import TTCollection


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "02_romfs" / "merged-v1.0.3"
RENDERED = ROOT / "03_text" / "rendered-final-v3"
CUMULATIVE = ROOT / "03_text" / "translated" / "final-all-text-v3-cumulative.tsv"
OLD_FONT_DIR = ROOT / "05_build" / "v015-scene1100" / "romfs" / "System"
NEW_FONT_DIR = ROOT / "03_text" / "runtime-fonts-final-v3"
VERIFY_OUT = ROOT / "03_text" / "translated" / "final-v3-reextract.tsv"
FONT_OUT = ROOT / "03_text" / "translated" / "final-v3-font-coverage.tsv"
FONT_NAMES = ["dfgotp5.ttc", "dfhsr4.ttc", "dfmrg5_u.ttc"]

VOICE_RE = re.compile(r"@v{2,3}\d+")
GENERIC_CONTROL_RE = re.compile(r"@[A-Za-z][A-Za-z0-9_]*")
RUBY_RE = re.compile(r"@r[^@]*@[^@]*@")
PC_RUBY_RE = re.compile(r"\|[^\[]+\[[^\]]*\]")
KANA_RE = re.compile(r"[\u3040-\u30ff]")


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


def verify_resources(rows: list[dict[str, str]], errors: list[str]) -> dict[str, int]:
    by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        by_file[r["file"]].append(r)

    verify_rows = []
    matched = source_bad = voice_bad = strict_bad = kana_bad = markup_bad = 0
    for rel, file_rows in sorted(by_file.items()):
        src_path = CLEAN / rel
        dst_path = RENDERED / rel
        if not src_path.is_file():
            errors.append(f"missing_clean:{rel}")
            continue
        if not dst_path.is_file():
            errors.append(f"missing_rendered:{rel}")
            continue
        src = src_path.read_bytes()
        dst = dst_path.read_bytes()
        shift = 0
        for r in sorted(file_rows, key=lambda x: int(x["length_offset"])):
            old_off = int(r["length_offset"])
            old_stored = struct.unpack_from("<I", src, old_off)[0]
            old_start = old_off + 4
            old_end = old_start + old_stored
            original = src[old_start:old_end-1].decode("utf-8")
            if original != r["source"]:
                source_bad += 1
                errors.append(f"source:{rel}:{old_off}")

            new_off = old_off + shift
            new_stored = struct.unpack_from("<I", dst, new_off)[0]
            new_start = new_off + 4
            new_end = new_start + new_stored
            actual = dst[new_start:new_end-1].decode("utf-8")
            target = r["translation"]
            ok = actual == target
            matched += int(ok)
            if not ok:
                errors.append(f"reextract:{rel}:{old_off}")

            sv, tv = VOICE_RE.findall(original), VOICE_RE.findall(actual)
            if sv != tv:
                voice_bad += 1
            if strict_controls(original) != strict_controls(actual):
                strict_bad += 1
            no_ruby = RUBY_RE.sub("", actual)
            if "@r" in no_ruby or "^n" in actual or PC_RUBY_RE.search(actual):
                markup_bad += 1
            if KANA_RE.search(actual):
                kana_bad += 1

            verify_rows.append([
                rel, r["length_offset"], new_off, r.get("scene", ""),
                r.get("ns_filtered_index", ""), "1" if ok else "0", actual,
            ])
            old_record = 4 + old_stored
            new_record = 4 + new_stored
            shift += new_record - old_record

    if source_bad: errors.append(f"source_bad:{source_bad}")
    if voice_bad: errors.append(f"voice_bad:{voice_bad}")
    if strict_bad: errors.append(f"strict_bad:{strict_bad}")
    if kana_bad: errors.append(f"kana_bad:{kana_bad}")
    if markup_bad: errors.append(f"markup_bad:{markup_bad}")

    with VERIFY_OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["file", "original_offset", "patched_offset", "scene", "ns_filtered_index", "match", "translation"])
        w.writerows(verify_rows)

    return {
        "files": len(by_file), "rows": len(rows), "matched": matched,
        "source_bad": source_bad, "voice_bad": voice_bad, "strict_bad": strict_bad,
        "kana_bad": kana_bad, "markup_bad": markup_bad,
    }


def verify_fonts(rows: list[dict[str, str]], errors: list[str]):
    cps = collect_target_cps(rows)
    coverage = {}
    added = {}
    audit = []
    for name in FONT_NAMES:
        old_coll = TTCollection(str(OLD_FONT_DIR / name))
        new_coll = TTCollection(str(NEW_FONT_DIR / name))
        if len(old_coll.fonts) != len(new_coll.fonts):
            errors.append(f"font_face_count:{name}")
            continue
        miss_faces = []
        added_set = set()
        for face, (old, new) in enumerate(zip(old_coll.fonts, new_coll.fonts)):
            old_order, new_order = old.getGlyphOrder(), new.getGlyphOrder()
            if new_order[:len(old_order)] != old_order:
                errors.append(f"glyph_order:{name}:{face}")
            old_cmap, new_cmap = unicode_cmap(old), unicode_cmap(new)
            cmap_changed = sum(new_cmap.get(cp) != glyph for cp, glyph in old_cmap.items())
            hmtx_changed = sum(old["hmtx"].metrics[g] != new["hmtx"].metrics[g] for g in old_order)
            vmtx_changed = 0
            if "vmtx" in old and "vmtx" in new:
                vmtx_changed = sum(old["vmtx"].metrics[g] != new["vmtx"].metrics[g] for g in old_order)
            glyf_changed = 0
            for g in old_order:
                ob = old["glyf"][g].compile(old["glyf"], recalcBBoxes=False)
                nb = new["glyf"][g].compile(new["glyf"], recalcBBoxes=False)
                glyf_changed += ob != nb
            if cmap_changed or hmtx_changed or vmtx_changed or glyf_changed:
                errors.append(
                    f"font_existing_changed:{name}:{face}:c{cmap_changed}:h{hmtx_changed}:v{vmtx_changed}:g{glyf_changed}"
                )
            missing = sum(cp not in new_cmap for cp in cps)
            miss_faces.append(missing)
            added_set.update(cp for cp in cps if cp not in old_cmap and cp in new_cmap)
            audit.append([
                name, face, len(old_order), len(new_order), len(new_order)-len(old_order),
                missing, cmap_changed, hmtx_changed, vmtx_changed, glyf_changed,
            ])
        coverage[name] = miss_faces
        added[name] = len(added_set)
        if any(miss_faces):
            errors.append(f"font_coverage:{name}:{miss_faces}")

    with FONT_OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow([
            "font", "face", "old_glyphs", "new_glyphs", "added_glyphs", "missing_target",
            "changed_cmap", "changed_hmtx", "changed_vmtx", "changed_glyf",
        ])
        w.writerows(audit)
    return len(cps), coverage, added


def main() -> int:
    with CUMULATIVE.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    errors = []
    if len(rows) != 14178:
        errors.append(f"cumulative_rows:{len(rows)}")
    resource = verify_resources(rows, errors)
    target_cps, coverage, added = verify_fonts(rows, errors)
    print(f"resource_files={resource['files']}")
    print(f"resource_rows={resource['rows']}")
    print(f"reextract_match={resource['matched']}/{resource['rows']}")
    print(f"source_bad={resource['source_bad']} voice_bad={resource['voice_bad']} strict_bad={resource['strict_bad']}")
    print(f"kana_bad={resource['kana_bad']} markup_bad={resource['markup_bad']}")
    print(f"font_target_codepoints={target_cps}")
    print(f"font_coverage={coverage}")
    print(f"font_added_codepoints={added}")
    print(f"errors={len(errors)}")
    for e in errors[:100]:
        print(f"ERROR\t{e}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
