# -*- coding: utf-8 -*-
"""拼音数据层测试（音节解析 + Unihan 读音）。"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pinyin.syllable import parse, parse_marked, parse_numbered, to_zhuyin  # noqa: E402


def test_numbered_basic():
    s = parse_numbered("xing2")
    assert (s.initial, s.final, s.tone) == ("x", "ing", 2)
    assert s.marked() == "xíng"
    assert s.zhuyin() == "ㄒㄧㄥˊ"


def test_marked_basic():
    s = parse_marked("zhōng")
    assert (s.initial, s.final, s.tone) == ("zh", "ong", 1)
    assert s.numbered() == "zhong1"


def test_y_w_spelling_preserved():
    assert parse("yin2").spelling == "yin"
    assert parse("yin2").marked() == "yín"
    assert parse("yin2").zhuyin() == "ㄧㄣˊ"
    assert parse("wang3").marked() == "wǎng"
    assert parse("yuan2").marked() == "yuán"
    assert parse("yuan2").zhuyin() == "ㄩㄢˊ"


def test_u_umlaut():
    s = parse("lüe4")
    assert (s.initial, s.final, s.tone) == ("l", "üe", 4)
    assert s.marked() == "lüè"
    assert s.zhuyin() == "ㄌㄩㄝˋ"
    assert parse("nü3").final == "ü"   # 数字调号形式
    assert parse_marked("nǚ").final == "ü"  # 变音调号形式
    assert parse_marked("nǚ").marked() == "nǚ"


def test_apical_vowels():
    # zhi/chi/shi/ri/zi/ci/si 的 i 是舌尖元音
    assert parse("zhi1").final == "-i"
    assert parse("zi4").final == "-i"
    assert parse("zhi1").zhuyin() == "ㄓ"  # 注音不写舌尖元音
    # di/ti/ni/li 的 i 是普通韵母
    assert parse("di2").final == "i"
    assert parse("di2").zhuyin() == "ㄉㄧˊ"


def test_neutral_and_unknown_tone():
    assert parse("de5").tone == 5
    assert parse("de5").zhuyin() == "ㄉㄜ˙"
    assert parse("hang").tone == 0  # 无调号 → 未知
    assert parse("hang").marked() == "hang"
    assert parse("hang").numbered() == "hang"


def test_to_zhuyin_phrase():
    assert to_zhuyin("tian1 shen2") == "ㄊㄧㄢ ㄕㄣˊ"


def test_interjection_syllables():
    """叹词音节：yo / m / n / ng。"""
    yo = parse("yo1")
    assert (yo.initial, yo.final) == ("", "yo")
    assert yo.zhuyin() == "ㄧㄛ"
    assert yo.marked() == "yō"
    assert parse("ng4").zhuyin() == "ㄫˋ"
    assert parse_marked("m̄").zhuyin() == "ㄇ"
    assert parse_marked("ḿ").marked() == "ḿ"


def test_unihan_readings_fixture(monkeypatch):
    """Unihan 读音解析（离线 fixture，不联网）。"""
    from src.pinyin import unihan
    monkeypatch.setattr(
        unihan, "_unihan",
        lambda: {
            "行": {"kMandarin": "xíng",
                   "kHanyuPinyin": "20811.060:háng,xìng,xíng,hàng,héng 0443.050:hang"},
            "龘": {"kHanyuPinyin": "74806.090:dá"},
        },
    )
    readings = unihan.readings("行")
    marked = [s.marked() for s in readings]
    assert marked[0] == "xíng"  # kMandarin 优先
    assert "háng" in marked and "hàng" in marked
    # 无调号重复项应被剔除
    assert not any(s.tone == 0 for s in readings)
    assert unihan.pinyin("龘", "marked") == ["dá"]
    assert unihan.pinyin("龘", "zhuyin") == ["ㄉㄚˊ"]


def test_annotate_word_integration():
    """词级标注集成测试（需要 CEDICT 数据，缺失则跳过）。"""
    from pathlib import Path as _P
    if not (_P(__file__).resolve().parent.parent / "data" / "cedict_ts.u8").exists():
        pytest.skip("缺少 data/cedict_ts.u8")
    from src.pinyin.annotate import annotate_word
    from src.pinyin.cedict import load_cedict
    cedict = load_cedict()
    cases = {
        "银行": "yin2 hang2",
        "行走": "xing2 zou3",
        "音乐": "yin1 yue4",
        "便宜": "pian2 yi5",      # 多义项按频率选择
        "还是": "hai2 shi4",      # 人工校对覆盖
        "待会儿": "dai1 hui4 er5",  # 儿化 r5 → er5
    }
    for word, expected in cases.items():
        entry = annotate_word(word, cedict)
        assert entry["numbered"] == expected, f"{word}: {entry}"
