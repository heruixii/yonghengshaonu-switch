# GitHub 备份说明

## 备份性质

本仓库是本地 `D:\switch游戏\个人汉化\永恒少女～堕落花园的少女～` 的**汉化工程级备份**，不是完整磁盘镜像。

本地目录约 32 GB，其中包含游戏本体、解包 NSP/NCA、完整 RomFS、PC 汉化版、字体虚拟环境和多代构建。这些内容不进入 GitHub。

## 已备份

### 最终补丁

`汉化补丁/09_release/v019-final-complete/`

这是当前唯一正式发布基线。历史文档记录最终 ZIP SHA256：

`B0ECF8E42C43F19DAC3FF713FA178F6D4D1902C1B5462490CA00556C54B792DD`

仓库不保存重复的 `09_release.rar`，也不保存 `05_build` 中同一 payload 的第二、第三份镜像。

### 最终文本与 QA

- `final-all-text-v3-cumulative.tsv`
- `final-v3-reextract.tsv`
- `final-v3-font-coverage.tsv`
- 最终随机 holdout / findings
- `pc-ns-alignment-v3-jp.tsv`
- `05_build/v019-final-complete/qa-final.tsv`

### 工程源码与文档

- `04_scripts/`
- `docs/`
- `03_text/alignment_samples/`

## 明确排除

- `本体/` 中的 NSZ；
- `01_container/` 的 NSP/NCA/Ticket/Cert；
- `02_romfs/` 的完整原始/更新 RomFS；
- `永恒少女 ～堕落庭园的少女们～「PC汉化」/` 的完整 PC 游戏资源；
- `.venv-font/`；
- `tools/` 二进制工具；
- v001～v018 和 v019 的重复中间构建树；
- `prod.keys`、`*.keys` 和其它私有密钥；
- 压缩归档的重复副本。

## 本地复现

GitHub 可恢复最终补丁、最终译文、对齐数据、QA、脚本和完整工程文档。若要从头重新构建，仍需要用户自行合法持有对应 Switch/PC 源资源以及本地工具和密钥环境。
