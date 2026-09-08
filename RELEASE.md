# 天神 v0.3 发布说明（形 + 音 + 意：真三维词空间）

**项目**：天神（Tianshen）——中文原生 AI 全栈体系，第三版：形音意三维词空间。
**许可证**：GPL-3.0（全文见 LICENSE）。
**发布日期**：2026-09。

## 本包内容

```
README.md           项目总览与实验结果
LICENSE             GPL-3.0 全文
RELEASE.md          本文件
pyproject.toml      项目配置（v0.3.0）
requirements.txt    Python 依赖
src/                代码（语料层 / 分词器层 / 拼音层 / 语义层）
eval/               评测体系（分词四维 / 多音消歧 / 义近检索 / token 经济学）
tests/              58 个单元测试（全绿）
docs/               调研、设计、决策记录（ADR 001~031）、全景架构图（00）、
                    新板块接入协议（10）、深度分析、发布清单
models/             词表模型（64k/32k/整字对照/拉丁挂件）
pinyin/             形+音标注（词级拼音 JSON、繁体映射）
semantic/           真三维词空间（F/P/S 三平面矩阵、深义关键词层、维度证书、义近评测）
report/             分词器四维对比报告
data/               字形/词典数据 + 许可证清单
tools/              下载、复现、演示脚本（demo_v02 / demo_3d / certify_* / e2e_check）
```

## v0.3 新增（意）

1. **意平面 S**（432 维义素层 + 1737 维深义关键词层）：
   - 义素层：214 部首义素表（人工策管）+ 部件义素聚合；
   - 深义层：维基词典中文释义关键词袋（自家分词器切词，IDF 加权、死列剪枝、共线合并、简繁校准）；
   - 义项数据：维基词典中文释义（字 25.1% / 词 31.4% 覆盖，CC BY-SA）。
2. **挂谷独立性检验通过**：深义层被 形⊕音 解释的方差 R² = **0.0202**（判据 < 0.3）
   ——意带来了真正独立于形、音的新维度（总重叠 0.52 为合法形义同源）。
3. **真三维词空间 W3 = F⊕P⊕S2**：3,041 维，实测秩 2,826，三平面正交；
   结构依赖预算：F 秩/可达 0.9988、P·IDF 1.0、S 1.0、深义层 1.0。
4. **义近检索评测基准**：36 个人工策管近义探针；意平面 S2 Hit@10 = 0.194
   vs 形平面 0.139 vs 音平面 0.000（音与义无关的数学证据）。
5. **三维几何演示**（tools/demo_3d.py）：输入一字，形近/音近/义近三列并排。
6. **简体核心 + 繁体挂件**：核心 12,468 字 / 31,466 词；繁体挂件 3,730 条繁→简路由
   （可插拔，ADR-027）。
7. **发布闸门 11/11 PASS**（ADR-029/030/031）：自动审计 + 自动校准 + 词级平面重建
   + 端到端贯通验证（一条文本走完 形→音→意 + 四挂件，tools/e2e_check.py）。

## 三步总路线状态

- 一、形 ✅ v0.1：64k 词表，整字保持率 1.0（全场唯一），token/字 0.762 实测第一
- 二、音 ✅ v0.2：词级拼音（多音消歧 185 词 100% vs pypinyin 95.1%），注音/发声双挂件
- 三、意 ✅ v0.3：意平面通过维度准入，真三维词空间组装完成

## Token 经济学（完整报告 report/token_economy.md）

- 纯文本 token/字：天神 0.762 全场第一（DeepSeek 0.849 / Qwen 0.943 / GPT-4o 1.079）
- 等知识量成本（模型需"知道读音"）：天神 1.52 元/百万字 vs DeepSeek 5.80 元
  （3.8x）/ GPT-4o 57.58 元（37.9x）——知识住在三维几何里，不花 token。

## 一键复现

```powershell
pip install -r requirements.txt
python tools/fetch_gutenberg.py && python tools/fetch_wiki.py --shards 0,1,2
python tools/fetch_english.py
# 训练 64k 词表 + 拼音标注 + 繁体映射
python -m src.tokenizer.train --group a --input data/corpus_clean/train_all.txt --vocab-size 64000 --sentence-limit 3000000 --prefix artifacts/group_a_64k
python -m src.pinyin.annotate --model artifacts/group_a_64k --out artifacts/pinyin/group_a_64k_pinyin.json
python tools/build_traditional_map.py
# 维基词典释义 + 三维平面 + 维度证书 + 词级平面
python tools/parse_wiktionary.py
python tools/certify_planes.py && python tools/certify_meaning.py
python tools/build_word_planes.py
# 评测 + 端到端贯通
python -m eval.polyphone_bench && python -m eval.semantic_bench
python -m eval.token_economy && python -m eval.benchmark --ours artifacts/group_a_64k
python tools/e2e_check.py
python -m pytest -q
# 一键全量（发布闸门：自动审计+自动校准，11 步全过才可发布）
# powershell: Invoke-Expression (Get-Content -Raw tools\audit_gate.ps1)
```

## 数据与许可证（详见 data/README.md）

CC-CEDICT / 中文维基词典 / 中文维基百科：CC BY-SA 4.0（与 GPL-3.0 单向兼容）；
pypinyin（MIT）、edge-tts（GPL-3.0）、Unihan（Unicode License v3）、
CHISE IDS（GPL-2.0-or-later，GPL-3.0 下再发布）；公版经典（公有领域）。

## 已知局限（诚实声明）

1. 义近检索受释义数据覆盖限制（深义层期望词覆盖 22.9%），v0.4 主线为扩展释义源；
2. 义素层与形平面存在合法形义同源重叠（R² 0.52），独立新维度由深义层承担；
3. 部首义素表 13 条冷僻部首标 🟡 待校（开源策管）；
4. 发声挂件需联网（edge-tts）；离线 piper 后端因 espeak 路径问题暂缓（ADR-020）。

## 路线图

- 一、形 ✅ → 二、音 ✅ → 三、意 ✅（本包）
- v0.4：指称钩子（具身接地）+ 释义覆盖扩展
- 阶段 2：小规模预训练（三维词空间作嵌入初始化/特征）
