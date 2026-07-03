"""销量与淡旺季分析。"""
import matplotlib.pyplot as plt
import pandas as pd

from src.analysis import load_cleaned, save_fig


def run() -> pd.DataFrame:
    df = load_cleaned()
    sub = df[df["Order-year"].between(2011, 2014)]
    qty = sub.pivot_table(
        index="Order-month", columns="Order-year", values="Quantity", aggfunc="sum"
    )
    from src.config import CHARTS_DIR

    qty.to_csv(CHARTS_DIR.parent / "monthly_quantity.csv")

    monthly_sales = (
        sub.groupby(["Order-year", "Order-month"])["Sales"]
        .sum()
        .reset_index()
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    for year in sorted(sub["Order-year"].unique()):
        s = monthly_sales[monthly_sales["Order-year"] == year]
        ax.plot(s["Order-month"], s["Sales"], marker="o", label=str(int(year)))
    ax.set_title("月度销售额趋势（淡旺季）")
    ax.set_xlabel("月份")
    ax.set_ylabel("销售额")
    ax.legend()
    save_fig("seasonality_sales.png")
    return qty
