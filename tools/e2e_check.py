# -*- coding: utf-8 -*-
"""端到端贯通验证（形 → 音 → 意 一体 + 挂件路由）。

把"整个体系是一个能跑的整体"变成可执行断言：一条真实文本走完
分词(形) → 注音(音) → 三维向量与检索(意) → 四个挂件路由（繁/拉丁/注音/发声），
任一环节断链即 exit 非 0。已接入发布闸门（每次大版本自动执行）。

用法：
    tools/python/python.exe tools/e2e_check.py
（分词器加载必须用 ASCII 相对路径——SentencePiece C++ 不支持中文路径。）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import scipy.sparse as sp  # noqa: E402

FAILS: list[str] = []
HANS = lambda s: [c for c in s if "\u4e00" <= c <= "\u9fff"]  # noqa: E731


def check(cond: bool, msg: str) -> None:
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAILS.append(msg)


def load_plane(name: str) -> sp.csr_matrix:
    return sp.load_npz(str(ROOT / "artifacts" / "semantic" / f"{name}.npz"))


def cos(X: sp.csr_matrix, chars: list[str], a: str, b: str) -> float:
    idx = {c: i for i, c in enumerate(chars)}
    va = np.asarray(X[idx[a]].toarray()).ravel()
    vb = np.asarray(X[idx[b]].toarray()).ravel()
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(va @ vb / (na * nb))


def main() -> int:
    print("=" * 66)
    print("天神 端到端贯通验证：形 → 音 → 意（一条文本走完全程）")
    print("=" * 66)

    # ================= L1 形：分词器 =================
    print("\n【形】分词器（核心 64k + 拉丁挂件，默认挂件关闭）")
    from src.tokenizer.tokenizer import CompositeTokenizer
    tok = CompositeTokenizer("artifacts/group_a_64k", "artifacts/plug_en")
    text = "人工智能改变世界，银行与音乐同行。language model 是语言模型。"
    pieces = tok.pieces(text)
    print("  分词:", " | ".join(p.replace("\u2581", "␣") for p in pieces))
    # 恒等归一化下，空格以 ▁ 表示；还原闭环按"字符级无损"判定（空格归一）
    rt = "".join(p.replace("\u2581", "") for p in pieces).replace(" ", "")
    check(rt == text.replace(" ", ""), "形→还原闭环：字符级无损（空格以 ▁ 表示）")

    # 拉丁挂件路由：开关不影响中文，只影响 ASCII 片段
    cn_on = tok.pieces("人工智能改变世界")
    tok.enable_plug(True)
    pieces_on = tok.pieces("language model")
    ascii_on = [p.replace("\u2581", "") for p in pieces_on]
    tok.enable_plug(False)
    pieces_off = tok.pieces("language model")
    ascii_off = [p.replace("\u2581", "") for p in pieces_off]
    check(tok.pieces("人工智能改变世界") == cn_on, "挂件开关不影响中文路由（中文永远走核心）")
    check(ascii_on == ["language", "model"] and "language" not in ascii_off,
          f"拉丁挂件生效：启用整词切分 {ascii_on}，禁用核心碎片 {ascii_off}")

    # ================= L2 音：注音 =================
    print("\n【音】词级读音（多音消歧）+ 注音挂件")
    from src.pinyin.annotator import PinyinAnnotator
    ann = PinyinAnnotator(str(ROOT / "artifacts" / "pinyin" / "group_a_64k_pinyin.json"))
    check(ann.numbered("银行") == "yin2 hang2", f"银行 → {ann.numbered('银行')}（hang2 不是 xing2）")
    check(ann.numbered("行走") == "xing2 zou3", f"行走 → {ann.numbered('行走')}（xing2 不是 hang2）")
    check(ann.numbered("音乐") == "yin1 yue4", f"音乐 → {ann.numbered('音乐')}")
    check(ann.numbered("重庆") == "chong2 qing4", f"重庆 → {ann.numbered('重庆')}（多音地名）")

    # 音阶段吃"形"的输出：对切分片逐片注音，覆盖全部汉字片
    print("  对【形】的切分结果逐片注音：")
    miss = []
    for p in pieces:
        w = p.replace("\u2581", "")
        if HANS(w):
            py = ann.pinyin(w)
            if not py:
                miss.append(w)
            print(f"    {w:<6} → {py}")
    check(not miss, f"形→音贯通：全部汉字片均有读音（缺：{miss}）")

    check(ann.zhuyin_render("银行") is None, "注音挂件默认关闭（核心不含注音）")
    ann.zhuyin.enable(True)
    zy = ann.zhuyin_render("银行")
    check(bool(zy) and "ㄏㄤˊ" in zy, f"注音挂件开启：银行 → {zy}")
    ann.zhuyin.enable(False)

    # ================= L3 意：三平面 + 检索 =================
    print("\n【意】三平面加载 + 键一致性 + 三维检索")
    from src.semantic.core_sets import core_chars, core_words, trad_index
    chars = core_chars()
    plane_keys_ok = True
    for name in ["form_plane", "sound_plane", "meaning_plane", "meaning_keywords"]:
        meta = json.loads((ROOT / "artifacts" / "semantic" / f"{name}.meta.json")
                          .read_text(encoding="utf-8"))
        ok = meta["keys"] == chars
        plane_keys_ok = plane_keys_ok and ok
        print(f"    {name}: {len(meta['keys'])} 键 vs 核心集 {len(chars)} {'✓' if ok else '✗'}")
    check(plane_keys_ok, "字级四平面键与核心字符集（12,468）完全一致")

    from src.semantic import weighting as WT
    from src.semantic import meaning_plane as MP
    from eval.semantic_bench import retrieve
    F = WT.idf_transform(load_plane("form_plane"), keep_last_col_unweighted=True)
    P = WT.idf_transform(load_plane("sound_plane"))
    # 与 certify_meaning 完全一致的 S2：S 逐块共线合并（ADR-030）→ IDF（末 4 列不降权）+ K
    S_orig = load_plane("meaning_plane")
    S_raw, _ = WT.merge_collinear(
        S_orig, [MP.DIM_SEMEME, MP.DIM_COMPONENT_SEMEME, MP.DIM_DEF_FEATURES])
    w = WT.idf_weights(S_raw)
    w[-MP.DIM_DEF_FEATURES:] = 1.0
    S2 = sp.hstack([WT.apply_idf(S_raw, w), load_plane("meaning_keywords")]).tocsr()

    c_lake_fox = cos(P, chars, "湖", "蝴")
    check(abs(c_lake_fox - 1.0) < 1e-9, f"音平面：湖/蝴 同音 hú 向量重合（cos={c_lake_fox:.4f}）")
    c_ff = cos(F, chars, "湖", "河")
    check(c_ff > 0.1, f"形平面：湖/河 共享水部+氵（cos={c_ff:.4f}）")
    c_ss = cos(S2, chars, "湖", "河")
    check(c_ss > 0.0, f"意平面：湖/河 水类义素相近（cos={c_ss:.4f}）")

    print(f"\n  三维检索演示（{'探针':<4}{'形近 F':<16}{'音近 P':<16}{'义近 S2':<16}）")
    for q in ["水", "火", "心", "山", "爱", "湖"]:
        f = retrieve(F, chars, q, 4)
        p = retrieve(P, chars, q, 4)
        s = retrieve(S2, chars, q, 4)
        print(f"  {q:<4}{' '.join(f):<16}{' '.join(p):<16}{' '.join(s):<16}")
    check(all(retrieve(F, chars, q, 4) and retrieve(P, chars, q, 4) and retrieve(S2, chars, q, 4)
              for q in ["水", "火", "心", "山", "爱", "湖"]), "六探针三平面检索全部有返回")

    # 三维组装 W3 = F ⊕ P ⊕ S2（与证书维度核对）
    W3 = sp.hstack([F, P, S2]).tocsr()
    mc = json.loads((ROOT / "artifacts" / "semantic" / "meaning_certificates.json")
                    .read_text(encoding="utf-8"))
    w3_cert = next(c for c in mc if c["plane"].startswith("W3"))
    check(W3.shape[1] == w3_cert["dim_nominal"],
          f"W3 组装维度 {W3.shape[1]} == 证书 {w3_cert['dim_nominal']}（形⊕音⊕意 一体）")

    # ================= 词级平面 =================
    print("\n【词级】三平面（核心词 31,466）")
    words = core_words()
    wok = True
    for name in ["word_form_plane", "word_sound_plane", "word_meaning_plane"]:
        meta = json.loads((ROOT / "artifacts" / "semantic" / f"{name}.meta.json")
                          .read_text(encoding="utf-8"))
        ok = meta["keys"] == words
        wok = wok and ok
        print(f"    {name}: {len(meta['keys'])} 键 vs 核心词集 {len(words)} {'✓' if ok else '✗'}")
    check(wok, "词级三平面键与核心词集（31,466）完全一致")
    WM = load_plane("word_meaning_plane")
    widx = {w: i for i, w in enumerate(words)}
    v_bank = np.asarray(WM[widx["银行"]].toarray()).ravel()
    check(np.linalg.norm(v_bank) > 0, "词级意向量：银行 非零（有中文释义）")

    # ================= 挂件：繁体路由 =================
    print("\n【挂件】繁体（繁→简路由，简体核心不受污染）")
    from src.semantic.script_tag import to_simplified
    check(to_simplified("銀行") == "银行", f"銀行 → {to_simplified('銀行')}")
    check(trad_index()["愛"] == "爱" and "愛" not in set(chars),
          "繁体挂件：愛 在挂件索引内、不在核心集内")

    # ================= 挂件：发声（需联网，可选） =================
    print("\n【挂件】发声（可选，需联网）")
    try:
        ann.voice.enable(True)
        out = str(ROOT / ".tmp" / "e2e_tianshen.mp3")
        ok = ann.speak("天神", out)
        print(f"  {'✓' if ok else '✗'} 合成\"天神\" → {out if ok else '失败'}")
    except Exception as e:  # noqa: BLE001
        print(f"  - 发声挂件跳过（需联网）：{type(e).__name__}")
    ann.voice.enable(False)

    # ================= 汇总 =================
    print("\n" + "=" * 66)
    if FAILS:
        print(f"端到端贯通验证：FAIL（断链 {len(FAILS)} 处）")
        for f in FAILS:
            print("  -", f)
        return 1
    print("端到端贯通验证：PASS —— 形、音、意是一条流水线上的整体 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
