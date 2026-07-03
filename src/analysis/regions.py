"""地区分店分析。"""
import matplotlib.pyplot as plt
import pandas as pd

from src.analysis import load_cleaned, save_fig


def _group_small_markets(market_sales: pd.Series, threshold_pct: float = 1.0) -> pd.Series:
    """占比小于 threshold_pct 的区域合并为「其他」。"""
    total = market_sales.sum()
    pct = market_sales / total * 100
    main = market_sales[pct >= threshold_pct]
    other_sum = market_sales[pct < threshold_pct].sum()
    if other_sum > 0:
        main = pd.concat([main, pd.Series({"其他": other_sum})])
    return main.sort_values(ascending=False)


def run() -> None:
    df = load_cleaned()
    market_sales = df.groupby("Market")["Sales"].sum()
    pie_data = _group_small_markets(market_sales)

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(pie_data.values, labels=pie_data.index, autopct="%1.1f%%")
    ax.set_title("各区域销售额占比")
    save_fig("region_share.png")
