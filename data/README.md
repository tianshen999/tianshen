# 数据来源与许可证声明

本项目发布的代码、词表与文档遵循 GPL-3.0（见根目录 LICENSE）。
本项目使用/派生的外部数据按各自许可证声明如下：

## 训练语料

| 语料 | 来源 | 许可证 | 说明 |
|---|---|---|---|
| 公版中文经典（三国演义/西游记/红楼梦/论语等 5 部） | Project Gutenberg（pg23950 等） | 公有领域 | 下载脚本 tools/fetch_gutenberg.py |
| 中文维基百科 20231101 版（3 个 parquet 分片） | wikimedia/wikipedia（经 hf-mirror.com 镜像下载） | CC BY-SA 4.0 | 词表为统计派生数据；如再发布维基原文需遵守相同许可并署名 |
| 公版英文经典（Pride and Prejudice 等 4 部） | Project Gutenberg | 公有领域 | 挂件词表训练语料，tools/fetch_english.py |

## 字形数据

| 数据 | 来源 | 许可证 |
|---|---|---|
| Unihan.zip | https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip | Unicode 数据文件与软件许可（Unicode License v3） |
| IDS 部件分解（IDS-UCS-Basic + Ext-A 合并） | CHISE IDS 项目（github.com/chise/ids） | GPL-2.0-or-later（源项目），本项目在 GPL-3.0 下重新发布 |

## 评测参考词表（仅用于对比，不随发布包分发）

GPT（tiktoken 编码文件）、Qwen/DeepSeek/Yi/ChatGLM 官方 tokenizer——
评测脚本按需从官方源下载，版权归各自所有者。

## 大规模语料（不入库、不随发布包分发）

清洗后的 4.32 亿字符语料（data/corpus_clean/）体积过大不入库；
发布包只含**下载与复现脚本**，任何人可一键重建。
