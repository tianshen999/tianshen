# -*- coding: utf-8 -*-
"""四维评测指标（docs/02 §7）。

约定：分词器统一以 pieces(text) -> list[str] 形式传入。
1. 词元效率：token 数 / 中文字符数（fertility，越低越好）
2. 压缩率：bits/char = token 数 × log2(词表大小) / 字符数（信息论口径，越低越省）
3. 字形可解析性：汉字整字保持率 + 部首可恢复率
4. 下游语义：占位（阶段 2 用困惑度代理，见 docs）
"""
from __future__ import annotations

import math

import regex as re

# 注意：扩展 B+ 区必须用 8 位 \U 转义，\u 只吃 4 位
CJK_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\U00020000-\U0002FA1F]")


def cjk_chars(text: str) -> list[str]:
    return CJK_RE.findall(text)


def tokens_per_char(pieces: list[str], text: str) -> float:
    """词元效率：每个中文字符消耗多少 token。"""
    n = len(cjk_chars(text))
    return len(pieces) / n if n else float("inf")


def chars_per_token(pieces: list[str], text: str) -> float:
    """每个 token 平均承载多少中文字符。"""
    return (len(cjk_chars(text)) / len(pieces)) if pieces else 0.0


def bits_per_char(pieces: list[str], text: str, vocab_size: int) -> float:
    """压缩率（信息论口径）：编码每个中文字符平均需要的比特数。

    = token 数 × log2(词表大小) / 中文字符数。词表越大单 token 信息量越大，
    但 token 数也会随词表增大而减少；该指标综合两者，越低越省。
    """
    n = len(cjk_chars(text))
    if not n or not pieces:
        return float("inf")
    return len(pieces) * math.log2(max(vocab_size, 2)) / n


def char_atomicity(pieces: list[str], text: str) -> float:
    """汉字整字保持率：多少个中文字符在 token 化后仍作为完整整字存在。

    国际模型（字节级 BPE）常把汉字拆成 2~3 个字节 token，此项会显著低于 1。
    我们的设计原则要求此项恒等于 1。
    """
    chars = cjk_chars(text)
    if not chars:
        return 1.0
    kept = 0
    for ch in chars:
        if any(ch in p for p in pieces):
            kept += 1
    return kept / len(chars)


def radical_recoverability(pieces: list[str], text: str, radical_fn) -> float:
    """部首可恢复率：汉字保持整字、且部首信息可从数据层查得 的比例。"""
    chars = cjk_chars(text)
    if not chars:
        return 1.0
    ok = 0
    for ch in chars:
        if any(ch in p for p in pieces) and radical_fn(ch) is not None:
            ok += 1
    return ok / len(chars)


def cross_language_efficiency(zh_pieces: list[str], en_pieces: list[str]) -> float:
    """跨语言效率比：中文 token 数 / 英文 token 数（<1 = 中文更省）。

    需要中英平行文本，评测时逐对计算后取均值。
    """
    return len(zh_pieces) / len(en_pieces) if en_pieces else float("inf")


def evaluate_text(pieces: list[str], text: str, vocab_size: int | None = None,
                  radical_fn=None) -> dict:
    """对单段文本计算全部指标。"""
    out = {
        "chars": len(cjk_chars(text)),
        "tokens": len(pieces),
        "tokens_per_char": round(tokens_per_char(pieces, text), 4),
        "chars_per_token": round(chars_per_token(pieces, text), 4),
        "char_atomicity": round(char_atomicity(pieces, text), 4),
    }
    if vocab_size:
        out["bits_per_char"] = round(bits_per_char(pieces, text, vocab_size), 4)
    if radical_fn is not None:
        out["radical_recoverability"] = round(radical_recoverability(pieces, text, radical_fn), 4)
    return out
