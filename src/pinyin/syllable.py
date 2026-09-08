# -*- coding: utf-8 -*-
"""音节解析：拼音 ↔ 结构（声母/韵母/声调）↔ 注音符号。

设计（ADR-016）：核心是"读音"（声母+韵母+声调，符号无关的语言事实）；
拼音是标准输出格式，注音是挂件输出。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ---------- 基本表 ----------

# 声母（含零声母 ""）
INITIALS = ["zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l",
            "g", "k", "h", "j", "q", "x", "r", "z", "c", "s", ""]

# 韵母 → 注音（按汉语拼音方案韵母表；-i 为 zhi/chi/shi/ri/zi/ci/si 的舌尖元音，注音不写）
# 另含叹词音节：yo/io、m、n、ng
FINAL_TO_ZHUYIN = {
    "a": "ㄚ", "o": "ㄛ", "e": "ㄜ", "ê": "ㄝ",
    "ai": "ㄞ", "ei": "ㄟ", "ao": "ㄠ", "ou": "ㄡ",
    "an": "ㄢ", "en": "ㄣ", "ang": "ㄤ", "eng": "ㄥ", "ong": "ㄨㄥ", "er": "ㄦ",
    "i": "ㄧ", "ia": "ㄧㄚ", "ie": "ㄧㄝ", "iao": "ㄧㄠ", "iu": "ㄧㄡ",
    "ian": "ㄧㄢ", "in": "ㄧㄣ", "iang": "ㄧㄤ", "ing": "ㄧㄥ", "iong": "ㄩㄥ",
    "u": "ㄨ", "ua": "ㄨㄚ", "uo": "ㄨㄛ", "uai": "ㄨㄞ", "ui": "ㄨㄟ",
    "uan": "ㄨㄢ", "un": "ㄨㄣ", "uang": "ㄨㄤ", "ueng": "ㄨㄥ",
    "ü": "ㄩ", "üe": "ㄩㄝ", "üan": "ㄩㄢ", "ün": "ㄩㄣ",
    "-i": "",  # 舌尖元音（zhi/zi 等）：注音只写声母
    "yo": "ㄧㄛ", "io": "ㄧㄛ", "m": "ㄇ", "n": "ㄋ", "ng": "ㄫ",
}

# 声母 → 注音
INITIAL_TO_ZHUYIN = {
    "b": "ㄅ", "p": "ㄆ", "m": "ㄇ", "f": "ㄈ", "d": "ㄉ", "t": "ㄊ", "n": "ㄋ", "l": "ㄌ",
    "g": "ㄍ", "k": "ㄎ", "h": "ㄏ", "j": "ㄐ", "q": "ㄑ", "x": "ㄒ",
    "zh": "ㄓ", "ch": "ㄔ", "sh": "ㄕ", "r": "ㄖ", "z": "ㄗ", "c": "ㄘ", "s": "ㄙ",
    "": "",
}

# 声调 → 注音调号（轻声用 ˙）
TONE_TO_ZHUYIN = {1: "", 2: "ˊ", 3: "ˇ", 4: "ˋ", 5: "˙"}

# 元音变音符号映射（解析带调号拼音）
_VOWEL_MARKS = {
    "ā": ("a", 1), "á": ("a", 2), "ǎ": ("a", 3), "à": ("a", 4),
    "ē": ("e", 1), "é": ("e", 2), "ě": ("e", 3), "è": ("e", 4),
    "ī": ("i", 1), "í": ("i", 2), "ǐ": ("i", 3), "ì": ("i", 4),
    "ō": ("o", 1), "ó": ("o", 2), "ǒ": ("o", 3), "ò": ("o", 4),
    "ū": ("u", 1), "ú": ("u", 2), "ǔ": ("u", 3), "ù": ("u", 4),
    "ǖ": ("ü", 1), "ǘ": ("ü", 2), "ǚ": ("ü", 3), "ǜ": ("ü", 4),
    "ê̄": ("ê", 1), "ế": ("ê", 2), "ê̌": ("ê", 3), "ề": ("ê", 4),
    "m̄": ("m", 1), "ḿ": ("m", 2), "m̀": ("m", 4),
    "ń": ("n", 2), "ň": ("n", 3), "ǹ": ("n", 4),
}

# 标调位置（带调号输出用）：每个韵母中标调元音的索引
_TONE_POS = {
    "a": 0, "o": 0, "e": 0, "ê": 0, "ai": 0, "ei": 0, "ao": 0, "ou": 0,
    "an": 0, "en": 0, "ang": 0, "eng": 0, "ong": 0, "er": 0,
    "i": 0, "ia": 1, "ie": 1, "iao": 1, "iu": 1, "ian": 1, "in": 0,
    "iang": 1, "ing": 0, "iong": 1,
    "u": 0, "ua": 1, "uo": 1, "uai": 1, "ui": 1, "uan": 1, "un": 0,
    "uang": 1, "ueng": 1,
    "ü": 0, "üe": 1, "üan": 1, "ün": 0, "-i": -1, "": -1,
    "yo": 1, "io": 1, "m": 0, "n": 0, "ng": -1,
}


def _tone_diacritic(vowel: str, tone: int) -> str:
    table = {"a": ["a", "ā", "á", "ǎ", "à"], "e": ["e", "ē", "é", "ě", "è"],
             "i": ["i", "ī", "í", "ǐ", "ì"], "o": ["o", "ō", "ó", "ǒ", "ò"],
             "u": ["u", "ū", "ú", "ǔ", "ù"], "ü": ["ü", "ǖ", "ǘ", "ǚ", "ǜ"],
             "ê": ["ê", "ê̄", "ế", "ê̌", "ề"],
             "m": ["m", "m̄", "ḿ", "m\u030c", "m̀"],
             "n": ["n", "n\u0304", "ń", "ň", "ǹ"]}
    row = table.get(vowel)
    if row is None:
        return vowel  # 未知"元音"：保持原样（防御）
    return row[tone] if 1 <= tone <= 4 else vowel


def _unwrap(base: str) -> str:
    """把 y/w 开头的拼写还原为结构韵母（用于注音等结构输出）。"""
    if base.startswith("y"):
        rest = base[1:]
        if rest == "i":
            return "i"
        if rest == "u":
            return "ü"
        if rest in ("a", "e", "ao", "ou", "an", "in", "ang", "ing", "ong"):
            return {"a": "ia", "e": "ie", "ao": "iao", "ou": "iu", "an": "ian",
                    "in": "in", "ang": "iang", "ing": "ing", "ong": "iong"}[rest]
        if rest in ("ue", "uan", "un"):
            return {"ue": "üe", "uan": "üan", "un": "ün"}[rest]
        return base
    if base.startswith("w"):
        rest = base[1:]
        if rest == "u":
            return "u"
        if rest in ("a", "o", "ai", "ei", "an", "en", "ang", "eng"):
            return {"a": "ua", "o": "uo", "ai": "uai", "ei": "ui", "an": "uan",
                    "en": "un", "ang": "uang", "eng": "ueng"}[rest]
        return base
    return base


@dataclass(frozen=True)
class Syllable:
    """一个读音：声母 + 韵母 + 声调（1~4，5=轻声，0=未知）。

    spelling 为原始拼写（保留 y/w 与 ü 的写法，如 "yin"、"lüe"），
    用于拼音输出；initial/final 为结构表示（yin → 声母"" 韵母"in"），
    用于注音等结构输出。
    """
    initial: str
    final: str
    tone: int
    spelling: str = ""

    def __post_init__(self):
        if not self.spelling:
            object.__setattr__(self, "spelling", self.initial + self.final)

    @property
    def base(self) -> str:
        """结构拼写（声母+韵母）。"""
        return self.initial + ("" if self.final == "-i" else self.final)

    def numbered(self) -> str:
        """带数字调号：yin2（未知声调不加数字）。"""
        return self.spelling + (str(self.tone) if 1 <= self.tone <= 5 else "")

    def marked(self) -> str:
        """带调号输出：shì（未知声调不标）。

        舌尖元音 -i（zhi/chi/shi/ri/zi/ci/si）的调号标在拼写末尾的 i 上。
        """
        if self.tone not in (1, 2, 3, 4):
            return self.spelling
        if self.final == "-i":
            idx = len(self.spelling) - 1
        else:
            pos = _TONE_POS.get(self.final, -1)
            if pos < 0:
                return self.spelling
            # 标调位置 = 拼写中韵母的起始 + 韵母内部标调索引
            idx = len(self.spelling) - len(self.final) + pos
        if idx < 0 or idx >= len(self.spelling):
            return self.spelling
        chars = list(self.spelling)
        chars[idx] = _tone_diacritic(chars[idx], self.tone)
        return "".join(chars)

    def zhuyin(self) -> str:
        """注音符号：ㄒㄧㄥˊ（声调号附后）。"""
        core = INITIAL_TO_ZHUYIN.get(self.initial, "") + FINAL_TO_ZHUYIN.get(self.final, "")
        return core + TONE_TO_ZHUYIN.get(self.tone, "")

    def tone_name(self) -> str:
        return {1: "阴平", 2: "阳平", 3: "上声", 4: "去声", 5: "轻声", 0: "未知"}.get(self.tone, "?")


def _split_initial_final(base: str) -> tuple[str, str]:
    """无调号拼音 → (声母, 韵母)。zhi/chi/shi/ri/zi/ci/si 的韵母记为 -i。

    y/w 开头的拼写先还原为结构韵母（yi→i, yu→ü, wang→uang ...）。
    """
    b = _unwrap(base)
    for ini in ["zh", "ch", "sh"]:
        if b.startswith(ini):
            rest = b[len(ini):]
            if rest == "i":
                return ini, "-i"  # zhi/chi/shi 的舌尖元音
            if rest in FINAL_TO_ZHUYIN:
                return ini, rest
    if b[:1] in "bpmfdtnlgkhjqxrzcs" and len(b) >= 2:
        rest = b[1:]
        if rest == "i" and b[0] in "rzcs":
            return b[0], "-i"  # ri/zi/ci/si 的舌尖元音（di/ti/ni/li 的 i 是普通韵母）
        if rest in FINAL_TO_ZHUYIN:
            return b[0], rest
    if b in FINAL_TO_ZHUYIN or b in ("m", "n", "ng"):
        return "", b
    # 兜底：按最长声母再切
    for ini in ["zh", "ch", "sh"]:
        if b.startswith(ini):
            return ini, b[len(ini):]
    if b[:1] in "bpmfdtnlgkhjqxrzcs":
        return b[0], b[1:]
    return "", b


def parse_numbered(s: str) -> Syllable:
    """yin2 → Syllable(initial='', final='in', tone=2, spelling='yin')。"""
    m = re.match(r"^(.*?)([1-5])$", s.strip())
    if not m:
        return parse_marked(s.strip())
    spelling, tone = m.group(1), int(m.group(2))
    spelling = spelling.replace("v", "ü").replace("u:", "ü")
    ini, fin = _split_initial_final(spelling)
    return Syllable(ini, fin, tone, spelling)


def parse_marked(s: str) -> Syllable:
    """yín → Syllable(initial='', final='in', tone=2, spelling='yin')。"""
    s = s.strip()
    tone = 0
    spelling_chars: list[str] = []
    for ch in s:
        if ch in _VOWEL_MARKS:
            plain, t = _VOWEL_MARKS[ch]
            spelling_chars.append(plain)
            tone = t
        else:
            spelling_chars.append(ch)
    spelling = "".join(spelling_chars).replace("v", "ü").replace("u:", "ü")
    ini, fin = _split_initial_final(spelling)
    return Syllable(ini, fin, tone, spelling)


def parse(s: str) -> Syllable:
    """自动识别数字调号或变音调号。"""
    return parse_numbered(s) if re.search(r"[1-5]$", s.strip()) else parse_marked(s)


def to_zhuyin(text: str, sep: str = " ") -> str:
    """一串带调/数字拼音 → 注音（如 'tian1 shen2' → 'ㄊㄧㄢ ㄕㄣˊ'）。"""
    return sep.join(parse(tok).zhuyin() for tok in text.split())
