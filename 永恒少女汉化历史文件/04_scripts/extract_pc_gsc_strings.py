#!/usr/bin/env python3
"""Extract GBK strings from CodeX RScript/Liar-soft .gsc files.

The PC Chinese release used by this project stores translated script strings
in the GSC string pool using GBK.  Integers in the GSC header and declaration
table are little-endian 32-bit values.
"""

from __future__ import annotations

import argparse
import csv
import struct
from pathlib import Path


def read_i32(data: bytes, offset: int) -> tuple[int, int]:
    if offset + 4 > len(data):
        raise ValueError(f"unexpected EOF reading int32 at 0x{offset:X}")
    return struct.unpack_from("<i", data, offset)[0], offset + 4


def parse_gsc(path: Path, encoding: str) -> tuple[dict[str, int], list[dict[str, object]]]:
    data = path.read_bytes()
    pos = 0

    file_length, pos = read_i32(data, pos)
    header_length, pos = read_i32(data, pos)
    command_length, pos = read_i32(data, pos)
    decl_length, pos = read_i32(data, pos)
    def_length, pos = read_i32(data, pos)

    if header_length < 20 or header_length % 4:
        raise ValueError(f"invalid header length {header_length}")
    if file_length != len(data):
        raise ValueError(f"header file length {file_length} != actual {len(data)}")

    # Remaining optional header fields are not needed for extraction.
    pos = header_length
    command_end = pos + command_length
    if command_end > len(data):
        raise ValueError("command section exceeds file")
    pos = command_end

    # Declaration begins with two int32 values (normally 0 and 1), followed
    # by cumulative end offsets for all strings except the last one.
    if pos + 8 > len(data):
        raise ValueError("missing string declaration header")
    pos += 8

    string_count = decl_length // 4 - 2 + 1
    if string_count < 0:
        raise ValueError(f"invalid string count derived from declaration length {decl_length}")

    cumulative_ends: list[int] = []
    for _ in range(max(0, string_count - 1)):
        value, pos = read_i32(data, pos)
        cumulative_ends.append(value)
    if string_count:
        cumulative_ends.append(def_length)

    if pos >= len(data):
        raise ValueError("missing string-pool leading zero")
    pos += 1

    pool_start = pos
    previous_end = 1
    rows: list[dict[str, object]] = []
    decode_replacements = 0

    for index, cumulative_end in enumerate(cumulative_ends):
        byte_count = cumulative_end - previous_end - 1
        if byte_count < 0 or pos + byte_count >= len(data):
            raise ValueError(
                f"invalid string span index={index} previous={previous_end} end={cumulative_end}"
            )

        raw = data[pos : pos + byte_count]
        text_offset = pos
        pos += byte_count
        terminator = data[pos]
        pos += 1
        if terminator != 0:
            raise ValueError(f"string {index} missing NUL terminator")

        try:
            text = raw.decode(encoding, errors="strict")
            decode_ok = True
        except UnicodeDecodeError:
            text = raw.decode(encoding, errors="replace")
            decode_ok = False
            decode_replacements += 1

        rows.append(
            {
                "string_index": index,
                "text_offset": text_offset,
                "byte_length": len(raw),
                "decode_ok": "1" if decode_ok else "0",
                "text": text,
            }
        )
        previous_end = cumulative_end

    header = {
        "file_length": file_length,
        "header_length": header_length,
        "command_length": command_length,
        "string_declaration_length": decl_length,
        "string_definition_length": def_length,
        "string_count": string_count,
        "pool_start": pool_start,
        "decode_replacements": decode_replacements,
    }
    return header, rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract strings from PC Chinese GSC scripts.")
    ap.add_argument("gsc_dir", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--encoding", default="gbk")
    args = ap.parse_args()

    files = sorted(args.gsc_dir.glob("*.gsc"), key=lambda p: p.name.lower())
    if not files:
        raise SystemExit(f"no .gsc files found in {args.gsc_dir}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    total_strings = 0
    bad_decode = 0

    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "file",
                "scene",
                "string_index",
                "text_offset",
                "byte_length",
                "decode_ok",
                "text",
            ],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for path in files:
            header, rows = parse_gsc(path, args.encoding)
            total_strings += len(rows)
            bad_decode += header["decode_replacements"]
            for row in rows:
                writer.writerow(
                    {
                        "file": path.name,
                        "scene": path.stem,
                        **row,
                    }
                )

    print(f"files_scanned={len(files)}")
    print(f"strings_extracted={total_strings}")
    print(f"decode_replacements={bad_decode}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
