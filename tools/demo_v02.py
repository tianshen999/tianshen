# -*- coding: utf-8 -*-
"""天神 v0.2 演示：形（分词）+ 音（拼音/注音/发声）一次看全。

用法：
    python tools/demo_v02.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from src.pinyin.annotator import PinyinAnnotator
    from src.tokenizer.tokenizer import load_tokenizer

    print("=" * 56)
    print("天神 v0.2 演示：形 + 音")
    print("=" * 56)

    # ---------- 形：中文原生分词器 ----------
    tok = load_tokenizer("artifacts/group_a_64k")
    text = "人工智能改变世界，银行与音乐同行"
    pieces = tok.pieces(text)
    print(f"\n【形】分词: {text}")
    print("  ", " | ".join(p.replace(chr(9601), "␣") for p in pieces))

    # ---------- 音：拼音 / 注音 / 发声 ----------
    ann = PinyinAnnotator("artifacts/pinyin/group_a_64k_pinyin.json")
    print("\n【音】词级读音（核心，挂件无关）:")
    for w in ["人工智能", "银行", "音乐", "行走", "重庆"]:
        print(f"  {w:<6} {ann.pinyin(w)}  ({ann.numbered(w)})")

    print("\n【注音挂件】默认关闭 ->", ann.zhuyin_render("银行"))
    ann.zhuyin.enable(True)
    print("  开启后       ->", ann.zhuyin_render("银行"), "| 天神 ->", ann.zhuyin_render("天神"))
    ann.zhuyin.enable(False)

    print("\n【发声挂件】默认关闭 ->", "未合成（挂件关闭）")
    ann.voice.enable(True)
    ok = ann.speak("天神", str(ROOT / ".tmp" / "demo_tianshen.mp3"))
    print("  开启后，合成\"天神\" ->", "成功，播放 .tmp/demo_tianshen.mp3" if ok else "失败（需联网）")
    ann.voice.enable(False)

    # ---------- 汉字读音（多音字全览） ----------
    from src.pinyin.unihan import pinyin as char_pinyin
    print("\n【字级多音】行:", " / ".join(char_pinyin("行", "marked")),
          "| 注音:", " / ".join(char_pinyin("行", "zhuyin")))
    print("=" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
