#!/usr/bin/env python3
"""Apply reviewed BINU8 translations to a LayeredFS-style work tree.

The writer intentionally permits removal/replacement of Japanese ruby markup
(@rDISPLAY@READING@), because Chinese text normally does not need the original
Japanese reading.  Voice controls and all other non-layout controls are kept
strictly intact.
"""

from __future__ import annotations

import argparse
import csv
import re
import struct
from pathlib import Path


VOICE_RE = re.compile(r"@v{2,3}\d+")
GENERIC_CONTROL_RE = re.compile(r"@[A-Za-z][A-Za-z0-9_]*")
RUBY_SPAN_RE = re.compile(r"@r[^@]*@[^@]*@")


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_record(data: bytes | bytearray, row: dict[str, str]) -> tuple[int, int, str]:
    length_offset = int(row["length_offset"])
    if length_offset < 0 or length_offset + 4 > len(data):
        raise ValueError(f"length offset out of range at {row['file']}:{length_offset}")
    stored_length = struct.unpack_from("<I", data, length_offset)[0]
    text_start = length_offset + 4
    text_end = text_start + stored_length
    if text_end > len(data) or stored_length < 1 or data[text_end - 1] != 0:
        raise ValueError(f"invalid string record at {row['file']}:{length_offset}")
    original = bytes(data[text_start : text_end - 1]).decode("utf-8")
    if original != row["source"]:
        raise ValueError(
            f"source mismatch at {row['file']}:{length_offset}: "
            f"expected {row['source']!r}, found {original!r}"
        )
    if row.get("stored_length") and int(row["stored_length"]) != stored_length:
        raise ValueError(f"stored length mismatch at {row['file']}:{length_offset}")
    if row.get("byte_length") and int(row["byte_length"]) != stored_length - 1:
        raise ValueError(f"byte length mismatch at {row['file']}:{length_offset}")
    return text_start, text_end, original


def strict_controls(text: str) -> list[str]:
    # Ruby is presentation markup and may be legitimately removed or replaced.
    text = RUBY_SPAN_RE.sub("", text)
    # @n is layout markup; PC and Switch can choose different line breaks.
    controls = [code for code in GENERIC_CONTROL_RE.findall(text) if code not in {"@n", "@r"}]
    return controls


def validate_replacement(original: str, translation: str, row: dict[str, str]) -> bytes:
    if "\x00" in translation:
        raise ValueError(f"NUL in translation at {row['file']}:{row['length_offset']}")
    if "^n" in translation or re.search(r"\|[^\[]+\[[^\]]*\]", translation):
        raise ValueError(f"unconverted PC markup at {row['file']}:{row['length_offset']}")

    original_voices = VOICE_RE.findall(original)
    translated_voices = VOICE_RE.findall(translation)
    if original_voices != translated_voices:
        raise ValueError(
            f"voice-control mismatch at {row['file']}:{row['length_offset']}: "
            f"{original_voices!r} != {translated_voices!r}"
        )
    if strict_controls(original) != strict_controls(translation):
        raise ValueError(
            f"strict-control mismatch at {row['file']}:{row['length_offset']}: "
            f"{strict_controls(original)!r} != {strict_controls(translation)!r}"
        )

    encoded = translation.encode("utf-8")
    return struct.pack("<I", len(encoded) + 1) + encoded + b"\0"


def apply_file(source: Path, target: Path, rows: list[dict[str, str]]) -> int:
    source_data = source.read_bytes()
    data = bytearray(source_data)
    edits: list[tuple[int, int, bytes, str]] = []
    seen_offsets: set[int] = set()

    for row in rows:
        translation = row.get("translation", "")
        if not translation:
            continue
        length_offset = int(row["length_offset"])
        if length_offset in seen_offsets:
            raise ValueError(f"duplicate offset at {row['file']}:{length_offset}")
        seen_offsets.add(length_offset)
        _text_start, text_end, original = read_record(source_data, row)
        replacement = validate_replacement(original, translation, row)
        edits.append((length_offset, text_end, replacement, translation))

    for start, end, replacement, _translation in sorted(edits, reverse=True):
        data[start:end] = replacement

    # Verify every edited record using its shifted post-write offset.
    for length_offset, _text_end, _replacement, translation in edits:
        shift = sum(
            len(other_replacement) - (other_end - other_start)
            for other_start, other_end, other_replacement, _other_translation in edits
            if other_start < length_offset
        )
        new_offset = length_offset + shift
        stored_length = struct.unpack_from("<I", data, new_offset)[0]
        start = new_offset + 4
        end = start + stored_length
        if end > len(data) or data[end - 1] != 0:
            raise ValueError(f"post-write record invalid at original offset {length_offset}")
        actual = bytes(data[start : end - 1]).decode("utf-8")
        if actual != translation:
            raise ValueError(f"post-write verification failed at original offset {length_offset}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return len(edits)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("romfs", type=Path)
    ap.add_argument("translations", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    root = args.romfs.resolve()
    rows = [row for row in load_rows(args.translations) if row.get("translation", "")]
    by_file: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_file.setdefault(row["file"], []).append(row)

    total = 0
    for relative, file_rows in by_file.items():
        source = root / Path(relative)
        target = args.output / Path(relative)
        if not source.is_file():
            raise FileNotFoundError(source)
        total += apply_file(source, target, file_rows)

    print(f"files_written={len(by_file)}")
    print(f"strings_written={total}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
