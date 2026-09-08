# -*- coding: utf-8 -*-
"""挂件（拉丁通道）测试：核心是"可切断性"——禁用挂件后行为必须与从未启用完全一致。

需要已训练的模型（artifacts/group_a_64k.model / artifacts/plug_en.model），
模型缺失时自动跳过。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.tokenizer.tokenizer import CompositeTokenizer, load_tokenizer  # noqa: E402

CORE = ROOT / "artifacts" / "group_a_64k"
PLUG = ROOT / "artifacts" / "plug_en"

pytestmark = pytest.mark.skipif(
    not (CORE.with_suffix(".model").exists() and PLUG.with_suffix(".model").exists()),
    reason="需要已训练的 core/plug 模型",
)

TEXTS = [
    "人工智能改变世界",
    "大语言模型LLM正在快速发展",
    "模型基于Transformer架构，训练需要GPU算力",
    "2026年9月，第三次全国代表大会召开",
    "hello world 你好世界 mixed text 12345",
]


@pytest.fixture(scope="module")
def tok():
    # 相对路径（纯 ASCII）：SentencePiece 的 C++ 打开不了含中文的绝对路径
    return CompositeTokenizer("artifacts/group_a_64k", "artifacts/plug_en")


def test_default_off(tok):
    """默认关闭：出厂即纯中文模式。"""
    assert tok.plug_enabled is False


def test_cutoff_no_side_effect(tok):
    """切断保证：启用→禁用后，行为与从未启用完全一致。"""
    for text in TEXTS:
        before = (tok.pieces(text), tok.encode(text))
        tok.enable_plug(True)
        tok.enable_plug(False)
        after = (tok.pieces(text), tok.encode(text))
        assert before == after, f"切断后行为变化：{text}"


def test_pure_chinese_untouched_by_plug(tok):
    """纯中文文本：挂件开/关，编码逐字节相同（核心永不经过挂件）。"""
    text = "人工智能改变世界，汉字原子性永不拆碎。"
    off = (tok.pieces(text), tok.encode(text))
    tok.enable_plug(True)
    on = (tok.pieces(text), tok.encode(text))
    tok.enable_plug(False)
    assert off == on


def test_plug_improves_latin(tok):
    """挂件开启后，多字母拉丁词应比关闭时更少 token。"""
    text = "Transformer architecture and language models"
    tok.enable_plug(False)
    n_off = len(tok.pieces(text))
    tok.enable_plug(True)
    n_on = len(tok.pieces(text))
    tok.enable_plug(False)
    assert n_on < n_off, f"挂件未减少拉丁 token：off={n_off} on={n_on}"


def test_encode_decode_chinese_roundtrip(tok):
    """纯中文 roundtrip：encode→decode 还原原文（id 空间不冲突）。"""
    text = "人工智能"
    assert tok.decode(tok.encode(text)) == text


def test_plug_ids_offset(tok):
    """挂件 token id 必须偏移到核心词表之后，不与核心冲突。"""
    tok.enable_plug(True)
    zh_ids = tok.encode("人工智能")
    en_ids = tok.encode("language")
    tok.enable_plug(False)
    core_size = tok.core.vocab_size
    assert zh_ids and all(i < core_size for i in zh_ids)
    # 纯 ASCII 片段启用挂件后 id 进入挂件区段
    assert en_ids and all(i >= core_size for i in en_ids)
