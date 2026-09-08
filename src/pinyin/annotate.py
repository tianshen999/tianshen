# -*- coding: utf-8 -*-
"""词级拼音标注：为 64k 词表全部词条标注词级读音。

规则（ADR-018）：
- 多字词：优先查 CC-CEDICT 词级读音（多音字按词消歧）；未收录则逐字
  用普通话代表音（kMandarin）拼合，并标记 source=char（fallback）。
- 单字：记录全部读音，普通话代表音在前。
- 简体为主、繁体同步：CEDICT 繁体词条同时入表（标 trad=True）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.pinyin.cedict import load_cedict  # noqa: E402
from src.pinyin.syllable import parse, to_zhuyin  # noqa: E402
from src.pinyin.unihan import readings  # noqa: E402
from src.tokenizer.tokenizer import load_tokenizer  # noqa: E402

_CJK_ONLY = re.compile(r"^[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\U00020000-\U0002FA1F]+$")


def char_reading(ch: str) -> dict:
    """单字读音信息。"""
    syls = readings(ch)
    return {
        "marked": [s.marked() for s in syls],
        "numbered": [s.numbered() for s in syls],
        "zhuyin": [s.zhuyin() for s in syls],
        "tones": [s.tone for s in syls],
    }


def _pypinyin_word(word: str) -> list[str] | None:
    """pypinyin 词组读音（MIT 许可的第二数据源）。失败/未收录返回 None。

    规范化为数字调号形式：无数字的轻声补 5（与 CEDICT 的 5 约定一致）。
    """
    try:
        import pypinyin
        from pypinyin import Style
        syls = pypinyin.pinyin(word, style=Style.TONE3, heteronym=False)
        toks = [s[0] for s in syls]
        return [t + "5" if t and not t[-1].isdigit() else t for t in toks]
    except Exception:
        return None


# 常见虚词尾字：词末读音多为轻声
_PARTICLES = set("的地得了着们子么头儿")

# 人工校对覆盖表（以《现代汉语词典》为标准；优先级最高，source=manual）
OVERRIDES: dict[str, str] = {
    "还是": "hai2 shi4",
    "几个": "ji3 ge4",
    "困难": "kun4 nan2",
    "称呼": "cheng1 hu1",
    "切开": "qie1 kai1",
}


def annotate_word(word: str, cedict: dict) -> dict:
    """多字词标注：人工校对 → CEDICT → pypinyin 词组 → 逐字兜底。

    多义项选择（ADR-018 词级消歧）：
    1. 末字为常见虚词时，优先选末尾轻声（5）的义项；
    2. 否则若 pypinyin 词组读音在 CEDICT 候选中，取之（频率排序）；
    3. 否则取 CEDICT 第一义项。
    """
    manual = OVERRIDES.get(word)
    if manual:
        syls = [parse(t) for t in manual.split()]
        return {
            "pinyin": " ".join(s.marked() for s in syls),
            "numbered": manual,
            "zhuyin": " ".join(s.zhuyin() for s in syls),
            "source": "manual",
            "n_readings": 1,
        }
    hit = cedict.get(word)
    if hit:
        readings_list = [e["pinyin"] for e in hit]
        chosen = readings_list[0]
        if len(readings_list) > 1:
            py = _pypinyin_word(word)
            if word[-1] in _PARTICLES:
                neutral = [r for r in readings_list if r and r[-1].endswith("5")]
                if len(neutral) == 1:
                    chosen = neutral[0]
                elif py and py in readings_list:
                    chosen = py
            elif py and py in readings_list:
                chosen = py
        # CEDICT 儿化 "r5" → 规范 "er5"
        numbered = [tok.lower().replace("r5", "er5") for tok in chosen]
        syls = [parse(t) for t in numbered]
        return {
            "pinyin": " ".join(s.marked() for s in syls),
            "numbered": " ".join(s.numbered() for s in syls),
            "zhuyin": " ".join(s.zhuyin() for s in syls),
            "source": "cedict",
            "n_readings": len(readings_list),
            "all_readings": [" ".join(r) for r in readings_list][:5],
        }
    # 第二数据源：pypinyin 词组读音（MIT）。
    # 例外：末字为常见虚词且逐字读音末音节为轻声时，逐字结果更可信
    # （pypinyin 词组词典对"地/的/得"等虚词常误标全调）。
    char_syls = [readings(ch)[0] if readings(ch) else parse("?") for ch in word]
    py = _pypinyin_word(word)
    use_py = bool(py) and not (
        word[-1] in _PARTICLES and char_syls and char_syls[-1].tone == 5
    )
    if use_py:
        syls = [parse(t) for t in py]
        return {
            "pinyin": " ".join(s.marked() for s in syls),
            "numbered": " ".join(s.numbered() for s in syls),
            "zhuyin": " ".join(s.zhuyin() for s in syls),
            "source": "pypinyin",
            "n_readings": 1,
        }
    # fallback：逐字普通话代表音
    syls = char_syls
    return {
        "pinyin": " ".join(s.marked() for s in syls),
        "numbered": " ".join(s.numbered() for s in syls),
        "zhuyin": " ".join(s.zhuyin() for s in syls),
        "source": "char",
        "n_readings": 0,
    }


def annotate_model(model_prefix: str, out_path: str) -> dict:
    tok = load_tokenizer(model_prefix)
    cedict = load_cedict()
    out: dict = {"model": Path(model_prefix).name, "entries": {}}
    stats = {"total": 0, "word_cedict": 0, "word_char": 0, "char": 0, "other": 0}

    for piece in tok.sp.id_to_piece(range(tok.sp.get_piece_size())):
        core = piece.lstrip("\u2581")
        if not core:
            stats["other"] += 1
            continue
        stats["total"] += 1
        if len(core) >= 2 and _CJK_ONLY.match(core):
            entry = annotate_word(core, cedict)
            entry["type"] = "word"
            if entry["source"] == "cedict":
                stats["word_cedict"] += 1
            else:
                stats["word_char"] += 1
            out["entries"][core] = entry
        elif len(core) == 1 and _CJK_ONLY.match(core):
            entry = char_reading(core)
            entry["type"] = "char"
            stats["char"] += 1
            out["entries"][core] = entry
        else:
            stats["other"] += 1

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="64k 词表词级拼音标注")
    ap.add_argument("--model", default="artifacts/group_a_64k")
    ap.add_argument("--out", default="artifacts/pinyin/group_a_64k_pinyin.json")
    args = ap.parse_args(argv)
    stats = annotate_model(args.model, args.out)
    n_word = stats["word_cedict"] + stats["word_char"]
    print(f"词表条目: {stats['total']}（单字 {stats['char']}，多字词 {n_word}，其他 {stats['other']}）")
    print(f"多字词中：CEDICT 词级命中 {stats['word_cedict']}，逐字兜底 {stats['word_char']} "
          f"（命中率 {stats['word_cedict'] / max(n_word, 1):.1%}）")
    print(f"标注文件: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
