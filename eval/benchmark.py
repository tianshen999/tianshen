# -*- coding: utf-8 -*-
"""对比评测主脚本：我们的分词器 vs 主流词表，输出 JSON 供报告生成。

对比对象：
- 英文中心派：GPT-4o(o200k) / GPT-3.5(cl100k) / LLaMA-3
- 中文优先派：Qwen2.5 / DeepSeek-V3 / ChatGLM3 / Yi
- Claude 无公开分词器，跳过并记录
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.metrics import evaluate_text  # noqa: E402
from src.tokenizer.tokenizer import load_tokenizer  # noqa: E402


class PiecesAdapter:
    """统一第三方分词器到 pieces(text) 接口。"""
    def __init__(self, name: str, fn, vocab_size: int = 0):
        self.name = name
        self._fn = fn
        self.vocab_size = vocab_size

    def pieces(self, text: str) -> list[str]:
        return self._fn(text)


def load_reference_tokenizers(verbose: bool = True) -> list[PiecesAdapter]:
    """加载可用的第三方词表；不可用的静默跳过（记录原因）。"""
    adapters: list[PiecesAdapter] = []

    def try_add(name: str, loader):
        try:
            fn, vocab_size = loader()
            adapters.append(PiecesAdapter(name, fn, vocab_size))
            if verbose:
                print(f"  ✓ {name}")
        except Exception as e:
            if verbose:
                print(f"  ✗ {name}: {type(e).__name__}: {e}")

    try:
        import tiktoken
        for label, enc_name in [("gpt-4o (o200k_base)", "o200k_base"),
                                ("gpt-3.5 (cl100k_base)", "cl100k_base")]:
            enc = tiktoken.get_encoding(enc_name)

            def make(_enc=enc):
                def pieces(text: str) -> list[str]:
                    return [b.decode("utf-8", "ignore")
                            for b in _enc.decode_tokens_bytes(_enc.encode(text))]
                return pieces, _enc.n_vocab

            try_add(label, make)
    except ImportError:
        pass

    # 开源模型官方词表：直接下载 tokenizer 文件（不依赖 transformers/torch）
    REF_TOKENIZERS = {
        "Qwen2.5-7B": ("tokenizer.json",
                        "https://huggingface.co/Qwen/Qwen2.5-7B/resolve/main/tokenizer.json"),
        "DeepSeek-V3": ("tokenizer.json",
                        "https://huggingface.co/deepseek-ai/DeepSeek-V3/resolve/main/tokenizer.json"),
        "Yi-6B": ("tokenizer.model",
                  "https://huggingface.co/01-ai/Yi-6B/resolve/main/tokenizer.model"),
        "ChatGLM3-6B": ("tokenizer.model",
                        "https://huggingface.co/THUDM/chatglm3-6b/resolve/main/tokenizer.model"),
        "LLaMA-3.1-8B": ("tokenizer.json",
                         "https://huggingface.co/meta-llama/Llama-3.1-8B/resolve/main/tokenizer.json"),
    }

    def _hf(name, fname, url):
        import urllib.request
        from pathlib import Path as _P
        cache_dir = _P(__file__).resolve().parent.parent / "artifacts" / "ref_tokenizers"
        cache_dir.mkdir(parents=True, exist_ok=True)
        dest = cache_dir / f"{name}-{fname}"
        # huggingface.co 在部分网络不可达，依次尝试官方源与镜像
        mirrors = [url, url.replace("https://huggingface.co/", "https://hf-mirror.com/")]
        if not dest.exists():
            last_err = None
            for m in mirrors:
                try:
                    req = urllib.request.Request(m, headers={"User-Agent": "zh-native-tokenizer/0.1"})
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        dest.write_bytes(resp.read())
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
            if last_err is not None:
                raise last_err
        if fname.endswith(".json"):
            from tokenizers import Tokenizer as _T
            tok = _T.from_file(str(dest))
            def pieces(text: str) -> list[str]:
                # ByteLevel 模型的 .tokens 是字节级乱码，逐 token 解码得到可读文本
                ids = tok.encode(text).ids
                return [tok.decode([i]) for i in ids]
            return pieces, tok.get_vocab_size()
        else:
            import os as _os
            import sentencepiece as _spm
            # SentencePiece 的 C++ 用窄字符 API 打开文件，绝对路径含中文会失败；
            # 工作区内相对路径为纯 ASCII 时可正常加载。
            sp = _spm.SentencePieceProcessor(model_file=_os.path.relpath(dest, _os.getcwd()))
            return (lambda t: sp.encode(t, out_type=str)), sp.get_piece_size()

    for name, (fname, url) in REF_TOKENIZERS.items():
        try_add(name, lambda n=name, f=fname, u=url: _hf(n, f, u))

    return adapters


def load_samples(samples_dir: Path) -> list[tuple[str, str]]:
    """读取评测样本文本集：目录下每个 .txt 为一类。"""
    out = []
    for f in sorted(samples_dir.glob("*.txt")):
        text = f.read_text(encoding="utf-8").strip()
        if text:
            out.append((f.stem, text))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="中文原生分词器对比评测")
    ap.add_argument("--samples", default=str(ROOT / "eval" / "samples"))
    ap.add_argument("--ours", action="append", default=[],
                    help="我们的模型前缀（可多次：如 artifacts/group_a）")
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "eval_results.json"))
    ap.add_argument("--skip-refs", action="store_true", help="跳过第三方词表（离线模式）")
    args = ap.parse_args(argv)

    samples = load_samples(Path(args.samples))
    if not samples:
        print("未找到评测样本（eval/samples/*.txt）", file=sys.stderr)
        return 1

    tokenizers: dict[str, object] = {}
    for prefix in args.ours:
        try:
            tokenizers[Path(prefix).stem] = load_tokenizer(prefix)
            print(f"  ✓ 加载我们的分词器：{prefix}")
        except FileNotFoundError as e:
            print(f"  ✗ {e}")

    if not args.skip_refs:
        for adapter in load_reference_tokenizers():
            tokenizers[adapter.name] = adapter
    if not tokenizers:
        print("没有任何可用分词器", file=sys.stderr)
        return 1

    # 部首数据（我们的分词器才可计算部首可恢复率）
    radical_fn = None
    try:
        from src.tokenizer.radicals import char_radical
        radical_fn = char_radical
    except Exception:
        pass

    results: dict = {"samples": {}, "tokenizers": {}}
    for cat, text in samples:
        results["samples"][cat] = {"chars": len(text), "categories": {}}
        for name, tok in tokenizers.items():
            pieces = tok.pieces(text)
            vocab_size = getattr(tok, "vocab_size", 0)
            results["samples"][cat]["categories"][name] = evaluate_text(
                pieces, text, vocab_size=vocab_size, radical_fn=radical_fn
            )

    # 汇总（跨类别平均）
    for name in tokenizers:
        sums: dict = {}
        n = len(samples)
        for cat, text in samples:
            m = results["samples"][cat]["categories"][name]
            for k, v in m.items():
                sums[k] = sums.get(k, 0.0) + (v if isinstance(v, (int, float)) else 0)
        results["tokenizers"][name] = {k: round(v / n, 4) for k, v in sums.items()}

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果已写入 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
