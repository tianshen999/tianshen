# -*- coding: utf-8 -*-
"""v0.3b 流水线：构建意平面 S → 独立性检验 → 组装 F⊕P⊕S → 义近检索演示。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import scipy.sparse as sp  # noqa: E402

from src.semantic import kakeya_check as KC  # noqa: E402
from src.semantic import meaning_plane as MP  # noqa: E402
from src.semantic import weighting as WT  # noqa: E402
from src.semantic import def_keywords as DK  # noqa: E402
from src.semantic.form_plane import FormPlaneBuilder  # noqa: E402
from src.semantic import sound_plane as SP  # noqa: E402


def load_char_set() -> list[str]:
    """核心字符集（简体+通用；ADR-027）。"""
    from src.semantic.core_sets import core_chars
    return core_chars()


def load_plane(name: str) -> sp.csr_matrix:
    return sp.load_npz(str(ROOT / "artifacts" / "semantic" / f"{name}.npz"))


def probe_semantic(S_idf: sp.csr_matrix, chars: list[str], probes: list[str],
                   top_k: int = 6) -> dict:
    """义近检索：探针字在 S 子空间内的最近邻。"""
    idx = {c: i for i, c in enumerate(chars)}
    out = {}
    for p in probes:
        if p not in idx:
            continue
        v = np.asarray(S_idf[idx[p]].toarray()).ravel()
        sims = np.asarray(S_idf @ v).ravel()
        order = np.argsort(-sims)
        nn = []
        for j in order:
            if chars[j] == p:
                continue
            nn.append((chars[j], round(float(sims[j]), 3)))
            if len(nn) >= top_k:
                break
        out[p] = nn
    return out


def main() -> int:
    chars = load_char_set()
    print(f"字符集: {len(chars)}；意平面维度 {MP.DIM}")

    # 1. 构建 S（原始保存；共线列逐块合并 = ADR-030 校准层，仅用于证书）
    S_orig = MP.build(chars)
    MP.save_plane(S_orig, chars, str(ROOT / "artifacts" / "semantic"))
    S_blocks = [MP.DIM_SEMEME, MP.DIM_COMPONENT_SEMEME, MP.DIM_DEF_FEATURES]
    S, S_blocks = WT.merge_collinear(S_orig, S_blocks)
    w = WT.idf_weights(S)
    w[-MP.DIM_DEF_FEATURES:] = 1.0
    S_idf = WT.apply_idf(S, w)

    # 1.5 深义层：义项关键词袋（释义文本语义，独立于形/音）
    K, vocab = DK.build_matrix(chars, min_freq=3, top_k=2000, idf=True)
    DK.save_keywords(K, chars, vocab, str(ROOT / "artifacts" / "semantic"))
    print(f"深义层关键词词汇表: {len(vocab)} 词（样本: {'、'.join(vocab[:12])}）")
    S2 = sp.hstack([S_idf, K]).tocsr()  # S v2 = 义素层 + 深义层

    # 2. S 自身证书
    cert_s = KC.certify("S(意)·原始", S, block_sizes=S_blocks)
    cert_si = KC.certify("S(意)·IDF加权", S_idf, block_sizes=S_blocks)
    cert_k = KC.certify("S深义(关键词)·IDF", K, block_sizes=[K.shape[1]])

    # 3. 独立性检验：S 对 F⊕P 的回归（R² 必须低 = 新维度）
    F_idf = WT.idf_transform(load_plane("form_plane"), keep_last_col_unweighted=True)
    P_idf = WT.idf_transform(load_plane("sound_plane"))
    FP = sp.hstack([F_idf, P_idf]).tocsr()
    indep_total = KC.cross_analysis(FP, S2, k=150)
    indep_deep = KC.cross_analysis(FP, K, k=150)
    cert_k["independence_vs_FP"] = indep_deep
    cert_si["independence_vs_FP_total"] = indep_total
    print(f"\n独立性检验：")
    print(f"  S v2（义素+深义）被 形⊕音 解释 R² = {indep_total['r2_F_explains_P']:.4f}"
          f"（含合法的形义同源重叠）")
    print(f"  深义层（关键词）被 形⊕音 解释 R² = {indep_deep['r2_F_explains_P']:.4f}"
          f"（判据 < 0.3 = 意带来真正新维度）")

    # 4. 组装三维空间 W3 = F ⊕ P ⊕ S2（IDF 版）
    W3 = sp.hstack([F_idf, P_idf, S2]).tocsr()
    norms = np.sqrt(np.asarray(W3.power(2).sum(axis=1)).ravel())
    W3n = sp.diags(1.0 / np.maximum(norms, 1e-12)).dot(W3).tocsr()
    cert_w3 = KC.certify("W3(F⊕P⊕S2)·IDF", W3n, auto_blocks=False)  # ADR-031：拼装平面豁免结构预算

    # 5. 义近检索演示（S2 空间）
    probes = ["水", "火", "心", "木", "金", "山", "言", "手", "女", "日"]
    demo = probe_semantic(S2, chars, probes)
    print("\n=== 义近检索演示（S2 子空间最近邻）===")
    for p, nn in demo.items():
        print(f"{p} -> " + " ".join(f"{c}({s})" for c, s in nn))

    # 6. 证书输出
    certs = [cert_s, cert_si, cert_k, cert_w3]
    KC.save_certificates(certs, str(ROOT / "artifacts" / "semantic" / "meaning_certificates.json"))
    md = KC.make_report(certs, str(ROOT / "artifacts" / "semantic" / "meaning_certificates.md"))
    print("\n" + md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
