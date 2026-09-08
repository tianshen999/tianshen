# -*- coding: utf-8 -*-
"""列向 IDF 加权（修订 2）：抑制高频特征维度的谱主导。

谱集中的根源是"特征跨字频率"失衡（氵 出现在数千字、罕见部件只出现几次），
行内平方根加权无效（ADR-022）。IDF：w_j = log((N+1)/(df_j+1)) + 1。
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp


def idf_weights(X: sp.csr_matrix) -> np.ndarray:
    """每列 IDF 权重（平滑）。全零列权重记 1。"""
    N = X.shape[0]
    df = np.asarray((X != 0).sum(axis=0)).ravel()
    w = np.log((N + 1.0) / (df + 1.0)) + 1.0
    w = np.where(np.isfinite(w), w, 1.0)
    return w.astype(np.float64)


def apply_idf(X: sp.csr_matrix, w: np.ndarray) -> sp.csr_matrix:
    """X @ diag(w)，然后行 L2 归一化。"""
    Y = X.multiply(w[None, :]).tocsr()
    row_norms = np.sqrt(np.asarray(Y.power(2).sum(axis=1)).ravel())
    return sp.diags(1.0 / np.maximum(row_norms, 1e-12)).dot(Y).tocsr()


def idf_transform(X: sp.csr_matrix, keep_last_col_unweighted: bool = False) -> sp.csr_matrix:
    """一步式：计算 IDF 并应用。

    keep_last_col_unweighted=True 时（形平面的笔画数值列）最后一列权重恒为 1。
    """
    w = idf_weights(X)
    if keep_last_col_unweighted and X.shape[1] > 0:
        w = w.copy()
        w[-1] = 1.0
    return apply_idf(X, w)


def merge_collinear(X: sp.csr_matrix, block_sizes: list[int] | None = None
                    ) -> tuple[sp.csr_matrix, list[int] | None]:
    """共线列合并（ADR-030 校准层）：完全同形的列合并为一维。

    block_sizes 提供时逐块合并（保持特征块结构，供结构依赖预算使用），
    返回 (合并后矩阵, 新块大小列表)；否则全局合并。
    """
    Xc = X.tocsc()
    if block_sizes is None:
        blocks = [list(range(Xc.shape[1]))]
    else:
        blocks = []
        pos = 0
        for size in block_sizes:
            blocks.append(list(range(pos, min(pos + size, Xc.shape[1]))))
            pos += size
    keep_all: list[int] = []
    new_sizes: list[int] = []
    for blk in blocks:
        seen: dict[tuple, int] = {}
        keep: list[int] = []
        for j in blk:
            col = Xc[:, j]
            pattern = tuple(col.indices)
            if pattern in seen:
                continue
            seen[pattern] = j
            keep.append(j)
        keep_all.extend(keep)
        new_sizes.append(len(keep))
    Y = X[:, keep_all]
    return Y, (new_sizes if block_sizes is not None else None)
