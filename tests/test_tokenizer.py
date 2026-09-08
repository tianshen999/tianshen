# -*- coding: utf-8 -*-
"""分词器与评测指标测试（无需训练模型即可运行）。"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.metrics import (  # noqa: E402
    bits_per_char, char_atomicity, chars_per_token, cjk_chars, tokens_per_char,
)
from src.corpus.preprocess import clean_line, is_keep_line  # noqa: E402
from src.tokenizer.tokenizer import CharTokenizer  # noqa: E402


def test_char_tokenizer_roundtrip():
    vocab_dir = ROOT / ".tmp" / "test_vocab"
    vocab_dir.mkdir(parents=True, exist_ok=True)
    vocab = vocab_dir / "c.vocab"
    vocab.write_text("<unk>\t0\n<s>\t1\n人\t2\n工\t3\n智\t4\n能\t5\n", encoding="utf-8")
    try:
        tok = CharTokenizer(str(vocab))
        text = "人工智能"
        ids = tok.encode(text)
        assert ids == [2, 3, 4, 5]
        assert tok.decode(ids) == text
        assert tok.pieces(text) == list(text)
        assert tok.encode("X") == [0]  # 未知字符 -> unk
        assert tok.vocab_size == 6
    finally:
        shutil.rmtree(vocab_dir, ignore_errors=True)


def test_clean_line():
    assert clean_line("  你好 世界  \x1f") == "你好 世界"
    assert clean_line("你好\x00世界") == "你好世界"  # 控制字符直接删除
    assert clean_line("  \x7f  ") == ""


def test_is_keep_line():
    assert is_keep_line("人工智能改变世界的十个理由分析", min_len=5, cjk_ratio=0.5)
    assert not is_keep_line("print(hello world 123)", min_len=5, cjk_ratio=0.5)  # 纯英文代码
    assert not is_keep_line("短句", min_len=5)  # 太短


def test_metrics_basics():
    text = "人工智能"
    pieces = ["人工", "智能"]
    assert cjk_chars(text) == ["人", "工", "智", "能"]
    assert tokens_per_char(pieces, text) == 0.5
    assert chars_per_token(pieces, text) == 2.0
    assert char_atomicity(pieces, text) == 1.0


def test_metrics_byte_split_penalty():
    """字节级拆分（模拟国际模型）：整字保持率应显著下降。"""
    text = "人工智能"
    pieces = ["äº", "ºå", "·¥", "æ™", "ºè", "ƒ½"]  # UTF-8 字节碎片的近似模拟
    assert char_atomicity(pieces, text) < 1.0


def test_bits_per_char():
    text = "人工智能"
    pieces = ["人工智能"]
    # 1 token × log2(100) / 4 字
    assert abs(bits_per_char(pieces, text, 100) - (1 * 6.643856 / 4)) < 1e-4
    # token 数相同的情况下，小词表更省（信息论口径）
    assert bits_per_char(pieces, text, 100) > bits_per_char(pieces, text, 32)


def test_train_defaults_no_forced_symbols():
    """防回归（ADR-011）：默认训练不得强制注入 GB2312 字符。

    历史事故：user_defined_symbols 会抑制所有包含这些字符的多字词学习；
    且曾出现"默认参数为 None，但函数内部又偷偷改回强制"的双重 bug。
    """
    import inspect
    from src.tokenizer.train import train_unigram
    sig = inspect.signature(train_unigram)
    assert sig.parameters["force_atomic_chars"].default is None
    # 源文件中不得再出现 None -> gb2312_chars() 的默认覆盖
    src = Path(__file__).resolve().parent.parent / "src" / "tokenizer" / "train.py"
    code = src.read_text(encoding="utf-8")
    assert "if force_atomic_chars is None:" not in code
