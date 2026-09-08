# -*- coding: utf-8 -*-
"""拼音数据层：从 Unihan 提取汉字读音（kHanyuPinyin/kMandarin/kXHC1983）。"""
from __future__ import annotations

import re
from functools import lru_cache

from src.pinyin.syllable import Syllable, parse

# kHanyuPinyin 值形如 "20811.060:háng,xìng,xíng,hàng,héng"（页.位:读音列表）
_HANYU_RE = re.compile(r"^[\d.]+:(.+)$")


@lru_cache(maxsize=1)
def _unihan() -> dict[str, dict[str, str]]:
    from src.tokenizer import radicals
    return radicals.load_unihan()


def _parse_readings(value: str | None, toneless_tone: int = 0) -> list[Syllable]:
    """解析 Unihan 读音字段值 → 音节列表（去重、保序）。

    kHanyuPinyin/kXHC1983 值形如 "20811.060:háng,xìng 0443.050:hang"
    ——多个"页码.位:读音列表"段以空格分隔；每段读音以逗号分隔。

    toneless_tone：无调号读音的解释——kMandarin/kXHC1983 的无调号即轻声（5），
    kHanyuPinyin 的无调号是声调未知（0）。
    """
    if not value:
        return []
    out: list[Syllable] = []
    seen: set[str] = set()
    for seg in value.split():
        if ":" in seg:
            seg = seg.split(":", 1)[1]
        for tok in seg.split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                syl = parse(tok)
            except Exception:
                continue
            if syl.tone == 0 and toneless_tone:
                syl = Syllable(syl.initial, syl.final, toneless_tone, syl.spelling)
            key = (syl.spelling, syl.tone)
            if key not in seen:
                seen.add(key)
                out.append(syl)
    return out


def readings(ch: str, source: str = "all") -> list[Syllable]:
    """汉字读音。source: kHanyuPinyin（全量多音）/ kMandarin（普通话代表音）
    / kXHC1983（现代汉语词典）/ all（kMandarin 优先合并，去重）。

    无调号读音解释：kMandarin/kXHC1983 → 轻声（5）；kHanyuPinyin → 未知（0）。
    """
    props = _unihan().get(ch, {})
    if source == "all":
        merged: list[Syllable] = []
        seen: set[str] = set()
        for key, toneless_tone in (("kMandarin", 5), ("kXHC1983", 5), ("kHanyuPinyin", 0)):
            for syl in _parse_readings(props.get(key), toneless_tone):
                k = (syl.spelling, syl.tone)
                if k not in seen:
                    seen.add(k)
                    merged.append(syl)
        # 清理：仅删除"声调未知"且与已知读音同音的重复项（轻声是合法读音，保留）
        known = {(s.initial, s.final) for s in merged if s.tone in (1, 2, 3, 4, 5)}
        merged = [s for s in merged
                  if s.tone != 0 or (s.initial, s.final) not in known]
        return merged
    toneless_tone = 0 if source == "kHanyuPinyin" else 5
    return _parse_readings(props.get(source), toneless_tone)


def pinyin(ch: str, style: str = "marked") -> list[str]:
    """汉字 → 拼音串列表。style: marked/numbered/zhuyin。"""
    syls = readings(ch)
    if style == "marked":
        return [s.marked() for s in syls]
    if style == "numbered":
        return [s.numbered() for s in syls]
    if style == "zhuyin":
        return [s.zhuyin() for s in syls]
    raise ValueError(style)


def primary(ch: str, style: str = "marked") -> str | None:
    """普通话代表读音（kMandarin 优先，无则取第一条）。"""
    syls = readings(ch)
    if not syls:
        return None
    if style == "marked":
        return syls[0].marked()
    if style == "numbered":
        return syls[0].numbered()
    if style == "zhuyin":
        return syls[0].zhuyin()
    raise ValueError(style)
