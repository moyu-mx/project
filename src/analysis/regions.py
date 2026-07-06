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

    sub = df[(df["Order-year"] >= 2011) & (df["Order-year"] <= 2014)]
    top6 = sub.groupby("Market")["Sales"].sum().nlargest(6).index.tolist()
    yearly = (
        sub[sub["Market"].isin(top6)]
        .groupby(["Order-year", "Market"])["Sales"]
        .sum()
        .unstack(fill_value=0)
        .reindex(columns=top6)
    )
    yearly.index = yearly.index.astype(int)
    ax = yearly.plot(kind="bar", figsize=(10, 5), rot=0)
    ax.set_title("前六区域年度销售额（2011-2014）")
    ax.set_xlabel("年份")
    ax.set_ylabel("销售额")
    ax.legend(title="区域", bbox_to_anchor=(1.02, 1), loc="upper left")
    save_fig("region_yearly_sales_top6.png")
