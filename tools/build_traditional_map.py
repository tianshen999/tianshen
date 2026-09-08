# -*- coding: utf-8 -*-
"""繁体同步标注：从 CEDICT 繁体键生成 繁体词 → 读音 映射表（ADR-018）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pinyin.cedict import load_cedict  # noqa: E402
from src.pinyin.syllable import parse  # noqa: E402


def build_traditional_map(cedict: dict | None = None) -> dict[str, dict]:
    cedict = cedict or load_cedict()
    out: dict[str, dict] = {}
    for simp, entries in cedict.items():
        for e in entries:
            trad = e["trad"]
            if trad == simp or not trad:
                continue
            numbered = [t.lower().replace("r5", "er5") for t in e["pinyin"]]
            syls = [parse(t) for t in numbered]
            entry = {
                "pinyin": " ".join(s.marked() for s in syls),
                "numbered": " ".join(numbered),
                "zhuyin": " ".join(s.zhuyin() for s in syls),
                "simp": simp,
            }
            # 同名多义项：保留全部读音列表
            if trad in out:
                out[trad].setdefault("alt_readings", []).append(entry["numbered"])
            else:
                out[trad] = entry
    return out


def main() -> int:
    trad_map = build_traditional_map()
    out_path = ROOT / "artifacts" / "pinyin" / "traditional_map.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(trad_map, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"繁体词条: {len(trad_map)}，已写入 {out_path}")
    for w in ["銀行", "音樂", "長大", "重慶", "電腦", "臺灣"]:
        print(w, "->", trad_map.get(w, {}).get("pinyin", "（未收录）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
