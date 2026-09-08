# 天神（Tianshen）：中文原生 AI

[![license](https://img.shields.io/badge/license-GPL--3.0-blue)](LICENSE)
[![release](https://img.shields.io/github/v/release/tianshen999/tianshen)](https://github.com/tianshen999/tianshen/releases)
[![gate](https://img.shields.io/github/actions/workflow/status/tianshen999/tianshen/gate.yml?label=gate)](https://github.com/tianshen999/tianshen/actions/workflows/gate.yml)
[![tests](https://img.shields.io/badge/tests-58%2F58-brightgreen)](tests/)

从零构建、全程开源的**中文原生 AI 全栈体系**（GPL-3.0）。

**核心理念**：中文不是英文的子集。从分词器这一层开始，让中文成为第一等公民。

> 📐 全景架构图（人工终审版）：[docs/00-全景架构图.md](docs/00-全景架构图.md)
> 🔌 新板块接入协议（机制自动、判题人工）：[docs/10-新板块接入协议.md](docs/10-新板块接入协议.md)

## 路线图

**中文词表三步总路线（形 → 音 → 意）**

| 步骤 | 内容 | 状态 |
|---|---|---|
| 一、形 | 汉字字形：分词器词表 | ✅ v0.1（64k 词表：整字保持率 1.0 唯一满分，token/字 0.762 全场第一） |
| 二、音 | 汉字拼音、发声 | ✅ v0.2（词级拼音 + 多音消歧 100% + 注音/发声双挂件） |
| 三、意 | 每个字/词/偏旁的含义 | ✅ v0.3（意平面过独立性检验，真三维词空间发布） |

**v0.3（意）内部路线**

| 步骤 | 内容 | 状态 |
|---|---|---|
| 意1 | 维基词典中文释义解析（字 25.1% / 词 31.4% 覆盖） | ✅ |
| 意2 | 214 部首义素表（人工策管，开源） | ✅ |
| 意3 | 意平面 S（义素层 432 维 + 深义关键词层 1737 维） | ✅ |
| 意4 | 独立性检验：深义层被形⊕音解释 R²=0.0202 ✅ 带来新维度 | ✅ |
| 意5 | 三维组装 F⊕P⊕S2（3041 维，实测秩 2826）+ 义近评测 + 3D 演示 | ✅ |
| 意6 | v0.3 发布 | ✅ GitHub v0.3（含 11 步闸门 + 端到端贯通 + 维度证书） |

## 快速体验（开箱即用，无需训练）

仓库自带全部预构建产物（`artifacts/`：分词模型、拼音表、三维平面、维度证书、评测报告）。
clone 后安装依赖即可直接体验：

```powershell
pip install -r requirements.txt

python tools/demo_v02.py                      # 形：分词 + 音：拼音/注音/发声
python tools/demo_3d.py 水 火 心 山 爱 湖      # 意：形近/音近/义近 三列检索
python tools/e2e_check.py                     # 端到端贯通：一条文本走完 形→音→意 + 四挂件
python -m pytest -q                           # 58 个单元测试

# 发布闸门（11 步：自动审计 + 自动校准 + 端到端贯通；全过才可发布）
powershell -Command "Invoke-Expression (Get-Content -Raw tools\audit_gate.ps1)"
```

> 发布 zip 内的产物目录为 `models/` `pinyin/` `semantic/` `report/`（面向最终用户）；
> 本仓库使用与工具代码一致的 `artifacts/` 布局，clone 即跑。

## 目录结构

```
docs/       研究笔记、设计文档、决策记录（ADR 001~031）、全景架构图（00）、新板块接入协议（10）
src/        代码（corpus 语料层 / tokenizer 分词器层 / pinyin 拼音层 / semantic 语义层）
eval/       评测体系（分词四维 / 多音消歧 / 义近检索 / token 经济学）
tests/      单元测试（58 个，全绿）
tools/      发布闸门（11 步）、自动校准/审计、演示、数据抓取、发布脚本
artifacts/  预构建产物：64k/32k/拉丁挂件模型、拼音表、三维平面与证书、评测报告
data/       数据源：Unihan / IDS / CC-CEDICT（许可证清单见 data/README.md）
.github/    GitHub Actions：每次 push 自动跑闸门（gate.yml）；手动全量 11 步（full-gate.yml）
```

## 训练（复现 v0.1 分词器；A=纯中文 / B=最小英文通道 / C=纯整字对照）

```powershell
python -m src.tokenizer.train --group a --input data\corpus_clean\all.txt --vocab-size 32000 --prefix artifacts\group_a
```

## 对比评测（自动下载 GPT/Qwen/DeepSeek/Yi/GLM 官方词表）

```powershell
python -m eval.benchmark --ours artifacts\group_a --ours artifacts\group_b --ours artifacts\group_c
python -m eval.report artifacts\eval_results.json
```

## 语料

```powershell
python tools\fetch_gutenberg.py          # 公版经典（已内置）
python -m src.corpus.download --list      # 大规模语料清单
```

## 实验结果（2026-09，M1 规模化）

**语料**：中文维基百科 3 分片 + 公版经典，清洗后 4.32 亿字符、600 万行。
**模型**：group_a_64k（Unigram，character_coverage=1.0，词表 64k：单字 15,739 + 多字词 39,594）。

| 分词器 | token/字 ↓ | bits/字 ↓ | 整字保持率 ↑ |
|---|---|---|---|
| **我们的 64k** | 0.938 | **14.98 最低** | **1.0 唯一满分** |
| DeepSeek-V3（12.9万词表） | 0.902 | 15.30 | 0.943 |
| Qwen2.5（15万词表） | 0.950 | 16.36 | 0.955 |
| GPT-4o | 1.094 | 19.27 | 0.900 |
| GPT-3.5 | 1.542 | 25.62 | 0.671 |

- **token/字 0.938**：已反超 Qwen/ChatGLM/Yi/GPT-4o，仅剩 DeepSeek 在前（其词表 12.9 万 vs 我们 64k，96k/128k 档实验即可追平）；
- **整字保持率 1.0**：汉字原子性设计目标达成，全场唯一（其他模型都会拆碎生僻字）；
- **bits/字 全场最低**：信息论口径编码成本已赢。

> 更新基准（token 经济学，14.1 万字符）：天神 **0.762 token/字 全场第一**（DeepSeek 0.849 / Qwen 0.943 / GPT-4o 1.079），详见 `artifacts/token_economy.md`。

## 当前成绩快照（v0.3）

| 指标 | 数值 |
|---|---|
| 简体核心字符 / 词 / 繁体挂件 | 12,468 / 31,466 / 3,730 |
| 多音消歧 | 185/185 = 100%（pypinyin 95.1%） |
| 三维空间 W3 = F⊕P⊕S2 | 3,041 维，实测秩 2,826 |
| 独立性检验（意 vs 形⊕音） | R² = 0.0202（判据 < 0.3）✅ 真三维 |
| 义近检索 S2 Hit@10 | 0.194（形 0.139 / 音 0.000） |
| 发布闸门 | 11/11 PASS（报告 `artifacts/audit_gate_report.md`） |

完整报告：`artifacts/eval_results.md`、`artifacts/token_economy.md`、`artifacts/semantic/certificates.md`（全部自动生成、可复现、随仓库公开）。

## 发布历史

| 版本 | 内容 | Release |
|---|---|---|
| v0.1 | 形：64k 中文原生分词器 | [链接](https://github.com/tianshen999/tianshen/releases/tag/v0.1) |
| v0.2 | 音：词级拼音 + 多音消歧 + 双挂件 | [链接](https://github.com/tianshen999/tianshen/releases/tag/v0.2) |
| v0.3 | 意：真三维词空间 F⊕P⊕S | [链接](https://github.com/tianshen999/tianshen/releases/tag/v0.3) |

## 许可证

全部成果无限开源，**GPL-3.0**（全文见 [LICENSE](LICENSE)）。数据源许可证清单见 `data/README.md`。
