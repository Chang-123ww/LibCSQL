# -*- coding: utf-8 -*-
"""
runner.py — 批量实验执行器（25 组 模型×提示方法 组合）

用法示例:
  python -m src.runner                                # 跑 config.yaml 中全部模型 × 全部方法
  python -m src.runner --models gpt-4o --methods zero,cot_sl
  python -m src.runner --limit 10                     # 每组只跑前10条（小成本试跑，强烈建议先做）

特性:
  - 断点续跑：结果逐条写入 results/raw/{model}__{method}.jsonl，重跑自动跳过已完成用例
  - 记录：EX、LF、延迟、输入/输出Token、安全校验结果、执行错误、原始模型输出
  - error_type 字段留空，供论文 3.4 节的人工定性编码（schema_linking / logic / syntax / terminology）
"""
import argparse
import json
import os
import re
import time
from datetime import datetime

import yaml
from dotenv import load_dotenv

from .llm_client import LLMClient
from .metrics import execution_match, logical_form_match
from .prompts import METHODS, build_prompt, parse_model_output
from .safety import validate_sql

RAW_DIR = "results/raw"

# Windows文件名非法字符正则
INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def safe_filename(name: str) -> str:
    """将模型名/方法名中的非法文件名字符替换为下划线，兼容Windows系统"""
    return INVALID_FILENAME_CHARS.sub('_', name)


def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_cases(path="data/test_cases.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_done_ids(out_path):
    done = set()
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["case_id"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return done


def run_combo(client: LLMClient, method: str, cases, db_path: str, sleep_s: float):
    safe_model = safe_filename(client.name)
    safe_method = safe_filename(method)
    out_path = os.path.join(RAW_DIR, f"{safe_model}__{safe_method}.jsonl")
    done = load_done_ids(out_path)
    todo = [c for c in cases if c["id"] not in done]
    print(f"\n=== {client.name} × {method} | 已完成 {len(done)} / 待跑 {len(todo)} ===")
    with open(out_path, "a", encoding="utf-8") as fout:
        for i, case in enumerate(todo, 1):
            prompt = build_prompt(method, case["question_zh"])
            resp = client.generate(prompt)
            record = {
                "case_id": case["id"],
                "difficulty": case["difficulty"],
                "question": case["question_zh"],
                "gold_sql": case["sql_gold"],
                "model": client.name,
                "method": method,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "latency": round(resp["latency"], 3),
                "input_tokens": resp["input_tokens"],
                "output_tokens": resp["output_tokens"],
                "api_error": resp["error"],
                "raw_output": resp["text"],
                "error_type": "",  # 人工定性编码列
            }
            if resp["error"]:
                record.update({"pred_sql": "", "safety": "api_error",
                               "ex": 0, "lf": 0, "exec_error": None})
            else:
                parsed = parse_model_output(resp["text"])
                v = validate_sql(parsed.get("sql", ""))
                record["pred_sql"] = v["sql"]
                record["safety"] = v["reason"]
                record["schema_links"] = parsed.get("schema_links")
                record["reasoning"] = parsed.get("reasoning")
                if v["ok"]:
                    ex_res = execution_match(db_path, v["sql"], case["sql_gold"])
                    record["ex"] = ex_res["ex"]
                    record["exec_error"] = ex_res["pred_error"]
                    record["lf"] = logical_form_match(v["sql"], case["sql_gold"])
                else:
                    record.update({"ex": 0, "lf": 0, "exec_error": None})
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            fout.flush()
            mark = "✓" if record["ex"] else "✗"
            print(f"  [{i}/{len(todo)}] {case['id']} {mark} "
                  f"(lat={record['latency']}s, tok={record['input_tokens']}+{record['output_tokens']})")
            time.sleep(sleep_s)


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--cases", default="data/test_cases.json")
    ap.add_argument("--db", default="data/library.db")
    ap.add_argument("--models", default="", help="逗号分隔，缺省=config中全部")
    ap.add_argument("--methods", default="", help=f"逗号分隔，可选: {','.join(METHODS)}")
    ap.add_argument("--limit", type=int, default=0, help="每组只跑前N条（试跑用）")
    args = ap.parse_args()

    cfg = load_config(args.config)
    cases = load_cases(args.cases)
    if args.limit:
        cases = cases[: args.limit]
    os.makedirs(RAW_DIR, exist_ok=True)

    model_names = [m.strip() for m in args.models.split(",") if m.strip()] or list(cfg["models"].keys())
    methods = [m.strip() for m in args.methods.split(",") if m.strip()] or METHODS
    sleep_s = cfg.get("rate_limit_sleep", 1.0)

    print(f"实验计划: {len(model_names)} 模型 × {len(methods)} 方法 × {len(cases)} 用例 "
          f"= {len(model_names)*len(methods)*len(cases)} 次调用")

    for name in model_names:
        try:
            client = LLMClient(name, cfg["models"][name], cfg["generation"])
        except Exception as e:
            print(f"\n!! 跳过模型 {name}: {e}")
            continue
        for method in methods:
            run_combo(client, method, cases, args.db, sleep_s)

    print("\n全部完成。运行 python analysis/anova_analysis.py 进行统计分析。")


if __name__ == "__main__":
    main()
