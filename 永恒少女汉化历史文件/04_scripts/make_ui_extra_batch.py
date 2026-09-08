#!/usr/bin/env python3
"""Build the second reviewed UI translation batch for Ever Maiden NS."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


MAP: dict[str, dict[str, str]] = {
    "Script/eventmode.binu8": {
        "イベントの最初に戻りました": "已返回事件开头",
        "イベントモード中は使用できません": "事件模式中无法使用",
    },
    "Script/replaymode.binu8": {
        "回想の最初に戻りました": "已返回回想开头",
        "回想モード中は使用できません": "回想模式中无法使用",
    },
    "Config/button.datu8": {
        "１番～６番のデータに移動します": "切换到第1～6号存档",
        "７番～１２番のデータに移動します": "切换到第7～12号存档",
        "１３番～１８番のデータに移動します": "切换到第13～18号存档",
        "１９番～２４番のデータに移動します": "切换到第19～24号存档",
        "２５番～３０番のデータに移動します": "切换到第25～30号存档",
        "３１番～３６番のデータに移動します": "切换到第31～36号存档",
        "３７番～４２番のデータに移動します": "切换到第37～42号存档",
        "４３番～４８番のデータに移動します": "切换到第43～48号存档",
        "４９番～５４番のデータに移動します": "切换到第49～54号存档",
        "５５番～６０番のデータに移動します": "切换到第55～60号存档",
        "オートセーブ１番～６番のデータに移動します": "切换到自动存档1～6",
        "オートセーブ７番～１２番のデータに移動します": "切换到自动存档7～12",
        "クイックセーブのデータに移動します": "切换到快速存档",
        "表示しているページの設定をデフォルトに戻します": "将当前页面恢复默认设置",
        "すべての設定をデフォルトに戻します": "将全部设置恢复默认值",
        "ボイスのテスト再生を行います": "测试播放语音",
        "前の曲を再生します": "播放上一首曲目",
        "曲を再生・一時停止します": "播放/暂停曲目",
        "曲を停止します": "停止播放",
        "次の曲を再生します": "播放下一首曲目",
        "再生中の曲のみをループ再生します": "循环播放当前曲目",
        "曲を順次再生します": "顺序播放曲目",
        "曲をランダム再生します": "随机播放曲目",
        "サムネイルやボタンを非表示にします": "隐藏缩略图和按钮",
        "スライドショーを終了します": "结束幻灯片播放",
        "前のＣＧを表示します": "显示上一张CG",
        "次のＣＧを表示します": "显示下一张CG",
        "スライドショーの速度を変更します": "调整幻灯片播放速度",
        "ＣＧモードへ移行します": "进入CG鉴赏",
        "ミュージックモードへ移行します": "进入音乐鉴赏",
        "リプレイモードへ移行します": "进入回想模式",
        "イベントモードへ移行します": "进入事件模式",
        "キャラモードへ移行します": "进入角色鉴赏",
        "クイックセーブします": "快速保存",
        "クイックロードします": "快速读取",
        "ゲームをセーブして終了します": "保存并退出游戏",
        "ボタンの選択箇所を切り替えます": "切换按钮选择位置",
        "画面のスクリーンショットを撮ります": "截取游戏画面",
        "機能割り当てを解除します": "解除功能分配",
    },
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ns_extract", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    rows: list[dict[str, str]] = []
    found: set[tuple[str, str]] = set()
    with args.ns_extract.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            mapping = MAP.get(row["file"])
            if not mapping or row["text"] not in mapping:
                continue
            found.add((row["file"], row["text"]))
            rows.append({
                "file": row["file"],
                "length_offset": row["length_offset"],
                "text_offset": row["text_offset"],
                "stored_length": row["stored_length"],
                "byte_length": row["byte_length"],
                "source": row["text"],
                "translation": mapping[row["text"]],
                "scene": "UI-extra-v1",
                "ns_filtered_index": "",
                "pc_file": "",
                "pc_string_index": "",
                "alignment_status": "manual-reviewed-ui",
                "alignment_reason": "exact-source-map",
            })

    missing = [(file, source) for file, m in MAP.items() for source in m if (file, source) not in found]
    if missing:
        for file, source in missing:
            print(f"MISSING\t{file}\t{source}")
        raise SystemExit(f"reviewed UI sources missing: {len(missing)}")

    rows.sort(key=lambda r: (r["file"], int(r["length_offset"])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "file", "length_offset", "text_offset", "stored_length", "byte_length",
        "source", "translation", "scene", "ns_filtered_index", "pc_file",
        "pc_string_index", "alignment_status", "alignment_reason",
    ]
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"rows_written={len(rows)}")
    for file in MAP:
        print(f"{file}={sum(r['file'] == file for r in rows)}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
