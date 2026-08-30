# -*- coding: utf-8 -*-
"""
reevaluate.py — 对 results/raw/*.jsonl 重新判定 EX（修复 JSON 残渣解析问题）

背景：部分模型（尤其本地 qwen2.5-coder:7b）输出的 JSON 中，SQL 字段末尾会残留
`"}` 等收尾字符，导致执行时报 "unrecognized token" 语法错误、被误判为 EX=0。
本脚本在【不改动模型原始输出】的前提下，清理这些残渣后重新执行判定。

清理规则（与论文 §3.3.7 一致，确定性、只作用于字符串末尾）：
    依次剥去结尾的 `"}`、`}`、`"`、`;`；不改动语句内部，不新增任何 token。

【重要】该规则对全部 5,000 条记录一律适用，不区分原判是 0 还是 1。
只有双向施加，"有多少条由 0 变 1、有多少条由 1 变 0"才是可检验的实证结果，
而不是流程本身保证的结论。脚本同时报告两个方向的条数（论文 §4.2.1 报告 32 / 0）。

用法：
  # 先重建测试库（与实验时同一确定性种子，保证一致）
  python -m src.db_setup --db data/library.db

  # 单模型试验证（推荐先跑这个，确认数字与预期一致）
  python reevaluate.py --model qwen2.5-coder:7b

  # 全量重评测，输出 revalidated.csv
  python reevaluate.py

输出：
  控制台打印 清理前/后 EX 对比、双向变动条数、模型×方法矩阵
  --out 指定时写出逐条重评测结果 csv（默认 results/revalidated.csv）
  列 ex_orig = 原始运行时的判定；ex = 施加清理规则后的判定（论文所用）
"""
import argparse
import glob
import json
import os
import re
import sqlite3

DB_DEFAULT = "data/library.db"
CASES_DEFAULT = "data/test_cases.json"
RAW_DIR = "results/raw"

BLOCKED = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|replace|attach|"
    r"detach|pragma|vacuum|grant|revoke|exec|execute)\b", re.IGNORECASE)


def clean_sql(sql: str) -> str:
    """清理模型 SQL 输出末尾的 JSON 残渣（引号、大括号），不改动 SQL 主体。"""
    if not sql:
        return ""
    s = sql.strip()
    # 依次剥去末尾的 `"}`、`}`、`"` 残渣（仅结尾，不动语句内部）
    s = re.sub(r'\s*"\s*\}\s*$', '', s)
    s = re.sub(r'\s*\}\s*$', '', s)
    s = re.sub(r'"\s*$', '', s)
    return s.strip().rstrip(';').strip()


def norm_rows(rows):
    return [tuple(round(v, 6) if isinstance(v, float) else v for v in r) for r in rows]


def run_sql(db, sql):
    conn = sqlite3.connect(db)
    try:
        return [tuple(r) for r in conn.execute(sql).fetchmany(5000)], None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()


def has_top_order_by(sql):
    depth, out = 0, []
    for c in sql:
        if c == '(':
            depth += 1
        elif c == ')':
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(c)
    return re.search(r'\border\s+by\b', ''.join(out), re.IGNORECASE) is not None


def judge(db, gold_sql, gold_rows, pred_sql):
    """安全校验 + 执行 + 结果集比对，返回 0/1。规则与实验时一致。"""
    s = (pred_sql or "").strip()
    if not s:
        return 0
    if not re.match(r"^(select|with)\b", s, re.IGNORECASE) or BLOCKED.search(s):
        return 0
    if gold_rows is None:
        return 0
    prows, perr = run_sql(db, s)
    if perr is not None or prows is None:
        return 0
    p = norm_rows(prows)
    if has_top_order_by(gold_sql):
        return 1 if gold_rows == p else 0
    return 1 if sorted(map(repr, gold_rows)) == sorted(map(repr, p)) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--cases", default=CASES_DEFAULT)
    ap.add_argument("--raw", default=RAW_DIR)
    ap.add_argument("--model", default="", help="只重评测指定模型（试验证用）")
    ap.add_argument("--out", default="results/revalidated.csv")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"找不到测试库 {args.db}，请先运行 python -m src.db_setup --db {args.db}")

    cases = json.load(open(args.cases, encoding="utf-8"))
    gold = {c["id"]: c["sql_gold"] for c in cases}
    diff = {c["id"]: c["difficulty"] for c in cases}

    # 预计算标注SQL的结果集
    goldres = {}
    for cid, gs in gold.items():
        r, e = run_sql(args.db, gs)
        goldres[cid] = norm_rows(r) if r is not None else None

    files = sorted(glob.glob(os.path.join(args.raw, "*.jsonl")))
    if args.model:
        key = args.model.replace(":", "_")
        files = [f for f in files if key in os.path.basename(f) or args.model in os.path.basename(f)]
        if not files:
            raise SystemExit(f"未找到模型 {args.model} 的文件（在 {args.raw} 下）")

    records = []
    n_up = n_down = 0        # 0→1 与 1→0，双向统计
    for f in files:
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            cid = r["case_id"]
            ex_orig = r.get("ex", 0)
            raw_sql = r.get("pred_sql", "") or ""
            # 清理规则对每一条记录一律适用，与原判是 0 还是 1 无关
            ex = judge(args.db, gold[cid], goldres.get(cid), clean_sql(raw_sql))
            if ex_orig == 0 and ex == 1:
                n_up += 1
            elif ex_orig == 1 and ex == 0:
                n_down += 1
            records.append({
                "model": r["model"], "method": r["method"],
                "case_id": cid, "difficulty": diff.get(cid),
                "ex_orig": ex_orig, "ex": ex,
                "latency": r.get("latency", 0),
                "input_tokens": r.get("input_tokens", 0),
                "output_tokens": r.get("output_tokens", 0),
            })

    # 汇总输出
    try:
        import pandas as pd
        df = pd.DataFrame(records)
        print(f"重评测记录数: {len(df)}  |  清理规则对全部记录一律适用")
        print(f"  由 0 → 1（原误判、清理后正确）: {n_up} 条")
        print(f"  由 1 → 0（原判正确、清理后错误）: {n_down} 条")
        print(f"总体 EX  清理前={df.ex_orig.mean():.4f}  清理后={df.ex.mean():.4f}\n")
        order = [m for m in ["zero", "few", "cot", "sl", "cot_sl"] if m in df.method.unique()]
        piv = df.pivot_table(index="model", columns="method", values="ex", aggfunc="mean")[order]
        print("模型 × 方法  EX 矩阵（清理后，论文 Table 4.2）：")
        print(piv.round(3).to_string())
        print("\n各方法均值:", {m: round(df[df.method == m].ex.mean(), 3) for m in order})
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        df.to_csv(args.out, index=False, encoding="utf-8-sig")
        print(f"\n已写出逐条结果: {args.out}")
        print("清理前后的完整对照（论文 Table 4.1）：python analysis/sensitivity_cleaning.py")
    except ImportError:
        from collections import defaultdict
        agg = defaultdict(lambda: [0, 0])
        for r in records:
            k = (r["model"], r["method"])
            agg[k][0] += r["ex"]; agg[k][1] += 1
        print(f"重评测记录数: {len(records)}  |  0→1: {n_up} 条  1→0: {n_down} 条\n")
        for (m, meth), (s, n) in sorted(agg.items()):
            print(f"  {m:<24} {meth:<8} EX={s/n:.3f} ({s}/{n})")


if __name__ == "__main__":
    main()
