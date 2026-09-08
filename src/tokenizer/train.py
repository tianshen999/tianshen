# -*- coding: utf-8 -*-
"""中文原生分词器训练。

实验组设计（docs/02 §3）：
- 组 A：纯中文语料训练，Unigram，GB2312 常用汉字强制原子入表
- 组 B：组 A 语料 + 少量英文样本（最小英文应急通道）
- 组 C：纯整字词表（对照组：每个字符一个 token，无任何合并）

技术要点：
- SentencePiece Unigram 模式以 Unicode 字符为基本单位，token 永不拆碎汉字
- user_defined_symbols 强制 GB2312 常用字整字入表（汉字原子性的确定性保证）
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import sentencepiece as spm  # noqa: E402

from src.tokenizer.radicals import gb2312_chars  # noqa: E402

SPECIAL_SYMBOLS = ["<unk>", "<s>", "</s>", "<pad>"]


def train_unigram(
    input_files: list[str],
    model_prefix: str,
    vocab_size: int = 32000,
    force_atomic_chars: list[str] | None = None,
    extra_symbols: list[str] | None = None,
    max_piece_length: int = 16,
    sentence_limit: int = 5_000_000,
) -> str:
    """训练 Unigram 分词器。返回模型路径（model_prefix + '.model'）。

    注意：sentence_limit 是 SentencePiece 实际读取的句数上限。
    实测本机（低配 CPU）32k 词表 × 1000 万句需约 1.5 小时；
    词表统计 500 万句（约 2 亿字符）已足够收敛，可显著提速。
    """
    Path(model_prefix).parent.mkdir(parents=True, exist_ok=True)
    symbols = SPECIAL_SYMBOLS + (extra_symbols or [])
    print(f"训练 {model_prefix}: vocab={vocab_size}, 强制原子汉字={len(force_atomic_chars or [])}")
    spm.SentencePieceTrainer.train(
        input=input_files,
        model_prefix=model_prefix,
        model_type="unigram",
        vocab_size=vocab_size,
        # 原子性保证：character_coverage=1.0 → 语料中出现的每一个字符都作为
        # 整字 piece 入表（Unigram 模式下 piece 永不拆碎字符，天然满足汉字原子性）。
        # 教训（ADR-011）：不要用 user_defined_symbols 强制常用字——
        # SentencePiece 会禁止学习任何"包含"user-defined symbol 的片段，
        # 等于封死了所有多字词。
        character_coverage=1.0,
        # 恒等归一化：不折叠全角/半角、不改变任何字符——中文原生的"保真"原则。
        # 同时也绕开预编译字符映射表在非 ASCII 路径下的加载问题。
        normalization_rule_name="identity",
        # 注意：必须是符号列表（逐元素）；<unk> 等控制符号是保留字，不得重复定义。
        # 默认不再强制注入（见 character_coverage 说明）；仅实验时可选。
        user_defined_symbols=(force_atomic_chars or []),
        max_sentencepiece_length=max_piece_length,
        max_sentence_length=1_000_000,
        num_threads=max(1, (os.cpu_count() or 2) - 1),
        unk_id=0, bos_id=1, eos_id=2, pad_id=3,
        hard_vocab_limit=False,
        input_sentence_size=sentence_limit,
        shuffle_input_sentence=True,
        seed_sentencepiece_size=1_000_000,
    )
    return model_prefix + ".model"


def build_char_vocab(input_files: list[str], output_path: str) -> dict:
    """组 C：纯整字词表。每个出现过的字符一个 token。返回统计。"""
    chars: set[str] = set()
    for fpath in input_files:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as fin:
            for line in fin:
                chars.update(line.rstrip("\n"))
    vocab = SPECIAL_SYMBOLS + sorted(chars)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fout:
        for i, tok in enumerate(vocab):
            fout.write(f"{tok}\t{i}\n")
    return {"tokens": len(vocab), "chars": len(chars)}


def inspect_model(model_path: str) -> dict:
    """训练后自检：统计词表构成（整字 / 多字词 / 非中文）。

    注意：SentencePiece 的词首 token 带 ▁ 前缀（空格占位符），
    统计时先剥离 ▁ 再判断是否纯中文。
    """
    sp = spm.SentencePieceProcessor(model_file=model_path)
    n_cjk_char = n_cjk_word = n_other = 0
    for piece in sp.id_to_piece(range(sp.get_piece_size())):
        core = piece.lstrip("\u2581")
        if not core:
            n_other += 1
            continue
        cjk = sum(1 for c in core if "\u3400" <= c <= "\u9fff" or "\u4e00" <= c <= "\u9fff")
        if cjk == len(core) == 1:
            n_cjk_char += 1
        elif cjk == len(core) and cjk >= 2:
            n_cjk_word += 1
        else:
            n_other += 1
    return {"total": sp.get_piece_size(), "单字": n_cjk_char, "多字词": n_cjk_word, "其他": n_other}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="训练中文原生分词器（A/B/C 三组）")
    ap.add_argument("--group", choices=["a", "b", "c"], default="a")
    ap.add_argument("--input", action="append", required=True, help="训练语料（可多次指定）")
    ap.add_argument("--extra-inputs", action="append", default=[], help="组 B 的英文等附加语料")
    ap.add_argument("--vocab-size", type=int, default=32000)
    ap.add_argument("--sentence-limit", type=int, default=5_000_000, help="训练读取的句数上限")
    ap.add_argument("--prefix", default="artifacts/group_a", help="模型前缀")
    ap.add_argument("--force-atomic", action="store_true",
                    help="【实验用】强制 GB2312 常用字入表（会抑制多字词学习，见 ADR-011）")
    args = ap.parse_args(argv)

    if args.group == "c":
        stats = build_char_vocab(args.input + args.extra_inputs, args.prefix + ".vocab")
        print(f"组 C 完成：{stats}")
        return 0

    extra_symbols = None
    if args.group == "b":
        extra_symbols = ["<en>"]
    model_path = train_unigram(
        input_files=args.input + args.extra_inputs,
        model_prefix=args.prefix,
        vocab_size=args.vocab_size,
        force_atomic_chars=gb2312_chars() if args.force_atomic else None,
        extra_symbols=extra_symbols,
        sentence_limit=args.sentence_limit,
    )
    print(f"模型已保存：{model_path}")
    print("词表构成自检：", inspect_model(model_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
