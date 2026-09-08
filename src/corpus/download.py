# -*- coding: utf-8 -*-
"""开源中文语料下载清单与脚本。

注意：数据文件不入库（见 .gitignore）。本文件只记录来源与许可证，
下载脚本供需要时运行。所有来源见 docs/02 §5 的选型理由。
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

# (名称, 规模, 许可证, 说明/URL)
CORPORA: list[dict] = [
    {
        "name": "zhwiki",
        "desc": "中文维基百科全量 dump（~2.5GB 压缩包，解压后约 15 亿字符）",
        "license": "CC BY-SA 4.0",
        "url": "https://dumps.wikimedia.org/zhwiki/latest/zhwiki-latest-pages-articles.xml.bz2",
        "note": "需要 wiki 文本抽取（extract_text），可由 preprocess 之后的本项目脚本处理",
    },
    {
        "name": "wanjuan",
        "desc": "书生·万卷 WanJuan 1.0 文本子集（上海 AI 实验室，3B+ 文档）",
        "license": "开放（研究用途，具体以官方为准）",
        "url": "https://opendatalab.com/WanJuan1.0",
        "note": "建议经 HuggingFace/OpenDataLab 下载文本子集",
    },
    {
        "name": "skypile",
        "desc": "SkyPile-150B（昆仑万维，150B token 网络文本）",
        "license": "开放",
        "url": "https://huggingface.co/datasets/Skywork/SkyPile-150B",
        "note": "HF datasets 流式抽样即可，无需全量下载",
    },
    {
        "name": "mnbvc",
        "desc": "MNBVC 超大规模中文语料集（目标 40T，含古诗/歌词/台词/聊天等小众领域）",
        "license": "开源项目（各子集许可证不同，需逐集核对）",
        "url": "https://github.com/esbatmop/MNBVC",
        "note": "按领域目录抽样",
    },
    {
        "name": "mc4-zh",
        "desc": "mC4 中文子集（Common Crawl）",
        "license": "开放（CC 派生）",
        "url": "https://huggingface.co/datasets/mc4",
        "note": "备选",
    },
]


def download(url: str, dest: Path, chunk: int = 1 << 20) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"下载 {url} -> {dest}")
    req = urllib.request.Request(url, headers={"User-Agent": "zh-native-tokenizer/0.1"})
    with urllib.request.urlopen(req) as resp, open(dest, "wb") as fout:
        while True:
            buf = resp.read(chunk)
            if not buf:
                break
            fout.write(buf)
    print(f"完成：{dest}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="开源中文语料清单与下载")
    ap.add_argument("--list", action="store_true", help="仅列出语料清单")
    ap.add_argument("--get", help="按名称下载（仅支持直链）")
    ap.add_argument("--dest", default="data/raw")
    args = ap.parse_args(argv)

    if args.list or not args.get:
        for c in CORPORA:
            print(f"{c['name']:10s} | {c['license']:30s} | {c['desc']}")
            print(f"{'':10s}   {c['url']}  ({c['note']})")
        return 0

    target = next((c for c in CORPORA if c["name"] == args.get), None)
    if target is None:
        print(f"未知语料：{args.get}（用 --list 查看）", file=sys.stderr)
        return 1
    download(target["url"], Path(args.dest) / (target["name"] + ".raw"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
