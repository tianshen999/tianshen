# -*- coding: utf-8 -*-
"""核心字符/词汇集与繁体挂件索引（ADR-027）。

核心 = 简体 + 通用字符；繁体经挂件索引路由到对应简体。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from src.semantic.script_tag import classify, to_simplified

ROOT = Path(__file__).resolve().parent.parent.parent


@lru_cache(maxsize=1)
def _entries() -> dict:
    return json.loads(
        (ROOT / "artifacts" / "pinyin" / "group_a_64k_pinyin.json").read_text(encoding="utf-8")
    )["entries"]


@lru_cache(maxsize=1)
def core_chars() -> list[str]:
    """核心字符集：简体 + 通用（排除繁体）。"""
    return sorted(k for k, v in _entries().items()
                  if v.get("type") == "char" and classify(k) != "繁")


@lru_cache(maxsize=1)
def trad_chars() -> list[str]:
    return sorted(k for k, v in _entries().items()
                  if v.get("type") == "char" and classify(k) == "繁")


@lru_cache(maxsize=1)
def core_words() -> list[str]:
    """核心词集：原词转简后去重（繁体词路由到简体形式）。

    特殊处理："幺"在 什幺/怎幺 等词中是"么"的旧写法，统一归一为"么"
    （"老幺"等正确用"幺"的词不受影响——仅替换 什幺/怎幺 组合）。
    """
    seen: set[str] = set()
    out: list[str] = []
    for k, v in _entries().items():
        if v.get("type") != "word":
            continue
        s = to_simplified(k)
        s = (s.replace("什幺", "什么").replace("怎幺", "怎么")
              .replace("这幺", "这么").replace("那幺", "那么")
              .replace("要幺", "要么").replace("多幺", "多么"))
        if s not in seen:
            seen.add(s)
            out.append(s)
    return sorted(out)


@lru_cache(maxsize=1)
def trad_index() -> dict[str, str]:
    """繁体挂件索引：繁字 → 简字；路由目标不在核心时指向自身（安全回退）。"""
    core = set(core_chars())
    out: dict[str, str] = {}
    for t in trad_chars():
        s = to_simplified(t)
        out[t] = s if s in core else t
    return out


def save_trad_index(out_path: str) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(trad_index(), ensure_ascii=False, indent=1), encoding="utf-8")
    return p
