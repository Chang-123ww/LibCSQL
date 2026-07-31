# -*- coding: utf-8 -*-
"""safety.py — SQL 安全过滤（后处理层）：仅放行单条只读 SELECT 语句"""
import re

_BLOCKED = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|replace|attach|detach|"
    r"pragma|vacuum|grant|revoke|exec|execute)\b",
    re.IGNORECASE,
)


def validate_sql(sql: str) -> dict:
    """返回 {'ok': bool, 'sql': 清理后的SQL, 'reason': 说明}"""
    s = (sql or "").strip().rstrip(";").strip()
    if not s:
        return {"ok": False, "sql": s, "reason": "empty_sql"}
    if ";" in s:
        return {"ok": False, "sql": s, "reason": "multiple_statements"}
    if not re.match(r"^(select|with)\b", s, re.IGNORECASE):
        return {"ok": False, "sql": s, "reason": "not_select"}
    if _BLOCKED.search(s):
        return {"ok": False, "sql": s, "reason": "blocked_keyword"}
    return {"ok": True, "sql": s, "reason": "passed"}
