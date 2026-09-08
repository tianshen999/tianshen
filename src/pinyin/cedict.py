# -*- coding: utf-8 -*-
"""CC-CEDICT 词-音词典解析（词级拼音与多音字消歧的词典来源）。

数据：CC-CEDICT（12.5 万词条），许可证 CC BY-SA 4.0（与 GPL-3.0 单向兼容，
本包在 GPL-3.0 下重新发布——见 data/README.md）。
格式：繁 简 [pin1 yin1] /释义/
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CEDICT_PATH = DATA_DIR / "cedict_ts.u8"

_LINE_RE = re.compile(r"^(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.*)/$")


@lru_cache(maxsize=1)
def load_cedict(path: str | None = None) -> dict[str, list[dict]]:
    """解析 CEDICT → {词: [{pinyin: [...], trad: 繁体, def: 释义}]}（以简体为键）。"""
    p = Path(path) if path else CEDICT_PATH
    data: dict[str, list[dict]] = {}
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = _LINE_RE.match(line)
            if not m:
                continue
            trad, simp, pinyin_str, definition = m.groups()
            readings = [tok.replace("u:", "ü").replace("v", "ü")
                        for tok in pinyin_str.split()]
            data.setdefault(simp, []).append(
                {"pinyin": readings, "trad": trad, "def": definition}
            )
    return data


def lookup(word: str, cedict: dict | None = None) -> list[list[str]]:
    """词 → 读音列表（每个义项一条，第一条为最常用）。未收录返回空列表。"""
    d = cedict if cedict is not None else load_cedict()
    return [e["pinyin"] for e in d.get(word, [])]


def word_pinyin(word: str, cedict: dict | None = None) -> list[str] | None:
    """词 → 主读音（拼音数字调号列表，如 ['yin2','hang2']）。未收录返回 None。"""
    r = lookup(word, cedict)
    return r[0] if r else None
