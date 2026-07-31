# -*- coding: utf-8 -*-
"""
prompts.py — 五种提示工程方法的 Prompt 构建（Prompt 构建层）
方法: zero | few | cot | sl | cot_sl
所有模板要求模型只输出 JSON，便于统一解析。
"""
import json
import re

from .db_setup import get_ddl_text
from .glossary import match_glossary, glossary_prompt_block

METHODS = ["zero", "few", "cot", "sl", "cot_sl"]
METHOD_NAMES = {
    "zero": "Zero-shot",
    "few": "Few-shot",
    "cot": "Chain-of-Thought",
    "sl": "Schema-Linking",
    "cot_sl": "CoT+Schema-Linking",
}

FEWSHOT_BLOCK = """
### 示例
Q: 查询所有2022年出版的图书书名
SQL: SELECT title FROM books WHERE publish_year = 2022

Q: 统计每个出版社的图书数量
SQL: SELECT p.publisher_name, COUNT(*) AS book_count FROM books b JOIN publishers p ON b.publisher_id = p.publisher_id GROUP BY p.publisher_name

Q: 查询借书次数超过2次的读者姓名
SQL: SELECT r.name FROM readers r JOIN borrow_records br ON r.reader_id = br.reader_id GROUP BY r.reader_id, r.name HAVING COUNT(*) > 2
"""

_CONSTRAINTS = (
    "### 约束\n"
    "- 只允许生成一条 SELECT 语句（可用 WITH 子句），禁止任何写操作\n"
    "- 使用 SQLite 兼容语法；日期为文本，用字符串比较（如 borrow_date LIKE '2025%' 或 substr(borrow_date,1,7)）\n"
    "- 严格只输出一个 JSON 对象，不要输出任何其他文字、解释或 Markdown 代码块标记"
)

_TAIL = {
    "zero": '\n\n### 输出格式\n{"sql": "生成的SQL语句"}',
    "few": FEWSHOT_BLOCK + '\n### 输出格式\n{"sql": "生成的SQL语句"}',
    "cot": (
        "\n\n### 任务\n首先一步一步思考查询逻辑：需要哪些表、哪些字段、什么筛选/连接/聚合条件，然后再生成正确的 SQL。"
        '\n\n### 输出格式\n{"reasoning": "分步推理过程（中文，3-6步）", "sql": "生成的SQL语句"}'
    ),
    "sl": (
        "\n\n### 任务\n第一步：识别用户查询中的每个关键表述对应数据库中的哪张表、哪个字段或条件（Schema Linking）；"
        "第二步：基于映射结果生成 SQL。"
        '\n\n### 输出格式\n{"schema_links": [{"phrase": "查询中的表述", "table": "表名", "column": "字段或条件"}], "sql": "生成的SQL语句"}'
    ),
    "cot_sl": (
        "\n\n### 任务\n第一步：识别用户查询中的每个关键表述对应数据库中的哪张表、哪个字段或条件（Schema Linking）；"
        "第二步：基于映射结果一步一步推理查询逻辑（表连接、筛选、聚合、排序）；第三步：生成最终 SQL。"
        '\n\n### 输出格式\n{"schema_links": [{"phrase": "查询中的表述", "table": "表名", "column": "字段或条件"}], '
        '"reasoning": "分步推理过程（中文）", "sql": "生成的SQL语句"}'
    ),
}


def build_prompt(method: str, question: str, use_glossary: bool = True) -> str:
    assert method in METHODS, f"未知提示方法: {method}"
    hits = match_glossary(question) if use_glossary else []
    return (
        "你是高校图书馆信息系统的 SQL 生成专家。数据库 Schema 如下：\n\n"
        + get_ddl_text()
        + glossary_prompt_block(hits)
        + f"\n### 用户查询\n{question}\n\n"
        + _CONSTRAINTS
        + _TAIL[method]
    )


def parse_model_output(text: str) -> dict:
    """从模型输出中稳健地解析 JSON；失败时降级用正则提取 SQL。
    兼容推理模型（如 DeepSeek-R1）：先剥离 <think>...</think> 思考段。"""
    raw = text or ""
    # 剥离推理模型的思考标签（含未闭合的情况：截断时只保留标签后内容）
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    raw = re.sub(r"^.*?</think>", "", raw, flags=re.DOTALL)  # 只出现闭合标签时
    if "<think>" in raw:  # 思考未闭合即被截断，无有效答案
        return {"sql": "", "_parse_fallback": True, "_truncated_thinking": True}
    clean = re.sub(r"```(?:json|sql)?", "", raw).strip()
    try:
        return json.loads(clean)
    except (json.JSONDecodeError, ValueError):
        pass
    m = re.search(r"\{.*\}", clean, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except (json.JSONDecodeError, ValueError):
            pass
    sql = re.search(r"(?:with|select)\b.*", clean, re.IGNORECASE | re.DOTALL)
    return {"sql": sql.group(0).strip() if sql else "", "_parse_fallback": True}
