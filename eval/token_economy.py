# -*- coding: utf-8 -*-
"""Token 经济学评测：分词消耗 + 形/音信息注入成本 + 折算费用。

核心问题：要让一个模型"知道"每个字/词的读音（音信息），
- 天神：词表自带（外部查表），**注入 token = 0**；
- 其他模型：必须把拼音作为文本注入上下文 → 额外 token。

数据：eval 样本 + 维基语料抽样 2000 行（固定种子）。
价格：公开价约数（2026 初，仅供量级参考，注明估算）。
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.benchmark import load_reference_tokenizers  # noqa: E402
from src.pinyin.unihan import primary  # noqa: E402
from src.pinyin.syllable import parse  # noqa: E402
from src.tokenizer.tokenizer import load_tokenizer  # noqa: E402

# 公开价约数（元/百万 token，输入价；2026 初估算）
PRICE_CNY_PER_1M = {
    "天神（开源，按 DeepSeek 价估算）": 2.0,
    "gpt-4o (o200k_base)": 2.50 * 7.2,   # USD → CNY（约）
    "gpt-3.5 (cl100k_base)": 0.5 * 7.2,
    "Qwen2.5-7B": 0.8,
    "DeepSeek-V3": 2.0,
    "Yi-6B": 1.0,
    "ChatGLM3-6B": 0.5,
}


def load_corpus() -> str:
    texts = []
    for f in sorted((ROOT / "eval" / "samples").glob("*.txt")):
        texts.append(f.read_text(encoding="utf-8").strip())
    wiki = ROOT / "data" / "corpus_clean" / "wiki_all.txt"
    if wiki.exists():
        rng = random.Random(20260901)
        with open(wiki, encoding="utf-8") as fh:
            pool = [next(fh) for _ in range(200000)]
        sample = rng.sample(pool, 2000)
        texts.append("".join(sample))
    return "\n".join(texts)


def char_pinyin(text: str) -> str:
    """逐字主读音拼音串（调号形式）。"""
    out = []
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            p = primary(ch, "marked")
            if p:
                out.append(p)
    return " ".join(out)


def char_zhuyin(text: str) -> str:
    out = []
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            p = primary(ch, "numbered")
            if p:
                out.append(parse(p).zhuyin())
    return " ".join(out)


def main() -> int:
    corpus = load_corpus()
    n_chars = sum(1 for c in corpus if "\u4e00" <= c <= "\u9fff")
    print(f"评测语料：{len(corpus)} 字符（汉字 {n_chars}）")

    tokenizers: dict[str, object] = {
        "天神·64k": load_tokenizer("artifacts/group_a_64k"),
    }
    for adapter in load_reference_tokenizers(verbose=False):
        tokenizers[adapter.name] = adapter

    pinyin_str = char_pinyin(corpus)
    zhuyin_str = char_zhuyin(corpus)

    rows = []
    for name, tok in tokenizers.items():
        base = len(tok.pieces(corpus))
        pin = len(tok.pieces(pinyin_str))
        zhu = len(tok.pieces(zhuyin_str))
        rows.append({
            "tokenizer": name,
            "base_tokens": base,
            "tokens_per_char": round(base / n_chars, 3),
            "pinyin_injection_tokens": pin,
            "zhuyin_injection_tokens": zhu,
            "total_with_pinyin": base + pin,
        })

    # 天神：音信息零注入（表外查表）
    ours = next(r for r in rows if r["tokenizer"] == "天神·64k")
    ours["pinyin_injection_tokens"] = 0
    ours["total_with_pinyin"] = ours["base_tokens"]
    ours["note"] = "音/形/意信息由词表外部查表提供，注入 token = 0"

    # 折算：处理 100 万汉字的输入成本（元）
    for r in rows:
        scale = 1_000_000 / n_chars
        price = PRICE_CNY_PER_1M.get(r["tokenizer"], 2.0)
        r["cost_1M_chars_base"] = round(r["base_tokens"] * scale / 1e6 * price, 2)
        r["cost_1M_chars_with_pinyin"] = round(r["total_with_pinyin"] * scale / 1e6 * price, 2)

    print(f"\n{'分词器':<22}{'token/字':>9}{'+拼音后/字':>11}{'百万字纯文本¥':>12}{'百万字+音¥':>11}")
    for r in sorted(rows, key=lambda x: x["tokens_per_char"]):
        print(f"{r['tokenizer']:<22}{r['tokens_per_char']:>9}{r['total_with_pinyin']/n_chars:>11.3f}"
              f"{r['cost_1M_chars_base']:>12}{r['cost_1M_chars_with_pinyin']:>11}")
        if r.get("note"):
            print(f"  ↳ {r['note']}")

    out = ROOT / "artifacts" / "token_economy.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"n_chars": n_chars, "rows": rows,
                               "price_notes": "公开价约数，2026 初估算，仅量级参考"},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n结果已保存: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
