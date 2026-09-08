#!/usr/bin/env python3
"""Build PC-original-Japanese -> Switch-Japanese alignment, carrying PC Chinese by index.

Only scenes whose original-JP and translated-CN GSC files have identical raw
string counts are emitted here.  Count-mismatch scenes are deliberately left
for separate handling.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NS_TSV = ROOT / "03_text" / "ns_extracted" / "ns-strings-v1.0.3.tsv"
V2_ALIGNMENT = ROOT / "03_text" / "matched" / "pc-ns-alignment-candidates-v2.tsv"
PC_JP_TSV = ROOT / "03_text" / "pc_extracted" / "pc-original-jp-gsc-strings.tsv"
PC_CN_TSV = ROOT / "03_text" / "pc_extracted" / "pc-gsc-strings.tsv"
OUT = ROOT / "03_text" / "matched" / "pc-ns-alignment-v3-jp.tsv"
SUMMARY = ROOT / "03_text" / "matched" / "scene-alignment-summary-v3-jp.tsv"

# The translated PC GSCs below contain a few extra Chinese-only strings, but
# the original strings themselves remain in order.  Values are
# (first_original_index_after_insertion, cumulative_CN_index_shift).
RAW_INDEX_SHIFTS: dict[str, tuple[int, int]] = {
    "3160": (111, 6),
    "3170": (137, 4),
    "3190": (3, 2),
    "3250": (152, 3),
    "3260": (60, 3),
    "4351": (11, 1),
    "4440": (116, 1),
}

SCENE_RE = re.compile(r"^Script/scr(\d+)\.binu8$")
VOICE_RE = re.compile(r"^@v{2,3}[A-Za-z0-9]+")
NS_RUBY_RE = re.compile(r"@r([^@]+)@[^@]+@")
PC_RUBY_RE = re.compile(r"\|([^\[]+)\[[^\]]*\]")
JP_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
ASCII_RESOURCE_RE = re.compile(
    r"(?:"
    r"(?:se|bgm|cutin|grpo|grpe|visual|movie|voice|face)[A-Za-z0-9_.\-]*"
    r"|[A-Za-z0-9_.\-]+\.(?:png|jpg|jpeg|opus|mp4|spm|fil|fnt|bnsh|wcg|lwg)"
    r"|[A-Za-z_][A-Za-z0-9_@ .\-]*"
    r"|\d+"
    r")$", re.IGNORECASE,
)
QUOTE_PAIRS = (("「", "」"), ("『", "』"))
PUNCTUATION = set("。！？!?…、，,；;：:")


@dataclass
class Tok:
    scene: str
    kind: str
    text: str
    norm: str
    row: dict[str, str]
    filtered_index: int = -1


def normalize_ns(text: str) -> str:
    text = VOICE_RE.sub("", text)
    text = NS_RUBY_RE.sub(r"\1", text)
    text = text.replace("@n", "").replace("@p", "").replace("@k", "")
    return re.sub(r"\s+", "", text)


def normalize_pc_jp(text: str) -> str:
    text = PC_RUBY_RE.sub(r"\1", text)
    text = text.replace("^n", "")
    return re.sub(r"\s+", "", text)


def looks_resource(text: str) -> bool:
    if not text or "@関数内ローカル変数" in text:
        return True
    return bool(ASCII_RESOURCE_RE.fullmatch(text))


def fully_quoted(text: str) -> bool:
    t = text.strip()
    return any(t.startswith(a) and t.endswith(b) for a, b in QUOTE_PAIRS)


def short_speaker(text: str) -> bool:
    t = text.strip()
    if not t or len(t) > 18 or t.startswith(("「", "『")):
        return False
    if any(ch in t for ch in PUNCTUATION):
        return False
    return bool(JP_RE.search(t))


def trim_ns(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    for i, r in enumerate(rows):
        if r["text"] == "ReplayMode":
            return rows[:i]
    return rows


def classify_ns(scene: str, rows: list[dict[str, str]]) -> list[Tok]:
    rough: list[Tok] = []
    for r in trim_ns(rows):
        text = r["text"]
        norm = normalize_ns(text)
        if looks_resource(norm):
            continue
        if VOICE_RE.match(text) or fully_quoted(norm):
            kind = "D"
        elif JP_RE.search(norm):
            kind = "N"
        else:
            continue
        rough.append(Tok(scene, kind, text, norm, r))
    out: list[Tok] = []
    for i, t in enumerate(rough):
        if t.kind == "N" and short_speaker(t.norm) and i + 1 < len(rough) and rough[i + 1].kind == "D":
            continue
        out.append(t)
    for i, t in enumerate(out):
        t.filtered_index = i
    return out


def classify_pc_jp(scene: str, rows: list[dict[str, str]]) -> list[Tok]:
    rough: list[Tok] = []
    for r in rows:
        text = r["text"].strip()
        norm = normalize_pc_jp(text)
        if looks_resource(norm):
            continue
        if fully_quoted(norm):
            kind = "D"
        elif JP_RE.search(norm):
            kind = "N"
        else:
            continue
        rough.append(Tok(scene, kind, text, norm, r))
    out: list[Tok] = []
    for i, t in enumerate(rough):
        if t.kind == "N" and short_speaker(t.norm) and i + 1 < len(rough) and rough[i + 1].kind == "D":
            continue
        out.append(t)
    for i, t in enumerate(out):
        t.filtered_index = i
    return out


def similarity(a: Tok, b: Tok) -> float:
    if not a.norm or not b.norm:
        return 0.0
    if a.norm == b.norm:
        return 1.0
    return SequenceMatcher(None, a.norm, b.norm, autojunk=False).ratio()


def match_cost(a: Tok, b: Tok) -> tuple[float, float]:
    sim = similarity(a, b)
    cost = (1.0 - sim) * 3.0
    if a.kind != b.kind:
        cost += 1.2
    return cost, sim


def align(ns: list[Tok], pc: list[Tok]):
    n, m = len(ns), len(pc)
    gap = 0.82
    inf = 1e12
    dp = [[inf] * (m + 1) for _ in range(n + 1)]
    bt = [[""] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(1, n + 1):
        dp[i][0] = i * gap; bt[i][0] = "U"
    for j in range(1, m + 1):
        dp[0][j] = j * gap; bt[0][j] = "L"
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            c, _ = match_cost(ns[i-1], pc[j-1])
            opts = ((dp[i-1][j-1] + c, "M"), (dp[i-1][j] + gap, "U"), (dp[i][j-1] + gap, "L"))
            dp[i][j], bt[i][j] = min(opts, key=lambda x: x[0])
    out = []
    i, j = n, m
    while i or j:
        op = bt[i][j]
        if op == "M":
            c, sim = match_cost(ns[i-1], pc[j-1])
            out.append((ns[i-1], pc[j-1], c, sim)); i -= 1; j -= 1
        elif op == "U":
            out.append((ns[i-1], None, gap, 0.0)); i -= 1
        elif op == "L":
            out.append((None, pc[j-1], gap, 0.0)); j -= 1
        else:
            raise RuntimeError((i, j, op))
    out.reverse()
    return out, dp[n][m]


def main() -> int:
    # Reuse the exact NS story-token set/indexing established by v2 so v3 only
    # changes PC-side alignment quality, never the project's NS index scheme.
    ns_tokens_by: dict[str, dict[int, Tok]] = defaultdict(dict)
    with V2_ALIGNMENT.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if not r["ns_filtered_index"]:
                continue
            scene = r["scene"]
            idx = int(r["ns_filtered_index"])
            if idx in ns_tokens_by[scene]:
                continue
            source = r["ns_source"]
            ns_tokens_by[scene][idx] = Tok(
                scene=scene,
                kind=r["ns_kind"],
                text=source,
                norm=normalize_ns(source),
                row={
                    "file": r["ns_file"],
                    "length_offset": r["ns_length_offset"],
                    "text_offset": r["ns_text_offset"],
                },
                filtered_index=idx,
            )

    jp_by: dict[str, list[dict[str, str]]] = defaultdict(list)
    cn_by: dict[str, list[dict[str, str]]] = defaultdict(list)
    with PC_JP_TSV.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            jp_by[r["scene"]].append(r)
    with PC_CN_TSV.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            cn_by[r["scene"]].append(r)

    safe_scenes = sorted(
        s for s in set(ns_tokens_by) & set(jp_by) & set(cn_by)
        if len(jp_by[s]) > 0
        and (len(jp_by[s]) == len(cn_by[s]) or s in RAW_INDEX_SHIFTS)
    )
    cn_index = {(r["scene"], int(r["string_index"])): r for rows in cn_by.values() for r in rows}

    def cn_raw_index(scene: str, jp_raw_index: int) -> int:
        threshold_shift = RAW_INDEX_SHIFTS.get(scene)
        if threshold_shift is None:
            return jp_raw_index
        threshold, shift = threshold_shift
        return jp_raw_index + (shift if jp_raw_index >= threshold else 0)

    fields = [
        "scene", "status", "reason", "similarity", "pair_cost",
        "ns_filtered_index", "pc_filtered_index", "ns_file", "ns_length_offset",
        "ns_text_offset", "ns_source", "ns_kind", "pc_file", "pc_string_index",
        "pc_jp_source", "pc_translation", "pc_kind",
    ]
    sum_fields = [
        "scene", "ns_story_tokens", "pc_story_tokens", "paired", "ns_gaps", "pc_gaps",
        "exact", "high", "review", "weak_pairs", "alignment_score",
    ]
    summaries = []
    counts = Counter()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for scene in safe_scenes:
            ns = [ns_tokens_by[scene][i] for i in sorted(ns_tokens_by[scene])]
            pc = classify_pc_jp(scene, jp_by[scene])
            aligned, score = align(ns, pc)
            stats = Counter()
            for a, b, cost, sim in aligned:
                if a is None:
                    status, reason = "pc-only", "no-ns-pair"; stats["pc_gaps"] += 1
                elif b is None:
                    status, reason = "unmatched-ns", "no-pc-pair"; stats["ns_gaps"] += 1
                else:
                    stats["paired"] += 1
                    if sim >= 0.999999:
                        status, reason = "exact-jp", "normalized-japanese-exact"; stats["exact"] += 1
                    elif sim >= 0.86 and a.kind == b.kind:
                        status, reason = "high-jp", "japanese-similarity>=0.86"; stats["high"] += 1
                    elif sim >= 0.62:
                        status, reason = "review-jp", "japanese-similarity>=0.62"; stats["review"] += 1
                    else:
                        status, reason = "weak-pair", "japanese-similarity<0.62"; stats["weak_pairs"] += 1
                counts[status] += 1
                cn = None
                if b is not None:
                    jp_raw = int(b.row["string_index"])
                    cn_raw = cn_raw_index(scene, jp_raw)
                    cn = cn_index.get((scene, cn_raw))
                    if cn is None:
                        raise ValueError(f"missing CN row {scene}: JP={jp_raw} CN={cn_raw}")
                w.writerow({
                    "scene": scene, "status": status, "reason": reason,
                    "similarity": "" if a is None or b is None else f"{sim:.6f}",
                    "pair_cost": "" if a is None or b is None else f"{cost:.6f}",
                    "ns_filtered_index": "" if a is None else a.filtered_index,
                    "pc_filtered_index": "" if b is None else b.filtered_index,
                    "ns_file": "" if a is None else a.row["file"],
                    "ns_length_offset": "" if a is None else a.row["length_offset"],
                    "ns_text_offset": "" if a is None else a.row["text_offset"],
                    "ns_source": "" if a is None else a.text,
                    "ns_kind": "" if a is None else a.kind,
                    "pc_file": "" if b is None else b.row["file"],
                    "pc_string_index": "" if b is None else b.row["string_index"],
                    "pc_jp_source": "" if b is None else b.text,
                    "pc_translation": "" if cn is None else cn["text"],
                    "pc_kind": "" if b is None else b.kind,
                })
            summaries.append({
                "scene": scene, "ns_story_tokens": len(ns), "pc_story_tokens": len(pc),
                "paired": stats["paired"], "ns_gaps": stats["ns_gaps"], "pc_gaps": stats["pc_gaps"],
                "exact": stats["exact"], "high": stats["high"], "review": stats["review"],
                "weak_pairs": stats["weak_pairs"], "alignment_score": f"{score:.4f}",
            })
    with SUMMARY.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sum_fields, delimiter="\t", lineterminator="\n")
        w.writeheader(); w.writerows(summaries)
    print(f"safe_scenes={len(safe_scenes)}")
    print(f"status_counts={dict(counts)}")
    print(f"ns_rows={sum(int(r['ns_story_tokens']) for r in summaries)}")
    print(f"exact_or_high={sum(int(r['exact'])+int(r['high']) for r in summaries)}")
    print(f"review={sum(int(r['review']) for r in summaries)}")
    print(f"weak_pairs={sum(int(r['weak_pairs']) for r in summaries)}")
    print(f"ns_gaps={sum(int(r['ns_gaps']) for r in summaries)}")
    print(f"output={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
