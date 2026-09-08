# -*- coding: utf-8 -*-
"""音平面 P：字符 → 音向量（声母/韵母/声调，多音字取全读音词袋）。

设计定案见 docs/08。字符向量 L2 归一化；词级向量 = 字符向量均值后归一化。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from src.pinyin.syllable import FINAL_TO_ZHUYIN, INITIAL_TO_ZHUYIN, INITIALS
from src.pinyin.unihan import readings

# 维度定义（依据 syllable.py 实际表）
FINALS = sorted(set(FINAL_TO_ZHUYIN.keys()) - {"-i"}) + ["-i"]  # 韵母槽（含叹词与舌尖元音）
DIM_INITIAL = len(INITIALS) + 1          # 21 声母 + 零声母 + 未知
DIM_FINAL = len(FINALS) + 1              # 全部韵母 + 未知
DIM_TONE = 6                              # 1~4 + 轻声 + 未知
DIM = DIM_INITIAL + DIM_FINAL + DIM_TONE

_INITIAL_IDX = {ini: i for i, ini in enumerate(INITIALS)}
_FINAL_IDX = {f: i for i, f in enumerate(FINALS)}
_UNK_INITIAL = len(INITIALS)
_UNK_FINAL = len(FINALS)


def char_vector(ch: str, weighted: bool = False) -> np.ndarray:
    """字符音向量：全部读音的词袋 one-hot 求和 + L2 归一化。

    weighted=True 时读数计数取平方根（修订 1：抑制高频读音的谱主导）。
    """
    v = np.zeros(DIM, dtype=np.float32)
    for syl in readings(ch):
        v[_INITIAL_IDX.get(syl.initial, _UNK_INITIAL)] += 1.0
        v[DIM_INITIAL + _FINAL_IDX.get(syl.final, _UNK_FINAL)] += 1.0
        v[DIM_INITIAL + DIM_FINAL + min(max(syl.tone, 0), 5)] += 1.0
    if weighted:
        v = np.sqrt(v)
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


def word_vector(word: str, weighted: bool = False) -> np.ndarray:
    vecs = [char_vector(c, weighted) for c in word]
    v = np.mean(vecs, axis=0) if vecs else np.zeros(DIM, dtype=np.float32)
    norm = np.linalg.norm(v)
    return (v / norm).astype(np.float32) if norm > 0 else v


def build(chars: list[str], weighted: bool = False) -> sp.csr_matrix:
    return sp.csr_matrix(np.vstack([char_vector(c, weighted) for c in chars]))


def save_plane(matrix: sp.csr_matrix, keys: list[str], out_dir: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sp.save_npz(out / "sound_plane.npz", matrix)
    meta = {
        "plane": "P",
        "n": matrix.shape[0],
        "dim": DIM,
        "dim_initial": DIM_INITIAL,
        "dim_final": DIM_FINAL,
        "dim_tone": DIM_TONE,
        "initials": INITIALS,
        "finals": FINALS,
        "keys": keys,
    }
    (out / "sound_plane.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return out / "sound_plane.npz"
