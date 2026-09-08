#!/usr/bin/env python3
"""Merge reviewed translation TSVs while rejecting duplicate game records."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    rows: list[dict[str, str]] = []
    fields: list[str] | None = None
    seen: set[tuple[str, str]] = set()
    counts: dict[str, int] = {}

    for path in args.inputs:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            if reader.fieldnames is None:
                raise ValueError(f"missing TSV header: {path}")
            if fields is None:
                fields = list(reader.fieldnames)
            elif list(reader.fieldnames) != fields:
                raise ValueError(f"header mismatch: {path}")
            count = 0
            for row in reader:
                key = (row["file"], row["length_offset"])
                if key in seen:
                    raise ValueError(f"duplicate translation record: {key}")
                seen.add(key)
                rows.append(row)
                count += 1
            counts[path.name] = count

    assert fields is not None
    rows.sort(key=lambda r: (r["file"].lower(), int(r["length_offset"])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"input_counts={counts}")
    print(f"rows_written={len(rows)}")
    print(f"unique_records={len(seen)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
