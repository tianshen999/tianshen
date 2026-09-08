# -*- coding: utf-8 -*-
"""分词器统一封装：我们的模型（SentencePiece / 整字表）与第三方词表的适配层。

所有分词器统一暴露三个接口（供评测指标使用）：
- pieces(text) -> list[str]   切分结果（token 字符串列表）
- encode(text) -> list[int]   token id 列表
- decode(ids) -> str          解码回文本
"""
from __future__ import annotations

import re
from pathlib import Path


class CharTokenizer:
    """组 C：纯整字词表。每个 Unicode 字符一个 token。"""

    def __init__(self, vocab_file: str):
        self.char2id: dict[str, int] = {}
        with open(vocab_file, "r", encoding="utf-8") as f:
            for line in f:
                tok, sid = line.rstrip("\n").split("\t", 1)  # 语料字符本身可能含 \t
                self.char2id[tok] = int(sid)
        self.unk_id = self.char2id.get("<unk>", 0)
        self.vocab_size = len(self.char2id)

    def pieces(self, text: str) -> list[str]:
        return list(text)

    def encode(self, text: str) -> list[int]:
        return [self.char2id.get(c, self.unk_id) for c in text]

    def decode(self, ids: list[int]) -> str:
        id2char = {v: k for k, v in self.char2id.items()}
        return "".join(id2char.get(i, "<unk>") for i in ids)


class SpTokenizer:
    """组 A/B：SentencePiece Unigram 模型。"""

    def __init__(self, model_file: str):
        import sentencepiece as spm
        self.sp = spm.SentencePieceProcessor(model_file=model_file)
        self.vocab_size = self.sp.get_piece_size()

    def pieces(self, text: str) -> list[str]:
        return self.sp.encode(text, out_type=str)

    def encode(self, text: str) -> list[int]:
        return self.sp.encode(text, out_type=int)

    def decode(self, ids: list[int]) -> str:
        return self.sp.decode(ids)


def load_tokenizer(prefix: str):
    """按前缀加载我们的分词器：优先 .model（A/B），否则 .vocab（C）。"""
    model = Path(prefix + ".model")
    vocab = Path(prefix + ".vocab")
    if model.exists():
        return SpTokenizer(str(model))
    if vocab.exists():
        return CharTokenizer(str(vocab))
    raise FileNotFoundError(f"未找到分词器：{prefix}.model 或 {prefix}.vocab")


# 路由规则（ADR-013）：挂件只处理"纯 ASCII 片段"（拉丁字母/阿拉伯数字/ASCII 标点）。
# 其余一切——汉字、中文标点（、。「」）、全角符号（，！）——永远归核心词表。
# 这样挂件无论开或关，中文体系的每一字节都只经过核心。
_ASCII_RUN = re.compile(r"[\x20-\x7E\t\n]+")
_SPLIT_RUN = re.compile(r"[\x20-\x7E\t\n]+|[^\x20-\x7E\t\n]+")


class CompositeTokenizer:
    """核心 + 挂件双词表路由（ADR-013 分离式挂件架构）。

    规则：
    - 非纯 ASCII 片段（汉字/中文标点/全角符号）→ 永远走核心词表；
    - 纯 ASCII 片段（拉丁/数字/ASCII 标点）→ 挂件启用时走挂件词表，
      未启用时走核心词表（核心自带数字与标点处理能力）；
    - 挂件默认关闭；"可切断性"由路由构造保证——禁用挂件后，
      任何输入的行为与从未启用完全一致（tests 锁定该性质）。

    注意：数字与标点属于核心能力，不属于挂件；挂件只改善
    多字母拉丁词（如 "language" 一个 token vs 逐字母）。
    """

    def __init__(self, core_prefix: str, plug_prefix: str | None = None):
        self.core = load_tokenizer(core_prefix)
        self.plug = load_tokenizer(plug_prefix) if plug_prefix else None
        self.plug_enabled = False  # 默认关闭：出厂即纯中文模式
        self.vocab_size = self.core.vocab_size + (self.plug.vocab_size if self.plug else 0)

    def enable_plug(self, on: bool = True) -> None:
        self.plug_enabled = bool(on) and self.plug is not None

    @staticmethod
    def _runs(text: str) -> list[str]:
        return _SPLIT_RUN.findall(text)

    @staticmethod
    def _is_ascii(run: str) -> bool:
        return bool(run) and bool(_ASCII_RUN.match(run))

    def _route(self, run: str):
        if not self._is_ascii(run) or not self.plug_enabled or self.plug is None:
            return self.core
        return self.plug

    def pieces(self, text: str) -> list[str]:
        out: list[str] = []
        for run in self._runs(text):
            out.extend(self._route(run).pieces(run))
        return out

    def encode(self, text: str) -> list[int]:
        ids: list[int] = []
        offset = self.core.vocab_size
        for run in self._runs(text):
            tok = self._route(run)
            if tok is self.core:
                ids.extend(self.core.encode(run))
            else:
                ids.extend(i + offset for i in self.plug.encode(run))
        return ids

    def decode(self, ids: list[int]) -> str:
        core_size = self.core.vocab_size
        out: list[str] = []
        for i in ids:
            if i < core_size:
                piece = self.core.sp.id_to_piece(i)
            elif self.plug is not None:
                piece = self.plug.sp.id_to_piece(i - core_size)
            else:
                piece = "<oov>"
            out.append(piece.replace("\u2581", " ").lstrip())
        return "".join(out)
