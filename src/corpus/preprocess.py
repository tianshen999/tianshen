# -*- coding: utf-8 -*-
"""语料清洗：为分词器训练准备干净的中文文本。

设计原则（见 docs/02）：
- 只做清洗，不做繁简转换（保留繁体实验组的可能性，转换留作可选 flag）
- 以"行"为单位去重，去除控制字符
"""
from __future__ import annotations

import argparse
import random
import re
import sys
from pathlib import Path

# CJK 统一表意文字主要区块（注意：扩展 B+ 区必须用 8 位 \U 转义，\u 只吃 4 位）
CJK_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\U00020000-\U0002FA1F]")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WHITESPACE_RE = re.compile(r"[ \t\u3000]+")


def count_cjk(text: str) -> int:
    return len(CJK_RE.findall(text))


def clean_line(line: str) -> str:
    """清洗单行文本，返回清洗后的字符串；不合适的行返回空串。"""
    line = CONTROL_RE.sub("", line)
    line = WHITESPACE_RE.sub(" ", line)
    line = line.strip()
    return line


def is_keep_line(line: str, min_len: int = 10, cjk_ratio: float = 0.5) -> bool:
    """判定一行是否保留：长度够 + 中文占比够（避免纯代码/纯乱码）。"""
    if len(line) < min_len:
        return False
    total_alpha = sum(1 for ch in line if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    if total_alpha == 0:
        return False
    return count_cjk(line) / total_alpha >= cjk_ratio


def clean_corpus(
    input_path: Path,
    output_path: Path,
    min_len: int = 10,
    cjk_ratio: float = 0.5,
    dedup: bool = True,
    max_lines: int | None = None,
) -> dict:
    """清洗整个语料文件。返回统计信息。"""
    seen: set[str] = set()
    kept = 0
    total = 0
    with open(input_path, "r", encoding="utf-8", errors="ignore") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:
        for line in fin:
            total += 1
            if max_lines is not None and total > max_lines:
                break
            line = clean_line(line)
            if not is_keep_line(line, min_len, cjk_ratio):
                continue
            if dedup:
                if line in seen:
                    continue
                seen.add(line)
            fout.write(line + "\n")
            kept += 1
    return {"total": total, "kept": kept, "drop_rate": 1 - kept / max(total, 1)}


def reservoir_sample(
    input_path: Path,
    output_path: Path,
    n_lines: int = 2_000_000,
    seed: int = 42,
) -> int:
    """蓄水池抽样：从大语料中均匀抽 n 行（分词器训练约 5~10 亿字符即可）。"""
    rng = random.Random(seed)
    reservoir: list[str] = []
    total = 0
    with open(input_path, "r", encoding="utf-8", errors="ignore") as fin:
        for line in fin:
            total += 1
            if len(reservoir) < n_lines:
                reservoir.append(line)
            else:
                j = rng.randrange(total)
                if j < n_lines:
                    reservoir[j] = line
    with open(output_path, "w", encoding="utf-8") as fout:
        fout.writelines(reservoir)
    return len(reservoir)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="清洗中文语料")
    ap.add_argument("input", help="输入文本文件")
    ap.add_argument("output", help="输出文本文件")
    ap.add_argument("--min-len", type=int, default=10)
    ap.add_argument("--cjk-ratio", type=float, default=0.5)
    ap.add_argument("--no-dedup", action="store_true")
    ap.add_argument("--max-lines", type=int, default=None)
    args = ap.parse_args(argv)
    stats = clean_corpus(
        Path(args.input), Path(args.output),
        min_len=args.min_len, cjk_ratio=args.cjk_ratio,
        dedup=not args.no_dedup, max_lines=args.max_lines,
    )
    print(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
