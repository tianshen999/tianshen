# -*- coding: utf-8 -*-
"""注音输出挂件（ADR-016/ADR-013：默认关闭、可切断）。

核心（拼音输出）不依赖本模块；移除本文件不影响任何拼音功能。
"""
from __future__ import annotations

from src.pinyin.syllable import parse


class ZhuyinPlug:
    """注音输出：数字调号拼音 → 注音符号。默认关闭。"""

    def __init__(self):
        self.enabled = False

    def enable(self, on: bool = True) -> None:
        self.enabled = bool(on)

    def render(self, numbered: str) -> str | None:
        """'yin2 hang2' → 'ㄧㄣˊ ㄏㄤˊ'。未启用返回 None。"""
        if not self.enabled:
            return None
        return " ".join(parse(t).zhuyin() for t in numbered.split())
