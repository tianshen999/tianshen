# -*- coding: utf-8 -*-
"""形平面 F：字符 → 形向量（部首/原子部件/结构类型/笔画）。

设计定案见 docs/08。字符向量 L2 归一化；词级向量 = 字符向量均值后归一化。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from src.semantic.script_tag import to_simplified
from src.tokenizer import radicals as R

STRUCTURE_OPS = list("⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻")


@lru_cache(maxsize=None)
def _decompose_cached(ch: str, depth: int = 3) -> list[str]:
    return R.decompose(ch, depth)


@lru_cache(maxsize=None)
def _atomic(ch: str) -> bool:
    """原子部件：自身无 IDS 分解记录。"""
    return ch not in R.load_ids()


def collect_atomic_components(chars: list[str], depth: int = 3) -> list[str]:
    """从字符集收集原子部件词汇表（按出现频次排序；部件经简繁校准转简）。"""
    freq: dict[str, int] = {}
    for ch in chars:
        parts = _decompose_cached(ch, depth)
        for p in parts:
            if _atomic(p):
                p = to_simplified(p)  # 部件脚本校准（ADR-030）
                freq[p] = freq.get(p, 0) + 1
    return sorted(freq, key=lambda c: -freq[c])


class FormPlaneBuilder:
    """构建形平面矩阵。维度 = 214 部首 + N_c 部件 + 12 结构 + 1 笔画。"""

    def __init__(self, chars: list[str]):
        self.chars = list(chars)
        self.components = collect_atomic_components(self.chars)
        self.dim_radical = 214
        self.dim_component = len(self.components)
        self.dim_struct = 12
        self.dim_stroke = 1
        self.dim = self.dim_radical + self.dim_component + self.dim_struct + self.dim_stroke
        self._comp_idx = {c: i for i, c in enumerate(self.components)}

    def char_vector(self, ch: str, weighted: bool = False) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        # 部首
        rn = R.char_radical_num(ch)
        if rn is not None and 1 <= rn <= 214:
            v[rn - 1] = 1.0
        # 原子部件（词袋；weighted 时取平方根抑制高频部件；部件经简繁校准）
        for p in _decompose_cached(ch):
            if not _atomic(p):
                continue
            p = to_simplified(p)
            if p in self._comp_idx:
                v[self.dim_radical + self._comp_idx[p]] += 1.0
        if weighted:
            idx = slice(self.dim_radical, self.dim_radical + self.dim_component)
            v[idx] = np.sqrt(v[idx])
        # 结构类型（一级 IDS 运算符）
        ids = R.load_ids().get(ch, "")
        if ids and ids[0] in STRUCTURE_OPS:
            v[self.dim_radical + self.dim_component + STRUCTURE_OPS.index(ids[0])] = 1.0
        # 笔画数
        strokes = R.load_unihan().get(ch, {}).get("kTotalStrokes", "")
        try:
            v[-1] = min(int(strokes), 64) / 64.0
        except (TypeError, ValueError):
            pass
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v

    def build(self, weighted: bool = False) -> sp.csr_matrix:
        rows = [self.char_vector(c, weighted) for c in self.chars]
        return sp.csr_matrix(np.vstack(rows))

    def word_vector(self, word: str, weighted: bool = False) -> np.ndarray:
        """词级聚合：字符向量均值 + L2 归一化。"""
        vecs = [self.char_vector(c, weighted) for c in word]
        if not vecs:
            return np.zeros(self.dim, dtype=np.float32)
        v = np.mean(vecs, axis=0)
        norm = np.linalg.norm(v)
        return (v / norm).astype(np.float32) if norm > 0 else v


def save_plane(matrix: sp.csr_matrix, keys: list[str], builder: "FormPlaneBuilder",
               out_dir: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sp.save_npz(out / "form_plane.npz", matrix)
    import json
    meta = {
        "plane": "F",
        "n": matrix.shape[0],
        "dim": builder.dim,
        "dim_radical": builder.dim_radical,
        "dim_component": builder.dim_component,
        "dim_struct": builder.dim_struct,
        "dim_stroke": builder.dim_stroke,
        "components": builder.components,
        "structure_ops": STRUCTURE_OPS,
        "keys": keys,
    }
    (out / "form_plane.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return out / "form_plane.npz"
