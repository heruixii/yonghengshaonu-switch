#!/usr/bin/env python3
"""Validate and emit direct translations for the 368 v3 uncertain NS rows."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from v3_direct_part1 import T as T1
from v3_direct_part2 import T as T2


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "03_text" / "translated" / "v3-new-direct-needed.tsv"
OUTPUT = ROOT / "03_text" / "translated" / "v3-new-direct-translations.tsv"
VOICE_RE = re.compile(r"^(@v{2,3}[A-Za-z0-9]+)")
KANA_RE = re.compile(r"[\u3040-\u30ff]")
STRICT_TOKEN_RE = re.compile(r"@(?:p|k)(?![A-Za-z0-9_])")


def main() -> int:
    T = dict(T1)
    overlap = set(T1) & set(T2)
    if overlap:
        raise ValueError(f"translation map overlap: {sorted(overlap)}")
    T.update(T2)

    with SOURCE.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    keys = {(r["scene"], int(r["ns_filtered_index"])) for r in rows}
    if keys != set(T):
        missing = sorted(keys - set(T))
        extra = sorted(set(T) - keys)
        raise ValueError(f"translation key mismatch: missing={missing} extra={extra}")

    out = []
    kana_rows = 0
    for r in rows:
        key = (r["scene"], int(r["ns_filtered_index"]))
        source = r["ns_source"]
        translation = T[key]

        sv = VOICE_RE.match(source)
        tv = VOICE_RE.match(translation)
        if (sv.group(1) if sv else None) != (tv.group(1) if tv else None):
            raise ValueError(f"voice mismatch {key}: {source!r} -> {translation!r}")

        # @p and @k affect flow/interaction and must remain in the same order.
        sc = STRICT_TOKEN_RE.findall(source)
        tc = STRICT_TOKEN_RE.findall(translation)
        if sc != tc:
            raise ValueError(f"strict-control mismatch {key}: {sc} != {tc}")
        # Keep explicit NS line/page layout in direct translations as well.
        if source.count("@n") != translation.count("@n"):
            raise ValueError(
                f"@n count mismatch {key}: {source.count('@n')} != {translation.count('@n')}"
            )

        if KANA_RE.search(translation):
            kana_rows += 1
            raise ValueError(f"Japanese kana residue {key}: {translation!r}")
        out.append({**r, "translation": translation})

    fields = list(rows[0].keys()) + ["translation"]
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        w.writeheader(); w.writerows(out)

    print(f"rows={len(out)}")
    print(f"part1={len(T1)} part2={len(T2)}")
    print(f"kana_rows={kana_rows}")
    print(f"output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
