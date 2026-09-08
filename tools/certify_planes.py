# -*- coding: utf-8 -*-
"""v0.3a 全量流水线：构建 F/P 平面 → 挂谷检验 → 维度证书 + 形声字专章。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import scipy.sparse as sp  # noqa: E402

from src.pinyin.unihan import readings  # noqa: E402
from src.semantic import kakeya_check as KC  # noqa: E402
from src.semantic.form_plane import FormPlaneBuilder, save_plane as save_form_plane  # noqa: E402
from src.semantic import sound_plane as SP  # noqa: E402
from src.semantic import weighting as WT  # noqa: E402
from src.semantic.phonetic import phonetic_report  # noqa: E402
from src.tokenizer import radicals as R  # noqa: E402


def load_char_set() -> list[str]:
    """核心字符集（简体+通用；ADR-027）。"""
    from src.semantic.core_sets import core_chars
    return core_chars()


def phonetic_subset(chars: list[str], builder: FormPlaneBuilder) -> tuple[list[str], list[str]]:
    """形声字检测：字符的原子部件中存在与主读音同音（声母+韵母）的单字部件。

    返回 (形声字列表, 非形声字列表)。
    """
    hits, misses = [], []
    for ch in chars:
        r = readings(ch)
        if not r:
            misses.append(ch)
            continue
        key = (r[0].initial, r[0].final)
        if key[0] == "":  # 零声母不作形声判据
            misses.append(ch)
            continue
        found = False
        for p in builder._comp_idx:
            if p == ch:
                continue
            pr = readings(p)
            if pr and (pr[0].initial, pr[0].final) == key:
                found = True
                break
        (hits if found else misses).append(ch)
    return hits, misses


def main() -> int:
    chars = load_char_set()
    print(f"字符集: {len(chars)}")

    # 1. 构建平面（原始保存；IDF + 共线列逐块合并 = ADR-030 校准层，仅用于证书）
    fb = FormPlaneBuilder(chars)
    print(f"形平面维度: {fb.dim}（部首 {fb.dim_radical} + 部件 {fb.dim_component} "
          f"+ 结构 {fb.dim_struct} + 笔画 {fb.dim_stroke}）")
    F_orig = fb.build(weighted=False)
    SP.save_plane(SP.build(chars, weighted=False), chars, str(ROOT / "artifacts" / "semantic"))
    save_form_plane(F_orig, chars, fb, str(ROOT / "artifacts" / "semantic"))
    F_blocks = [fb.dim_radical, fb.dim_component, fb.dim_struct, fb.dim_stroke]
    F_raw, F_blocks = WT.merge_collinear(F_orig, F_blocks)
    F_idf = WT.idf_transform(F_raw, keep_last_col_unweighted=True)
    P_orig = SP.build(chars, weighted=False)
    P_blocks = [SP.DIM_INITIAL, SP.DIM_FINAL, SP.DIM_TONE]
    P_raw, P_blocks = WT.merge_collinear(P_orig, P_blocks)
    P_idf = WT.idf_transform(P_raw)
    print(f"音平面维度: {SP.DIM} → 合并后 F {F_raw.shape[1]} / P {P_raw.shape[1]}")

    # 2. 挂谷检验
    cross = KC.cross_analysis(F_raw, P_raw, k=150)
    cert_f = KC.certify("F(形)·原始", F_raw, cross=cross, block_sizes=F_blocks)
    cert_fi = KC.certify("F(形)·IDF加权", F_idf, block_sizes=F_blocks)
    cert_p = KC.certify("P(音)·原始", P_raw, block_sizes=P_blocks)
    cert_pi = KC.certify("P(音)·IDF加权", P_idf, block_sizes=P_blocks)
    W = sp.hstack([F_raw, P_raw]).tocsr()
    row_norms = np.sqrt(np.asarray(W.power(2).sum(axis=1)).ravel())
    Wn = sp.diags(1.0 / np.maximum(row_norms, 1e-12)).dot(W).tocsr()
    pr_sum = cert_f["participation_ratio"] + cert_p["participation_ratio"]
    pr_w = KC.participation_ratio(KC.covariance_evals(Wn))
    cert_w = KC.certify("W(F⊕P)·原始", Wn, concat_note={
        "pr_sum_of_planes": round(pr_sum, 2),
        "pr_concat": round(pr_w, 2),
        "deviation_pct": round(abs(pr_w - pr_sum) / max(pr_sum, 1e-9) * 100, 1),
    }, auto_blocks=False)  # ADR-031：拼装平面豁免结构预算（跨平面冗余属预期）

    # 3. 定向形声检验（部件 → 主读音互信息/提升度）
    comp_cols = slice(fb.dim_radical, fb.dim_radical + fb.dim_component)
    ph = phonetic_report(chars, F_raw, fb, comp_cols)
    print(f"定向形声检验：评估部件 {ph['n_components_evaluated']} 个；"
          f"平均 MI(声母)={ph['mean_mi_initial']}；平均 MI(韵母)={ph['mean_mi_final']}")
    cert_f["phonetic_mi"] = ph
    for t in ph["top_components"][:8]:
        print(f"  部件 {t['component']}（承载 {t['n_chars']} 字）主导声母 {t['dominant_initial']} "
              f"提升 {t['lift']}x 例: {''.join(t['examples'])}")

    # 4. 输出证书
    certs = [cert_f, cert_fi, cert_p, cert_pi, cert_w]
    KC.save_certificates(certs, str(ROOT / "artifacts" / "semantic" / "certificates.json"))
    md = KC.make_report(certs, str(ROOT / "artifacts" / "semantic" / "certificates.md"))
    print("\n" + md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
