# -*- coding: utf-8 -*-
"""glossary.py — 图书馆专业术语标准化词典（预处理层）"""

GLOSSARY = [
    ("在馆",   "books.available_copies > 0"),
    ("可借",   "books.available_copies > 0"),
    ("在架",   "books.available_copies > 0"),
    ("馆藏地", "locations 表（经 categories.location_id 关联到图书）"),
    ("索书号", "locations.shelf_range（架位范围）"),
    ("借阅量", "COUNT(borrow_records.record_id)"),
    ("借书次数", "COUNT(borrow_records.record_id)"),
    ("未归还", "borrow_records.return_date IS NULL"),
    ("未还",   "borrow_records.return_date IS NULL"),
    ("逾期",   "borrow_records.return_date IS NULL AND borrow_records.due_date < 当前参照日期"),
    ("续借",   "borrow_records.renew_count"),
    ("学院",   "readers.department"),
    ("复本",   "books.total_copies"),
    ("馆藏复本", "books.total_copies"),
    ("现刊",   "本库未建期刊表，提示用户该查询超出范围"),
]


def match_glossary(question: str):
    """返回查询文本命中的术语映射列表 [(term, rule), ...]"""
    return [(t, r) for t, r in GLOSSARY if t in question]


def glossary_prompt_block(hits) -> str:
    if not hits:
        return ""
    lines = "\n".join(f'- "{t}" → {r}' for t, r in hits)
    return f"\n### 图书馆术语标准化对照（预处理层输出）\n{lines}\n"
