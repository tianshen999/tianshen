# -*- coding: utf-8 -*-
"""评测报告生成：JSON -> Markdown 表格。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def json_to_markdown(results: dict) -> str:
    lines: list[str] = []
    lines.append("# 中文原生分词器评测报告\n")
    lines.append("> 由 eval/report.py 自动生成。指标定义见 docs/02 §7。\n")

    tokenizers = list(results["tokenizers"].keys())
    metric_names = ["tokens_per_char", "bits_per_char", "char_atomicity", "chars_per_token"]

    # 汇总表
    lines.append("## 汇总（各类别平均）\n")
    lines.append("| 分词器 | token/字 ↓ | bits/字 ↓ | 整字保持率 ↑ | 字/token ↑ |")
    lines.append("|---|---|---|---|---|")
    for name in tokenizers:
        m = results["tokenizers"][name]
        lines.append(
            f"| {name} | {m['tokens_per_char']} | {m.get('bits_per_char', '-')} "
            f"| {m['char_atomicity']} | {m['chars_per_token']} |"
        )
    lines.append("")

    # 分文本类别表
    for cat, entry in results["samples"].items():
        lines.append(f"## 类别：{cat}\n")
        lines.append("| 分词器 | token/字 ↓ | bits/字 ↓ | 整字保持率 ↑ |")
        lines.append("|---|---|---|---|")
        for name in tokenizers:
            m = entry["categories"].get(name)
            if m is None:
                continue
            lines.append(
                f"| {name} | {m['tokens_per_char']} | {m.get('bits_per_char', '-')} | {m['char_atomicity']} |"
            )
        lines.append("")

    lines.append("### 读法")
    lines.append("- **token/字**：每中文字符消耗的 token 数，越低越省（中文税的直接度量）")
    lines.append("- **bits/字**：token 数 × log2(词表大小) / 字数，信息论口径的编码成本，越低越省")
    lines.append("- **整字保持率**：汉字不被拆碎的占比（我们的设计目标 = 1.0）")
    lines.append("- **字/token**：每个 token 承载的中文字符数，越高越密")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="评测报告生成")
    ap.add_argument("results", help="eval_results.json 路径")
    ap.add_argument("--out", default=None, help="输出 md 路径（默认与 results 同目录）")
    args = ap.parse_args(argv)
    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    md = json_to_markdown(data)
    out = Path(args.out) if args.out else Path(args.results).with_suffix(".md")
    out.write_text(md, encoding="utf-8")
    print(f"报告已生成：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
