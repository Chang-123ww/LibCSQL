# -*- coding: utf-8 -*-
"""
fewshot_overlap.py — 论文 §4.2.7 / 附录 C.5（few-shot 示例同型题检查）与 §4.3（L1 过度结构化计数）的复现脚本

1) 同型题检查：把 200 条 gold SQL 与 src/prompts.py 中的 3 条 few-shot 示例逐一比较，
   比较两项——读取的表集合、包含的子句集合
   （JOIN / WHERE / GROUP BY / HAVING / ORDER BY / LIMIT / SELECT DISTINCT / 子查询 / WITH / CASE），
   忽略字面值、选择列、比较运算符和聚合函数。两项都相同即判为“同型”。
   论文结果（复核后的 gold）：28 条同型（示例1 25 条、示例2 2 条、示例3 1 条）；另报告两条“只多一个 WHERE”的近邻 L3-029、L4-024。
2) 去掉 29 条后，用 results/revalidated.csv 重算 25 个组合的 EX（论文表 C.1），不重新调用任何模型。
3) L1 过度结构化：对所有判错的 L1 记录，解析模型 SQL（先按 §3.3.7 规则清理），
   统计其中含有 gold 没有的 JOIN / 子查询或 WITH / GROUP BY / 聚合 的条数（论文 §4.3：226 条中 37 条）。

依赖：pip install sqlglot pandas
用法：python analysis/fewshot_overlap.py
"""
import glob
import json
import os
import sys

import pandas as pd
import sqlglot
from sqlglot import exp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reevaluate import clean_sql  # noqa: E402  与论文 §3.3.7 相同的清理规则

FEWSHOT = [
    "SELECT title FROM books WHERE publish_year = 2022",
    "SELECT p.publisher_name, COUNT(*) AS book_count FROM books b JOIN publishers p "
    "ON b.publisher_id = p.publisher_id GROUP BY p.publisher_name",
    "SELECT r.name FROM readers r JOIN borrow_records br ON r.reader_id = br.reader_id "
    "GROUP BY r.reader_id, r.name HAVING COUNT(*) > 2",
]
MODELS = ["qwen3.7-plus", "doubao-seed-2-0-mini", "ernie-4.5-turbo-32k", "glm-4.7-flashX", "qwen2.5-coder:7b"]
METHODS = ["zero", "few", "cot", "sl", "cot_sl"]


def signature(sql):
    t = sqlglot.parse_one(sql, read="sqlite")
    tables = frozenset(x.name for x in t.find_all(exp.Table))
    clauses = set()
    for name, cls in [("JOIN", exp.Join), ("WHERE", exp.Where), ("GROUP BY", exp.Group),
                      ("HAVING", exp.Having), ("ORDER BY", exp.Order), ("LIMIT", exp.Limit),
                      ("WITH", exp.With), ("CASE", exp.Case), ("UNION", exp.Union)]:
        if any(True for _ in t.find_all(cls)):
            clauses.add(name)
    if any(isinstance(s.args.get("distinct"), exp.Distinct) for s in t.find_all(exp.Select)):
        clauses.add("SELECT DISTINCT")
    if len(list(t.find_all(exp.Select))) > 1:
        clauses.add("SUBQUERY")
    return tables, frozenset(clauses)


def added_structure(sql):
    try:
        t = sqlglot.parse_one(sql, read="sqlite")
    except Exception:
        return None
    f = set()
    if any(True for _ in t.find_all(exp.Group)): f.add("GROUP BY")
    if any(True for _ in t.find_all(exp.Having)): f.add("HAVING")
    if any(True for _ in t.find_all(exp.AggFunc)): f.add("aggregate")
    if any(True for _ in t.find_all(exp.Join)): f.add("JOIN")
    if len(list(t.find_all(exp.Select))) > 1: f.add("subquery")
    if any(True for _ in t.find_all(exp.With)): f.add("WITH")
    return f


def main():
    cases = json.load(open(os.path.join(ROOT, "data/test_cases.json"), encoding="utf-8"))
    sigs = [signature(e) for e in FEWSHOT]
    match, near = {}, {}
    for c in cases:
        s = signature(c["sql_gold"])
        for i, se in enumerate(sigs, 1):
            if s == se:
                match.setdefault(c["id"], []).append(i)
            elif s[0] == se[0] and s[1] - se[1] == {"WHERE"} and se[1] <= s[1]:
                near.setdefault(c["id"], []).append(i)
    print(f"== 同型题：{len(match)} 条 ==")
    for i in (1, 2, 3):
        ids = sorted(k for k, v in match.items() if i in v)
        print(f"  示例{i}：{len(ids)} 条  {', '.join(ids)}")
    print("  近邻（示例模式 + 一个 WHERE）：", ", ".join(f"{k}(示例{v[0]})" for k, v in sorted(near.items())))

    rev = pd.read_csv(os.path.join(ROOT, "results/revalidated.csv"), encoding="utf-8-sig")
    rev["model"] = rev["model"].replace({"qwen2.5-coder_7b": "qwen2.5-coder:7b"})
    for label, excl in [("全部 200 条", set()), (f"去掉 {len(match)} 条同型题（论文表 C.1）", set(match)),
                        ("再去掉 L3-029、L4-024", set(match) | {"L3-029", "L4-024"})]:
        d = rev[~rev.case_id.isin(excl)]
        t = d.pivot_table(index="model", columns="method", values="ex", aggfunc="mean").loc[MODELS, METHODS]
        t["Mean"] = t.mean(axis=1)
        t.loc["Method mean"] = t.mean()
        print(f"\n== EX：{label}（每格 n = {d.case_id.nunique()}）==")
        print(t.round(3).to_string())

    rows = []
    exmap = {(r.model, r.method, r.case_id): r.ex for r in rev.itertuples()}
    for fn in glob.glob(os.path.join(ROOT, "results/raw/*.jsonl")):
        for line in open(fn, encoding="utf-8"):
            r = json.loads(line)
            if not r["case_id"].startswith("L1") or exmap.get((r["model"], r["method"], r["case_id"])) != 0:
                continue
            g, p = added_structure(r["gold_sql"]), added_structure(clean_sql(r.get("pred_sql") or ""))
            rows.append(dict(model=r["model"], method=r["method"],
                             added=bool(p is not None and g is not None and (p - g))))
    d = pd.DataFrame(rows)
    print(f"\n== L1 判错 {len(d)} 条，其中含多余结构 {int(d.added.sum())} 条（论文 §4.3）==")
    print(pd.crosstab(d[d.added].model, d[d.added].method, margins=True))


if __name__ == "__main__":
    main()
