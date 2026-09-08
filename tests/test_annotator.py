# -*- coding: utf-8 -*-
"""形+音核心 API 与挂件测试（挂件默认关闭 + 可切断语义）。"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ANNOTATION = ROOT / "artifacts" / "pinyin" / "group_a_64k_pinyin.json"

pytestmark = pytest.mark.skipif(
    not ANNOTATION.exists(), reason="需要先运行音2标注（artifacts/pinyin/...）"
)


@pytest.fixture(scope="module")
def ann():
    from src.pinyin.annotator import PinyinAnnotator
    return PinyinAnnotator(str(ANNOTATION))


def test_core_pinyin(ann):
    assert ann.pinyin("银行") == "yín háng"
    assert ann.numbered("行走") == "xing2 zou3"
    assert ann.pinyin("人工智能") != ""  # 词表外词动态标注
    assert ann.pinyin("天") == "tiān"


def test_zhuyin_plug_default_off(ann):
    """注音挂件默认关闭：核心拼音不受影响，注音输出返回 None。"""
    assert ann.zhuyin_render("银行") is None
    assert ann.pinyin("银行") == "yín háng"  # 核心不受影响


def test_zhuyin_plug_enable(ann):
    ann.zhuyin.enable(True)
    assert ann.zhuyin_render("银行") == "ㄧㄣˊ ㄏㄤˊ"
    ann.zhuyin.enable(False)
    assert ann.zhuyin_render("银行") is None  # 切断后恢复


def test_voice_plug_default_off(ann):
    assert ann.voice.enabled is False
    # 未启用时不产生任何音频
    assert ann.speak("天神", str(ROOT / ".tmp" / "should_not_exist.mp3")) is False


def test_voice_plug_available(ann):
    from src.pinyin.voice import VoicePlug
    assert VoicePlug.available() is True


def test_annotator_with_plugs_enabled():
    from src.pinyin.annotator import PinyinAnnotator
    ann2 = PinyinAnnotator(str(ANNOTATION), enable_zhuyin=True)
    assert ann2.zhuyin_render("天神") == "ㄊㄧㄢ ㄕㄣˊ"
    assert ann2.pinyin("天神") == "tiān shén"
