"""RFM 客户价值分析（2014）。"""
import matplotlib.pyplot as plt
import pandas as pd

from src.analysis import load_cleaned, save_fig

SEGMENT_MAP = {
    (1, 1, 1): "重要价值客户",
    (0, 1, 1): "重要保持客户",
    (1, 0, 1): "重要发展客户",
    (0, 0, 1): "重要挽留客户",
    (1, 1, 0): "一般价值客户",
    (0, 1, 0): "一般保持客户",
    (1, 0, 0): "一般发展客户",
    (0, 0, 0): "一般挽留客户",
}


def run(snapshot_year: int = 2014) -> pd.DataFrame:
    df = load_cleaned()
    sub = df[df["Order-year"] == snapshot_year].copy()
    ref = pd.Timestamp(f"{snapshot_year}-12-31")

    rfm = sub.groupby("Customer ID").agg(
        recency=("Order Date", lambda s: (ref - s.max()).days),
        frequency=("Order ID", "count"),
        monetary=("Sales", "sum"),
    )
    rfm["r_score"] = (rfm["recency"] < rfm["recency"].mean()).astype(int)
    rfm["f_score"] = (rfm["frequency"] > rfm["frequency"].mean()).astype(int)
    rfm["m_score"] = (rfm["monetary"] > rfm["monetary"].mean()).astype(int)
    rfm["value_segment"] = [
        SEGMENT_MAP.get((r, f, m), "未知")
        for r, f, m in zip(rfm["r_score"], rfm["f_score"], rfm["m_score"])
    ]

    counts = rfm["value_segment"].value_counts()
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.pie(counts.values, labels=counts.index, autopct="%1.1f%%")
    ax.set_title(f"{snapshot_year} 年 RFM 客户价值分布")
    save_fig("rfm_distribution.png")
    return rfm.reset_index()
