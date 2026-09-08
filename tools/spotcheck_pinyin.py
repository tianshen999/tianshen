# -*- coding: utf-8 -*-
"""抽查词级拼音标注的关键多音词（兼容字/词两种条目格式）。"""
import json
import sys

WORDS = ["银行", "行走", "长大", "音乐", "快乐", "重庆", "重新", "重要",
         "得", "的", "地", "银行家", "行长", "首都", "都是"]


def main() -> int:
    data = json.load(open("artifacts/pinyin/group_a_64k_pinyin.json", encoding="utf-8"))
    for w in WORDS:
        e = data["entries"].get(w)
        if not e:
            print(f"{w:<4} -> （词表中无此词条）")
            continue
        pinyin = e.get("pinyin") or " ".join(e["marked"])
        src = e.get("source", "char")
        zhuyin = e.get("zhuyin") or " ".join(e["zhuyin2"]) if "zhuyin2" in e else e.get("zhuyin", "")
        print(f"{w:<4} -> {pinyin:<16} [{src}]  注音: {zhuyin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
