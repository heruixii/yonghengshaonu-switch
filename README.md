# 《永恒少女～堕落花园的少女～》Nintendo Switch 简体中文汉化工程

这是《永恒少女～堕落花园的少女～》Nintendo Switch 简体中文汉化工程的源码级备份与最终补丁镜像。

- 中文项目名：**永恒少女～堕落花园的少女～**
- PC 汉化资料目录原名：**永恒少女 ～堕落庭园的少女们～「PC汉化」**
- Nintendo Switch Title ID：`01008DC019F7A000`
- 对应更新 Title ID：`01008DC019F7A800`
- 目标版本：**v1.0.3**
- 最终发布基线：**v019-final-complete**

## 最终状态

工程最终文档记录：

- cumulative rows：`14,178`
- re-extract：`14,178 / 14,178`
- story scenes：`188`
- story rows：`13,828`
- story covered：`13,828 / 13,828`
- coverage errors：`0`
- 最终发布 QA：`errors=0`

## 仓库内容

- `汉化补丁/09_release/v019-final-complete/`：最终 Atmosphère LayeredFS 补丁；
- `永恒少女汉化历史文件/03_text/translated/`：最终累计译文、回读和最终 QA 数据；
- `永恒少女汉化历史文件/03_text/matched/`：最终 PC / Switch 日文对齐表；
- `永恒少女汉化历史文件/04_scripts/`：提取、对齐、文本注入、字体、UI 和 QA 脚本；
- `永恒少女汉化历史文件/docs/`：从 v001 到 v019 的工程记录与最终发布说明；
- `永恒少女汉化历史文件/05_build/v019-final-complete/qa-final.tsv`：最终发布 QA。

## 安装

将最终补丁中的 `atmosphere` 文件夹复制到 SD 卡根目录，使路径成为：

`atmosphere/contents/01008DC019F7A000/romfs/...`

本仓库不包含游戏本体、NSP/NSZ/NCA、系统密钥或完整原版 RomFS。

更详细的备份范围见 `GITHUB_BACKUP.md`。
