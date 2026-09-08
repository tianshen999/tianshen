# -*- coding: utf-8 -*-
"""意平面 S：字符/词 → 意向量（部首义素 + 部件义素聚合 + 义项特征）。

设计定案见 docs/09。字符向量 L2 归一化；词级 = 字符向量均值（义素部分）
+ 词级义项特征，再归一化。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from src.semantic.radical_semantics import sememe_of_char
from src.tokenizer import radicals as R

ROOT = Path(__file__).resolve().parent.parent.parent

DIM_SEMEME = 214            # 部首义素
DIM_COMPONENT_SEMEME = 214  # 部件义素聚合
DIM_DEF_FEATURES = 4        # 中文义项存在 / 义项数 / 英文释义存在 / 多音标记
DIM = DIM_SEMEME + DIM_COMPONENT_SEMEME + DIM_DEF_FEATURES


@lru_cache(maxsize=None)
def _decompose(ch: str) -> list[str]:
    return R.decompose(ch, 3)


@lru_cache(maxsize=None)
def _is_atomic(ch: str) -> bool:
    return ch not in R.load_ids()


@lru_cache(maxsize=1)
def _wiktionary() -> dict[str, list[str]]:
    p = ROOT / "artifacts" / "semantic" / "wiktionary_zh.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


@lru_cache(maxsize=1)
def _max_def_count() -> int:
    w = _wiktionary()
    return max((len(v) for v in w.values()), default=1)


def _def_features(key: str, is_char: bool) -> list[float]:
    """义项特征 4 维：[有中文释义, log 义项数归一, 有 kDefinition, 多音]。"""
    w = _wiktionary()
    defs = w.get(key)
    has_zh = 1.0 if defs else 0.0
    n = len(defs) if defs else 0
    log_n = np.log1p(n) / np.log1p(_max_def_count())
    has_en = 1.0 if R.load_unihan().get(key, {}).get("kDefinition") else 0.0
    from src.pinyin.unihan import readings
    poly = 1.0 if len(readings(key)) > 1 else 0.0
    return [has_zh, float(log_n), has_en, poly]


def char_vector(ch: str) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    # 部首义素
    s = sememe_of_char(ch)
    if s is not None:
        v[s] = 1.0
    # 部件义素聚合：原子部件的部首义素词袋
    for p in _decompose(ch):
        if not _is_atomic(p):
            continue
        ps = sememe_of_char(p)
        if ps is not None:
            v[DIM_SEMEME + ps] += 1.0
    # 义项特征（字符级）
    v[DIM_SEMEME + DIM_COMPONENT_SEMEME:] = _def_features(ch, is_char=True)
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


def word_vector(word: str) -> np.ndarray:
    vecs = [char_vector(c) for c in word]
    v = np.mean(vecs, axis=0) if vecs else np.zeros(DIM, dtype=np.float32)
    # 词级义项特征覆盖字符级
    v[DIM_SEMEME + DIM_COMPONENT_SEMEME:] = _def_features(word, is_char=False)
    norm = np.linalg.norm(v)
    return (v / norm).astype(np.float32) if norm > 0 else v


def build(chars: list[str]) -> sp.csr_matrix:
    return sp.csr_matrix(np.vstack([char_vector(c) for c in chars]))


def save_plane(matrix: sp.csr_matrix, keys: list[str], out_dir: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sp.save_npz(out / "meaning_plane.npz", matrix)
    meta = {
        "plane": "S",
        "n": matrix.shape[0],
        "dim": DIM,
        "dim_sememe": DIM_SEMEME,
        "dim_component_sememe": DIM_COMPONENT_SEMEME,
        "dim_def_features": DIM_DEF_FEATURES,
        "keys": keys,
    }
    (out / "meaning_plane.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return out / "meaning_plane.npz"
