# -*- coding: utf-8 -*-
"""下载公版英文经典，清洗为拉丁字母语料（挂件词表训练用）。"""
import re
import sys
import urllib.request
from pathlib import Path

BOOKS = {1342: "pride", 84: "frankenstein", 11: "alice", 2701: "mobydick"}
ASCII_LINE = re.compile(r"^[A-Za-z0-9 .,;:!?\"'\-()\[\]]+$")


def main() -> int:
    out_dir = Path("data/raw")
    clean_dir = Path("data/corpus_clean")
    out_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    with open(clean_dir / "en_all.txt", "w", encoding="utf-8") as fout:
        for eid, name in BOOKS.items():
            url = f"https://www.gutenberg.org/cache/epub/{eid}/pg{eid}.txt"
            req = urllib.request.Request(url, headers={"User-Agent": "zh-native-tokenizer/0.1"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            (out_dir / f"en_{name}.txt").write_text(raw, encoding="utf-8")
            kept = 0
            for line in raw.splitlines():
                line = line.strip()
                if len(line) < 20 or not ASCII_LINE.match(line):
                    continue
                fout.write(line + "\n")
                kept += 1
                total += 1
            print(f"{name}: {kept} lines")
    print(f"English corpus total: {total} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
