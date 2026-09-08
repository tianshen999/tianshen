# -*- coding: utf-8 -*-
"""下载 Project Gutenberg 上的公版中文经典，按中文占比筛选保留。"""
import sys
import urllib.request
from pathlib import Path

# 候选：三国演义/西游记/水浒传/红楼梦/论语等（ID 不全确定，靠中文占比自动筛选）
CANDIDATES = [23950, 23962, 24024, 24264, 25286, 23838, 23948, 24017, 23962]


def cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    cjk = sum(1 for c in text if "\u3400" <= c <= "\u9fff" or "\U00020000" <= c <= "\U0002FA1F")
    alpha = sum(1 for c in text if c.isalnum() or "\u3400" <= c <= "\u9fff")
    return cjk / max(alpha, 1)


def main() -> int:
    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    kept = 0
    for eid in CANDIDATES:
        url = f"https://www.gutenberg.org/cache/epub/{eid}/pg{eid}.txt"
        dest = out_dir / f"gutenberg_{eid}.txt"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "zh-native-tokenizer/0.1"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
            text = raw.decode("utf-8", errors="ignore")
            ratio = cjk_ratio(text)
            size_mb = len(raw) / 1e6
            print(f"pg{eid}: {size_mb:.2f} MB, 中文占比 {ratio:.2%}")
            if ratio > 0.5 and len(raw) > 100_000:
                dest.write_bytes(raw)
                kept += 1
                print(f"  -> 保留 {dest}")
        except Exception as e:
            print(f"pg{eid}: 失败 {e}")
    print(f"保留 {kept} 部")
    return 0


if __name__ == "__main__":
    sys.exit(main())
