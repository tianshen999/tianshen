# -*- coding: utf-8 -*-
"""挂谷检验与向量平面测试：合成数据验证指标正确性 + 真实数据构建冒烟。

严谨性要求（docs/08 §5）：每个指标必须先在已知答案的合成数据上验证。
"""
import sys
from pathlib import Path

import numpy as np
import pytest
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.semantic import kakeya_check as KC  # noqa: E402

HAS_DATA = (ROOT / "data" / "Unihan.zip").exists() and (ROOT / "data" / "IDS.TXT").exists()


# ---------- 合成数据：指标正确性 ----------

def _rand_matrix(n: int, d: int, seed: int = 7) -> sp.csr_matrix:
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, d))
    X = X / np.linalg.norm(X, axis=1, keepdims=True)
    return sp.csr_matrix(X)


def test_full_rank_matrix_certifies_pass():
    """满秩随机矩阵：PR/ER 应≈标称维度，判据通过。"""
    X = _rand_matrix(2000, 60)
    evals = KC.covariance_evals(X)
    pr, er = KC.participation_ratio(evals), KC.effective_rank(evals)
    assert pr > 0.9 * 60, f"PR={pr}"
    assert er > 0.9 * 60, f"ER={er}"


def test_collapsed_matrix_detected():
    """塌缩矩阵（大量重复列）：有效维度应远低于标称维度。"""
    rng = np.random.default_rng(3)
    base = rng.standard_normal((1000, 3))
    X = np.hstack([base, base[:, :1]] * 20)  # 60 列但只有 3 个独立方向
    X = sp.csr_matrix(X)
    evals = KC.covariance_evals(X)
    pr, er = KC.participation_ratio(evals), KC.effective_rank(evals)
    assert pr < 10, f"塌缩未检出 PR={pr}"
    assert er < 10, f"塌缩未检出 ER={er}"


def test_anisotropy_bounds():
    """各向异性：均匀分布→低；完全相同向量→1。"""
    X = _rand_matrix(500, 20)
    assert KC.anisotropy(X) < 0.5
    ones = sp.csr_matrix(np.ones((100, 10)) / np.sqrt(10))
    assert KC.anisotropy(ones) > 0.99


def test_cross_analysis_orthogonal_planes():
    """正交合成平面：ρ_max ≈ 0。"""
    F = _rand_matrix(3000, 80, seed=11)
    P = _rand_matrix(3000, 30, seed=22)  # 独立生成 → 高维下近似正交
    out = KC.cross_analysis(F, P, k=30)
    assert out["rho_max"] < 0.3, f"ρ_max={out['rho_max']}"
    assert out["r2_F_explains_P"] < 0.3


def test_cross_analysis_dependent_planes():
    """相关平面：P 的多数维度来自 F 的主奇异方向 → 应检出高 R²。"""
    F = _rand_matrix(3000, 60, seed=5)
    U, S, Vt = np.linalg.svd(F.toarray(), full_matrices=False)
    basis = U[:, :10]  # F 的主方向
    rng = np.random.default_rng(9)
    P = np.hstack([basis @ rng.standard_normal((10, 15)), rng.standard_normal((3000, 5))])
    P = sp.csr_matrix(P)
    out = KC.cross_analysis(F, P, k=50)
    assert out["r2_F_explains_P"] > 0.5, f"未检出依赖 R²={out['r2_F_explains_P']}"


# ---------- 真实数据：构建冒烟 ----------

@pytest.mark.skipif(not HAS_DATA, reason="需要 data/Unihan.zip 与 IDS.TXT")
def test_form_plane_builder_real():
    from src.semantic.form_plane import FormPlaneBuilder
    b = FormPlaneBuilder(["湖", "河", "海"])
    v = b.char_vector("湖")
    assert abs(np.linalg.norm(v) - 1.0) < 1e-4
    # 部首：湖属水部（康熙 85）→ 索引 84 位置应为非零（L2 归一化后 ≈0.38）
    assert v[84] > 0.3
    # 部件：氵 必在其中
    assert "氵" in b.components
    assert v[b.dim_radical + b._comp_idx["氵"]] > 0
    # 词级聚合：均值归一
    w = b.word_vector("湖河")
    assert abs(np.linalg.norm(w) - 1.0) < 1e-4


@pytest.mark.skipif(not HAS_DATA, reason="需要拼音数据")
def test_sound_plane_real():
    from src.pinyin.syllable import INITIALS
    from src.semantic import sound_plane as SP
    v = SP.char_vector("行")  # 多音：xíng / háng
    assert abs(np.linalg.norm(v) - 1.0) < 1e-4
    assert v[INITIALS.index("x")] > 0 and v[INITIALS.index("h")] > 0
    w = SP.word_vector("银行")
    assert abs(np.linalg.norm(w) - 1.0) < 1e-4


def test_word_aggregation_idempotent():
    from src.semantic import sound_plane as SP
    v1 = SP.word_vector("人人")
    v2 = SP.char_vector("人")
    assert np.allclose(v1, v2, atol=1e-5)


# ---------- 意平面（v0.3b）----------

@pytest.mark.skipif(not HAS_DATA, reason="需要字形/拼音/维基词典数据")
def test_meaning_char_vector():
    from src.semantic import meaning_plane as MP
    v = MP.char_vector("湖")
    assert abs(np.linalg.norm(v) - 1.0) < 1e-4
    # 部首义素：湖属水部 → 义素槽 84
    assert v[84] > 0.3
    # 部件义素：氵（水部 84）必在聚合袋中
    assert v[MP.DIM_SEMEME + 84] > 0


@pytest.mark.skipif(not HAS_DATA, reason="需要数据")
def test_meaning_word_vector_and_def_features():
    from src.semantic import meaning_plane as MP
    wv = MP.word_vector("银行")
    assert abs(np.linalg.norm(wv) - 1.0) < 1e-4
    # 词级义项特征：银行有维基词典中文释义 → has_zh = 1
    off = MP.DIM_SEMEME + MP.DIM_COMPONENT_SEMEME
    assert wv[off] > 0
    # 龘：有 kDefinition → has_en 槽 = 1（off+2）
    v = MP.char_vector("龘")
    assert v[off + 2] > 0


@pytest.mark.skipif(not HAS_DATA, reason="需要数据")
def test_meaning_independence_criterion_bounds():
    """独立性判据函数可用性：正交随机平面 → R² 低（合成冒烟，真实判定在流水线）。"""
    from src.semantic import kakeya_check as KC
    F = _rand_matrix(2000, 60, seed=31)
    S = _rand_matrix(2000, 40, seed=32)
    out = KC.cross_analysis(F, S, k=30)
    assert out["r2_F_explains_P"] < 0.3


# ---------- 义近检索评测（v0.3c）----------

def test_probe_set_valid():
    from eval.semantic_bench import PROBES
    assert len(PROBES) >= 30
    for probe, expected in PROBES.items():
        assert len(probe) == 1 and all(len(e) == 1 for e in expected)
        assert probe not in expected


def test_retrieve_skips_zero_and_self():
    from eval.semantic_bench import retrieve
    X = sp.csr_matrix(np.array([
        [1.0, 0.0],   # 甲
        [0.7, 0.0],   # 乙
        [0.0, 0.0],   # 丙（零向量，应跳过）
    ]))
    nn = retrieve(X, ["甲", "乙", "丙"], "甲", top_k=5)
    assert nn == ["乙"]  # 跳过自身与零向量


def test_score_metrics_sanity():
    from eval.semantic_bench import score
    # 甲=探针，乙/丁=有数据，丙=零向量；期望=[乙]
    X = sp.csr_matrix(np.array([
        [1.0, 0.0], [0.7, 0.0], [0.0, 0.0], [0.0, 1.0],
    ]))
    # 甲向量与乙相似（0.7），丁正交
    import json
    # score 用全局 PROBES——这里直接测 retrieve 语义已覆盖；score 集成在流水线跑
    from eval.semantic_bench import retrieve
    nn = retrieve(X, ["甲", "乙", "丙", "丁"], "甲", top_k=3)
    assert "乙" in nn and "丙" not in nn


# ---------- 深义关键词层（v0.3b 修订1）----------

@pytest.mark.skipif(not (ROOT / "artifacts" / "semantic" / "wiktionary_zh.json").exists(),
                    reason="需要维基词典解析结果")
def test_def_keywords_vector():
    from src.semantic import def_keywords as DK
    vocab = DK.build_vocab(min_freq=3, top_k=500)
    idx = {k: i for i, k in enumerate(vocab)}
    v = DK.keyword_vector("银行", vocab, idx)
    assert abs(np.linalg.norm(v) - 1.0) < 1e-4
    assert v.sum() > 0  # 银行有释义 → 非零
    # 关键词词汇表应含真实语义词（避免模板套话占位）
    assert any(k in vocab for k in ["植物", "動物", "金屬", "金屬", "身体", "身體"])


# ---------- 简繁分离（ADR-027）----------

@pytest.mark.skipif(not HAS_DATA, reason="需要 Unihan 数据")
def test_script_classify():
    from src.semantic.script_tag import classify, to_simplified
    assert classify("爱") == "简"
    assert classify("愛") == "繁"
    assert classify("水") == "通用"
    assert to_simplified("銀行") == "银行"
    assert to_simplified("水") == "水"


@pytest.mark.skipif(not HAS_DATA, reason="需要数据")
def test_core_sets_exclude_traditional():
    from src.semantic.core_sets import core_chars, trad_chars, trad_index
    chars = core_chars()
    assert "愛" not in chars and "爱" in chars
    assert "愛" in trad_chars()
    idx = trad_index()
    assert idx.get("愛") == "爱"


# ---------- IDF 加权（修订 2）----------

def test_idf_downweights_common_columns():
    from src.semantic.weighting import idf_weights
    rng = np.random.default_rng(1)
    X = sp.csr_matrix(rng.random((500, 4)) > 0.3).astype(np.float64)
    X[:, 0] = sp.csr_matrix(np.ones((500, 1)))  # 全出现列
    X[:, 3] = sp.csr_matrix((rng.random(500) > 0.98).astype(float).reshape(-1, 1))  # 极罕见列
    w = idf_weights(X)
    assert w[0] < 1.5, f"全出现列权重应≈1，实际 {w[0]}"
    assert w[3] > w[0] * 3, f"罕见列权重应远高于常见列：{w[0]} vs {w[3]}"


# ---------- 结构块自动识别（ADR-031 新板块接入协议）----------

def _onehot_families_matrix(n: int = 300, seed: int = 12) -> sp.csr_matrix:
    """合成矩阵：部首 one-hot（4 列，全覆盖）+ 声调 one-hot（5 列，仅 240 行有值，
    其余未知 —— 避免两族列和重合的巧合依赖）+ 两个计数列。"""
    rng = np.random.default_rng(seed)
    r_idx = rng.integers(0, 4, size=n)
    A = np.zeros((n, 4)); A[np.arange(n), r_idx] = 1.0
    t_idx = rng.integers(0, 5, size=240)
    B = np.zeros((n, 5)); B[np.arange(240), t_idx] = 1.0
    C = np.column_stack([rng.uniform(0.1, 1, n), rng.uniform(0.1, 1, n)])
    return sp.csr_matrix(np.hstack([A, B, C]))


def test_detect_blocks_finds_one_hot_families():
    """自动识别：两个 one-hot 家族各成一整块，全支持计数列各自成块。"""
    X = _onehot_families_matrix()
    blocks = KC.detect_blocks(X)
    block_sets = [set(b) for b in blocks]
    assert {0, 1, 2, 3} in block_sets, f"部首 one-hot 应成整块: {block_sets}"
    assert {4, 5, 6, 7, 8} in block_sets, f"声调 one-hot 应成整块: {block_sets}"
    assert {9} in block_sets and {10} in block_sets, "全支持计数列应各自成块"


def test_achievable_rank_auto_blocks():
    """auto_blocks：无声明分块时自动计算预算。
    支撑互斥的 one-hot 家族各自满秩（4、5），两个独立计数列各秩 1：
    可达 4+5+1+1=11；实测秩 11 → 秩/可达 = 1.0。"""
    X = _onehot_families_matrix()
    b = KC.achievable_rank(X, None, auto_blocks=True)
    assert b is not None and b["auto_detected"] is True
    assert b["achievable"] == 11, f"可达秩应为 4+5+1+1=11，实际 {b['achievable']}"
    assert b["n_blocks"] == 4 and b["per_block"] == [4, 5, 1, 1]
    cert = KC.certify("合成板块", X)  # ADR-031：默认自动启用，零声明接入
    assert cert["structure_budget"]["auto_detected"] is True
    assert cert["rank_vs_achievable"] == 1.0 and cert["achievable_criterion"] is True


def test_achievable_rank_explicit_and_disabled():
    """声明分块结果与自动识别一致；auto_blocks=False 且无声明 → None（豁免）。"""
    X = _onehot_families_matrix()
    b1 = KC.achievable_rank(X, [4, 5, 2], auto_blocks=False)
    assert b1 is not None and b1["auto_detected"] is False
    assert b1["achievable"] == 11 and b1["per_block"] == [4, 5, 2]
    assert KC.achievable_rank(X, None, auto_blocks=False) is None
    assert KC.achievable_rank(X, []) is None
    cert = KC.certify("拼装空间·豁免", X, auto_blocks=False)
    assert "structure_budget" not in cert


def test_achievable_rank_captures_block_dependency():
    """块内真实依赖计入预算：2 个完全重复列 → 块秩 1（可达 1，非 2）。
    注：auto 识别按支撑集分块，重复列支撑重叠会各自成块（可达 2，上界更松）；
    完全同形列由校准层 merge_collinear 在证书生成前去除（ADR-030）。"""
    rng = np.random.default_rng(42)
    dup = rng.choice([0.0, 1.0], size=(200, 1))
    X = sp.csr_matrix(np.hstack([dup, dup]))
    b = KC.achievable_rank(X, [2], auto_blocks=False)
    assert b["achievable"] == 1 and b["per_block"] == [1]


# ---------- 定向形声检验（真实数据）----------

@pytest.mark.skipif(not HAS_DATA, reason="需要字形与拼音数据")
def test_phonetic_report_real():
    from src.semantic.form_plane import FormPlaneBuilder
    from src.semantic.phonetic import phonetic_report
    chars = ["湖", "糊", "蝴", "胡", "江", "河", "海", "清", "晴", "情", "请", "精", "静"]
    fb = FormPlaneBuilder(chars)
    F = fb.build()
    rep = phonetic_report(chars, F, fb,
                          slice(fb.dim_radical, fb.dim_radical + fb.dim_component))
    assert rep["n_components_evaluated"] > 0
    assert rep["mean_mi_initial"] > 0, "部件应携带声母信息（形声结构存在）"
    # 胡 作为部件：承载字（湖糊蝴）主读音声母应为 h，提升度 > 2
    hu = next((t for t in rep["top_components"] if t["component"] == "胡"), None)
    if hu is not None:
        assert hu["dominant_initial"] == "h" and hu["lift"] > 2.0
