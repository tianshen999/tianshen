# -*- coding: utf-8 -*-
"""字形部首数据层：从 Unicode Unihan 与 CHISE IDS 提取部首/部件结构。

数据来源（开源）：
- Unihan.zip: https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip
  （kRSUnicode=部首+残笔画, kIRG_GSource=中国大陆源, kDefinition=释义）
- CHISE IDS: https://github.com/chise/ids （表意文字描述序列，部件分解）
"""
from __future__ import annotations

import io
import os
import urllib.request
import zipfile
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"
UNIHAN_ZIP = DATA_DIR / "Unihan.zip"
UNIHAN_DIR = DATA_DIR / "unihan"  # 解压后的 Unihan_*.txt
IDS_URLS = [
    "https://raw.githubusercontent.com/chise/ids/main/IDS-UCS-Basic.txt",
    "https://raw.githubusercontent.com/chise/ids/main/IDS-UCS-Ext-A.txt",
]
IDS_TXT = DATA_DIR / "IDS.TXT"

# 康熙部首（U+2F00 ~ U+2FD5，共 214 个）
KANGXI_RADICALS = "".join(chr(0x2F00 + i) for i in range(214))
# 表意文字描述运算符
IDS_OPERATORS = set("⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻")


def is_cjk(ch: str) -> bool:
    return ("\u3400" <= ch <= "\u4DBF" or "\u4E00" <= ch <= "\u9FFF"
            or "\uF900" <= ch <= "\uFAFF" or "\U00020000" <= ch <= "\U0002FA1F")


def ensure_data(force: bool = False) -> tuple[Path, Path]:
    """确保 Unihan 数据（解压目录）与 IDS.TXT 存在；缺失则下载。返回两者路径。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not UNIHAN_DIR.exists() or force or not any(UNIHAN_DIR.glob("*.txt")):
        print(f"下载 Unihan 数据 -> {UNIHAN_ZIP}")
        req = urllib.request.Request(UNIHAN_URL, headers={"User-Agent": "zh-native-tokenizer/0.1"})
        with urllib.request.urlopen(req) as resp:
            UNIHAN_ZIP.write_bytes(resp.read())
        UNIHAN_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(UNIHAN_ZIP) as zf:
            for name in zf.namelist():
                if name.endswith(".txt"):
                    target = UNIHAN_DIR / Path(name).name
                    target.write_bytes(zf.read(name))
        print(f"Unihan 数据就绪：{len(list(UNIHAN_DIR.glob('*.txt')))} 个文件")
    if not IDS_TXT.exists() or force:
        # IDS-UCS-Basic 覆盖常用汉字区，Ext-A 补充扩展区
        IDS_TXT.write_bytes(b"")
        for url in IDS_URLS:
            try:
                print(f"下载 IDS 数据 -> {url}")
                req = urllib.request.Request(url, headers={"User-Agent": "zh-native-tokenizer/0.1"})
                with urllib.request.urlopen(req) as resp:
                    with open(IDS_TXT, "ab") as fout:
                        fout.write(resp.read())
            except Exception as e:  # 单个文件失败不致命
                print(f"  失败（{e}），跳过")
    return UNIHAN_DIR, IDS_TXT


@lru_cache(maxsize=1)
def load_unihan(force: bool = False) -> dict[str, dict[str, str]]:
    """解析 Unihan_*.txt 全部文件。返回 {汉字: {kRSUnicode: "9.2", kIRG_GSource: "G0-4523", ...}}"""
    path, _ = ensure_data(force)
    data: dict[str, dict[str, str]] = {}
    for txt in sorted(path.glob("Unihan_*.txt")):
        with open(txt, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip() or line.startswith("#"):
                    continue
                fields = line.rstrip("\n").split("\t")
                if len(fields) < 3:
                    continue
                code, prop, value = fields[0], fields[1], fields[2]
                if not code.startswith("U+"):
                    continue
                try:
                    ch = chr(int(code[2:], 16))
                except ValueError:
                    continue
                data.setdefault(ch, {})[prop] = value
    return data


@lru_cache(maxsize=1)
def load_ids(force: bool = False) -> dict[str, str]:
    """解析 IDS 文件。返回 {汉字: IDS序列}（如 "你" -> "⿰亻尔"）。

    文件格式：U+4F60<TAB>你<TAB>⿰亻尔（码位、汉字、IDS 三列）。
    无分解信息的字（IDS 为自身）不收录。
    """
    _, path = ensure_data(force)
    data: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 3:
                continue
            code = fields[0]
            if not code.startswith("U+") or " " in code:
                continue
            try:
                ch = chr(int(code[2:], 16))
            except ValueError:
                continue
            if "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf":
                if fields[2] != ch:  # 跳过自引用（无分解信息）
                    data[ch] = fields[2]
    return data


def char_radical_num(ch: str) -> int | None:
    """汉字 -> 康熙部首序号（1~214）；无数据返回 None。"""
    raw = load_unihan().get(ch, {}).get("kRSUnicode")
    if not raw:
        return None
    try:
        return int(raw.split(".")[0].split("'")[0])
    except ValueError:
        return None


def char_radical(ch: str) -> str | None:
    """汉字 -> 部首汉字（如 "湖" -> "水"（氵 归水部））。"""
    num = char_radical_num(ch)
    if num is None:
        return None
    return KANGXI_RADICALS[num - 1]


def char_strokes(ch: str) -> int | None:
    """汉字 -> 残笔画数。"""
    raw = load_unihan().get(ch, {}).get("kRSUnicode")
    if not raw:
        return None
    try:
        return int(raw.split(".")[1].split("'")[0])
    except (IndexError, ValueError):
        return None


def char_definition(ch: str) -> str | None:
    return load_unihan().get(ch, {}).get("kDefinition")


def gb2312_chars() -> list[str]:
    """GB2312 常用汉字（G0/G1 源，约 6763 字）——用作词表强制原子字符集。"""
    out = []
    for ch, props in load_unihan().items():
        gs = props.get("kIRG_GSource", "")
        if gs.startswith(("G0-", "G1-")):
            out.append(ch)
    return sorted(out)


def all_hanzi() -> list[str]:
    """Unihan 中所有带部首信息的汉字（约 2.7 万+）。"""
    return sorted(load_unihan().keys())


def decompose(ch: str, depth: int = 3, _seen: frozenset[str] | None = None) -> list[str]:
    """按 IDS 递归提取部件（限定 CJK 部件，跳过描述运算符）。

    例：decompose("你") -> ["亻", "尔"]；decompose("龘") -> ["龍", "龍", "龍"]
    """
    if _seen is None:
        _seen = frozenset()
    if depth <= 0 or ch in _seen:
        return []
    seq = load_ids().get(ch)
    if seq is None:
        return []
    # 只保留 CJK 部件；过滤 IDS 运算符与 &CDP-XXXX; 等外部引用串
    parts = [c for c in seq if is_cjk(c)]
    out: list[str] = []
    for p in parts:
        out.append(p)
        out.extend(decompose(p, depth - 1, _seen | {ch}))
    return out


def component_chars(ch: str, depth: int = 3) -> list[str]:
    """返回该字及其递归部件（含自身）。用于"部件序列方案 B"的候选集。"""
    return [ch] + decompose(ch, depth)


def radical_groups(radical: str) -> list[str]:
    """返回某部首下所有汉字（用于字形聚类的实验分析）。"""
    return [ch for ch in load_unihan() if char_radical(ch) == radical]


if __name__ == "__main__":
    # 自检：打印示例
    ensure_data()
    for ch in ["湖", "你", "龘", "汉"]:
        print(f"{ch}: 部首={char_radical(ch)} 笔画={char_strokes(ch)} 部件={decompose(ch)} 释义={char_definition(ch)}")
    print(f"GB2312 常用汉字数: {len(gb2312_chars())}")
    print(f"Unihan 部首汉字总数: {len(all_hanzi())}")
