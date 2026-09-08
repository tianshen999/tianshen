# -*- coding: utf-8 -*-
"""义项关键词袋（深义层）：从维基词典中文释义提取语义关键词向量。

这是意平面中真正独立于形/音的部分——释义文本内容无法由部首或读音推出。
用自家分词器（group_a_64k）对释义分词，取高频实义词为关键词词汇表（top-K），
每个字/词的向量 = 其释义的关键词词袋（IDF 加权）。
"""
from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parent.parent.parent

from src.semantic.script_tag import to_simplified

STOPWORDS = set("的一种或亦指之人事物用于其和与为在是的有表示同上之乎者也这那".split())
STOPWORDS |= set("个条种名动形数量代助介连叹拟词缀前缀后缀专有名")
# 维基词典模板套话（第一轮词汇表观察所得，持续策管）
STOPWORDS |= {"一種", "的人", "之一", "用於", "的樣子", "作為", "一個", "沒有",
              "事物", "古代", "方言", "比喻", "位於", "使用", "書面", "形容",
              "中的", "進行", "國家", "中國", "臺灣", "閩南語", "粵語", "客家語",
              "泉漳", "乾燥", "藥材", "引申", "泛指", "俗称", "俗稱", "同義詞",
              "同义词", "指稱"}
# 简繁特征校准（ADR-030）：释义文本是繁体，关键词必须转简——停用词同步转简
STOPWORDS = {to_simplified(w) for w in STOPWORDS} | STOPWORDS

_CJK = re.compile(r"^[\u4e00-\u9fff]{2,}$")


@lru_cache(maxsize=1)
def _wiktionary() -> dict[str, list[str]]:
    p = ROOT / "artifacts" / "semantic" / "wiktionary_zh.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@lru_cache(maxsize=1)
def _tokenizer():
    from src.tokenizer.tokenizer import load_tokenizer
    return load_tokenizer("artifacts/group_a_64k")


def _def_words(defs: list[str]) -> list[str]:
    """释义 → 关键词列表（简繁校准：释义转简后再分词）。"""
    tok = _tokenizer()
    out = []
    for d in defs:
        d = to_simplified(re.sub(r"[^\u4e00-\u9fff]", " ", d))
        for piece in tok.pieces(d):
            core = piece.lstrip("\u2581")
            if _CJK.match(core) and core not in STOPWORDS:
                out.append(core)
    return out


def build_vocab(min_freq: int = 3, top_k: int = 2000) -> list[str]:
    w = _wiktionary()
    counter: Counter = Counter()
    for defs in w.values():
        for kw in set(_def_words(defs)):  # 每词条去重
            counter[kw] += 1
    vocab = [k for k, c in counter.most_common(top_k) if c >= min_freq]
    return vocab


def keyword_vector(key: str, vocab: list[str], idx: dict[str, int]) -> np.ndarray:
    defs = _wiktionary().get(key)
    if not defs:
        return np.zeros(len(vocab), dtype=np.float32)
    v = np.zeros(len(vocab), dtype=np.float32)
    for kw in set(_def_words(defs)):
        if kw in idx:
            v[idx[kw]] += 1.0
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


def build_matrix(keys: list[str], min_freq: int = 3, top_k: int = 2000,
                 idf: bool = True, prune_dead: bool = True,
                 merge_collinear: bool = True) -> tuple[sp.csr_matrix, list[str]]:
    vocab = build_vocab(min_freq, top_k)
    idx = {k: i for i, k in enumerate(vocab)}
    rows = [keyword_vector(k, vocab, idx) for k in keys]
    X = sp.csr_matrix(np.vstack(rows))
    if prune_dead:
        # 剪除死维度：在字符矩阵中从未激活的关键词列（其只在词释义中出现）
        active = np.asarray((X != 0).sum(axis=0)).ravel() > 0
        X = X[:, active]
        vocab = [v for v, a in zip(vocab, active) if a]
    if merge_collinear:
        # 共线列合并（ADR-030）：完全同形的列（共现关键词）合并为一维
        keep: list[int] = []
        seen: dict[tuple, int] = {}
        Xc = X.tocsc()
        for j in range(Xc.shape[1]):
            col = Xc[:, j]
            pattern = tuple(col.indices)  # 同形列 = 相同非零行
            if pattern in seen:
                continue
            seen[pattern] = j
            keep.append(j)
        X = X[:, keep]
        vocab = [vocab[j] for j in keep]
    if idf and X.shape[0] > 0:
        from src.semantic.weighting import idf_weights, apply_idf
        X = apply_idf(X, idf_weights(X))
    return X, vocab


def save_keywords(matrix: sp.csr_matrix, keys: list[str], vocab: list[str],
                  out_dir: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sp.save_npz(out / "meaning_keywords.npz", matrix)
    meta = {"n": matrix.shape[0], "dim": matrix.shape[1], "vocab": vocab, "keys": keys}
    (out / "meaning_keywords.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return out / "meaning_keywords.npz"
