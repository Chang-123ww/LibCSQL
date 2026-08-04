# -*- coding: utf-8 -*-
"""
descriptive_analysis.py — 实验结果描述性分析（对应论文 3.4.3 与 4.2 节）

输入:
  results/raw/*.jsonl        runner 的原始输出（5 模型 × 5 方法 × 200 用例 = 5000 条）
  results/revalidated.csv    reevaluate.py 输出的校正后判定（必需）

输出（results/ 目录）:
  summary_by_combo.csv        25 组合的 EX/LF/延迟/Token 均值与标准差 + 成本估算
  ex_matrix.csv               模型 × 方法 EX 矩阵（论文 Table 4.1）
  subgroup_by_difficulty.csv  难度 × 方法 EX 矩阵（论文 Table 4.2）
  cost_by_model.csv           分模型准确率/延迟/Token/成本（论文 Table 4.3）
  heatmap_ex.png              模型 × 方法 EX 热力图（论文 Figure 4.1）

统计口径说明（与论文 3.4.3、4.2.3、5.3.7 一致）:
  同一组 200 条测试用例在全部 25 个条件下各运行一次，因此 5000 条记录是同一批题目的
  重复测量，而非 25 组独立样本，且每格无重复试验。对其做双因素方差分析会把重复测量
  当作独立观测、低估残差，p 值不可解释；基于同一误差项的事后检验（如 Tukey HSD）
  同理。本脚本因此只输出描述性统计——单元格均值、边际均值、各因素极差、以及排序在
  不同条件下的稳定性。推断检验仅用于用户测试环节（20 名被试各贡献一个配对观测）。

  早期版本（anova_analysis.py）曾输出 ANOVA、Tukey HSD 与 logistic 稳健性检验，
  论文未采用这部分结果，脚本已移除。

注意: 所有 EX 数字均以 results/revalidated.csv 的校正后判定为准，与论文第 4 章一致；
      raw/*.jsonl 中的 ex 字段为校正前判定，不直接用于统计。
"""
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

matplotlib.rcParams["font.sans-serif"] = ["SimHei", "PingFang SC", "Microsoft YaHei",
                                          "Noto Sans CJK SC", "Arial Unicode MS", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

RAW = os.path.join("results", "raw")
REVALIDATED = os.path.join("results", "revalidated.csv")
OUT = "results"

MODEL_ORDER = ["qwen3.7-plus", "doubao-seed-2-0-mini", "ernie-4.5-turbo-32k",
               "glm-4.7-flashX", "qwen2.5-coder:7b"]
METHOD_ORDER = ["zero", "few", "cot", "sl", "cot_sl"]
DIFFICULTY_ORDER = ["L1_simple", "L2_aggregation", "L3_join", "L4_nested"]


def load_data() -> pd.DataFrame:
    rows = []
    for path in sorted(glob.glob(os.path.join(RAW, "*.jsonl"))):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if not rows:
        raise SystemExit("results/raw/ 下没有实验数据，请先运行 python -m src.runner")
    df = pd.DataFrame(rows)

    if not os.path.exists(REVALIDATED):
        raise SystemExit(
            "缺少 results/revalidated.csv，请先运行 python reevaluate.py。\n"
            "论文第 4 章的全部数字均以校正后判定为准。")
    rev = pd.read_csv(REVALIDATED)[["model", "method", "case_id", "ex"]]
    rev = rev.rename(columns={"ex": "ex_corrected"})

    before = len(df)
    df = df.drop(columns=["ex"]).merge(rev, on=["model", "method", "case_id"], how="left")
    if len(df) != before or df["ex_corrected"].isna().any():
        raise SystemExit("raw 记录与 revalidated.csv 未能一一对应，请确认两者来自同一次实验。")
    df = df.rename(columns={"ex_corrected": "ex"})

    for col in ["ex", "lf", "latency", "input_tokens", "output_tokens"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def load_prices():
    """返回 ({模型: (输入单价, 输出单价)}, 币种, 核对日期)。单价按每百万 token 计。"""
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except FileNotFoundError:
        return {}, "?", "?"
    meta = cfg.get("pricing", {})
    prices = {name: (m.get("price_in_per_m", 0), m.get("price_out_per_m", 0))
              for name, m in cfg.get("models", {}).items()}
    return prices, meta.get("currency", "?"), str(meta.get("checked_on", "?"))


def summary_table(df: pd.DataFrame) -> pd.DataFrame:
    prices, _, _ = load_prices()
    g = df.groupby(["model", "method"]).agg(
        n=("ex", "size"),
        ex_mean=("ex", "mean"), ex_std=("ex", "std"),
        lf_mean=("lf", "mean"), lf_std=("lf", "std"),
        latency_mean=("latency", "mean"), latency_std=("latency", "std"),
        tokens_in_mean=("input_tokens", "mean"),
        tokens_out_mean=("output_tokens", "mean"),
    ).reset_index()

    def cost_per_1k(row):
        pin, pout = prices.get(row["model"], (0, 0))
        return (row["tokens_in_mean"] * pin + row["tokens_out_mean"] * pout) / 1e6 * 1000

    g["cost_per_1000_queries"] = g.apply(cost_per_1k, axis=1).round(4)
    return g.round(4)


def ordered(idx, order):
    return [x for x in order if x in idx] + [x for x in idx if x not in order]


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load_data()
    print(f"载入 {len(df)} 条实验记录（EX 取自 revalidated.csv 的校正后判定）")
    print(f"模型: {sorted(df.model.unique())}\n方法: {sorted(df.method.unique())}")

    # ---- 1. 25 组合描述统计 ----
    summ = summary_table(df)
    summ.to_csv(os.path.join(OUT, "summary_by_combo.csv"), index=False, encoding="utf-8-sig")

    # ---- 2. EX 矩阵（Table 4.1）----
    piv = df.pivot_table(index="model", columns="method", values="ex", aggfunc="mean")
    piv = piv.loc[ordered(piv.index, MODEL_ORDER), ordered(piv.columns, METHOD_ORDER)]
    piv["Model Mean"] = piv.mean(axis=1)
    piv.loc["Method Mean"] = piv.mean(axis=0)
    piv.round(3).to_csv(os.path.join(OUT, "ex_matrix.csv"), encoding="utf-8-sig")
    print("\n== Table 4.1  EX by Model × Prompt Method ==")
    print(piv.round(3).to_string())

    # ---- 3. 边际均值与极差（论文 4.2.4 的依据）----
    mm = piv.iloc[:-1, :-1].mean(axis=1)
    pm = piv.iloc[:-1, :-1].mean(axis=0)
    cell = piv.iloc[:-1, :-1]
    print("\n== 边际均值与极差（论文 4.2.4）==")
    print(f"模型极差 {mm.max() - mm.min():.3f} | 方法极差 {pm.max() - pm.min():.3f}")
    print("固定方法看模型，极差: " + ", ".join(f"{c}={cell[c].max() - cell[c].min():.3f}" for c in cell.columns))
    print("固定模型看方法，极差: " + ", ".join(f"{i}={cell.loc[i].max() - cell.loc[i].min():.3f}" for i in cell.index))
    top = cell.idxmax(axis=0).value_counts()
    print(f"各方法下 EX 最高的模型: {top.to_dict()}")

    # ---- 4. 分难度亚组（Table 4.2）----
    sub = df.pivot_table(index="difficulty", columns="method", values="ex", aggfunc="mean")
    sub = sub.loc[ordered(sub.index, DIFFICULTY_ORDER), ordered(sub.columns, METHOD_ORDER)]
    sub.round(3).to_csv(os.path.join(OUT, "subgroup_by_difficulty.csv"), encoding="utf-8-sig")
    print("\n== Table 4.2  EX by Query Difficulty × Prompt Method ==")
    print(sub.round(3).to_string())

    # ---- 5. 分模型成本（Table 4.3）----
    cost = df.groupby("model").agg(
        ex=("ex", "mean"), latency=("latency", "mean"),
        tokens_in=("input_tokens", "mean"), tokens_out=("output_tokens", "mean"),
    )
    prices, currency, checked_on = load_prices()
    cost["cost_per_1000_queries"] = [
        (r.tokens_in * prices.get(m, (0, 0))[0] + r.tokens_out * prices.get(m, (0, 0))[1]) / 1e6 * 1000
        for m, r in cost.iterrows()]
    cost = cost.loc[ordered(cost.index, MODEL_ORDER)].round(3)
    cost.to_csv(os.path.join(OUT, "cost_by_model.csv"), encoding="utf-8-sig")
    print("\n== Table 4.3  Accuracy, latency, and cost by model ==")
    print(cost.to_string())
    print(f"成本单位: {currency} / 每 1000 次查询；单价取自 config.yaml，"
          f"核对日期 {checked_on}。价格会变动，复现前请重新核对。")

    # ---- 6. 热力图（Figure 4.1）----
    fig, ax = plt.subplots(figsize=(8, 4.5))
    im = ax.imshow(cell.values, cmap="YlGn", vmin=0.5, vmax=0.86, aspect="auto")
    ax.set_xticks(range(cell.shape[1]), cell.columns)
    ax.set_yticks(range(cell.shape[0]), cell.index)
    for i in range(cell.shape[0]):
        for j in range(cell.shape[1]):
            ax.text(j, i, f"{cell.values[i, j]:.3f}", ha="center", va="center", fontsize=9)
    ax.set_title("Execution Accuracy (EX) by Model x Prompt Method")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "heatmap_ex.png"), dpi=200)

    print(f"\n分析完成，结果已写入 {OUT}/ 目录。")


if __name__ == "__main__":
    main()
