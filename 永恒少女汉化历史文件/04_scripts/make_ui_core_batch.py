#!/usr/bin/env python3
"""Build the first reviewed core-UI translation batch for Ever Maiden NS.

Only exact, explicitly reviewed source strings are selected.  Repeated button
help strings are translated at every exact occurrence in Config/button.datu8.
No fuzzy matching is performed.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


MAP: dict[str, dict[str, str]] = {
    "Config/char.datu8": {
        "アルエット": "阿尔艾特",
        "ルク": "露珂",
        "マコー": "玛可",
        "パヴォーネ": "帕沃妮",
        "ロビン": "萝宾",
        "キャナリー": "卡娜莉",
        "アヴェルラ": "阿薇拉",
        "オルロ": "奥尔洛",
        "アドラー": "阿德拉",
        "その他": "其他",
        "ナレーション": "旁白",
    },
    "Script/system.binu8": {
        "タイトル画面では使用できません": "标题画面中无法使用",
        "確認する章を選んで下さい。@e": "请选择要查看的章节。@e",
        "第１章": "第1章",
        "第２章": "第2章",
        "第３章": "第3章",
        "第４章": "第4章",
    },
    "Script/title.binu8": {
        "タイトル画面ではセーブできません": "标题画面中无法保存",
    },
    "Config/button.datu8": {
        "上へスクロールします": "向上滚动",
        "下へスクロールします": "向下滚动",
        "パネルを固定・解除します": "固定/解除面板",
        "ウィンドウを閉じます": "关闭窗口",
        "ＴＩＰＳメニューを開きます": "打开TIPS菜单",
        "音声を再生します": "播放语音",
        "前の選択肢にジャンプします": "跳至上一个选项",
        "バックログを表示します": "显示历史记录",
        "オートモードへ移行します": "进入自动模式",
        "スキップモードへ移行します": "进入跳过模式",
        "次の選択肢にジャンプします": "跳至下一个选项",
        "セーブメニューを開きます": "打开保存菜单",
        "ロードメニューを開きます": "打开读取菜单",
        "システムメニューを開きます": "打开系统菜单",
        "設定メニューを開きます": "打开设置菜单",
        "タイトル画面に戻ります": "返回标题画面",
        "ゲームを終了します": "退出游戏",
        "メニューを閉じます": "关闭菜单",
        "オートモードを終了します": "结束自动模式",
        "オートモードの速度を変更します": "调整自动模式速度",
        "スキップモードを終了します": "结束跳过模式",
        "スキップモードの速度を変更します": "调整跳过模式速度",
        "全ての文章をスキップ可能にします": "允许跳过所有文本",
        "既読文のみスキップ可能にします": "仅允许跳过已读文本",
        "メッセージの表示速度を変更します": "调整文本显示速度",
        "ウィンドウの不透明度を変更します": "调整窗口透明度",
        "ボイスの再生速度を変更します": "调整语音播放速度",
        "マスター（全体）の音量を変更します": "调整主音量",
        "セーブデータを移動（入れ替え）します": "移动（交换）保存数据",
        "セーブデータを削除します": "删除保存数据",
        "セーブデータのコメントを編集します": "编辑保存数据备注",
        "ＡＤＶ関連の項目へ移動します": "切换到ADV相关设置",
        "システム関連の項目へ移動します": "切换到系统相关设置",
        "ディスプレイ関連の項目へ移動します": "切换到显示相关设置",
        "メッセージ１関連の項目へ移動します": "切换到消息1相关设置",
        "メッセージ２関連の項目へ移動します": "切换到消息2相关设置",
        "サウンド関連の項目へ移動します": "切换到声音相关设置",
        "ボイス関連の項目へ移動します": "切换到语音相关设置",
    },
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ns_extract", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    rows: list[dict[str, str]] = []
    found: dict[tuple[str, str], int] = {}

    with args.ns_extract.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            file_map = MAP.get(row["file"])
            if not file_map:
                continue
            translation = file_map.get(row["text"])
            if translation is None:
                continue
            found[(row["file"], row["text"])] = found.get((row["file"], row["text"]), 0) + 1
            rows.append(
                {
                    "file": row["file"],
                    "length_offset": row["length_offset"],
                    "text_offset": row["text_offset"],
                    "stored_length": row["stored_length"],
                    "byte_length": row["byte_length"],
                    "source": row["text"],
                    "translation": translation,
                    "scene": "UI-core-v1",
                    "ns_filtered_index": "",
                    "pc_file": "",
                    "pc_string_index": "",
                    "alignment_status": "manual-reviewed-ui",
                    "alignment_reason": "exact-source-map",
                }
            )

    missing = []
    for file, mapping in MAP.items():
        for source in mapping:
            if (file, source) not in found:
                missing.append((file, source))
    if missing:
        for file, source in missing:
            print(f"MISSING\t{file}\t{source}")
        raise SystemExit(f"reviewed UI sources missing from extraction: {len(missing)}")

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
