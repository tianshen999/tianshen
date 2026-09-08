# -*- coding: utf-8 -*-
"""下载中文维基百科 parquet 分片（hf-mirror），抽取正文并按字数上限抽样。

用法：python tools/fetch_wiki.py [--shards 0,1,2] [--max-chars 500000000]
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

REPO = "wikimedia/wikipedia"
REVISION = "20231101.zh"
BASE = f"https://hf-mirror.com/datasets/{REPO}/resolve/main/{REVISION}"


def download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"已存在，跳过：{dest.name}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"下载 {dest.name} ...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "zh-native-tokenizer/0.1"})
    with urllib.request.urlopen(req, timeout=600) as resp, open(dest, "wb") as fout:
        while True:
            buf = resp.read(1 << 20)
            if not buf:
                break
            fout.write(buf)
    print(f"完成 {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards", default="0,1,2", help="逗号分隔的分片编号")
    ap.add_argument("--max-chars", type=int, default=500_000_000, help="保留的最大字符数")
    args = ap.parse_args(argv)

    import pyarrow.parquet as pq

    out_dir = Path("data/raw/wiki")
    clean_dir = Path("data/corpus_clean")
    clean_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    total_chars = 0

    with open(clean_dir / "wiki_all.txt", "w", encoding="utf-8") as fout:
        for sid in [int(s) for s in args.shards.split(",")]:
            fname = f"train-{sid:05d}-of-00006.parquet"
            dest = out_dir / fname
            download(f"{BASE}/{fname}", dest)
            table = pq.read_table(dest, columns=["text"])
            text_col = table.column("text").to_pylist()
            kept = 0
            for doc in text_col:
                if not doc:
                    continue
                for line in str(doc).splitlines():
                    line = line.strip()
                    if len(line) < 8:
                        continue
                    cjk = sum(1 for c in line if "\u3400" <= c <= "\u9fff")
                    if cjk / max(len(line), 1) < 0.5:
                        continue
                    if line in seen:
                        continue
                    seen.add(line)
                    fout.write(line + "\n")
                    total_chars += len(line)
                    kept += 1
                    if total_chars >= args.max_chars:
                        print(f"达到上限 {args.max_chars} 字符，停止。")
                        print(f"合计保留 {kept} 行（本分片）")
                        return 0
            print(f"{fname}: 本分片保留 {kept} 行，累计 {total_chars / 1e8:.2f} 亿字符", flush=True)

    print(f"完成：累计 {total_chars / 1e8:.2f} 亿字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
