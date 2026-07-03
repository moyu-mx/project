"""新老客户与用户类型分析。"""
import matplotlib.pyplot as plt
import pandas as pd

from src.analysis import load_cleaned, save_fig


def run() -> None:
    df = load_cleaned()
    first_order = df.groupby("Customer ID")["Order-year"].min().rename("first_year")

    records = []
    for year in sorted(df["Order-year"].dropna().unique()):
        year = int(year)
        if year < 2011 or year > 2014:
            continue
        in_year = df[df["Order-year"] == year]
        for month in range(1, 13):
            m = in_year[in_year["Order-month"] == month]
            if m.empty:
                continue
            cust = m["Customer ID"].unique()
            new = sum(first_order.get(c, 9999) == year for c in cust)
            old = len(cust) - new
            records.append({"year": year, "month": month, "new": new, "old": old})
    trend = pd.DataFrame(records)
    if not trend.empty:
        agg = trend.groupby("year")[["new", "old"]].sum()
        agg.plot(kind="bar", figsize=(8, 4), stacked=True)
        plt.title("新老客户数量（按年）")
        plt.ylabel("客户数")
        save_fig("new_old_customers.png")

    seg = df.drop_duplicates("Customer ID")["Segment"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.pie(seg.values, labels=seg.index, autopct="%1.1f%%")
    ax.set_title("客户类型占比")
    save_fig("segment_share.png")

    seg_year = df.groupby(["Order-year", "Segment"])["Customer ID"].nunique().unstack(fill_value=0)
    seg_year.plot(kind="bar", figsize=(10, 5))
    plt.title("各年不同类型客户数量")
    plt.ylabel("客户数")
    save_fig("segment_yearly_count.png")

    seg_sales = df.groupby(["Order-year", "Segment"])["Sales"].sum().unstack(fill_value=0)
    seg_sales.plot(kind="bar", figsize=(10, 5))
    plt.title("各类型客户年度销售额")
    plt.ylabel("销售额")
    save_fig("segment_yearly_sales.png")
