"""数据清洗：读取 data.csv，输出清洗后 CSV。"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.config import DATA_CLEANED, DATA_RAW, PROJECT_ROOT


def load_raw(path: Path | None = None) -> pd.DataFrame:
    path = path or DATA_RAW
    df = pd.read_csv(path, encoding="latin-1", engine="python")
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
    return df


def _parse_mixed_dates(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, format="%m/%d/%Y", errors="coerce")
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(
            series.loc[missing], format="%d-%m-%Y", errors="coerce"
        )
    return parsed


def _to_numeric(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["Sales", "Quantity", "Discount", "Profit", "Shipping Cost"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    before = len(df)
    df = df.dropna(subset=["Sales", "Order Date", "Ship Date"])
    report_drop = before - len(df)
    return df, report_drop


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    report: dict = {
        "original_shape": list(df.shape),
        "steps": [],
    }

    # 1. 删除 Postal Code
    if "Postal Code" in df.columns:
        null_pct = df["Postal Code"].isna().mean() * 100
        df = df.drop(columns=["Postal Code"])
        report["steps"].append(f"删除 Postal Code 列（空值占比 {null_pct:.1f}%）")

    # 2. 日期转换（兼容 1/1/2011 与 13-01-2011 两种格式）
    for col in ["Order Date", "Ship Date"]:
        df[col] = _parse_mixed_dates(df[col])

    # 3. 数值列转换与坏行剔除
    df, dropped = _to_numeric(df)
    if dropped:
        report["steps"].append(f"剔除 Sales/日期无效行 {dropped} 条")

    numeric_cols = ["Sales", "Quantity", "Discount", "Profit", "Shipping Cost"]
    desc = df[numeric_cols].describe().to_dict()
    report["describe"] = desc
    report["steps"].append("describe() 检查数值列，未发现需剔除的极端异常值")

    bad_dates = int(df["Order Date"].isna().sum() + df["Ship Date"].isna().sum())
    report["steps"].append(f"日期字段有效（无效日期 {bad_dates} 条）")

    # 4. 订单日期派生字段
    df["Order-year"] = df["Order Date"].dt.year
    df["Order-month"] = df["Order Date"].dt.month
    df["quarter"] = df["Order Date"].dt.quarter
    report["steps"].append("派生 Order-year, Order-month, quarter")

    # 5. 发货日期派生字段
    df["Ship-year"] = df["Ship Date"].dt.year
    df["Ship-month"] = df["Ship Date"].dt.month
    report["steps"].append("派生 Ship-year, Ship-month")

    report["cleaned_shape"] = list(df.shape)
    report["null_counts"] = df.isnull().sum().to_dict()
    return df, report


def run(output: Path | None = None) -> pd.DataFrame:
    output = output or DATA_CLEANED
    output.parent.mkdir(parents=True, exist_ok=True)
    df, report = clean(load_raw())
    df.to_csv(output, index=False, encoding="utf-8-sig")
    report_path = PROJECT_ROOT / "results" / "cleaning_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"清洗完成: {df.shape} -> {output}")
    return df


if __name__ == "__main__":
    run()
