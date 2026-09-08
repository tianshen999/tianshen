# 天神 v0.2 发布说明（形 + 音）

**项目**：天神（Tianshen）——中文原生 AI 全栈体系，第二版：形+音合并词表。
**许可证**：GPL-3.0（全文见 LICENSE）。
**发布日期**：2026-09。

## 本包内容

```
README.md           项目总览与实验结果
LICENSE             GPL-3.0 全文
RELEASE.md          本文件
pyproject.toml      项目配置（v0.2.0）
requirements.txt    Python 依赖
src/                代码（语料层 / 分词器层 / 拼音层）
eval/               评测体系（分词器四维评测 + 多音消歧评测）
tests/              34 个单元测试（全绿）
docs/               调研笔记、设计文档、决策记录（ADR 001~020）
models/             词表模型（64k/32k/整字对照/拉丁挂件）
pinyin/             形+音标注数据（词级拼音 JSON、繁体映射、模型文件）
report/             评测报告（分词器四维对比）
data/               字形与词典数据 + 许可证清单
tools/              语料下载与复现脚本
```

## v0.2 新增（音阶段）

1. **拼音数据层**（src/pinyin/）：Unihan kHanyuPinyin/kMandarin/kXHC1983 整合
   —— GB2312 常用字（8,965 字）拼音覆盖 **100%**；全量汉字 44,359 字；
   多音字 8,537 个。音节解析支持数字调号/变音调号/注音符号三向转换。
2. **词级拼音标注**：64k 词表 **39,594 个多字词全部标注**词级读音。
   四级流水线：人工校对（《现代汉语词典》标准）→ CC-CEDICT → pypinyin 词组 → 逐字兜底。
3. **多音消歧评测**（eval/polyphone_bench.py）：185 个多音词公开测试集，
   **天神 100% vs pypinyin 95.1%**（同题对比，测试集随包发布）。
4. **注音输出挂件**（默认关闭）：银行 → ㄧㄣˊ ㄏㄤˊ；核心拼音输出不依赖挂件。
5. **字/词级发声挂件**（默认关闭）：edge-tts 后端，字/词标准读音合成；
   整句朗读按设计延后至"意"阶段（ADR-017）。
6. **繁体同步标注**：CEDICT 繁体键 76,839 词条（銀行→yín háng、音樂→yīn yuè）。

## 核心 API 速览

```python
from src.pinyin.annotator import PinyinAnnotator
ann = PinyinAnnotator("pinyin/group_a_64k_pinyin.json")
ann.pinyin("银行")            # 'yín háng'（核心，永远可用）
ann.numbered("行走")          # 'xing2 zou3'
ann.zhuyin_render("银行")     # None（注音挂件默认关）
ann.zhuyin.enable(True)       # 打开挂件
ann.zhuyin_render("银行")     # 'ㄧㄣˊ ㄏㄤˊ'
ann.voice.enable(True)        # 打开发声挂件
ann.speak("天神", "out.mp3")  # 合成标准读音音频
```

## 一键复现

```powershell
pip install -r requirements.txt
# 语料与词典（公版经典 / 中文维基 / 英文挂件语料 / CC-CEDICT）
python tools/fetch_gutenberg.py && python tools/fetch_wiki.py --shards 0,1,2
python tools/fetch_english.py
# 训练 64k 核心词表 + 词级拼音标注 + 繁体映射
python -m src.tokenizer.train --group a --input data/corpus_clean/train_all.txt --vocab-size 64000 --sentence-limit 3000000 --prefix artifacts/group_a_64k
python -m src.pinyin.annotate --model artifacts/group_a_64k --out artifacts/pinyin/group_a_64k_pinyin.json
python tools/build_traditional_map.py
# 评测
python -m eval.polyphone_bench
python -m eval.benchmark --ours artifacts/group_a_64k
python -m pytest -q
```

## 数据与许可证（详见 data/README.md）

- CC-CEDICT：CC BY-SA 4.0（与 GPL-3.0 单向兼容，本包 GPL-3.0 下再发布）
- pypinyin（词组读音数据源）：MIT
- edge-tts（发声挂件后端）：GPL-3.0
- 中文维基百科：CC BY-SA 4.0；公版经典：公有领域
- Unihan：Unicode License v3；CHISE IDS：GPL-2.0-or-later（GPL-3.0 下再发布）

## 已知局限

1. 发声挂件需联网（edge-tts）；离线 piper 后端因 espeak 数据路径的
   Windows 打包问题暂缓（ADR-020）。
2. 词级标注中 38.7% 词为 CEDICT 词级命中，其余按流水线兜底；
   多音评测集 100% 通过，但开放域文本仍有长尾风险。
3. 整句朗读留待"意"阶段。

## 路线图（形 → 音 → 意）

- 一、形 ✅（v0.1）
- 二、音 ✅（v0.2，本包）
- 三、意 ⏳（下一步）
