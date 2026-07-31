# -*- coding: utf-8 -*-
"""
anova_analysis.py — 实验结果统计分析（对应论文 3.4 与 4.2 节）

输入: results/raw/*.jsonl（runner 的输出）
输出（results/ 目录）:
  summary_by_combo.csv        25组合的 EX/LF/延迟/Token 均值与标准差 + 成本估算（Table 4.x 素材）
  anova_table.csv             双因素方差分析表（模型主效应、方法主效应、交互效应）
  tukey_model.txt             模型间 Tukey HSD 事后检验
  tukey_method.txt            提示方法间 Tukey HSD 事后检验
  subgroup_by_difficulty.csv  分查询难度的亚组 EX 均值
  error_summary.csv           安全拦截/执行错误分布（定性编码的起点）
  heatmap_ex.png              模型×方法 EX 热力图（Figure 4.x 素材）

统计说明（论文中需交代）:
  EX 为逐用例二元变量（0/1），本脚本按领域惯例对其做双因素 ANOVA（线性概率模型近似）。
  作为稳健性检验，同时输出逻辑回归（logit）主效应与交互项结果，二者结论一致时更有说服力。
"""
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.anova import anova_lm
from statsmodels.stats.multicomp import pairwise_tukeyhsd
import yaml

matplotlib.rcParams["font.sans-serif"] = ["SimHei", "PingFang SC", "Microsoft YaHei",
                                          "Noto Sans CJK SC", "Arial Unicode MS", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

RAW = "results/raw"
OUT = "results"


def load_data() -> pd.DataFrame:
    rows = []
    for path in sorted(glob.glob(os.path.join(RAW, "*.jsonl"))):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if not rows:
        raise SystemExit("results/raw/ 下没有实验数据，请先运行 python -m src.runner")
    df = pd.DataFrame(rows)
    for col in ["ex", "lf", "latency", "input_tokens", "output_tokens"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def load_prices():
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return {name: (m.get("price_in_per_m", 0), m.get("price_out_per_m", 0))
                for name, m in cfg.get("models", {}).items()}
    except FileNotFoundError:
        return {}


def summary_table(df: pd.DataFrame) -> pd.DataFrame:
    prices = load_prices()
    g = df.groupby(["model", "method"]).agg(
        n=("ex", "size"),
        ex_mean=("ex", "mean"), ex_std=("ex", "std"),
        lf_mean=("lf", "mean"), lf_std=("lf", "std"),
        latency_mean=("latency", "mean"), latency_std=("latency", "std"),
        tokens_in_mean=("input_tokens", "mean"),
        tokens_out_mean=("output_tokens", "mean"),
    ).reset_index()

    def cost(row):
        pin, pout = prices.get(row["model"], (0, 0))
        return (row["tokens_in_mean"] * pin + row["tokens_out_mean"] * pout) / 1e6

    g["est_cost_usd_per_query"] = g.apply(cost, axis=1).round(6)
    return g.round(4)


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load_data()
    print(f"载入 {len(df)} 条实验记录 | 模型: {sorted(df.model.unique())} | 方法: {sorted(df.method.unique())}")

    # ---- 1. 描述性统计 ----
    summ = summary_table(df)
    summ.to_csv(os.path.join(OUT, "summary_by_combo.csv"), index=False, encoding="utf-8-sig")
    print("\n== 各组合 EX 均值 ==")
    print(summ.pivot(index="model", columns="method", values="ex_mean"))

    # ---- 2. 双因素 ANOVA ----
    model_fit = smf.ols("ex ~ C(model) * C(method)", data=df).fit()
    anova = anova_lm(model_fit, typ=2)
    anova.to_csv(os.path.join(OUT, "anova_table.csv"), encoding="utf-8-sig")
    print("\n== Two-way ANOVA (Type II) ==")
    print(anova)

    # 稳健性检验：逻辑回归
    try:
        logit = smf.logit("ex ~ C(model) + C(method)", data=df).fit(disp=0)
        with open(os.path.join(OUT, "logit_robustness.txt"), "w", encoding="utf-8") as f:
            f.write(str(logit.summary()))
    except Exception as e:
        print(f"(逻辑回归稳健性检验未收敛/失败，可忽略: {e})")

    # ---- 3. Tukey HSD 事后检验 ----
    for factor in ["model", "method"]:
        tk = pairwise_tukeyhsd(df["ex"], df[factor])
        with open(os.path.join(OUT, f"tukey_{factor}.txt"), "w", encoding="utf-8") as f:
            f.write(str(tk.summary()))
        print(f"\n== Tukey HSD by {factor} ==")
        print(tk.summary())

    # ---- 4. 分难度亚组分析 ----
    sub = (df.groupby(["difficulty", "model", "method"])["ex"].mean()
             .reset_index().round(4))
    sub.to_csv(os.path.join(OUT, "subgroup_by_difficulty.csv"), index=False, encoding="utf-8-sig")

    # ---- 5. 错误分布（定性编码起点）----
    err = (df.assign(outcome=np.where(df.ex == 1, "correct",
                     np.where(df.safety != "passed", "safety_" + df.safety.astype(str),
                     np.where(df.exec_error.notna() & (df.exec_error != ""), "exec_error", "wrong_result"))))
             .groupby(["model", "method", "outcome"]).size()
             .reset_index(name="count"))
    err.to_csv(os.path.join(OUT, "error_summary.csv"), index=False, encoding="utf-8-sig")

    # ---- 6. 热力图 ----
    pivot = df.groupby(["model", "method"])["ex"].mean().unstack()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    im = ax.imshow(pivot.values, cmap="YlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)), pivot.columns)
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="black" if v > 0.5 else "#444", fontsize=9)
    ax.set_title("Execution Accuracy (EX) by LLM × Prompt Method")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "heatmap_ex.png"), dpi=200)

    print(f"\n分析完成，所有结果已写入 {OUT}/ 目录。")


if __name__ == "__main__":
    main()
