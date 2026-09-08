# -*- coding: utf-8 -*-
"""三维几何演示：输入一个字，并排展示 形近 / 音近 / 义近 三列检索结果。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import scipy.sparse as sp  # noqa: E402

from eval.semantic_bench import load_char_set, retrieve  # noqa: E402
from src.semantic import weighting as WT  # noqa: E402


def main() -> int:
    chars = load_char_set()
    F = WT.idf_transform(sp.load_npz(str(ROOT / "artifacts/semantic/form_plane.npz")),
                         keep_last_col_unweighted=True)
    P = WT.idf_transform(sp.load_npz(str(ROOT / "artifacts/semantic/sound_plane.npz")))
    S2 = sp.hstack([
        WT.idf_transform(sp.load_npz(str(ROOT / "artifacts/semantic/meaning_plane.npz"))),
        sp.load_npz(str(ROOT / "artifacts/semantic/meaning_keywords.npz")),
    ]).tocsr()

    queries = sys.argv[1:] or ["水", "火", "心", "山", "爱", "湖"]
    print(f"{'探针':<4} {'形近（F）':<24} {'音近（P）':<24} {'义近（S2）':<24}")
    print("-" * 80)
    for q in queries:
        if q not in set(chars):
            print(f"{q:<4} 不在字符集中")
            continue
        f = retrieve(F, chars, q, 5)
        p = retrieve(P, chars, q, 5)
        s = retrieve(S2, chars, q, 5)
        print(f"{q:<4} {' '.join(f):<24} {' '.join(p):<24} {' '.join(s):<24}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
