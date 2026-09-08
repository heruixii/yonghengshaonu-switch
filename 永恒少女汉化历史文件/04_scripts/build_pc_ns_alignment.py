#!/usr/bin/env python3
"""Build conservative PC-Chinese -> Switch-v1.0.3 scene alignment candidates.

This script DOES NOT modify game resources.  It consumes the two extraction
tables produced by this project and aligns story-bearing strings inside scenes
that share the same numeric scene id.

Important format differences handled here:
* Switch BINU8 embeds voice ids in dialogue (for example @vv10101...).
* Switch BINU8 interleaves SE/image/resource identifiers with story text.
* PC GSC stores speaker labels as separate string-pool rows before dialogue.
* PC GSC uses ^n for line breaks while Switch uses @n.
* Switch uses @rKANJI@READING@ ruby markup.

The output is a candidate/review table, not an automatic import table.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


SCENE_RE = re.compile(r"^Script/scr(\d+)\.binu8$")
VOICE_RE = re.compile(r"^@vv\d+")
RUBY_RE = re.compile(r"@r([^@]+)@[^@]+@")
JP_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
ASCII_RESOURCE_RE = re.compile(
    r"(?:"
    r"(?:se|bgm|cutin|grpo|grpe|visual|movie|voice|face)[A-Za-z0-9_.\-]*"
    r"|[A-Za-z0-9_.\-]+\.(?:png|jpg|jpeg|opus|mp4|spm|fil|fnt|bnsh|wcg|lwg)"
    r"|[A-Za-z_][A-Za-z0-9_@ .\-]*"
    r"|\d+"
    r")$",
    re.IGNORECASE,
)
PUNCTUATION = set("。！？!?…、，,；;：:")
QUOTE_STARTS = ("「", "『")
QUOTE_PAIRS = (("「", "」"), ("『", "』"))


@dataclass
class Token:
    side: str
    scene: str
    kind: str  # D=dialogue, N=narration/text
    text: str
    compare_text: str
    source_row: dict[str, str]
    filtered_index: int = -1


def normalize_ns_for_compare(text: str) -> str:
    text = VOICE_RE.sub("", text)
    text = RUBY_RE.sub(r"\1", text)
    text = text.replace("@n", "")
    return text.strip()


def normalize_pc_for_compare(text: str) -> str:
    text = text.replace("^n", "")
    # PC engine ruby: |display[reading].  Compare display text only.
    text = re.sub(r"\|([^\[]+)\[[^\]]*\]", r"\1", text)
    return text.strip()


def looks_like_resource(text: str) -> bool:
    if not text:
        return True
    if "@関数内ローカル変数" in text:
        return True
    if ASCII_RESOURCE_RE.fullmatch(text):
        return True
    return False


def is_short_speaker(text: str) -> bool:
    text = text.strip()
    if not text or len(text) > 18:
        return False
    if text in {"？？？", "???"}:
        return True
    if text.startswith(QUOTE_STARTS):
        return False
    if any(ch in text for ch in PUNCTUATION):
        return False
    # A speaker can be a name/pronoun in Chinese or Japanese; do not accept
    # ASCII resource identifiers here.
    return bool(JP_RE.search(text) or CJK_RE.search(text))


def is_fully_quoted(text: str) -> bool:
    text = text.strip()
    return any(text.startswith(left) and text.endswith(right) for left, right in QUOTE_PAIRS)


def trim_ns_story_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Cut common compiled-script helper tail at ReplayMode when present."""
    for i, row in enumerate(rows):
        if row["text"] == "ReplayMode":
            return rows[:i]
    return rows


def classify_ns(scene: str, rows: list[dict[str, str]]) -> list[Token]:
    rows = trim_ns_story_rows(rows)
    rough: list[Token] = []

    for row in rows:
        text = row["text"]
        compare = normalize_ns_for_compare(text)
        if looks_like_resource(compare):
            continue

        # @vv is an explicit Switch voice/dialogue marker.  Without @vv, only
        # treat a string as dialogue when the whole string is enclosed by a
        # quote pair.  A narration such as 「あの子」の薔薇色の肌へ... starts
        # with a quote but is not dialogue.
        if VOICE_RE.match(text) or is_fully_quoted(compare):
            kind = "D"
        elif JP_RE.search(compare):
            kind = "N"
        else:
            # Pure punctuation without a voice prefix is not a safe story row.
            continue

        rough.append(Token("ns", scene, kind, text, compare, row))

    # Remove explicit speaker rows only when their structural role is clear:
    # short text immediately followed by a dialogue token.
    result: list[Token] = []
    for i, token in enumerate(rough):
        if (
            token.kind == "N"
            and is_short_speaker(token.compare_text)
            and i + 1 < len(rough)
            and rough[i + 1].kind == "D"
        ):
            continue
        result.append(token)

    for i, token in enumerate(result):
        token.filtered_index = i
    return result


def classify_pc(scene: str, rows: list[dict[str, str]]) -> list[Token]:
    rough: list[Token] = []
    for row in rows:
        text = row["text"].strip()
        if looks_like_resource(text):
            continue
        compare = normalize_pc_for_compare(text)

        if is_fully_quoted(compare):
            kind = "D"
        elif CJK_RE.search(compare) or any(ch in compare for ch in "？？，。！？"):
            kind = "N"
        else:
            continue
        rough.append(Token("pc", scene, kind, text, compare, row))

    result: list[Token] = []
    for i, token in enumerate(rough):
        if (
            token.kind == "N"
            and is_short_speaker(token.compare_text)
            and i + 1 < len(rough)
            and rough[i + 1].kind == "D"
        ):
            continue
        result.append(token)

    for i, token in enumerate(result):
        token.filtered_index = i
    return result


def pair_cost(ns: Token, pc: Token) -> float:
    if ns.kind != pc.kind:
        return 7.5

    # Length is only a weak structural signal, but it is useful when deciding
    # which of two adjacent same-type strings absorbed/split text in a port.
    nlen = max(1, len(ns.compare_text))
    plen = max(1, len(pc.compare_text))
    observed_ratio = nlen / plen
    expected_jp_to_zh_ratio = 1.30
    length_penalty = abs(math.log(observed_ratio / expected_jp_to_zh_ratio))

    # Dialogue with dialogue is especially useful because voice-bearing NS
    # rows are unambiguous story records.
    type_bonus = -0.12 if ns.kind == "D" else 0.0
    return max(0.0, length_penalty + type_bonus)


def align_scene(ns_tokens: list[Token], pc_tokens: list[Token]):
    n, m = len(ns_tokens), len(pc_tokens)
    gap_cost = 1.70
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    bt = [[""] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = i * gap_cost
        bt[i][0] = "U"
    for j in range(1, m + 1):
        dp[0][j] = j * gap_cost
        bt[0][j] = "L"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            options = [
                (dp[i - 1][j - 1] + pair_cost(ns_tokens[i - 1], pc_tokens[j - 1]), "M"),
                (dp[i - 1][j] + gap_cost, "U"),
                (dp[i][j - 1] + gap_cost, "L"),
            ]
            dp[i][j], bt[i][j] = min(options, key=lambda x: x[0])

    aligned = []
    i, j = n, m
    while i or j:
        step = bt[i][j]
        if step == "M":
            c = pair_cost(ns_tokens[i - 1], pc_tokens[j - 1])
            aligned.append((ns_tokens[i - 1], pc_tokens[j - 1], c))
            i -= 1
            j -= 1
        elif step == "U":
            aligned.append((ns_tokens[i - 1], None, None))
            i -= 1
        elif step == "L":
            aligned.append((None, pc_tokens[j - 1], None))
            j -= 1
        else:
            raise RuntimeError(f"bad traceback state i={i} j={j}")

    aligned.reverse()
    return aligned, dp[n][m]


def local_confidence(aligned, index: int, cost: float | None) -> tuple[str, str]:
    if cost is None:
        return "unmatched", "gap"
    ns, pc, _ = aligned[index]
    if ns is None or pc is None or ns.kind != pc.kind:
        return "review", "type-mismatch"

    # Immediate continuity on BOTH sides is deliberately required for high
    # status (except at a true scene edge).  This prevents the row immediately
    # after a gap from inheriting a false high-confidence label.
    prev_good = False
    next_good = False
    if index > 0:
        a, b, c = aligned[index - 1]
        prev_good = a is not None and b is not None and c is not None and a.kind == b.kind and c <= 0.80
    if index + 1 < len(aligned):
        a, b, c = aligned[index + 1]
        next_good = a is not None and b is not None and c is not None and a.kind == b.kind and c <= 0.80

    left_ok = prev_good if index > 0 else True
    right_ok = next_good if index + 1 < len(aligned) else True
    if cost <= 0.55 and left_ok and right_ok:
        return "high-candidate", "type+length+bidirectional-continuity"
    if cost <= 0.95:
        return "review", "type+length"
    return "review", "weak-length-fit"


def load_tables(ns_path: Path, pc_path: Path):
    ns_by_scene: dict[str, list[dict[str, str]]] = defaultdict(list)
    pc_by_scene: dict[str, list[dict[str, str]]] = defaultdict(list)

    with ns_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            match = SCENE_RE.fullmatch(row["file"])
            if match:
                ns_by_scene[match.group(1)].append(row)

    with pc_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            pc_by_scene[row["scene"]].append(row)

    return ns_by_scene, pc_by_scene


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns", required=True, type=Path)
    ap.add_argument("--pc", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--summary", required=True, type=Path)
    args = ap.parse_args()

    ns_by_scene, pc_by_scene = load_tables(args.ns, args.pc)
    shared = sorted(set(ns_by_scene) & set(pc_by_scene))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)

    out_fields = [
        "scene",
        "status",
        "reason",
        "pair_cost",
        "ns_filtered_index",
        "pc_filtered_index",
        "ns_file",
        "ns_length_offset",
        "ns_text_offset",
        "ns_source",
        "ns_kind",
        "pc_file",
        "pc_string_index",
        "pc_translation",
        "pc_kind",
    ]
    summary_fields = [
        "scene",
        "ns_story_tokens",
        "pc_story_tokens",
        "paired",
        "ns_gaps",
        "pc_gaps",
        "high_candidates",
        "review",
        "alignment_score",
    ]

    status_counts = defaultdict(int)
    summary_rows = []

    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()

        for scene in shared:
            ns_tokens = classify_ns(scene, ns_by_scene[scene])
            pc_tokens = classify_pc(scene, pc_by_scene[scene])
            aligned, score = align_scene(ns_tokens, pc_tokens)

            paired = ns_gaps = pc_gaps = high = review = 0
            for idx, (ns, pc, cost) in enumerate(aligned):
                if ns is not None and pc is not None:
                    paired += 1
                    status, reason = local_confidence(aligned, idx, cost)
                elif ns is not None:
                    ns_gaps += 1
                    status, reason = "unmatched-ns", "no-pc-pair"
                else:
                    pc_gaps += 1
                    status, reason = "pc-only", "no-ns-pair"

                status_counts[status] += 1
                if status == "high-candidate":
                    high += 1
                elif status == "review":
                    review += 1

                writer.writerow(
                    {
                        "scene": scene,
                        "status": status,
                        "reason": reason,
                        "pair_cost": "" if cost is None else f"{cost:.4f}",
                        "ns_filtered_index": "" if ns is None else ns.filtered_index,
                        "pc_filtered_index": "" if pc is None else pc.filtered_index,
                        "ns_file": "" if ns is None else ns.source_row["file"],
                        "ns_length_offset": "" if ns is None else ns.source_row["length_offset"],
                        "ns_text_offset": "" if ns is None else ns.source_row["text_offset"],
                        "ns_source": "" if ns is None else ns.text,
                        "ns_kind": "" if ns is None else ns.kind,
                        "pc_file": "" if pc is None else pc.source_row["file"],
                        "pc_string_index": "" if pc is None else pc.source_row["string_index"],
                        "pc_translation": "" if pc is None else pc.text,
                        "pc_kind": "" if pc is None else pc.kind,
                    }
                )

            summary_rows.append(
                {
                    "scene": scene,
                    "ns_story_tokens": len(ns_tokens),
                    "pc_story_tokens": len(pc_tokens),
                    "paired": paired,
                    "ns_gaps": ns_gaps,
                    "pc_gaps": pc_gaps,
                    "high_candidates": high,
                    "review": review,
                    "alignment_score": f"{score:.4f}",
                }
            )

    with args.summary.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"shared_scenes={len(shared)}")
    for key in sorted(status_counts):
        print(f"{key}={status_counts[key]}")
    print(f"alignment_output={args.output.resolve()}")
    print(f"summary_output={args.summary.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
