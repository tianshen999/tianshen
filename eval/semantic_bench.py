# -*- coding: utf-8 -*-
"""义近检索评测基准：人工策管探针集（开源）在四个子空间上的命中率对比。

回答一个问题：义近检索必须靠意平面（S/深义层）——形平面和音平面做不到。
指标：Hit@10（期望词出现在前 10 名）与 MRR（平均倒数排名）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import scipy.sparse as sp  # noqa: E402

from src.semantic import weighting as WT  # noqa: E402

# 人工策管探针集：探针字 → 期望近义/强关联字（开源，欢迎社区扩充）
PROBES: dict[str, list[str]] = {
    "水": ["河", "江", "湖", "海", "泉", "溪"],
    "火": ["焰", "炎", "焚", "燃", "烧"],
    "心": ["情", "意", "思", "想", "念"],
    "木": ["树", "林", "森", "枝", "根"],
    "金": ["银", "铜", "铁", "钢", "锡"],
    "手": ["掌", "指", "拳", "腕", "握"],
    "山": ["峰", "岭", "岳", "丘", "峦"],
    "言": ["语", "话", "说", "讲", "谈"],
    "日": ["阳", "晴", "昼", "晨", "曦"],
    "月": ["夜", "阴", "朔", "望", "朗"],
    "大": ["巨", "宏", "伟", "硕", "浩"],
    "小": ["微", "细", "纤", "渺", "碎"],
    "快": ["速", "疾", "迅", "捷", "猛"],
    "慢": ["缓", "徐", "迟", "悠", "怠"],
    "好": ["善", "良", "优", "佳", "美"],
    "坏": ["恶", "劣", "歹", "凶", "邪"],
    "哭": ["泣", "啼", "嚎", "号", "咽"],
    "笑": ["乐", "欣", "喜", "欢", "悦"],
    "红": ["赤", "朱", "丹", "绛", "绯"],
    "白": ["素", "皓", "皑", "皎", "皙"],
    "黑": ["墨", "乌", "玄", "黛", "黢"],
    "冷": ["寒", "凉", "冻", "冰", "冽"],
    "热": ["炎", "暑", "烫", "暖", "炽"],
    "美": ["丽", "艳", "娇", "妍", "秀"],
    "丑": ["陋", "鄙", "狞", "媸"],
    "老": ["耄", "耋", "苍", "暮", "衰"],
    "幼": ["稚", "嫩", "婴", "童", "雏"],
    "死": ["亡", "殁", "逝", "卒", "薨"],
    "生": ["活", "存", "诞", "育", "萌"],
    "走": ["行", "步", "跑", "奔", "赴"],
    "看": ["望", "观", "瞧", "视", "睹"],
    "听": ["闻", "聆", "倾", "聪"],
    "说": ["道", "言", "讲", "述", "诉"],
    "拿": ["取", "持", "握", "执", "携"],
    "想": ["思", "念", "虑", "忖", "忆"],
    "爱": ["恋", "慕", "喜", "怜", "惜"],
}


def load_char_set() -> list[str]:
    """核心字符集（简体+通用；ADR-027）。"""
    from src.semantic.core_sets import core_chars
    return core_chars()


def _load(name: str) -> sp.csr_matrix:
    return sp.load_npz(str(ROOT / "artifacts" / "semantic" / f"{name}.npz"))


def retrieve(X: sp.csr_matrix, chars: list[str], probe: str, top_k: int = 10) -> list[str]:
    idx = {c: i for i, c in enumerate(chars)}
    if probe not in idx:
        return []
    v = np.asarray(X[idx[probe]].toarray()).ravel()
    if np.linalg.norm(v) < 1e-9:
        return []  # 探针本身无释义数据
    sims = np.asarray(X @ v).ravel()
    order = np.argsort(-sims)
    out = []
    for j in order:
        if chars[j] == probe:
            continue
        row_norm = np.sqrt(float(X[j].power(2).sum()))
        if row_norm < 1e-9:
            continue  # 跳过无数据候选（零向量）
        out.append(chars[j])
        if len(out) >= top_k:
            break
    return out


def score(X: sp.csr_matrix, chars: list[str], top_k: int = 10) -> dict:
    hits = 0
    mrr_sum = 0.0
    n = 0
    adj_hits = 0
    adj_mrr_sum = 0.0
    adj_n = 0
    details = []
    cov_total = cov_hit = 0
    idx = {c: i for i, c in enumerate(chars)}
    for probe, expected in PROBES.items():
        nn = retrieve(X, chars, probe, top_k)
        found = [i + 1 for i, c in enumerate(nn) if c in expected]
        hit = len(found) > 0
        mrr_sum += 1.0 / found[0] if found else 0.0
        hits += hit
        n += 1
        # 期望词数据覆盖率（诚实的命中天花板）
        covered_expected = []
        for e in expected:
            if e in idx:
                cov_total += 1
                if np.sqrt(float(X[idx[e]].power(2).sum())) > 1e-9:
                    cov_hit += 1
                    covered_expected.append(e)
        if covered_expected:  # 覆盖率调整：只算"有可命中目标"的探针
            adj_found = [i + 1 for i, c in enumerate(nn) if c in covered_expected]
            adj_hits += len(adj_found) > 0
            adj_mrr_sum += 1.0 / adj_found[0] if adj_found else 0.0
            adj_n += 1
        details.append({"probe": probe, "expected": expected, "found_in_top10": nn[:10],
                        "ranks": found})
    return {"hit_at_10": round(hits / max(n, 1), 3), "mrr": round(mrr_sum / max(n, 1), 3),
            "hit_at_10_adjusted": round(adj_hits / max(adj_n, 1), 3),
            "mrr_adjusted": round(adj_mrr_sum / max(adj_n, 1), 3),
            "n": n, "expected_coverage": round(cov_hit / max(cov_total, 1), 3),
            "details": details}


# 人工策管反义对（开源）：验证"反义词同域"假设——反义词共享语义域，
# 在意平面中应相近（域），但方向（极性）v0.3 不建模（诚实记录，v0.4 待办）
ANTONYMS: list[tuple[str, str]] = [
    ("大", "小"), ("黑", "白"), ("冷", "热"), ("好", "坏"),
    ("快", "慢"), ("美", "丑"), ("生", "死"), ("老", "幼"),
    ("新", "旧"), ("高", "低"), ("长", "短"), ("强", "弱"),
    ("富", "穷"), ("深", "浅"), ("明", "暗"), ("真", "假"),
]


def antonym_hit(X: sp.csr_matrix, chars: list[str], top_k: int = 10) -> dict:
    """反义同域检验：对 (A, B)，B 是否出现在 A 的 top-k 义近邻居中。"""
    hits = 0
    n = 0
    pairs = []
    for a, b in ANTONYMS:
        nn = retrieve(X, chars, a, top_k)
        if nn:
            hit = b in nn
            hits += hit
            n += 1
            pairs.append((a, b, hit, nn[:5]))
    return {"antonym_domain_hit": round(hits / max(n, 1), 3), "n": n, "pairs": pairs}


def main() -> int:
    chars = load_char_set()
    F = WT.idf_transform(_load("form_plane"), keep_last_col_unweighted=True)
    P = WT.idf_transform(_load("sound_plane"))
    S2 = sp.hstack([
        _load("meaning_plane") if False else WT.idf_transform(_load("meaning_plane")),
        _load("meaning_keywords"),
    ]).tocsr()
    K = _load("meaning_keywords")

    rows = []
    for name, X in [("形平面 F", F), ("音平面 P", P), ("意·义素层 S", S2[:, :432]),
                    ("意·深义层 K", K), ("意平面 S2", S2)]:
        s = score(X, chars)
        rows.append((name, s["hit_at_10"], s["mrr"], s["hit_at_10_adjusted"], s["mrr_adjusted"]))
        print(f"{name:<14} Hit@10 = {s['hit_at_10']:.3f}（覆盖率调整 {s['hit_at_10_adjusted']:.3f}）"
              f"  MRR = {s['mrr']:.3f}  期望词数据覆盖 = {s['expected_coverage']:.1%}")

    # 反义同域检验（诚实假设：反义词共享语义域）
    for name, X in [("意·深义层 K", K), ("意平面 S2", S2)]:
        a = antonym_hit(X, chars)
        print(f"{name:<14} 反义同域命中 = {a['antonym_domain_hit']:.3f}（16 对，"
              f"验证'反义同域'：反义词在意空间中相近；极性方向 v0.4 待办）")

    out = ROOT / "artifacts" / "semantic" / "semantic_bench.json"
    out.write_text(json.dumps({"results": rows, "probes": PROBES, "antonyms": ANTONYMS},
                              ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"\n结果已保存: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
