# -*- coding: utf-8 -*-
"""形+音词表核心 API：读音查询 + 两个挂件（注音、发声，均默认关闭）。

架构（ADR-013/016/017）：
- 核心：拼音输出（带调/数字调号）——不依赖任何挂件；
- 注音挂件：默认关闭，开启后可输出注音符号；
- 发声挂件：默认关闭，开启后可为字/词合成标准读音音频。
挂件整体可移除：删除 zhuyin_plug.py / voice.py 不影响核心。
"""
from __future__ import annotations

import json
from pathlib import Path

from src.pinyin.annotate import annotate_word
from src.pinyin.cedict import load_cedict
from src.pinyin.syllable import parse
from src.pinyin.zhuyin_plug import ZhuyinPlug
from src.pinyin.voice import VoicePlug


class PinyinAnnotator:
    """形+音合并词表接口。"""

    def __init__(self, annotation_json: str, enable_zhuyin: bool = False,
                 enable_voice: bool = False):
        self.data = json.loads(Path(annotation_json).read_text(encoding="utf-8"))
        self.entries: dict = self.data["entries"]
        self._cedict = load_cedict()
        self.zhuyin = ZhuyinPlug()
        self.voice = VoicePlug()
        if enable_zhuyin:
            self.zhuyin.enable(True)
        if enable_voice:
            self.voice.enable(True)

    def lookup(self, text: str) -> dict:
        """词/字 → 标注条目。词表外多字词动态标注（同四级流水线）。"""
        if text in self.entries:
            return self.entries[text]
        if len(text) >= 2:
            entry = annotate_word(text, self._cedict)
            entry["type"] = "word"
            return entry
        from src.pinyin.unihan import readings
        syls = readings(text)
        return {
            "type": "char",
            "marked": [s.marked() for s in syls],
            "numbered": [s.numbered() for s in syls],
            "zhuyin": [s.zhuyin() for s in syls],
            "tones": [s.tone for s in syls],
        }

    def pinyin(self, text: str) -> str:
        """核心输出：带调拼音（挂件无关）。"""
        e = self.lookup(text)
        return e.get("pinyin") or " ".join(e["marked"])

    def numbered(self, text: str) -> str:
        e = self.lookup(text)
        return e.get("numbered") or " ".join(e["numbered"])

    def zhuyin_render(self, text: str) -> str | None:
        """注音输出（需注音挂件启用，否则返回 None）。"""
        if not self.zhuyin.enabled:
            return None
        numbered = self.numbered(text)
        return self.zhuyin.render(numbered)

    def speak(self, text: str, out_path: str) -> bool:
        """发声（需发声挂件启用）。"""
        return self.voice.speak(text, out_path)
