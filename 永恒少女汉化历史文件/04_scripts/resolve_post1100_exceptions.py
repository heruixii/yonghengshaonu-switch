#!/usr/bin/env python3
"""Re-align post-1100 exception scenes between high-confidence anchors.

This is deliberately structural rather than linguistic: PC standalone speaker-name
rows are discarded, high-candidate rows are fixed anchors, and the remaining
tokens are aligned monotonically using kind, punctuation and relative length.
Unresolved NS rows are emitted for later direct translation.
"""

from __future__ import annotations

import csv
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALIGNMENT = ROOT / "03_text" / "matched" / "pc-ns-alignment-candidates-v2.tsv"
SUMMARY = ROOT / "03_text" / "matched" / "scene-alignment-summary-v2.tsv"
OUT_DIR = ROOT / "03_text" / "translated" / "bulk-post1100"
MAP_OUT = OUT_DIR / "exception-auto-map.tsv"
UNRESOLVED_OUT = OUT_DIR / "exception-unresolved-ns.tsv"

VOICE_RE = re.compile(r"^@v{2,3}\d+")
CTRL_RE = re.compile(r"@r[^@]*@[^@]*@|@v{2,3}\d+|@n")
PC_CTRL_RE = re.compile(r"\^n|\|([^\[]+)\[([^\]]+)\]")
PUNCT_RE = re.compile(r"[\s「」『』（）()，。！？!?、…—─・：:；;\-]|")

EXPLICIT_SPEAKERS = {
    "阿尔艾特", "玛可", "帕沃妮", "卡娜莉", "阿薇拉", "萝宾", "露珂", "阿德拉",
}


def visible_len(text: str) -> int:
    text = CTRL_RE.sub("", text)
    text = PC_CTRL_RE.sub(lambda m: m.group(1) or "", text)
    return max(1, len(re.sub(r"[\s「」『』（）()，。！？!?、…—─・：:；;]", "", text)))


def bracket_kind(text: str) -> str:
    t = VOICE_RE.sub("", text).lstrip()
    if t.startswith("（") or t.startswith("("):
        return "inner"
    if t.startswith("「") or t.startswith("『"):
        return "dialogue"
    return "narration"


def is_speaker(text: str, auto_speakers: set[str]) -> bool:
    return text.strip() in EXPLICIT_SPEAKERS | auto_speakers


def match_cost(ns: dict[str, str], pc: dict[str, str], ratio: float, v2_pairs: dict[int, int]) -> float:
    cost = 0.0
    if ns["ns_kind"] != pc["pc_kind"]:
        cost += 3.5
    nb = bracket_kind(ns["ns_source"])
    pb = bracket_kind(pc["pc_translation"])
    if nb != pb:
        if {nb, pb} <= {"dialogue", "inner"}:
            cost += 0.8
        else:
            cost += 2.2
    nr = visible_len(ns["ns_source"])
    pr = visible_len(pc["pc_translation"])
    observed = pr / nr
    if ratio > 0 and observed > 0:
        cost += min(3.0, abs(math.log(observed / ratio)))
    ni = int(ns["ns_filtered_index"])
    pi = int(pc["pc_filtered_index"])
    if v2_pairs.get(ni) == pi:
        cost -= 0.9
    return cost


def align_segment(
    ns_items: list[dict[str, str]],
    pc_items: list[dict[str, str]],
    ratio: float,
    v2_pairs: dict[int, int],
) -> tuple[list[tuple[dict[str, str], dict[str, str] | None, float]], list[dict[str, str]]]:
    n, m = len(ns_items), len(pc_items)
    inf = 10**9
    dp = [[inf] * (m + 1) for _ in range(n + 1)]
    prev: list[list[tuple[int, int, str, float] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            cur = dp[i][j]
            if cur >= inf:
                continue
            if i < n and j < m:
                c = match_cost(ns_items[i], pc_items[j], ratio, v2_pairs)
                if cur + c < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1] = cur + c
                    prev[i + 1][j + 1] = (i, j, "match", c)
            if j < m:
                # PC-only content is possible across versions; skipping is cheaper
                # than forcing a type-incompatible match.
                c = 1.55
                if cur + c < dp[i][j + 1]:
                    dp[i][j + 1] = cur + c
                    prev[i][j + 1] = (i, j, "skip_pc", c)
            if i < n:
                c = 2.15
                if cur + c < dp[i + 1][j]:
                    dp[i + 1][j] = cur + c
                    prev[i + 1][j] = (i, j, "skip_ns", c)

    aligned: list[tuple[dict[str, str], dict[str, str] | None, float]] = []
    skipped_pc: list[dict[str, str]] = []
    i, j = n, m
    while i or j:
        step = prev[i][j]
        if step is None:
            raise RuntimeError(f"broken DP backtrace n={n} m={m} at {i},{j}")
        pi, pj, op, c = step
        if op == "match":
            aligned.append((ns_items[pi], pc_items[pj], c))
        elif op == "skip_ns":
            aligned.append((ns_items[pi], None, c))
        else:
            skipped_pc.append(pc_items[pj])
        i, j = pi, pj
    aligned.reverse()
    skipped_pc.reverse()
    return aligned, skipped_pc


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with SUMMARY.open("r", encoding="utf-8-sig", newline="") as f:
        summary = list(csv.DictReader(f, delimiter="\t"))
    exception_scenes = {
        r["scene"] for r in summary
        if r["scene"].isdigit() and int(r["scene"]) > 1100 and int(r["ns_story_tokens"]) > 0
        and (int(r["ns_gaps"]) or int(r["pc_gaps"]) or int(r["review"]))
    }

    by_scene: dict[str, list[dict[str, str]]] = defaultdict(list)
    pc_only_short = defaultdict(int)
    with ALIGNMENT.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["scene"] in exception_scenes:
                by_scene[row["scene"]].append(row)
                if row["status"] == "pc-only":
                    t = row["pc_translation"].strip()
                    if 1 <= len(t) <= 8 and re.fullmatch(r"[\u3400-\u9fffA-Za-z0-9・]+", t):
                        pc_only_short[t] += 1
    auto_speakers = {t for t, count in pc_only_short.items() if count >= 3}

    map_rows: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    totals = defaultdict(int)

    for scene in sorted(exception_scenes, key=int):
        rows = by_scene[scene]
        ns_by_idx: dict[int, dict[str, str]] = {}
        pc_by_idx: dict[int, dict[str, str]] = {}
        v2_pairs: dict[int, int] = {}
        high_pairs: dict[int, int] = {}
        ratios = []
        for r in rows:
            if r["ns_filtered_index"]:
                ns_by_idx[int(r["ns_filtered_index"])] = r
            if r["pc_filtered_index"]:
                pc_by_idx[int(r["pc_filtered_index"])] = r
            if r["ns_filtered_index"] and r["pc_filtered_index"]:
                ni, pi = int(r["ns_filtered_index"]), int(r["pc_filtered_index"])
                v2_pairs[ni] = pi
                if r["status"] == "high-candidate":
                    high_pairs[ni] = pi
                    ratios.append(visible_len(r["pc_translation"]) / visible_len(r["ns_source"]))

        ratio = statistics.median(ratios) if ratios else 0.55
        ns_count = max(ns_by_idx) + 1 if ns_by_idx else 0
        pc_count = max(pc_by_idx) + 1 if pc_by_idx else 0
        anchors = [(-1, -1)] + sorted(high_pairs.items()) + [(ns_count, pc_count)]
        scene_mapped: dict[int, tuple[int | None, float, str]] = {}

        for ni, pi in high_pairs.items():
            scene_mapped[ni] = (pi, 0.0, "high-anchor")

        for (n0, p0), (n1, p1) in zip(anchors, anchors[1:]):
            ns_seg = [ns_by_idx[i] for i in range(n0 + 1, n1) if i in ns_by_idx and i not in high_pairs]
            pc_seg_all = [pc_by_idx[j] for j in range(p0 + 1, p1) if j in pc_by_idx]
            pc_seg = [p for p in pc_seg_all if not is_speaker(p["pc_translation"], auto_speakers)]
            aligned, _ = align_segment(ns_seg, pc_seg, ratio, v2_pairs)
            for ns, pc, cost in aligned:
                ni = int(ns["ns_filtered_index"])
                if pc is None:
                    scene_mapped[ni] = (None, cost, "unresolved")
                else:
                    pi = int(pc["pc_filtered_index"])
                    # A kind mismatch alone can add 3.5 even when sequence and
                    # visible punctuation clearly identify the corresponding PC
                    # line. Keep the monotonic DP result; only explicit skips
                    # remain unresolved for direct NS translation.
                    tag = "v2-review" if v2_pairs.get(ni) == pi else "auto-realigned"
                    if cost >= 3.15:
                        tag += "+kind-mismatch"
                    scene_mapped[ni] = (pi, cost, tag)

        for ni in range(ns_count):
            ns = ns_by_idx[ni]
            pi, cost, status = scene_mapped.get(ni, (None, 9.9, "unresolved-missing"))
            if pi is None:
                unresolved.append({
                    "scene": scene,
                    "ns_filtered_index": str(ni),
                    "ns_file": ns["ns_file"],
                    "ns_length_offset": ns["ns_length_offset"],
                    "ns_text_offset": ns["ns_text_offset"],
                    "ns_source": ns["ns_source"],
                    "ns_kind": ns["ns_kind"],
                    "reason": status,
                    "cost": f"{cost:.4f}",
                })
                totals["unresolved"] += 1
                continue
            pc = pc_by_idx[pi]
            map_rows.append({
                "scene": scene,
                "ns_filtered_index": str(ni),
                "ns_file": ns["ns_file"],
                "ns_length_offset": ns["ns_length_offset"],
                "ns_text_offset": ns["ns_text_offset"],
                "ns_source": ns["ns_source"],
                "ns_kind": ns["ns_kind"],
                "pc_filtered_index": str(pi),
                "pc_file": pc["pc_file"],
                "pc_string_index": pc["pc_string_index"],
                "pc_translation": pc["pc_translation"],
                "pc_kind": pc["pc_kind"],
                "map_status": status,
                "cost": f"{cost:.4f}",
            })
            totals[status] += 1

    map_fields = [
        "scene", "ns_filtered_index", "ns_file", "ns_length_offset", "ns_text_offset",
        "ns_source", "ns_kind", "pc_filtered_index", "pc_file", "pc_string_index",
        "pc_translation", "pc_kind", "map_status", "cost",
    ]
    with MAP_OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=map_fields, delimiter="\t", lineterminator="\n")
        w.writeheader(); w.writerows(map_rows)
    unresolved_fields = [
        "scene", "ns_filtered_index", "ns_file", "ns_length_offset", "ns_text_offset",
        "ns_source", "ns_kind", "reason", "cost",
    ]
    with UNRESOLVED_OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=unresolved_fields, delimiter="\t", lineterminator="\n")
        w.writeheader(); w.writerows(unresolved)

    print(f"exception_scenes={len(exception_scenes)}")
    print(f"auto_speakers={sorted(auto_speakers)}")
    print(f"mapped_rows={len(map_rows)}")
    print(f"unresolved_rows={len(unresolved)}")
    for key in sorted(totals):
        print(f"{key}={totals[key]}")
    print(f"map={MAP_OUT}")
    print(f"unresolved={UNRESOLVED_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
