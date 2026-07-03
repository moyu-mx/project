"""利润分析。"""
import matplotlib.pyplot as plt
import pandas as pd

from src.analysis import save_fig
from src.analysis import load_cleaned


def run() -> pd.DataFrame:
    df = load_cleaned()
    monthly = (
        df.groupby(["Order-year", "Order-month"])["Profit"]
        .sum()
        .reset_index()
    )
    years = sorted(df["Order-year"].dropna().unique())
    years = [y for y in years if 2011 <= y <= 2014]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()
    for i, year in enumerate(years[:4]):
        sub = monthly[monthly["Order-year"] == year]
        axes[i].bar(sub["Order-month"], sub["Profit"], color="steelblue")
        axes[i].set_title(f"{int(year)} 年月度利润")
        axes[i].set_xlabel("月份")
        axes[i].set_ylabel("利润")
    save_fig("profit_by_month.png")
    return monthly
