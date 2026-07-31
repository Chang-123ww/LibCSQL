# -*- coding: utf-8 -*-
"""
metrics.py — 执行层与评测指标（Execution & Feedback Layer）

EX (Execution Accuracy): 预测 SQL 与标注 SQL 在测试库上的执行结果集是否一致（核心指标）。
  - 标注 SQL 顶层含 ORDER BY 时按有序序列比较，否则按无序多重集比较；
  - 浮点值四舍五入到 1e-6 后比较，避免精度噪声。
LF (Logical Form Accuracy): 规范化（去注释、统一大小写与空白）后的字符串精确匹配，
  为 LF 的保守近似（低估真实语义等价率），论文中应说明以 EX 为主指标。
"""
import re
import sqlite3
import threading

try:
    import sqlparse
except ImportError:
    sqlparse = None

EXEC_TIMEOUT = 15  # 秒
ROW_LIMIT = 5000


def run_sql(db_path: str, sql: str):
    """执行只读 SQL，带超时与行数上限。返回 (rows, error)。rows 为 tuple 列表。"""
    conn = sqlite3.connect(db_path)
    timer = threading.Timer(EXEC_TIMEOUT, conn.interrupt)
    timer.start()
    try:
        cur = conn.execute(sql)
        rows = cur.fetchmany(ROW_LIMIT)
        return [tuple(r) for r in rows], None
    except sqlite3.OperationalError as e:
        msg = str(e)
        if "interrupted" in msg:
            return None, f"timeout(>{EXEC_TIMEOUT}s)"
        return None, msg
    except sqlite3.Error as e:
        return None, str(e)
    finally:
        timer.cancel()
        conn.close()


def _norm_value(v):
    if isinstance(v, float):
        return round(v, 6)
    return v


def _norm_rows(rows):
    return [tuple(_norm_value(v) for v in r) for r in rows]


def _has_top_level_order_by(sql: str) -> bool:
    # 去掉括号内内容后检测 ORDER BY（近似判断顶层排序）
    depth, out = 0, []
    for ch in sql:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return re.search(r"\border\s+by\b", "".join(out), re.IGNORECASE) is not None


def execution_match(db_path: str, pred_sql: str, gold_sql: str) -> dict:
    """计算 EX。返回 {'ex':0/1, 'pred_error':..., 'gold_error':..., 'pred_rows':n, 'gold_rows':n}"""
    gold_rows, gold_err = run_sql(db_path, gold_sql)
    if gold_err:
        return {"ex": 0, "pred_error": None, "gold_error": gold_err,
                "pred_rows": None, "gold_rows": None}
    pred_rows, pred_err = run_sql(db_path, pred_sql)
    if pred_err:
        return {"ex": 0, "pred_error": pred_err, "gold_error": None,
                "pred_rows": None, "gold_rows": len(gold_rows)}
    g, p = _norm_rows(gold_rows), _norm_rows(pred_rows)
    if _has_top_level_order_by(gold_sql):
        match = g == p
    else:
        match = sorted(map(repr, g)) == sorted(map(repr, p))
    return {"ex": int(match), "pred_error": None, "gold_error": None,
            "pred_rows": len(p), "gold_rows": len(g)}


def normalize_sql(sql: str) -> str:
    s = sql or ""
    if sqlparse is not None:
        s = sqlparse.format(s, keyword_case="lower", identifier_case="lower", strip_comments=True)
    else:
        s = re.sub(r"--[^\n]*", " ", s).lower()
    s = re.sub(r"\s+", " ", s).strip().rstrip(";").strip()
    return s


def logical_form_match(pred_sql: str, gold_sql: str) -> int:
    return int(normalize_sql(pred_sql) == normalize_sql(gold_sql))
