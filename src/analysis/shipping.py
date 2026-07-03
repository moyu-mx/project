"""发货时间与发货成本分析。"""
import matplotlib.pyplot as plt
import pandas as pd

from src.analysis import load_cleaned, save_fig


def run() -> pd.DataFrame:
    df = load_cleaned()
    ship = (
        df.groupby(["Ship-year", "Ship-month"])
        .agg(total_sales=("Sales", "sum"), shipping_cost=("Shipping Cost", "sum"))
        .reset_index()
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    for year in sorted(df["Ship-year"].dropna().unique()):
        s = ship[ship["Ship-year"] == year]
        ax.plot(s["Ship-month"], s["shipping_cost"], marker="o", label=str(int(year)))
    ax.set_title("各年发货成本月度趋势")
    ax.set_xlabel("月份")
    ax.set_ylabel("发货成本")
    ax.legend()
    save_fig("shipping_cost_trend.png")
    return ship
