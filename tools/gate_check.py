# -*- coding: utf-8 -*-
"""发布闸门阈值判定（ADR-029）：读取各评测产物 JSON，逐项判定 PASS/FAIL。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "artifacts"

# 阈值定义（唯一事实源；改动需修订 ADR-029）
THRESHOLDS = {
    "independence_r2": 0.3,        # 深义层被形⊕音解释 R² 上限
    "semantic_s2_hit": 0.19,       # 义近检索 S2 Hit@10 下限
    "polyphone_accuracy": 0.999,   # 多音消歧准确率下限
}

RESULTS: list[tuple[str, bool, str]] = []


def check(cond: bool, name: str, detail: str) -> None:
    RESULTS.append((name, bool(cond), detail))


def load_certificates() -> list[dict]:
    """ADR-031：自动发现 artifacts/semantic/ 下全部 *_certificates.json。
    新板块按命名约定落盘证书即被闸门自动纳入判定，无需改动本文件。"""
    certs: list[dict] = []
    for f in sorted((A / "semantic").glob("*_certificates.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            certs.extend(data if isinstance(data, list) else [data])
        except (json.JSONDecodeError, OSError) as e:
            check(False, f"证书文件解析·{f.name}", str(e))
    return certs


def main() -> int:
    certs = load_certificates()

    # 1. 独立性检验（含 independence_vs_FP 的深义层证书；未来板块同构接入）
    cert_k = next((c for c in certs if c.get("independence_vs_FP")), None)
    if cert_k and cert_k.get("independence_vs_FP"):
        r2 = cert_k["independence_vs_FP"]["r2_F_explains_P"]
        check(r2 < THRESHOLDS["independence_r2"], "独立性检验",
              f"深义层被形⊕音解释 R² = {r2}（阈 {THRESHOLDS['independence_r2']}）")
    else:
        check(False, "独立性检验", "证书缺失 independence_vs_FP")

    # 2. 秩判据（全部平面）——优先用结构依赖预算（ADR-030/031），旧判据兜底
    for c in certs:
        if "achievable_criterion" in c:
            check(c["achievable_criterion"], f"结构预算·{c['plane']}",
                  f"秩/可达 = {c.get('rank_vs_achievable')}（阈 0.95）")
        elif "rank_criterion" in c:
            check(c["rank_criterion"], f"秩判据·{c['plane']}",
                  f"实测秩 {c['rank_measured']}/{c['dim_nominal']}")

    # 3. 义近检索
    sb = json.loads((A / "semantic" / "semantic_bench.json").read_text(encoding="utf-8"))
    s2 = next((r for r in sb["results"] if r[0] == "意平面 S2"), None)
    if s2:
        check(s2[1] >= THRESHOLDS["semantic_s2_hit"], "义近检索",
              f"S2 Hit@10 = {s2[1]}（阈 {THRESHOLDS['semantic_s2_hit']}）")
    else:
        check(False, "义近检索", "semantic_bench 缺 S2 结果")

    # 4. 多音消歧
    pp = json.loads((A / "polyphone_results.json").read_text(encoding="utf-8"))
    check(pp["ours_accuracy"] >= THRESHOLDS["polyphone_accuracy"], "多音消歧",
          f"准确率 {pp['ours_accuracy']:.1%}（阈 {THRESHOLDS['polyphone_accuracy']:.1%}）")

    # 输出
    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    for name, ok, detail in RESULTS:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    print(f"\n闸门阈值判定: {len(RESULTS) - n_fail}/{len(RESULTS)} 通过")
    return 1 if n_fail else 0

if __name__ == "__main__":
    sys.exit(main())
