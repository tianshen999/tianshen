# 天神 v0.1 发布说明

**项目**：天神（Tianshen）——中文原生 AI 全栈体系，第一版：中文原生分词器。
**许可证**：GPL-3.0（全文见 LICENSE）。
**发布日期**：2026-09。

## 本包内容

```
README.md           项目总览与实验结果
LICENSE             GPL-3.0 全文
RELEASE.md          本文件
pyproject.toml      项目配置
requirements.txt    Python 依赖
src/                代码（语料层 / 分词器层）
eval/               评测体系与样本文本集
tests/              19 个单元测试（全绿）
docs/               调研笔记、设计文档、决策记录（ADR 001~014）
models/             训练好的词表模型（见下方模型卡片）
report/             评测报告（eval_results.md / .json）
data/               字形数据（Unihan / IDS）与语料许可证清单
tools/              语料下载与复现脚本
```

## 模型卡片

| 模型 | 词表 | 训练语料 | 关键配置 | 成绩（10 类样本） |
|---|---|---|---|---|
| models/group_a_64k | 64,000（整字 15,739 + 多字词 39,594） | 中文维基百科 3 分片 + 公版经典，抽样 300 万句（约 2.2 亿字符） | SentencePiece Unigram；character_coverage=1.0；normalization=identity；max_piece_length=16 | token/字 0.938；bits/字 14.98 全场最低；整字保持率 1.0 唯一满分 |
| models/group_a_32k | 32,000（整字 16,296 + 多字词 9,495） | 同上，抽样 400 万句 | 同上 | token/字 1.024；bits/字 15.32；整字保持率 1.0 |
| models/group_c_big | 22,910（纯整字） | 全量 4.32 亿字符 | 每字符一 token 的对照基线 | token/字 1.31~1.44 |
| models/plug_en | 8,000（拉丁子词挂件） | 公版英文经典 4 部 | Unigram 8k；默认关闭 | 见"已知局限" |

**设计三原则**（docs/02 §2）：
1. 汉字原子性——汉字永不拆碎（整字保持率 1.0，全场唯一）；
2. 字形通道不丢失——部首/部件信息可恢复（部首可恢复率 1.0）；
3. 中文第一公民 + 字符保真（identity 归一化，不折叠任何字符）。

**挂件架构**（ADR-013）：拉丁处理是独立、可切断、默认关闭的挂件模块；
只有纯 ASCII 片段才可能路由到挂件，中文体系（汉字/中文标点/全角符号）永远只经过核心词表。

## 一键复现

```powershell
# 0. 准备 Python 3.10+ 并安装依赖
pip install -r requirements.txt

# 1. 语料（公版经典 + 中文维基 + 英文挂件语料）
python tools/fetch_gutenberg.py
python tools/fetch_wiki.py --shards 0,1,2 --max-chars 500000000
python tools/fetch_english.py

# 2. 训练 64k 核心词表
python -m src.tokenizer.train --group a --input data/corpus_clean/train_all.txt --vocab-size 64000 --sentence-limit 3000000 --prefix artifacts/group_a_64k

# 3. 评测（自动下载 GPT/Qwen/DeepSeek/Yi/GLM 官方词表做对比）
python -m eval.benchmark --ours artifacts/group_a_64k
python -m eval.report artifacts/eval_results.json

# 4. 测试
python -m pytest -q
```

## 已知局限（v0.1 → v1.1 路线）

1. **挂件词表质量**：plug_en 训练语料为 19 世纪英文小说，对现代技术词汇不如核心词表自身；建议改用现代英文语料重训（架构与开关已验证无误，默认关闭即最优）。
2. **生僻字覆盖**：GB2312 常用字覆盖 98.7%；全量 10.3 万 Unihan 汉字覆盖 16.5%（扩展 B/C/D 区未覆盖）——"全字覆盖实验"（语料追加全量汉字行）待做。
3. **评测样本规模**：10 类人工样本，非大规模语料级评测；token/字 结论待更大规模验证。

## 路线图（形 → 音 → 意）

- 一、形（本版）：汉字字形 / 分词器 ✅
- 二、音（下一版）：汉字拼音、发声 ⏳
- 三、意（第三步）：每个字/词/偏旁的含义 ⏳

## 致谢与数据声明

训练语料：Project Gutenberg 公版经典（公有领域）、中文维基百科（CC BY-SA 4.0）。
字形数据：Unicode Unihan（Unicode License v3）、CHISE IDS（GPL-2.0-or-later，本包在 GPL-3.0 下重新发布）。
详见 data/README.md。
