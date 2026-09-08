# -*- coding: utf-8 -*-
"""解析中文维基词典 dump v2 → 字/词 → 中文义项列表（JSON）。

v2 修正（相对 v1）：
1. 词条页结构：释义位于 ==漢語== 区域内的词性小节（===名詞===/===動詞=== 等）
   与 ===釋義=== 小节；排除 翻譯/讀音/組詞/參考/编码/詞源 等非释义小节；
2. 简体→繁体重定向：收集 redirect 映射，解析后对缺失键沿链解析（防环）。
"""
from __future__ import annotations

import bz2
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DUMP = ROOT / "data" / "raw" / "zhwiktionary.xml.bz2"
OUT = ROOT / "artifacts" / "semantic" / "wiktionary_zh.json"

LINK_RE = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")
TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}")
TAG_RE = re.compile(r"<[^>]+>")
QUOTE_RE = re.compile(r"'{2,}")

# 释义类模板（先于通用模板清洗提取内容）
SYN_OF_RE = re.compile(r"\{\{\s*(?:syn of|synonym of|synonyms of)\|(?:[^|]*\|)*([^|}]+)\}\}")
LB_RE = re.compile(r"\{\{\s*(?:lb|label)\|(?:[^|]*\|)*([^|}]+)\}\}")


def _expand_def_templates(line: str) -> str:
    """把释义类模板展开为可读文字（同义词/用法标签），再清其余模板。"""
    line = SYN_OF_RE.sub(lambda m: f"同義詞：{m.group(1).strip()}", line)
    line = LB_RE.sub(lambda m: f"（{m.group(1).strip()}）", line)
    return line

# 释义小节白名单（词性 + 釋義/释义）
DEF_HEADINGS = re.compile(
    r"(?:釋義|释义|名詞|名词|動詞|动词|形容詞|形容词|副詞|副词|量詞|量词|"
    r"代词|代詞|數詞|数词|助詞|助词|介詞|介词|連詞|连词|叹词|嘆詞|"
    r"擬聲詞|拟声词|詞綴|词缀|前綴|前缀|后綴|後綴|後缀|名動|動名|专有名词|專有名詞)"
)
# 语言区标题：==漢語== / ==汉语== 等
LANG_HEADING = re.compile(r"^==\s*(?:漢語|汉语)\s*==\s*$")


def clean(line: str) -> str:
    line = _expand_def_templates(line)
    line = TEMPLATE_RE.sub("", line)
    line = LINK_RE.sub(r"\1", line)
    line = TAG_RE.sub("", line)
    line = QUOTE_RE.sub("", line)
    line = line.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
    return line.strip(" :：;#*|")


def extract_defs(text: str) -> list[str]:
    """==漢語== 区域内、释义小节下的 # 行。"""
    defs: list[str] = []
    in_zh = False
    in_def = False
    for raw in text.splitlines():
        s = raw.strip()
        if LANG_HEADING.match(s):
            in_zh = True
            in_def = False
            continue
        if s.startswith("==") and s.endswith("==") and not s.startswith("==="):
            in_zh = False  # 离开汉语区（其他语言区）
            in_def = False
            continue
        if not in_zh:
            continue
        if s.startswith("===") and s.endswith("==="):
            inner = s.strip("=").strip()
            in_def = bool(DEF_HEADINGS.search(inner)) and "翻譯" not in inner and "翻译" not in inner
            continue
        if in_def and s.startswith("#"):
            d = clean(s)
            if d and re.search(r"[\u4e00-\u9fff]", d):
                defs.append(d)
    return defs


def load_keys() -> set[str]:
    data = json.loads(
        (ROOT / "artifacts" / "pinyin" / "group_a_64k_pinyin.json").read_text(encoding="utf-8"))
    keys = set(data["entries"].keys())
    trad = json.loads(
        (ROOT / "artifacts" / "pinyin" / "traditional_map.json").read_text(encoding="utf-8"))
    keys |= set(trad.keys())
    keys |= {chr(0x2F00 + i) for i in range(214)}
    return keys


def main() -> int:
    keys = load_keys()
    print(f"目标键数: {len(keys)}")
    result: dict[str, list[str]] = {}
    redirects: dict[str, str] = {}
    title = ""
    buf: list[str] = []
    redir = ""
    n_pages = 0

    with bz2.open(DUMP, "rt", encoding="utf-8", errors="replace") as fh:
        for event, elem in ET.iterparse(fh, events=("end",)):
            if elem.tag.endswith("title"):
                title = (elem.text or "").strip()
            elif elem.tag.endswith("text"):
                buf.append(elem.text or "")
            elif elem.tag.endswith("redirect"):
                redir = elem.get("title", "")
            elif elem.tag.endswith("page"):
                n_pages += 1
                if redir:
                    if title in keys:
                        redirects[title] = redir
                else:
                    defs = extract_defs("\n".join(buf))
                    if defs:
                        result[title] = defs
                buf = []
                redir = ""
                title = ""
                elem.clear()
                if n_pages % 300000 == 0:
                    print(f"已处理 {n_pages} 页，命中 {len(result)}，重定向 {len(redirects)}", flush=True)

    # 重定向解析（最多 3 跳，防环）
    resolved = 0
    for key in keys:
        if key in result:
            continue
        cur, hops, seen = key, 0, set()
        while cur in redirects and hops < 3 and cur not in seen:
            seen.add(cur)
            cur = redirects[cur]
            hops += 1
            if cur in result:
                result[key] = result[cur]
                resolved += 1
                break

    # 简繁变体回退（v3）：页面自身无释义时，取其简/繁变体的释义
    from src.pinyin.cedict import load_cedict
    cedict = load_cedict()
    simp_to_trad: dict[str, str] = {}
    trad_to_simp: dict[str, str] = {}
    for simp, entries in cedict.items():
        for e in entries:
            trad = e.get("trad", "")
            if trad and trad != simp:
                simp_to_trad.setdefault(simp, trad)
                trad_to_simp.setdefault(trad, simp)
    variant_resolved = 0
    for key in keys:
        if key in result:
            continue
        variant = simp_to_trad.get(key) or trad_to_simp.get(key)
        if variant and variant in result:
            result[key] = result[variant]
            variant_resolved += 1
    print(f"总页数 {n_pages}；直接命中 {len(result) - resolved - variant_resolved}；"
          f"重定向解析 {resolved}；简繁变体回退 {variant_resolved}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
