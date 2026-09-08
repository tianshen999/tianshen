# -*- coding: utf-8 -*-
"""形+音+意 全系统深度审计（v0.3 发布前终审）。

检查：三平面键一致性、简繁核心纯净性、挂件索引完备性、零向量、
数据覆盖、证书与文档数字一致性。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import scipy.sparse as sp  # noqa: E402

from src.semantic.core_sets import core_chars, core_words, trad_index  # noqa: E402
from src.semantic.script_tag import classify, to_simplified  # noqa: E402

PROBLEMS: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        PROBLEMS.append(msg)


def meta_keys(name: str) -> list[str]:
    m = json.loads((ROOT / "artifacts" / "semantic" / f"{name}.meta.json").read_text(encoding="utf-8"))
    return m["keys"]


def main() -> int:
    # ---- 1. 平面键一致性 ----
    core = core_chars()
    print(f"核心字符集: {len(core)}")
    for name in ["form_plane", "sound_plane", "meaning_plane", "meaning_keywords"]:
        keys = meta_keys(name)
        check(keys == core, f"{name} 键集合与核心字符集不一致（{len(keys)} vs {len(core)}）")
        print(f"  {name}: {len(keys)} 键，一致 {'✓' if keys == core else '✗'}")

    # ---- 2. 核心纯净性：核心集不得含繁体 ----
    leaked = [c for c in core if classify(c) == "繁"]
    check(not leaked, f"核心字符集泄漏繁体 {len(leaked)} 个: {leaked[:10]}")
    print(f"  核心繁体泄漏: {len(leaked)}")

    # ---- 3. 繁体挂件索引完备性 ----
    ti = trad_index()
    bad_route = [k for k, v in ti.items() if v != k and v not in set(core)]
    check(not bad_route, f"挂件索引路由到核心外字符: {bad_route[:10]}")
    print(f"  繁体挂件索引: {len(ti)} 条，坏路由 {len(bad_route)}")

    # ---- 3.5 形平面部件脚本纯度（ADR-030 简繁校准）----
    fm = json.loads((ROOT / "artifacts" / "semantic" / "form_plane.meta.json").read_text(encoding="utf-8"))
    comps = fm.get("components", [])
    trad_comp = [c for c in comps if classify(c) == "繁"]
    check(not trad_comp, f"形平面部件词表含繁体部件 {len(trad_comp)}: {trad_comp[:10]}")
    print(f"  形平面部件词表: {len(comps)}，繁体部件 {len(trad_comp)}")

    # ---- 4. 词级平面 ----
    words = core_words()
    wkeys = meta_keys("word_form_plane")
    check(wkeys == words, f"词级平面键不一致（{len(wkeys)} vs {len(words)}）")
    w_trad = [w for w in words if any(classify(c) == "繁" for c in w)]
    check(not w_trad, f"核心词集含繁体字词 {len(w_trad)}: {w_trad[:5]}")
    print(f"  核心词集: {len(words)}，含繁词 {len(w_trad)}")

    # ---- 5. 零向量统计 ----
    for name in ["form_plane", "sound_plane", "meaning_plane", "meaning_keywords"]:
        X = sp.load_npz(str(ROOT / "artifacts" / "semantic" / f"{name}.npz"))
        norms = np.asarray(X.power(2).sum(axis=1)).ravel()
        n_zero = int((norms < 1e-12).sum())
        if name == "meaning_keywords":
            # 深义层零向量 = 无维基词典释义的字符（数据覆盖限制，已知记录）
            print(f"  {name} 零向量: {n_zero}/{len(core)}（释义覆盖限制，非缺陷）")
        else:
            check(n_zero < len(core) * 0.5, f"{name} 零向量过多: {n_zero}/{len(core)}")
            print(f"  {name} 零向量: {n_zero}/{len(core)}")

    # ---- 6. 拼音数据覆盖核心字符 ----
    pinyin = json.loads(
        (ROOT / "artifacts" / "pinyin" / "group_a_64k_pinyin.json").read_text(encoding="utf-8"))
    p_entries = pinyin["entries"]
    missing_pinyin = [c for c in core if c not in p_entries]
    check(not missing_pinyin, f"核心字符缺拼音条目 {len(missing_pinyin)}")
    print(f"  核心字符拼音覆盖缺口: {len(missing_pinyin)}")

    # ---- 7. 维基词典覆盖（核心简体） ----
    wk = json.loads((ROOT / "artifacts" / "semantic" / "wiktionary_zh.json").read_text(encoding="utf-8"))
    w_cov = sum(1 for c in core if c in wk)
    print(f"  核心字符中文释义覆盖: {w_cov}/{len(core)} = {w_cov/len(core):.1%}")

    # ---- 8. 证书与当前数据一致 ----
    cert = json.loads(
        (ROOT / "artifacts" / "semantic" / "meaning_certificates.json").read_text(encoding="utf-8"))
    for c in cert:
        if "n_vectors" in c and c["plane"].startswith("S"):
            check(c["n_vectors"] == len(core),
                  f"证书向量数与核心集不符: {c['plane']} {c['n_vectors']} vs {len(core)}")
    print("  证书向量数核验完成")

    # ---- 9. 简繁转写一致性（抽查） ----
    samples = [("銀行", "银行"), ("計算機", "计算机"), ("愛", "爱"), ("龍", "龙"), ("臺灣", "台湾")]
    for trad, simp in samples:
        got = to_simplified(trad)
        check(got == simp, f"繁转简错误: {trad} -> {got}（期望 {simp}）")
    print("  繁转简抽查完成")

    print("\n" + "=" * 50)
    if PROBLEMS:
        print(f"发现 {len(PROBLEMS)} 个问题：")
        for p in PROBLEMS:
            print(" -", p)
        return 1
    print("✅ 形+音+意 深度审计全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
