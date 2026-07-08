"""数据分析公共工具。"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from src.config import CHARTS_DIR, DATA_CLEANED
from src.db.connection import get_engine


def _load_from_db() -> pd.DataFrame:
    """从 SQLite 重建预测/分析所需的清洗后字段。"""
    sql = """
    SELECT
        order_date AS "Order Date",
        ship_date AS "Ship Date",
        customer_id AS "Customer ID",
        market AS "Market",
        sales AS "Sales",
        quantity AS "Quantity",
        discount AS "Discount",
        profit AS "Profit",
        order_year AS "Order-year",
        order_month AS "Order-month",
        order_quarter AS "Order-quarter"
    FROM orders
    """
    with get_engine().connect() as conn:
        df = pd.read_sql(text(sql), conn)
    for col in ("Order Date", "Ship Date"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def load_cleaned() -> pd.DataFrame:
    if DATA_CLEANED.is_file():
        return pd.read_csv(DATA_CLEANED, parse_dates=["Order Date", "Ship Date"])
    return _load_from_db()


def save_fig(name: str) -> str:
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHARTS_DIR / name
    try:
        plt.tight_layout()
    except Exception:
        plt.subplots_adjust(hspace=0.4, wspace=0.3)
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()
    return str(path)
