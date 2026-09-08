# -*- coding: utf-8 -*-
"""脚本判定与简繁映射（ADR-027：简体为主、繁体挂件）。

- classify(ch)：简 / 繁 / 通用（Unihan kSimplifiedVariant/kTraditionalVariant）
- trad_to_simp(ch)：繁 → 简（无对应返回自身）
- 繁体挂件索引：繁字不占核心坐标，路由到对应简字
"""
from __future__ import annotations

from functools import lru_cache

from src.tokenizer import radicals as R


@lru_cache(maxsize=None)
def classify(ch: str) -> str:
    """字符脚本分类（修正：Unihan 变体字段首位是字符自身，需排除）。

    - 简：kTraditionalVariant 首项指向他字（本字是某繁体字的简体）
    - 繁：kSimplifiedVariant 首项指向他字（本字是某简体字的繁体）
    - 通用：无变体，或变体首项指向自身（如 万/个——简繁同形的简化字）
    """
    props = R.load_unihan().get(ch, {})
    simp = _parse_variant(props.get("kSimplifiedVariant", ""))
    trad = _parse_variant(props.get("kTraditionalVariant", ""))
    if simp and simp != ch:
        return "繁"
    if trad and trad != ch:
        return "简"
    return "通用"


@lru_cache(maxsize=None)
def _parse_variant(value: str | None) -> str | None:
    """解析 Unihan 变体字段（U+7231 形式）→ 字符。空值返回 None。"""
    if not value:
        return None
    v = value.split()[0]
    if v.startswith("U+"):
        try:
            return chr(int(v[2:], 16))
        except ValueError:
            return None
    return v or None


@lru_cache(maxsize=None)
def trad_to_simp(ch: str) -> str:
    """繁体字 → 简体字（Unihan kSimplifiedVariant 第一映射）。"""
    v = R.load_unihan().get(ch, {}).get("kSimplifiedVariant", "")
    c = _parse_variant(v) if v else None
    return c if c else ch


@lru_cache(maxsize=1)
def cedict_pairs() -> tuple[dict[str, str], dict[str, str]]:
    """CEDICT 简繁双向映射（补充 Unihan 未覆盖的词级字对）。"""
    from src.pinyin.cedict import load_cedict
    s2t: dict[str, str] = {}
    t2s: dict[str, str] = {}
    for simp, entries in load_cedict().items():
        for e in entries:
            trad = e.get("trad", "")
            if trad and trad != simp and len(trad) == len(simp):
                for a, b in zip(trad, simp):
                    t2s.setdefault(a, b)
                    s2t.setdefault(b, a)
    return s2t, t2s


def trad_to_simp_full(ch: str) -> str:
    """繁→简（Unihan 优先，CEDICT 字对兜底）。"""
    v = trad_to_simp(ch)
    if v != ch:
        return v
    _, t2s = cedict_pairs()
    return t2s.get(ch, ch)


def to_simplified(text: str) -> str:
    """逐字转简（繁体挂件路由的入口）。"""
    return "".join(trad_to_simp_full(c) for c in text)
