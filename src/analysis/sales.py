"""销售额、增长率、客单价分析。"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analysis import load_cleaned, save_fig


def run() -> dict:
    df = load_cleaned()
    years = sorted(df["Order-year"].dropna().unique())
    years = [int(y) for y in years if 2011 <= y <= 2014]

    # 年度销售额
    yearly_sales = df.groupby("Order-year")["Sales"].sum()
    yearly_sales = yearly_sales.loc[years] if years else yearly_sales
    growth = yearly_sales.pct_change(fill_method=None) * 100

    # 客单价
    aov = df.groupby("Order-year").apply(
        lambda g: g["Sales"].sum() / g["Customer ID"].nunique(),
        include_groups=False,
    ).reindex(years)

    fig, ax1 = plt.subplots(figsize=(10, 5))
    x = np.arange(len(years))
    bars = ax1.bar(x, yearly_sales.values, color="cornflowerblue", label="销售额")
    ax1.set_xticks(x)
    ax1.set_xticklabels([str(y) for y in years])
    ax1.set_ylabel("销售额")
    ax1.set_title("年度销售额与增长率")
    ax2 = ax1.twinx()
    ax2.plot(x, growth.values, color="orangered", marker="o", label="增长率%")
    ax2.set_ylabel("增长率 (%)")
    save_fig("sales_growth.png")

    fig2, ax = plt.subplots(figsize=(8, 4))
    ax.plot(years, aov.values, marker="s", color="green")
    ax.set_title("年度客单价趋势")
    ax.set_xlabel("年份")
    ax.set_ylabel("客单价")
    save_fig("avg_order_value.png")

    return {"yearly_sales": yearly_sales, "growth": growth, "aov": aov}
