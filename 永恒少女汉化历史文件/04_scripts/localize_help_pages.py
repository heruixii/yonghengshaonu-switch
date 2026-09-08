#!/usr/bin/env python3
"""Rebuild the 11 reachable Switch help pages as clean Simplified-Chinese pages.

The original help PNGs mix Japanese explanatory text with screenshots that also
contain baked Japanese UI.  Pixel-level OCR replacement is therefore inherently
unsafe: even a correct left-column replacement would leave Japanese inside the
illustrative screenshots.  This script replaces the *whole* 1920x1080 help page
while preserving the filenames and the HelpMenu.spm call graph.

Only terminology already established by the project's localized UI is used.
Physical-button mappings are deliberately not guessed; the player is directed to
the current gamepad/touch bindings in System Settings instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from fontTools.ttLib import TTCollection
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "02_romfs" / "merged-v1.0.3" / "System"
OUT = ROOT / "03_text" / "ui" / "rendered-v019-help"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")

W, H = 1920, 1080

# Compact, functional help copy.  These labels match terms already used by the
# localized title/config/system UI and Config/button.datu8 translations.
PAGES: dict[int, dict[str, object]] = {
    1: {
        "title": "帮助目录",
        "subtitle": "操作与系统功能一览",
        "sections": [
            ("01  游戏画面", ["了解文本窗口、选项与常用功能。"]),
            ("02  基本操作", ["文本推进、历史记录、自动模式与跳过模式。"]),
            ("03  快捷操作", ["快速保存、快速读取与常用跳转功能。"]),
            ("04  标题菜单", ["从头开始、继续、环境设置、鉴赏与 EX剧情。"]),
            ("05  游戏进行与系统菜单", ["保存、读取、设置以及返回标题画面。"]),
            ("06  保存 / 读取", ["普通存档、快速存档以及存档管理。"]),
            ("07  系统设置", ["显示、消息、声音、语音与其他功能。"]),
            ("08  历史记录", ["回看已经显示过的文本与语音。"]),
            ("09  输入方式", ["触摸与手柄相关设置。"]),
        ],
    },
    2: {
        "title": "游戏画面",
        "subtitle": "阅读、选择与菜单操作",
        "sections": [
            ("文本推进", ["使用当前“确定”操作推进文本。", "文本仍在显示时执行确定操作，可立即显示本段剩余文字。"]),
            ("选项", ["出现选项时选择目标项目并确定。", "部分跳转功能可快速回到上一个或下一个选项位置。"]),
            ("窗口与菜单", ["可打开系统菜单、历史记录以及设置菜单。", "需要隐藏或恢复文本窗口时，使用对应的窗口操作。"]),
            ("按键说明", ["实体按键可能因手柄设置而变化。", "请以“系统设置 → 手柄”中当前绑定为准。"]),
        ],
    },
    3: {
        "title": "基本操作 1",
        "subtitle": "阅读模式",
        "sections": [
            ("历史记录", ["打开历史记录可回看已经显示过的文本。", "历史记录中可上下滚动；存在语音的记录可再次播放。"]),
            ("自动模式", ["进入自动模式后，文本会按设定的等待时间自动推进。", "自动模式的等待、语音结束等待等行为可在系统设置中调整。"]),
            ("跳过模式", ["进入跳过模式后可连续快速推进文本。", "是否允许跳过未读文本、经过选项后是否解除跳过，可在系统设置中调整。"]),
            ("按住加速", ["部分操作可在按住按键期间加快文本或处理速度。", "具体行为以当前系统设置与手柄绑定为准。"]),
        ],
    },
    4: {
        "title": "基本操作 2",
        "subtitle": "跳转与快捷功能",
        "sections": [
            ("选项跳转", ["可跳至上一个选项或下一个选项。", "若跳转起点之后没有可用选项，部分情况下会返回标题画面。"]),
            ("快速保存", ["快速保存会写入快速存档位置。", "是否在快速保存时显示确认窗口，可在系统设置中选择。"]),
            ("快速读取", ["快速读取会读取当前快速存档。", "是否在快速读取时显示确认窗口，可在系统设置中选择。"]),
            ("常用功能", ["系统菜单、设置菜单、历史记录等功能可通过界面按钮或当前绑定按键打开。"]),
        ],
    },
    5: {
        "title": "标题菜单",
        "subtitle": "开始游戏与鉴赏功能",
        "sections": [
            ("从头开始", ["从故事开头开始游戏。"]),
            ("继续", ["从已有保存数据继续游戏。"]),
            ("环境设置", ["打开系统设置，调整显示、文本、声音、语音等项目。"]),
            ("鉴赏", ["进入已解锁的 CG鉴赏、场景鉴赏与音乐鉴赏。"]),
            ("EX剧情", ["满足相应解锁条件后，可进入追加的 EX剧情。"]),
        ],
    },
    6: {
        "title": "游戏进行与系统菜单",
        "subtitle": "游玩中的主要功能入口",
        "sections": [
            ("保存", ["打开保存菜单，将当前进度写入保存数据。"]),
            ("读取", ["打开读取菜单，从已有保存数据继续。"]),
            ("系统设置", ["可在游玩中修改环境设置；多数项目会即时生效。"]),
            ("返回标题画面", ["离开当前游戏流程并返回标题菜单。", "执行前请确认是否需要保存当前进度。"]),
            ("退出/关闭", ["根据当前平台菜单提供的功能关闭窗口或退出游戏。"]),
        ],
    },
    7: {
        "title": "保存 / 读取",
        "subtitle": "保存数据管理",
        "sections": [
            ("保存数据", ["选择一个保存位置后写入当前游戏进度。", "覆盖已有保存数据时，可按系统设置显示确认窗口。"]),
            ("读取数据", ["选择已有保存数据即可从该位置继续。"]),
            ("快速存档", ["快速保存与快速读取使用独立的快捷位置。"]),
            ("管理功能", ["保存数据可进行移动、删除与编辑等操作。", "重要进度建议保留多个普通保存位置。"]),
        ],
    },
    8: {
        "title": "系统设置 1",
        "subtitle": "ADV / 显示 / 消息",
        "sections": [
            ("ADV", ["调整 NEW图标、语音播放时间、自动模式等待时间、曲名显示等项目。"]),
            ("显示", ["调整背景透明度、交错纹透明度与演出速度等显示项目。"]),
            ("消息 1", ["调整文字装饰、文字颜色、消息速度、自动模式速度与已读跳过速度。"]),
            ("消息 2", ["调整文本推进、自动模式、跳过模式以及语音相关的文本控制行为。"]),
        ],
    },
    9: {
        "title": "系统设置 2",
        "subtitle": "声音 / 语音 / 功能",
        "sections": [
            ("声音", ["调整主音量、BGM、音效、语音与系统音效。", "也可设置播放语音时是否降低 BGM 或音效音量。"]),
            ("语音", ["调整翻到下一段文本时的语音停止行为、语音等待以及左右声道分配。"]),
            ("功能与确认", ["可设置简易帮助、自动读取、自动保存、各种确认窗口等项目。"]),
            ("触摸 / 手柄", ["触摸与手柄相关项目用于调整输入操作。", "实体按键提示请以这里显示的当前绑定为准。"]),
        ],
    },
    10: {
        "title": "历史记录",
        "subtitle": "回看已显示文本",
        "sections": [
            ("打开历史记录", ["在游玩中使用“显示历史记录”功能进入。"]),
            ("浏览", ["向上或向下滚动查看较早/较新的记录。"]),
            ("语音", ["带有语音的记录可使用对应的语音播放功能再次收听。"]),
            ("返回游戏", ["使用返回/关闭操作离开历史记录并回到当前文本。"]),
        ],
    },
    11: {
        "title": "输入方式与其他提示",
        "subtitle": "触摸、手柄与常用操作",
        "sections": [
            ("输入方式", ["游戏支持界面按钮以及当前平台提供的触摸/手柄操作。"]),
            ("手柄绑定", ["不同控制器或自定义设置可能改变实体按键。", "请在“系统设置 → 手柄”中确认当前绑定。"]),
            ("触摸操作", ["触摸相关行为可在“系统设置 → 触摸”中调整。"]),
            ("遇到误操作时", ["可先打开系统菜单或历史记录确认当前位置。", "重要选择前建议使用普通保存或快速保存。"]),
        ],
    },
}


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), size=size, index=0)


def all_target_chars() -> set[str]:
    chars: set[str] = set()
    for page in PAGES.values():
        for text in [str(page["title"]), str(page["subtitle"])]:
            chars.update(ch for ch in text if ord(ch) > 127)
        for heading, lines in page["sections"]:  # type: ignore[index]
            chars.update(ch for ch in heading if ord(ch) > 127)
            for line in lines:
                chars.update(ch for ch in line if ord(ch) > 127)
    return chars


def verify_font() -> int:
    if not FONT.is_file():
        raise RuntimeError(f"missing font: {FONT}")
    coll = TTCollection(str(FONT))
    cmap: set[int] = set()
    for table in coll.fonts[0]["cmap"].tables:
        if table.isUnicode():
            cmap.update(table.cmap)
    chars = all_target_chars()
    missing = sorted(ch for ch in chars if ord(ch) not in cmap)
    if missing:
        raise RuntimeError("help font missing: " + " ".join(f"U+{ord(ch):04X}" for ch in missing))
    return len(chars)


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for ch in text:
        test = cur + ch
        box = draw.textbbox((0, 0), test, font=f)
        if cur and box[2] - box[0] > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def rounded_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int]) -> None:
    # Neutral dark UI: easy to read on handheld and does not imitate any
    # copyrighted screenshot/illustration from the original help pages.
    draw.rounded_rectangle(xy, radius=22, fill=(38, 38, 44), outline=(105, 105, 116), width=2)


def render_page(index: int, page: dict[str, object]) -> Image.Image:
    img = Image.new("RGB", (W, H), (18, 18, 22))
    d = ImageDraw.Draw(img)

    # Header.
    d.rectangle((0, 0, W, 150), fill=(30, 30, 36))
    d.text((90, 45), f"HELP {index:02d}", font=font(28), fill=(178, 178, 190))
    d.text((260, 32), str(page["title"]), font=font(58), fill=(248, 248, 250))
    d.text((260, 102), str(page["subtitle"]), font=font(27), fill=(180, 180, 190))

    sections = list(page["sections"])  # type: ignore[arg-type]
    n = len(sections)
    # The directory page has nine compact entries and is intentionally a 3x3
    # grid.  Functional detail pages use at most two columns for readability.
    cols = 3 if index == 1 else (2 if n >= 4 else 1)
    rows = (n + cols - 1) // cols
    gap_x, gap_y = 34, 28
    left, right = 90, W - 90
    top, bottom = 190, H - 110
    card_w = (right - left - gap_x * (cols - 1)) // cols
    card_h = (bottom - top - gap_y * (rows - 1)) // rows

    hf = font(34)
    bf = font(28)
    for i, (heading, lines) in enumerate(sections):
        col = i % cols
        row = i // cols
        x0 = left + col * (card_w + gap_x)
        y0 = top + row * (card_h + gap_y)
        x1, y1 = x0 + card_w, y0 + card_h
        rounded_box(d, (x0, y0, x1, y1))
        d.text((x0 + 30, y0 + 22), heading, font=hf, fill=(248, 248, 250))
        y = y0 + 78
        for line in lines:
            wrapped = wrap(d, "• " + line, bf, card_w - 58)
            for wline in wrapped:
                d.text((x0 + 30, y), wline, font=bf, fill=(205, 205, 214))
                y += 39
            y += 8
        if y > y1 - 18:
            raise RuntimeError(f"help{index:02d} text overflow in section {heading}: {y}>{y1-18}")

    d.text((90, H - 67), "※ 实体按键以当前“系统设置 → 手柄”绑定为准。", font=font(24), fill=(145, 145, 156))
    d.text((W - 305, H - 67), f"{index:02d} / 11", font=font(24), fill=(145, 145, 156))
    return img


def main() -> int:
    chars = verify_font()
    OUT.mkdir(parents=True, exist_ok=True)
    for i in range(1, 12):
        src = SOURCE / f"help{i:02d}.png"
        if not src.is_file():
            raise RuntimeError(f"missing source help page: {src}")
        with Image.open(src) as sim:
            if sim.size != (W, H):
                raise RuntimeError(f"unexpected source size: {src.name} {sim.size}")
        dst = OUT / src.name
        render_page(i, PAGES[i]).save(dst, optimize=True)
        print(f"{dst.relative_to(ROOT)}\t{dst.stat().st_size}")
    print(f"help_target_nonascii={chars}")
    print("help_pages=11")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

