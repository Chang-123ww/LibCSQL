import json
import os
from collections import defaultdict

RAW_DIR = "results/raw"

results = defaultdict(lambda: defaultdict(lambda: {"ex": [], "lf": [], "latency": [], "input_tok": [], "output_tok": []}))

for fname in os.listdir(RAW_DIR):
    if not fname.endswith(".jsonl"):
        continue
    # 解析文件名: model__method.jsonl
    model_part, method_part = fname.replace(".jsonl", "").split("__", 1)
    fpath = os.path.join(RAW_DIR, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            results[model_part][method_part]["ex"].append(rec["ex"])
            results[model_part][method_part]["lf"].append(rec["lf"])
            results[model_part][method_part]["latency"].append(rec["latency"])
            results[model_part][method_part]["input_tok"].append(rec["input_tokens"])
            results[model_part][method_part]["output_tok"].append(rec["output_tokens"])

# 按方法汇总平均
method_avg = defaultdict(lambda: {"ex": [], "lf": [], "output_tok": []})
print("="*80)
print(f"{'模型':<25} {'方法':<10} {'样本数':<6} {'EX准确率':<10} {'LF准确率':<10} {'平均输出Token':<12}")
print("-"*80)
for model in sorted(results.keys()):
    for method in ["zero", "few", "sl", "cot", "cot_sl"]:
        if method not in results[model]:
            continue
        d = results[model][method]
        n = len(d["ex"])
        ex_avg = sum(d["ex"])/n*100
        lf_avg = sum(d["lf"])/n*100
        out_tok_avg = sum(d["output_tok"])/n
        method_avg[method]["ex"].extend(d["ex"])
        method_avg[method]["lf"].extend(d["lf"])
        method_avg[method]["output_tok"].extend(d["output_tok"])
        print(f"{model:<25} {method:<10} {n:<6} {ex_avg:>6.1f}%   {lf_avg:>6.1f}%   {out_tok_avg:>8.0f}")
print("-"*80)
print("方法整体平均（跨所有模型）:")
print("-"*80)
for method in ["zero", "few", "sl", "cot", "cot_sl"]:
    d = method_avg[method]
    n = len(d["ex"])
    ex_avg = sum(d["ex"])/n*100
    lf_avg = sum(d["lf"])/n*100
    out_tok_avg = sum(d["output_tok"])/n
    print(f"{method:<10} 样本数{n:<6} EX: {ex_avg:>6.1f}%   LF: {lf_avg:>6.1f}%   平均输出Token: {out_tok_avg:>8.0f}")
print("="*80)

# 分难度统计
print("\n分难度EX准确率:")
print("-"*80)
diff_results = defaultdict(lambda: defaultdict(list))
for fname in os.listdir(RAW_DIR):
    if not fname.endswith(".jsonl"):
        continue
    model_part, method_part = fname.replace(".jsonl", "").split("__", 1)
    fpath = os.path.join(RAW_DIR, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            diff = rec["difficulty"]
            diff_results[method_part][diff].append(rec["ex"])

for method in ["zero", "few", "sl", "cot", "cot_sl"]:
    print(f"\n{method}:")
    for diff in ["L1_simple", "L2_aggregation", "L3_join", "L4_nested"]:
        d = diff_results[method][diff]
        if not d:
            continue
        avg = sum(d)/len(d)*100
        print(f"  {diff:<15}: {avg:>6.1f}% (n={len(d)})")
