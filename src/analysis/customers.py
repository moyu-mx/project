"""新老客户与用户类型分析。"""
import matplotlib.pyplot as plt
import pandas as pd

from src.analysis import load_cleaned, save_fig

MAIN_CATEGORIES = ["Technology", "Furniture", "Office Supplies"]
CATEGORY_CN = {
    "Technology": "科技产品",
    "Furniture": "家具产品",
    "Office Supplies": "办公用品",
}
SEGMENT_ORDER = ["Consumer", "Corporate", "Home Office"]
SEGMENT_CN = {
    "Consumer": "个人消费者",
    "Corporate": "企业客户",
    "Home Office": "居家办公",
}


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
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.pie(seg.values, labels=seg.index, autopct="%1.1f%%", startangle=90)
    ax.set_title("客户类型占比")
    ax.axis("equal")
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

    sub = df[df["Category"].isin(MAIN_CATEGORIES)]
    pivot = (
        sub.groupby(["Category", "Segment"])["Sales"]
        .sum()
        .unstack(fill_value=0)
        .reindex(MAIN_CATEGORIES)[SEGMENT_ORDER]
    )
    pivot.index = [CATEGORY_CN[c] for c in pivot.index]
    pivot.columns = [SEGMENT_CN[s] for s in pivot.columns]
    ax = pivot.plot(kind="bar", figsize=(10, 5), rot=0)
    ax.set_title("客户群体与产品类别销售额分析")
    ax.set_xlabel("产品类别")
    ax.set_ylabel("销售额")
    ax.legend(title="客户群体")
    save_fig("segment_category_sales.png")
