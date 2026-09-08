# -*- coding: utf-8 -*-
"""挂件代价/收益量化：核心词表开/关挂件，在纯中文与混排文本上的 token 消耗对比。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.tokenizer.tokenizer import CompositeTokenizer  # noqa: E402


def main() -> int:
    tok = CompositeTokenizer("artifacts/group_a_64k", "artifacts/plug_en")
    samples_dir = ROOT / "eval" / "samples"
    print(f"{'样本':<12} {'挂件关':>8} {'挂件开':>8} {'节省':>8}")
    print("-" * 40)
    for f in sorted(samples_dir.glob("*.txt")):
        text = f.read_text(encoding="utf-8").strip()
        tok.enable_plug(False)
        n_off = len(tok.pieces(text))
        tok.enable_plug(True)
        n_on = len(tok.pieces(text))
        delta = n_off - n_on
        sign = "+" if delta > 0 else ""
        print(f"{f.stem:<12} {n_off:>8} {n_on:>8} {sign}{delta:>7}")
    tok.enable_plug(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
