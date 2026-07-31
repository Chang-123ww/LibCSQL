# -*- coding: utf-8 -*-
"""
validate_test_cases.py — 校验测试集中所有标注 SQL 可执行且结果合理
每次新增/修改测试用例后必须运行。空结果不算错误，但会给出警告（建议标注SQL大多返回非空结果，
否则 EX 指标区分度会下降——很多错误SQL也会碰巧返回空集而被误判为正确）。
运行: python scripts/validate_test_cases.py
"""
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.metrics import run_sql  # noqa: E402

DB = "data/library.db"
CASES = "data/test_cases.json"


def main():
    with open(CASES, "r", encoding="utf-8") as f:
        cases = json.load(f)
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        print("!! 存在重复的 case id"); sys.exit(1)

    errors, empties = 0, 0
    by_level = {}
    for c in cases:
        rows, err = run_sql(DB, c["sql_gold"])
        by_level[c["difficulty"]] = by_level.get(c["difficulty"], 0) + 1
        if err:
            errors += 1
            print(f"  [错误] {c['id']}: {err}\n         SQL: {c['sql_gold'][:100]}")
        elif len(rows) == 0:
            empties += 1
            print(f"  [警告] {c['id']}: 结果集为空 — {c['question_zh']}")
        else:
            print(f"  [通过] {c['id']}: {len(rows)} rows")

    print("\n难度分布:", by_level)
    print(f"共 {len(cases)} 条 | 执行错误 {errors} | 空结果 {empties}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
