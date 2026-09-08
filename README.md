# 天神（Tianshen）：中文原生 AI

从零构建、全程开源的**中文原生 AI 全栈体系**（GPL-3.0）。

**核心理念**：中文不是英文的子集。从分词器这一层开始，让中文成为第一等公民。

## 路线图

**中文词表三步总路线（形 → 音 → 意）**

| 步骤 | 内容 | 状态 |
|---|---|---|
| 一、形 | 汉字字形：分词器词表 | ✅ v0.1 已开源（64k 词表 + 评测报告） |
| 二、音 | 汉字拼音、发声 | 🔨 v0.2 进行中（数据层/词级标注/双挂件已完成，待发布） |
| 三、意 | 每个字/词/偏旁的含义 | ⏳ 规划中 |

**阶段 2（音）内部路线**

| 步骤 | 内容 | 状态 |
|---|---|---|
| 音1 | 拼音数据层（Unihan 整合，GB2312 常用字覆盖 100%） | ✅ |
| 音2 | 64k 词表词级拼音标注（CEDICT + pypinyin + 逐字兜底四级流水线） | ✅ 39,594 词 |
| 音3 | 多音消歧评测（185 词测试集 vs pypinyin） | ✅ 天神 100% / pypinyin 95.1% |
| 音4 | 注音输出挂件 + 字/词级发声挂件（均默认关闭） | ✅ 34 测试全绿 |
| 音5 | v0.2 形+音合并词表发布 | 🔨 发布物就绪，待推送 |

## 目录结构

```
docs/       # 研究笔记、设计文档、决策记录（ADR）
src/        # 代码（corpus 语料层 / tokenizer 分词器层）
eval/       # 四维评测体系 + 样本文本集 + 报告生成
tests/      # 单元测试（12 个，全绿）
artifacts/  # 训练产物与评测报告（不入库）
data/       # 语料与数据（不入库）
tools/      # 便携 Python 运行时与下载工具（不入库）
```

## 快速开始

### 0. 环境（已在工作区内置，无需系统安装）

- 便携 Python：`tools\python\python.exe`（3.12.10，全部依赖已装）
- 运行时环境变量（每次执行前设置）：
  ```powershell
  $env:TMP = "$PWD\.tmp"; $env:TEMP = "$PWD\.tmp"; $env:PIP_CACHE_DIR = "$PWD\.pipcache"; $env:PYTHONUTF8 = "1"
  ```

### 1. 测试

```powershell
.\tools\python\python.exe -m pytest -q
```

### 2. 训练（A=纯中文 / B=最小英文通道 / C=纯整字对照）

```powershell
.\tools\python\python.exe -m src.tokenizer.train --group a --input data\corpus_clean\all.txt --vocab-size 32000 --prefix artifacts\group_a
```

### 3. 对比评测（自动下载 GPT/Qwen/DeepSeek/Yi/GLM 官方词表）

```powershell
.\tools\python\python.exe -m eval.benchmark --ours artifacts\group_a --ours artifacts\group_b --ours artifacts\group_c
.\tools\python\python.exe -m eval.report artifacts\eval_results.json
```

### 4. 语料

```powershell
.\tools\python\python.exe tools\fetch_gutenberg.py          # 公版经典（已内置）
.\tools\python\python.exe -m src.corpus.download --list      # 大规模语料清单
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

完整报告：`artifacts/eval_results.md`（自动生成，可复现）

## 许可证

全部成果无限开源（具体许可证待定，倾向 Apache-2.0 / MIT）。
