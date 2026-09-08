# -*- coding: utf-8 -*-
"""v0.2 形+音全面复核脚本：数据完整性、一致性、边缘情况。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pinyin.syllable import parse  # noqa: E402

PROBLEMS: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        PROBLEMS.append(msg)


def review_pinyin_json() -> dict:
    path = ROOT / "artifacts" / "pinyin" / "group_a_64k_pinyin.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data["entries"]
    stats = {"总条目": len(entries), "词": 0, "字": 0, "来源": {}}
    empty_syll = 0
    mismatches = 0
    count_mismatches = 0
    samples: dict[str, list[str]] = {}
    for word, e in entries.items():
        etype = e.get("type")
        if etype == "word":
            stats["词"] += 1
            src = e.get("source", "?")
            stats["来源"][src] = stats["来源"].get(src, 0) + 1
            numbered = e.get("numbered", "")
            check(numbered, f"词 {word!r} 缺少 numbered")
            if not numbered:
                continue
            toks = numbered.split()
            # 1) 音节数 == 字数（儿化除外）
            if len(toks) != len(word):
                count_mismatches += 1
                samples.setdefault("音节数≠字数", []).append(f"{word} -> {numbered}")
            # 2) 逐音节可解析且无空音节/未知
            for t in toks:
                if not t or t == "?":
                    empty_syll += 1
                    samples.setdefault("空/未知音节", []).append(f"{word} -> {numbered}")
                    continue
                try:
                    syl = parse(t)
                    if not syl.spelling:
                        empty_syll += 1
                except Exception:
                    PROBLEMS.append(f"词 {word!r} 音节解析失败: {t}")
            # 3) numbered → marked 应与 pinyin 字段一致
            try:
                marked = " ".join(parse(t).marked() for t in toks)
                if marked != e.get("pinyin"):
                    mismatches += 1
                    samples.setdefault("pinyin/numbered 不一致", []).append(
                        f"{word}: pinyin={e.get('pinyin')!r} 反推={marked!r}")
            except Exception:
                pass
            # 4) 多音词 all_readings 可解析
            for r in e.get("all_readings", []):
                try:
                    [parse(t) for t in r.split()]
                except Exception:
                    PROBLEMS.append(f"词 {word!r} all_readings 解析失败: {r}")
        elif etype == "char":
            stats["字"] += 1
            for key in ("marked", "numbered", "zhuyin"):
                check(key in e, f"字 {word!r} 缺少 {key}")
            check(len(e.get("marked", [])) == len(e.get("numbered", [])) == len(e.get("zhuyin", [])),
                  f"字 {word!r} 三列表长度不一致")
        else:
            PROBLEMS.append(f"条目 {word!r} 缺少 type")
    print("=== 拼音标注 JSON ===")
    print(f"条目 {stats['总条目']}（词 {stats['词']}，字 {stats['字']}）")
    print(f"词来源分布: {stats['来源']}")
    print(f"音节数≠字数: {count_mismatches} 例；空/未知音节: {empty_syll}；pinyin/numbered 不一致: {mismatches}")
    for k, v in samples.items():
        print(f"  [{k}] {len(v)} 例，前 3:", v[:3])
    return stats


def review_traditional_map() -> None:
    path = ROOT / "artifacts" / "pinyin" / "traditional_map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    bad = 0
    for w, e in data.items():
        if not e.get("numbered") or not e.get("zhuyin"):
            bad += 1
            continue
        try:
            [parse(t) for t in e["numbered"].split()]
        except Exception:
            bad += 1
    print(f"\n=== 繁体映射 ===")
    print(f"词条 {len(data)}；异常 {bad}")


def review_test_set() -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location("pb", ROOT / "eval" / "polyphone_bench.py")
    pb = importlib.util.module_from_spec(spec)
    sys.modules["pb"] = pb
    spec.loader.exec_module(pb) if spec.loader else None
    bad = 0
    for word, reading in pb.TEST_SET.items():
        toks = reading.split()
        if len(toks) != len(word):
            PROBLEMS.append(f"测试集 {word}: 音节数({len(toks)})≠字数({len(word)})")
            bad += 1
            continue
        for t in toks:
            try:
                syl = parse(t)
                if syl.tone not in (1, 2, 3, 4, 5):
                    PROBLEMS.append(f"测试集 {word}: 声调异常 {t}")
                    bad += 1
            except Exception:
                PROBLEMS.append(f"测试集 {word}: 解析失败 {t}")
                bad += 1
    print(f"\n=== 多音测试集 ===\n{len(pb.TEST_SET)} 词，异常 {bad}")


def review_requirements() -> None:
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    needed = {"pypinyin": "src/pinyin/annotate.py 运行时调用",
              "edge-tts": "发声挂件后端",
              "pyarrow": "tools/fetch_wiki.py 解析 parquet"}
    print("\n=== requirements.txt ===")
    for pkg, why in needed.items():
        if pkg not in req:
            PROBLEMS.append(f"requirements.txt 缺少 {pkg}（{why}）")
            print(f"缺失: {pkg} —— {why}")
    if not any("缺失" in p for p in PROBLEMS):
        pass


def review_adr_structure() -> None:
    text = (ROOT / "docs" / "03-决策记录.md").read_text(encoding="utf-8")
    headers = re.findall(r"^## ADR-\d+", text, re.M)
    ids = [int(h.split("-")[1]) for h in headers]
    dupes = [i for i in set(ids) if ids.count(i) > 1]
    missing = sorted(set(range(1, max(ids) + 1)) - set(ids)) if ids else []
    print(f"\n=== ADR 结构 ===\n共 {len(headers)} 条；重复: {dupes or '无'}；缺失编号: {missing or '无'}")
    if dupes or missing:
        PROBLEMS.append(f"ADR 结构异常: 重复{dupes} 缺失{missing}")


def main() -> int:
    review_pinyin_json()
    review_traditional_map()
    review_test_set()
    review_requirements()
    review_adr_structure()
    print("\n" + "=" * 50)
    if PROBLEMS:
        print(f"发现 {len(PROBLEMS)} 个问题：")
        for p in PROBLEMS[:30]:
            print(" -", p)
        return 1
    print("✅ 全部复核通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
