# -*- coding: utf-8 -*-
"""汉字覆盖率分析：检查词表对全量汉字的覆盖情况（哪些字会变成 <unk>）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.tokenizer.radicals import all_hanzi  # noqa: E402
from src.tokenizer.tokenizer import CharTokenizer, SpTokenizer, load_tokenizer  # noqa: E402


def check_coverage(prefix: str, charset: list[str] | None = None) -> dict:
    tok = load_tokenizer(prefix)
    chars = charset if charset is not None else all_hanzi()
    missing: list[str] = []
    for ch in chars:
        if isinstance(tok, SpTokenizer):
            # 注意：未登录字编码为 unk（id=0）但 out_type=str 会显示原字形，
            # 因此必须以 id 判断，不能用 piece 字符串。
            ids = tok.sp.encode(ch, out_type=int)
            covered = 0 not in ids
        else:
            ids = tok.encode(ch)
            covered = ids[0] != tok.unk_id
        if not covered:
            missing.append(ch)
    return {
        "total": len(chars),
        "covered": len(chars) - len(missing),
        "missing": len(missing),
        "coverage": round((len(chars) - len(missing)) / max(len(chars), 1), 4),
        "samples": missing[:20],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="词表汉字覆盖率检查")
    ap.add_argument("prefix", help="模型前缀（如 artifacts/group_a_32k）")
    args = ap.parse_args(argv)
    from src.tokenizer.radicals import gb2312_chars
    for label, charset in [
        ("全量汉字（Unihan）", all_hanzi()),
        ("GB2312 常用字", gb2312_chars()),
    ]:
        stats = check_coverage(args.prefix, charset)
        print(f"{label}: 覆盖 {stats['covered']}/{stats['total']} ({stats['coverage']:.2%})")
        if stats["missing"]:
            print(f"  缺失样本: {''.join(stats['samples'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
