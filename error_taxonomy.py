"""
error_taxonomy.py — reproducible classification of failed queries.

Every query that did not produce the gold result set is assigned to exactly one
category by a deterministic rule applied to the execution log. No manual coding
is involved, so the counts reported in Section 4.3 of the report can be
regenerated from the published files:

    python error_taxonomy.py

Inputs
    results/raw/*.jsonl        one record per query (5,000 in total)
    results/revalidated.csv    corrected verdicts produced by reevaluate.py

Outputs
    results/error_classification.csv   one row per query with its category
    stdout                             the contingency table used in Table 4.4

Classification rule, applied in this order:
    1. correct                  corrected verdict ex == 1
    2. api_error                the API call itself failed
    3. security_rejection       the safety module refused the statement
                                (empty_sql | multiple_statements | not_select)
    4. syntax_error             execution raised an SQLite message containing
                                "syntax error", "unrecognized token" or
                                "incomplete input"
    5. schema_reference_error   execution raised "no such column" / "no such table"
    6. other_execution_error    any remaining execution failure
    7. result_mismatch          statement executed but returned a different
                                result set from the gold SQL
"""

import json
import os
import sys

import pandas as pd

RAW_DIR = os.path.join("results", "raw")
REVALIDATED = os.path.join("results", "revalidated.csv")
OUT_CSV = os.path.join("results", "error_classification.csv")

METHOD_ORDER = ["zero", "few", "sl", "cot", "cot_sl"]
CATEGORY_ORDER = [
    "security_rejection",
    "syntax_error",
    "schema_reference_error",
    "other_execution_error",
    "result_mismatch",
]

SYNTAX_MARKERS = ("syntax error", "unrecognized token", "incomplete input")
SCHEMA_MARKERS = ("no such column", "no such table")


def nonempty(value):
    return isinstance(value, str) and value.strip() != ""


def load_raw(raw_dir):
    records = []
    for name in sorted(os.listdir(raw_dir)):
        if not name.endswith(".jsonl"):
            continue
        with open(os.path.join(raw_dir, name), encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
    return pd.DataFrame(records)


def classify(row):
    if row["ex_corrected"] == 1:
        return "correct"
    if nonempty(row["api_error"]):
        return "api_error"
    if row["safety"] != "passed":
        return "security_rejection"
    err = row["exec_error"]
    if nonempty(err):
        low = err.lower()
        if any(marker in low for marker in SYNTAX_MARKERS):
            return "syntax_error"
        if any(marker in low for marker in SCHEMA_MARKERS):
            return "schema_reference_error"
        return "other_execution_error"
    return "result_mismatch"


def main():
    if not os.path.isdir(RAW_DIR) or not os.path.isfile(REVALIDATED):
        sys.exit("Run this script from the repository root.")

    raw = load_raw(RAW_DIR)
    corrected = pd.read_csv(REVALIDATED)[["model", "method", "case_id", "ex"]]
    corrected = corrected.rename(columns={"ex": "ex_corrected"})

    data = raw.merge(corrected, on=["model", "method", "case_id"], how="left")
    if data["ex_corrected"].isna().any():
        sys.exit("Some raw records have no corrected verdict; check the inputs.")

    data["category"] = data.apply(classify, axis=1)

    keep = ["model", "method", "case_id", "difficulty", "safety",
            "exec_error", "ex_corrected", "category"]
    data[keep].to_csv(OUT_CSV, index=False, encoding="utf-8")

    total = len(data)
    correct = int((data["category"] == "correct").sum())
    failed = data[~data["category"].isin(["correct"])]

    print(f"records: {total}   correct: {correct}   "
          f"accuracy: {correct / total:.4f}   failed: {len(failed)}")
    print()

    table = failed.pivot_table(index="category", columns="method",
                               values="case_id", aggfunc="count", fill_value=0)
    table = table.reindex(index=[c for c in CATEGORY_ORDER if c in table.index],
                          columns=METHOD_ORDER, fill_value=0)
    table["total"] = table.sum(axis=1)
    table.loc["total"] = table.sum(axis=0)
    print(table.to_string())
    print()

    detail = failed[failed["category"] == "security_rejection"]
    if len(detail):
        print("security_rejection, by safety verdict:")
        print(detail.pivot_table(index="safety", columns="method",
                                 values="case_id", aggfunc="count",
                                 fill_value=0).reindex(columns=METHOD_ORDER,
                                                       fill_value=0).to_string())
        print()

    mismatch = failed[failed["category"] == "result_mismatch"]
    print("result_mismatch, by difficulty:")
    print(mismatch.groupby("difficulty").size().to_string())
    print()
    print(f"written: {OUT_CSV}")


if __name__ == "__main__":
    main()
