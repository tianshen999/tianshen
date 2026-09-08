# -*- coding: utf-8 -*-
"""定向形声检验（修订 2）：部件 → 读音 的牵引力（互信息与提升度）。

不依赖"精确同音"的过严判据；直接测量：包含部件 p 的字，其主读音的
声母/韵母分布相对全体基线偏移多少——形声结构的量化证据。
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import scipy.sparse as sp

from src.pinyin.syllable import FINAL_TO_ZHUYIN, INITIALS
from src.pinyin.unihan import readings

FINALS = sorted(set(FINAL_TO_ZHUYIN.keys()) - {"-i"}) + ["-i"]  # 与 sound_plane 一致


def _primary(ch: str) -> tuple[str, str] | None:
    r = readings(ch)
    if not r:
        return None
    return (r[0].initial, r[0].final)


def _mutual_info(has: np.ndarray, labels: list[int], n_classes: int) -> float:
    """互信息 I(has ; label)。has: 0/1 数组；labels: 类别序号。"""
    n = len(has)
    p1 = has.mean()
    cnt = np.bincount(labels, minlength=n_classes) / n
    mi = 0.0
    for h in (0, 1):
        idx = np.where(has == h)[0]
        if len(idx) == 0:
            continue
        ph = (len(idx) / n)
        sub = np.bincount([labels[i] for i in idx], minlength=n_classes) / n
        for c in range(n_classes):
            if sub[c] > 0:
                mi += sub[c] * np.log((sub[c] / max(ph, 1e-12)) / max(cnt[c], 1e-12))
    return float(mi)


def phonetic_report(chars: list[str], F: sp.csr_matrix, builder,
                    component_cols: slice, top_k: int = 15) -> dict:
    """部件 → 主读音 定向检验报告。

    返回：{top_components: [...], mean_mi_initial, mean_mi_final,
          baseline 与承载字分布示例}。
    """
    n = len(chars)
    labels = {}
    ini_idx = {ini: i for i, ini in enumerate(INITIALS)}
    fin_idx = {f: i for i, f in enumerate(FINALS)}
    prim = [_primary(c) for c in chars]
    ini_labels = np.array([ini_idx.get(p[0], len(INITIALS)) if p else len(INITIALS)
                           for p in prim])
    fin_labels = np.array([fin_idx.get(p[1], len(FINALS)) if p else len(FINALS)
                           for p in prim])
    base_ini = np.bincount(ini_labels, minlength=len(INITIALS) + 1) / n
    base_fin = np.bincount(fin_labels, minlength=len(FINALS) + 1) / n

    Fd = F.tocsc()
    mi_ini_list, mi_fin_list = [], []
    rows_info = []
    for j in range(component_cols.start, component_cols.stop):
        col = Fd[:, j]
        idx = np.asarray(col.nonzero()[0])
        if len(idx) < 3:
            continue
        has = np.zeros(n, dtype=np.int8)
        has[idx] = 1
        mi_i = _mutual_info(has, ini_labels, len(INITIALS) + 1)
        mi_f = _mutual_info(has, fin_labels, len(FINALS) + 1)
        mi_ini_list.append(mi_i)
        mi_fin_list.append(mi_f)
        # 提升度（承载字中该声母占比 / 基线占比）
        sub = np.bincount(ini_labels[idx], minlength=len(INITIALS) + 1) / len(idx)
        lift = sub / np.maximum(base_ini, 1e-9)
        best_c = int(np.argmax(lift))
        comp = builder.components[j - component_cols.start]
        rows_info.append({
            "component": comp,
            "n_chars": len(idx),
            "dominant_initial": INITIALS[best_c] if best_c < len(INITIALS) else "零/未知",
            "lift": round(float(lift[best_c]), 2),
            "examples": [chars[i] for i in idx[:5]],
            "mi_initial": round(mi_i, 4),
            "mi_final": round(mi_f, 4),
        })

    rows_info.sort(key=lambda r: -r["lift"])
    return {
        "n_components_evaluated": len(rows_info),
        "mean_mi_initial": round(float(np.mean(mi_ini_list)), 4),
        "mean_mi_final": round(float(np.mean(mi_fin_list)), 4),
        "top_components": rows_info[:top_k],
    }
