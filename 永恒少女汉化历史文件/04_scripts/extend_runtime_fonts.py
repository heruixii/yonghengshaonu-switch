#!/usr/bin/env python3
"""Incrementally add missing Chinese glyphs to the repaired runtime TTCs.

The project runtime fonts have already had their malformed format-4 cmaps
normalized.  This tool therefore starts from a known-good build font, preserves
all existing glyphs/tables, and adds only codepoints actually required by the
current cumulative translations.

Source glyphs are decomposed before copying, so composite references from the
Windows source font cannot leak into the game TTC.  Outlines and horizontal /
vertical metrics are scaled from source UPM to each destination UPM.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTCollection


FONT_NAMES = ["dfgotp5.ttc", "dfhsr4.ttc", "dfmrg5_u.ttc"]


def unicode_cmap(font) -> dict[int, str]:
    cmap: dict[int, str] = {}
    for table in font["cmap"].tables:
        if table.isUnicode():
            cmap.update(table.cmap)
    return cmap


def collect_codepoints(path: Path) -> set[int]:
    chars: set[int] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            for field in ("source", "translation"):
                chars.update(ord(ch) for ch in row.get(field, "") if ord(ch) > 127)
    return chars


def copy_glyph(src_font, src_name: str, dst_font, dst_name: str) -> None:
    src_upem = src_font["head"].unitsPerEm
    dst_upem = dst_font["head"].unitsPerEm
    scale = dst_upem / src_upem

    # Decompose components recursively so no source-font component glyph names
    # are required in the destination font.
    src_glyph_set = src_font.getGlyphSet()
    recording = DecomposingRecordingPen(src_glyph_set)
    src_glyph_set[src_name].draw(recording)
    tt_pen = TTGlyphPen(None)
    recording.replay(TransformPen(tt_pen, (scale, 0, 0, scale, 0, 0)))
    dst_font["glyf"].glyphs[dst_name] = tt_pen.glyph()

    advance, lsb = src_font["hmtx"].metrics[src_name]
    dst_font["hmtx"].metrics[dst_name] = (round(advance * scale), round(lsb * scale))

    if "vmtx" in src_font and "vmtx" in dst_font:
        advance_h, tsb = src_font["vmtx"].metrics[src_name]
        dst_font["vmtx"].metrics[dst_name] = (round(advance_h * scale), round(tsb * scale))


def add_mapping(dst_font, cp: int, glyph_name: str) -> None:
    for table in dst_font["cmap"].tables:
        if not table.isUnicode():
            continue
        if table.format == 4 and cp > 0xFFFF:
            continue
        table.cmap[cp] = glyph_name


def extend_one(
    src_font,
    src_cmap: dict[int, str],
    input_path: Path,
    output_path: Path,
    target_cps: set[int],
    glyph_prefix: str,
) -> list[int]:
    collection = TTCollection(str(input_path))
    added_union: set[int] = set()

    for face_index, dst_font in enumerate(collection.fonts):
        current = unicode_cmap(dst_font)
        missing = sorted(cp for cp in target_cps if cp not in current)
        for cp in missing:
            src_name = src_cmap.get(cp)
            if src_name is None:
                raise ValueError(f"source font missing U+{cp:04X}")

            dst_name = f"{glyph_prefix}_u{cp:04X}"
            order = dst_font.getGlyphOrder()
            if dst_name in order:
                raise ValueError(f"unexpected existing glyph name {dst_name} in {input_path} face {face_index}")
            order.append(dst_name)
            dst_font.setGlyphOrder(order)
            copy_glyph(src_font, src_name, dst_font, dst_name)
            add_mapping(dst_font, cp, dst_name)
            added_union.add(cp)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    collection.save(str(output_path))
    return sorted(added_union)


def verify_font(path: Path, target_cps: set[int]) -> list[int]:
    collection = TTCollection(str(path))
    missing_per_face: list[int] = []
    for font in collection.fonts:
        cmap = unicode_cmap(font)
        missing_per_face.append(sum(cp not in cmap for cp in target_cps))
    return missing_per_face


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-dir", required=True, type=Path, help="directory containing repaired TTC baseline")
    ap.add_argument("--translations", required=True, type=Path, help="cumulative translation TSV")
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--glyph-source", type=Path, default=Path(r"C:\Windows\Fonts\msyh.ttc"))
    ap.add_argument("--glyph-prefix", default="v009", help="prefix for newly appended glyph names")
    args = ap.parse_args()

    target_cps = collect_codepoints(args.translations)
    source_collection = TTCollection(str(args.glyph_source))
    src_font = source_collection.fonts[0]
    src_cmap = unicode_cmap(src_font)
    source_missing = sorted(cp for cp in target_cps if cp not in src_cmap)
    if source_missing:
        sample = " ".join(f"U+{cp:04X}" for cp in source_missing[:20])
        raise ValueError(f"glyph source missing {len(source_missing)} target codepoints: {sample}")

    print(f"target_codepoints={len(target_cps)}")
    print("glyph_source_missing=0")

    total_added = 0
    for name in FONT_NAMES:
        input_path = args.source_dir / name
        output_path = args.output_dir / name
        added = extend_one(src_font, src_cmap, input_path, output_path, target_cps, args.glyph_prefix)
        missing = verify_font(output_path, target_cps)
        if any(missing):
            raise ValueError(f"post-save font coverage failed: {name} {missing}")
        total_added += len(added)
        print(f"{name}\tadded_codepoints={len(added)}\tmissing_per_face={missing}")

    print(f"total_added_codepoints_across_fonts={total_added}")
    print("all_faces_missing=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
