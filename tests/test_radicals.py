# -*- coding: utf-8 -*-
"""部首/部件数据层测试（离线 fixture，不联网）。

注意：不使用 pytest 的 tmp_path——它在 Windows 上以受限权限位建目录，
沙箱安全上下文无法访问（WinError 5）。fixture 统一放在工作区 .tmp 下。
"""
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.tokenizer import radicals  # noqa: E402

UNIHAN_FIXTURE = """\
# 测试用最小 Unihan 数据
U+4EBA	kRSUnicode	9.0
U+4EBA	kIRG_GSource	G0-4EBA
U+4EBA	kDefinition	man; people
U+6C34	kRSUnicode	85.0
U+4F60	kRSUnicode	9.5
U+4F60	kIRG_GSource	G1-4F60
U+65E5	kRSUnicode	72.0
"""

IDS_FIXTURE = """\
# 测试用最小 IDS 数据（三列：码位、汉字、IDS）
U+4F60	你	⿰亻尔
U+6E56	湖	⿲氵古月
"""

FIXTURE_DIR = ROOT / ".tmp" / "test_fixtures"


@pytest.fixture(autouse=True)
def _fixture_data(monkeypatch):
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    unihan = FIXTURE_DIR / "Unihan_IRGSources.txt"
    unihan2 = FIXTURE_DIR / "Unihan_DictionaryLikeData.txt"
    ids = FIXTURE_DIR / "IDS.TXT"
    # 模拟新版 Unihan 拆分文件结构
    unihan.write_text("\n".join(
        l for l in UNIHAN_FIXTURE.splitlines()
        if "kDefinition" not in l) + "\n", encoding="utf-8")
    unihan2.write_text("U+4EBA\tkDefinition\tman; people\n", encoding="utf-8")
    ids.write_text(IDS_FIXTURE, encoding="utf-8")
    monkeypatch.setattr(radicals, "ensure_data", lambda force=False: (FIXTURE_DIR, ids))
    radicals.load_unihan.cache_clear()
    radicals.load_ids.cache_clear()
    yield
    shutil.rmtree(FIXTURE_DIR, ignore_errors=True)


def test_char_radical():
    assert radicals.char_radical("人") == radicals.KANGXI_RADICALS[8]   # 康熙第 9 部
    assert radicals.char_radical("水") == radicals.KANGXI_RADICALS[84]  # 康熙第 85 部
    assert radicals.char_radical("你") == radicals.KANGXI_RADICALS[8]   # 亻归人部
    assert radicals.char_radical("无此字") is None


def test_char_strokes():
    assert radicals.char_strokes("人") == 0
    assert radicals.char_strokes("你") == 5


def test_char_definition():
    assert radicals.char_definition("人") == "man; people"


def test_gb2312_chars():
    chars = radicals.gb2312_chars()
    assert "人" in chars
    assert "你" in chars
    assert "水" not in chars  # fixture 中水没有 G 源


def test_decompose():
    assert radicals.decompose("你") == ["亻", "尔"]
    parts = radicals.decompose("湖")
    assert "氵" in parts and "古" in parts and "月" in parts


def test_kangxi_radicals_count():
    assert len(radicals.KANGXI_RADICALS) == 214
