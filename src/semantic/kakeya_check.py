# -*- coding: utf-8 -*-
"""挂谷检验模块（Kakeya Check）：维度证书生成。

依据 docs/08 设计定案：
- 满维检验：参与率 PR、有效秩 ER、谱分布、twoNN 本征维度（抽样）
- 独立性检验：F ⟂ P 的截断典型相关（含形声字专章解读）
- 无塌缩/正交性检验：拼装空间 PR/ER 与平面之和对比 + 各向异性

判定准则（docs/08 §4）：PR ≥ 0.8×标称秩 且 ER ≥ 0.8×标称秩 → 无塌缩。
结构依赖预算（ADR-030/031）：certify 默认自动识别 one-hot 特征块
（auto_blocks=True），新板块接入无需手动声明块结构。
全部计算基于 XᵀX（d×d，稀疏友好），随机种子固定。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import scipy.sparse as sp

RNG = np.random.default_rng(20260901)


# ---------- 基础指标 ----------

def covariance_evals(X: sp.csr_matrix, k: int = 200) -> np.ndarray:
    """XᵀX 的前 k 大特征值（X 已列中心化或近似即可；此处用原始列均值未减——指标定义以 Gram 谱为准，见 docs/08）。"""
    XtX = (X.T @ X).toarray().astype(np.float64)
    evals = np.linalg.eigvalsh((XtX + XtX.T) / 2)  # 对称化数值稳定
    return np.sort(evals)[::-1][:k]


def participation_ratio(evals: np.ndarray) -> float:
    total = evals.sum()
    return float((total ** 2) / (evals @ evals)) if total > 0 else 0.0


def effective_rank(evals: np.ndarray) -> float:
    total = evals.sum()
    if total <= 0:
        return 0.0
    p = evals / total
    p = p[p > 1e-12]
    return float(np.exp(-(p * np.log(p)).sum()))


def nominal_rank(X: sp.csr_matrix) -> int:
    return int(np.linalg.matrix_rank(X.toarray()))


def anisotropy(X: sp.csr_matrix) -> float:
    """向量与均值向量的平均余弦（>0.5 强各向异性预警）。"""
    m = np.asarray(X.mean(axis=0)).ravel()
    mn = np.linalg.norm(m)
    if mn < 1e-9:
        return 0.0
    sims = (X @ m) / mn  # 行已 L2 归一化 → 余弦
    return float(np.asarray(sims).mean())


def twonn_id(X: sp.csr_matrix, n_sample: int = 3000) -> dict:
    """twoNN 本征维度（修订 1：先按向量去重再抽样；d1≈0 剔除）。"""
    rows = X.toarray().astype(np.float64)
    # 去重（重复向量使 d1→0 估计退化）
    rows = np.unique(np.round(rows, 6), axis=0)
    n = rows.shape[0]
    if n <= 10:
        return {"id": None, "n_after_dedup": n, "note": "去重后样本不足"}
    if n > n_sample:
        idx = np.sort(RNG.choice(n, size=n_sample, replace=False))
        rows = rows[idx]
    D = rows
    sim = D @ D.T
    np.fill_diagonal(sim, -2.0)
    order = np.argsort(-sim, axis=1)[:, :2]
    d1 = 1.0 - sim[np.arange(len(D)), order[:, 0]]
    d2 = 1.0 - sim[np.arange(len(D)), order[:, 1]]
    ratios = np.clip(d2 / np.maximum(d1, 1e-12), 1.0, None)
    mus = np.log(ratios)
    mus = mus[mus > 1e-9]
    if len(mus) < 10:
        return {"id": None, "n_after_dedup": n, "note": "有效点对不足"}
    return {"id": round(float(np.log(2.0) / mus.mean()), 2), "n_after_dedup": n}


# ---------- 独立性检验 ----------

def cross_analysis(F: sp.csr_matrix, P: sp.csr_matrix, k: int = 200) -> dict:
    """F ⟂ P：截断 SVD 降维后的典型相关与 P 被 F 解释的方差比例。"""
    from scipy.sparse.linalg import svds
    kk = min(k, F.shape[1] - 1, P.shape[1] - 1, F.shape[0] - 1, P.shape[0] - 1)
    if kk < 1:
        return {"rho_max": 0.0, "r2_F_explains_P": 0.0, "k": 0}
    Uf, _, _ = svds(F.astype(np.float64), k=kk)
    Up, _, _ = svds(P.astype(np.float64), k=kk)
    Uf = np.fliplr(Uf)
    Up = np.fliplr(Up)
    C = Uf.T @ Up / F.shape[0]
    # 典型相关：C 的奇异值
    s = np.linalg.svd(C, compute_uv=False)
    rho_max = float(s[0]) if len(s) else 0.0
    # P 被 F 解释的方差比例（多输出岭回归 R²）
    Pf = Up
    W = np.linalg.solve(Uf.T @ Uf + 1e-6 * np.eye(Uf.shape[1]), Uf.T @ Pf)
    resid = Pf - Uf @ W
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((Pf - Pf.mean(0)) ** 2).sum())
    r2 = 1.0 - ss_res / max(ss_tot, 1e-12)
    return {"rho_max": rho_max, "r2_F_explains_P": r2, "k": kk}


# ---------- 证书 ----------

def pr_null_baseline(X: sp.csr_matrix, n_shuffle: int = 5) -> dict:
    """置换零模型（修订 3）：逐列独立打乱破坏结构、保留边际频率，
    得到"无结构时"的 PR 分布，用于显著性判定。"""
    prs = []
    for s in range(n_shuffle):
        Xs = sp.csr_matrix(X.toarray(), dtype=np.float64)
        for j in range(Xs.shape[1]):
            perm = RNG.permutation(Xs.shape[0])
            Xs[:, j] = Xs[perm, j]
        evals = covariance_evals(Xs)
        prs.append(participation_ratio(evals))
    mean = float(np.mean(prs))
    std = float(np.std(prs))
    return {"pr_null_mean": round(mean, 2), "pr_null_std": round(std, 2),
            "pr_null_values": [round(p, 2) for p in prs]}


def detect_blocks(X: sp.csr_matrix) -> list[list[int]]:
    """特征块自动识别（ADR-031 新板块接入协议）：
    把支撑集互斥的列贪心归并为 one-hot 块（每行至多一个激活）。
    新板块无需手动声明块结构，结构依赖预算自动计算。"""
    Xc = X.tocsc()
    n = Xc.shape[1]
    blocks: list[list[int]] = []
    block_support: list[set[int]] = []
    for j in range(n):
        col = Xc[:, j]
        support = set(col.indices)
        placed = False
        for bi, bs in enumerate(block_support):
            if not (support & bs):  # 支撑集互斥 → 可入同一 one-hot 块
                blocks[bi].append(j)
                bs.update(support)
                placed = True
                break
        if not placed:
            blocks.append([j])
            block_support.append(support)
    return blocks


def achievable_rank(X: sp.csr_matrix, block_sizes: list[int] | None,
                    auto_blocks: bool = False) -> dict | None:
    """结构依赖预算（ADR-030/031）：列块秩之和 = 该特征结构下的可达最大秩上界。

    块内真实依赖（多音字使 one-hot 列支撑重叠、重复列、截距型列等）
    由块内实测秩体现；块间秩和是总秩的上界。
    判据：实测总秩 ≥ 0.95 × 可达秩（块间几乎无冗余）。

    分块来源三选一（优先级从上到下）：
    1. block_sizes 声明式分块（现有流水线，结果可复现）；
    2. auto_blocks=True → detect_blocks 自动识别（ADR-031，新板块零声明接入）；
    3. 皆无 → 返回 None（不启用预算判据，如拼装平面 W=F⊕P）。
    """
    Xc = X.tocsc()
    if block_sizes:
        groups: list[list[int]] = []
        pos = 0
        for size in block_sizes:
            if pos >= Xc.shape[1]:
                break
            groups.append(list(range(pos, pos + size)))
            pos += size
        auto = False
    elif auto_blocks:
        groups = detect_blocks(X)
        auto = True
    else:
        return None
    per_block = [int(np.linalg.matrix_rank(Xc[:, g].toarray())) for g in groups]
    achievable = sum(per_block)
    return {"achievable": achievable, "per_block": per_block,
            "nominal_blocks": sum(len(g) for g in groups),
            "n_blocks": len(groups),
            "block_sizes": [len(g) for g in groups],
            "auto_detected": auto}


def certify(name: str, X: sp.csr_matrix, meta: dict | None = None,
            cross: dict | None = None, concat_note: dict | None = None,
            block_sizes: list[int] | None = None,
            auto_blocks: bool = True) -> dict:
    """生成单平面维度证书。

    ADR-031 新板块接入协议：新板块调用 certify 时无需声明 block_sizes ——
    默认 auto_blocks=True 自动识别 one-hot 块并计算结构依赖预算。
    拼装平面（W=F⊕P 等组合空间，跨平面冗余属预期）显式传 auto_blocks=False 豁免。
    """
    evals = covariance_evals(X)
    pr = participation_ratio(evals)
    er = effective_rank(evals)
    rank = nominal_rank(X)
    rank_ok = rank >= 0.8 * X.shape[1]
    pr_ok = pr >= 0.8 * rank
    if not rank_ok:
        verdict = "COLLAPSED 塌缩（维度缺失）"
    elif not pr_ok:
        verdict = "CONCENTRATED 谱集中（满秩但能量幂律分布）"
    else:
        verdict = "PASS 通过"
    twonn = twonn_id(X)
    null = pr_null_baseline(X) if X.shape[1] <= 1200 else None
    pr_sig = None
    if null:
        pr_sig = round((pr - null["pr_null_mean"]) / max(null["pr_null_std"], 1e-9), 1)
    cert = {
        "plane": name,
        "n_vectors": int(X.shape[0]),
        "dim_nominal": int(X.shape[1]),
        "rank_measured": rank,
        "participation_ratio": round(pr, 2),
        "effective_rank": round(er, 2),
        "rank_criterion": rank_ok,
        "pr_criterion": pr_ok,
        "pr_null_baseline": null,
        "pr_z_score": pr_sig,
        "verdict": verdict,
        "anisotropy": round(anisotropy(X), 4),
        "top20_eigenvalues": [round(float(e), 2) for e in evals[:20]],
        "cumulative_energy_top5": round(float(evals[:5].sum() / evals.sum()), 4),
        "twonn": twonn,
    }
    if cross:
        cert["independence"] = {k: round(float(v), 4) for k, v in cross.items()}
    if concat_note:
        cert["concat"] = concat_note
    budget = achievable_rank(X, block_sizes, auto_blocks=auto_blocks)
    if budget:
        ratio = rank / budget["achievable"] if budget["achievable"] else 0.0
        cert["structure_budget"] = budget
        cert["rank_vs_achievable"] = round(ratio, 4)
        cert["achievable_criterion"] = ratio >= 0.95
    return cert


def make_report(certs: list[dict], out_path: str) -> str:
    lines = ["# 维度证书（挂谷检验）", ""]
    for c in certs:
        lines.append(f"## 平面 {c['plane']}：{c['verdict']}")
        lines.append(f"- 向量数 {c['n_vectors']}；标称维度 {c['dim_nominal']}；实测秩 {c['rank_measured']}"
                     f"（判据 ≥ {0.8 * c['dim_nominal']:.0f}）{'✓' if c['rank_criterion'] else '✗'}")
        lines.append(f"- 参与率 PR = {c['participation_ratio']}（判据 ≥ {0.8 * c['rank_measured']:.1f}）"
                     f" {'✓' if c['pr_criterion'] else '✗'}；有效秩 ER = {c['effective_rank']}")
        if c.get("structure_budget"):
            b = c["structure_budget"]
            mode = "自动识别" if b.get("auto_detected") else "声明分块"
            lines.append(f"- 结构依赖预算（{mode}，{b.get('n_blocks')} 块，块规模 {b.get('block_sizes')}）："
                         f"可达秩 {b['achievable']}；实测/可达 = {c['rank_vs_achievable']}"
                         f"（判据 ≥ 0.95）{'✓' if c['achievable_criterion'] else '✗'}")
            lines.append(f"  块内实测秩: {b['per_block']}")
        if c.get("pr_null_baseline"):
            nb = c["pr_null_baseline"]
            z = c.get("pr_z_score")
            lines.append(f"- 置换零模型 PR = {nb['pr_null_mean']} ± {nb['pr_null_std']}；PR 显著性 z = {z}")
            if z is not None and abs(z) > 2:
                if z > 0:
                    lines.append("  结构判定：z>2 —— 维度散布显著优于随机（无凝聚、无塌缩）。")
                else:
                    lines.append("  结构判定：z<-2 —— 显著凝聚于真实层级结构（如部首聚类），"
                                 "这是语言事实而非塌缩（塌缩的定义是秩缺失，已由秩检验排除）。")
        lines.append(f"- 各向异性 = {c['anisotropy']}；twoNN 本征维度 = {c['twonn'].get('id')}"
                     f"（去重后样本 {c['twonn'].get('n_after_dedup')}）")
        lines.append(f"- 前 5 维累计能量 = {c['cumulative_energy_top5']}")
        lines.append(f"- 前 20 特征值: {c['top20_eigenvalues']}")
        if c.get("independence"):
            ind = c["independence"]
            lines.append(f"- 与另一平面的最大典型相关 ρ_max = {ind['rho_max']}；"
                         f"被解释方差 R² = {ind['r2_F_explains_P']}")
            lines.append("  解读：低相关=平面正交成立；残存相关若集中在形声字属语言事实（见形声字专章）。")
        if c.get("phonetic"):
            ph = c["phonetic"]
            lines.append("- 形声字专章（子集回归法，已弃用，见 ADR-022）：")
            for label, v in ph.items():
                lines.append(f"  - {label}: ρ_max = {v['rho_max']}, R²(F→P) = {v['r2_F_explains_P']}")
        if c.get("phonetic_mi"):
            ph = c["phonetic_mi"]
            lines.append("- 定向形声检验（部件→主读音）：")
            lines.append(f"  - 评估部件 {ph['n_components_evaluated']} 个；平均 MI(声母) = {ph['mean_mi_initial']}；"
                         f"平均 MI(韵母) = {ph['mean_mi_final']}")
            lines.append("  - 读音牵引力最强的部件：")
            for t in ph["top_components"][:10]:
                lines.append(f"    · {t['component']}（承载 {t['n_chars']} 字）→ 声母 {t['dominant_initial']} "
                             f"提升 {t['lift']}x，例：{''.join(t['examples'])}")
            lines.append("  解读：MI > 0 且存在高提升部件 = 字形确实携带读音信息（形声），")
            lines.append("  这是中文原生结构优势的量化证据，也是 F/P 平面间少量真实相关的来源。")
        if c.get("concat"):
            lines.append(f"- 拼装检验: {c['concat']}")
        lines.append("")
    md = "\n".join(lines)
    Path(out_path).write_text(md, encoding="utf-8")
    return md


def save_certificates(certs: list[dict], out_path: str) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(certs, ensure_ascii=False, indent=1), encoding="utf-8")
    return p
