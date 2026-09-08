# -*- coding: utf-8 -*-
"""词级三维平面：为 39k 词汇构建 F/P/S 词向量（字符向量均值聚合 + 词级特征）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import scipy.sparse as sp  # noqa: E402

from src.semantic import meaning_plane as MP  # noqa: E402
from src.semantic import sound_plane as SP  # noqa: E402
from src.semantic.form_plane import FormPlaneBuilder  # noqa: E402


def load_word_set() -> list[str]:
    """核心词集（繁体词转简去重；ADR-027）。"""
    from src.semantic.core_sets import core_words
    return core_words()


def main() -> int:
    words = load_word_set()
    print(f"词集: {len(words)}")

    # 字符集（构建器需要）
    data = json.loads(
        (ROOT / "artifacts" / "pinyin" / "group_a_64k_pinyin.json").read_text(encoding="utf-8"))
    chars = sorted(k for k, v in data["entries"].items() if v.get("type") == "char")
    fb = FormPlaneBuilder(chars)

    F = sp.csr_matrix(np.vstack([fb.word_vector(w) for w in words]))
    P = sp.csr_matrix(np.vstack([SP.word_vector(w) for w in words]))
    S = sp.csr_matrix(np.vstack([MP.word_vector(w) for w in words]))

    out = ROOT / "artifacts" / "semantic"
    for name, X in [("word_form_plane", F), ("word_sound_plane", P), ("word_meaning_plane", S)]:
        sp.save_npz(out / f"{name}.npz", X)
        (out / f"{name}.meta.json").write_text(
            json.dumps({"n": X.shape[0], "dim": X.shape[1], "keys": words},
                       ensure_ascii=False), encoding="utf-8")
    print(f"已保存: word_form/sound/meaning_plane.npz（{len(words)} 词 × 三平面）")

    # 词级演示
    idx = {w: i for i, w in enumerate(words)}
    for probe in ["银行", "音乐", "高兴", "人工智能"]:
        if probe not in idx:
            continue
        print(f"\n【{probe}】")
        for name, X in [("形近", F), ("音近", P), ("义近", S)]:
            v = np.asarray(X[idx[probe]].toarray()).ravel()
            if np.linalg.norm(v) < 1e-9:
                print(f"  {name}: （无数据）")
                continue
            sims = np.asarray(X @ v).ravel()
            order = np.argsort(-sims)
            nn = []
            for j in order:
                if words[j] != probe:
                    nn.append(words[j])
                if len(nn) >= 5:
                    break
            print(f"  {name}: " + " ".join(nn))
    return 0


if __name__ == "__main__":
    sys.exit(main())
