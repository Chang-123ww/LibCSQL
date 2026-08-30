# -*- coding: utf-8 -*-
"""
sensitivity_cleaning.py — 复现论文 Table 4.1（输出清理规则的敏感性对照）

论文 §3.3.7 定义的清理规则不是预先设定的，而是初评发现 JSON 残渣后才写的。
因此 §4.2.1 给出清理前后的完整对照，使该规则对每一个被引用量的影响都可检查。
本脚本从 results/revalidated.csv 直接重算这张表：
    ex_orig = 清理前的判定，ex = 清理后的判定（清理规则对全部 5,000 条一律适用）。

用法：
  python -m src.db_setup --db data/library.db     # 若尚未生成测试库
  python reevaluate.py                            # 生成 results/revalidated.csv
  python analysis/sensitivity_cleaning.py

输出：
  控制台打印论文 Table 4.1 的全部行
  results/sensitivity_cleaning.csv （同一张表，便于引用）
"""
import os
import sys

import pandas as pd

SRC = "results/revalidated.csv"
OUT = "results/sensitivity_cleaning.csv"
METHODS = ["zero", "few", "cot", "sl", "cot_sl"]
LABEL = {"zero": "Zero", "few": "Few", "cot": "CoT", "sl": "SL", "cot_sl": "CoT+SL"}
SHORT = {"qwen3.7-plus": "qwen3.7-plus", "doubao-seed-2-0-mini": "doubao-2.0-mini",
         "ernie-4.5-turbo-32k": "ernie-4.5-turbo", "glm-4.7-flashX": "glm-4.7-flashX",
         "qwen2.5-coder:7b": "qwen2.5-coder:7b"}


def marginals(df, col):
    piv = df.pivot_table(index="model", columns="method", values=col, aggfunc="mean")[METHODS]
    models = {SHORT.get(m, m): piv.loc[m].mean() for m in piv.index}
    methods = {m: df[df.method == m][col].mean() for m in METHODS}
    return piv, models, methods


def order_str(d):
    return " > ".join(LABEL.get(k, k) for k in sorted(d, key=d.get, reverse=True))


def main():
    if not os.path.exists(SRC):
        sys.exit(f"找不到 {SRC}，请先运行 python reevaluate.py")
    df = pd.read_csv(SRC)
    pb, mob, meb = marginals(df, "ex_orig")   # before cleaning
    pa, moa, mea = marginals(df, "ex")        # after cleaning

    up = int(((df.ex_orig == 0) & (df.ex == 1)).sum())
    down = int(((df.ex_orig == 1) & (df.ex == 0)).sum())
    changed = [(m, me) for m in pa.index for me in METHODS
               if abs(pa.loc[m, me] - pb.loc[m, me]) > 1e-12]

    rows = [("Overall execution accuracy (5,000 records)",
             f"{df.ex_orig.mean():.3f}", f"{df.ex.mean():.3f}",
             f"{df.ex.mean()-df.ex_orig.mean():+.3f}")]
    for m, me in changed:
        rows.append((f"{SHORT.get(m, m)} x {LABEL[me]}",
                     f"{pb.loc[m, me]:.3f}", f"{pa.loc[m, me]:.3f}",
                     f"{pa.loc[m, me]-pb.loc[m, me]:+.3f}"))
    rows.append((f"The other {25-len(changed)} model x method cells", "unchanged", "unchanged", "0.000"))
    for m in sorted({SHORT.get(m, m) for m, _ in changed}):
        rows.append((f"Model mean, {m}", f"{mob[m]:.3f}", f"{moa[m]:.3f}", f"{moa[m]-mob[m]:+.3f}"))
    for me in sorted({me for _, me in changed}, key=METHODS.index):
        rows.append((f"Method mean, {LABEL[me]}", f"{meb[me]:.3f}", f"{mea[me]:.3f}", f"{mea[me]-meb[me]:+.3f}"))
    rb, ra = max(mob.values())-min(mob.values()), max(moa.values())-min(moa.values())
    hb, ha = max(meb.values())-min(meb.values()), max(mea.values())-min(mea.values())
    rows += [("Range across the five models", f"{rb:.3f}", f"{ra:.3f}", f"{ra-rb:+.3f}"),
             ("Range across the five prompting methods", f"{hb:.3f}", f"{ha:.3f}", f"{ha-hb:+.3f}"),
             ("Ordering of the five models",
              " > ".join(sorted(mob, key=mob.get, reverse=True)),
              "identical" if sorted(mob, key=mob.get, reverse=True) == sorted(moa, key=moa.get, reverse=True) else order_str(moa),
              "none" if sorted(mob, key=mob.get, reverse=True) == sorted(moa, key=moa.get, reverse=True) else "changed"),
             ("Ordering of the five methods", order_str(meb), order_str(mea),
              "unchanged" if order_str(meb) == order_str(mea) else "last two positions exchanged"),
             ("Records moving 0 -> 1 / 1 -> 0", "-", f"{up} / {down}", "-")]

    out = pd.DataFrame(rows, columns=["Quantity", "Before cleaning", "After cleaning", "Change"])
    print("Table 4.1  Sensitivity of execution accuracy to the output-cleaning rule\n")
    print(out.to_string(index=False))
    print("\nNote. Cleaning is applied to all 5,000 records of all 25 conditions, in both directions,")
    print("so the 1 -> 0 count is an empirical result and not a consequence of the procedure.")
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\n已写出: {OUT}")


if __name__ == "__main__":
    main()
