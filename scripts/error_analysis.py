import json
import os
from collections import defaultdict

RAW_DIR = "results/raw"

error_stats = defaultdict(lambda: defaultdict(int))
parse_fallback_stats = defaultdict(int)
empty_sql_stats = defaultdict(int)

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
            if rec["ex"] == 1:
                error_stats[method_part]["正确"] +=1
                continue
            # 错误分类
            if rec["api_error"]:
                error_stats[method_part]["API错误"] +=1
            elif rec["safety"] != "ok":
                error_stats[method_part]["安全拦截"] +=1
            elif not rec["pred_sql"].strip():
                error_stats[method_part]["SQL为空/解析失败"] +=1
                empty_sql_stats[method_part] +=1
            elif rec["exec_error"]:
                error_stats[method_part]["执行错误"] +=1
            else:
                error_stats[method_part]["逻辑错误"] +=1
            if rec.get("_parse_fallback"):
                parse_fallback_stats[method_part] +=1

print("各方法错误分布:")
print("-"*80)
for method in ["zero", "few", "sl", "cot", "cot_sl"]:
    total = sum(error_stats[method].values())
    print(f"\n{method} (总样本{total}):")
    for err_type, cnt in sorted(error_stats[method].items(), key=lambda x: -x[1]):
        print(f"  {err_type}: {cnt} ({cnt/total*100:.1f}%)")
    print(f"  解析fallback次数: {parse_fallback_stats[method]} ({parse_fallback_stats[method]/total*100:.1f}%)")
    print(f"  SQL为空次数: {empty_sql_stats[method]} ({empty_sql_stats[method]/total*100:.1f}%)")

# 抽5个cot_sl的错误案例看原始输出
print("\n" + "="*80)
print("随机抽取5个cot_sl错误案例的原始输出（前500字符）:")
print("-"*80)
cnt = 0
for fname in os.listdir(RAW_DIR):
    if not fname.endswith("cot_sl.jsonl"):
        continue
    fpath = os.path.join(RAW_DIR, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec["ex"] == 0 and cnt <5:
                print(f"\n模型: {fname.split('__')[0]}, 用例: {rec['case_id']}")
                print(f"问题: {rec['question']}")
                print(f"安全状态: {rec['safety']}, 预测SQL: {repr(rec['pred_sql'][:200])}")
                print(f"原始输出前500字符: {rec['raw_output'][:500]}")
                print("-"*60)
                cnt +=1
