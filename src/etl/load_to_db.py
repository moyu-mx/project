"""ETL：清洗后 CSV 入库 + 预计算汇总表。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.analysis.rfm import SEGMENT_MAP, run as run_rfm
from src.config import DATA_CLEANED, DB_PATH, PROJECT_ROOT
from src.db.connection import get_engine, init_schema

SEGMENT_MAP_LOCAL = SEGMENT_MAP


def _load_df() -> pd.DataFrame:
    if not DATA_CLEANED.exists():
        from src.cleaning.clean_data import run as clean

        clean()
    return pd.read_csv(DATA_CLEANED, parse_dates=["Order Date", "Ship Date"])


def load_dimensions_and_orders(df: pd.DataFrame, engine) -> None:
    customers = (
        df[["Customer ID", "Customer Name", "Segment", "City", "State", "Country"]]
        .drop_duplicates("Customer ID")
        .rename(
            columns={
                "Customer ID": "customer_id",
                "Customer Name": "customer_name",
                "Segment": "segment",
                "City": "city",
                "State": "state",
                "Country": "country",
            }
        )
        .fillna("")
    )
    products = (
        df[["Product ID", "Product Name", "Category", "Sub-Category"]]
        .drop_duplicates("Product ID")
        .rename(
            columns={
                "Product ID": "product_id",
                "Product Name": "product_name",
                "Category": "category",
                "Sub-Category": "sub_category",
            }
        )
    )
    regions = (
        df[["Market", "Region"]]
        .drop_duplicates("Market")
        .rename(columns={"Market": "market", "Region": "region"})
    )
    orders = df.rename(
        columns={
            "Row ID": "row_id",
            "Order ID": "order_id",
            "Order Date": "order_date",
            "Ship Date": "ship_date",
            "Ship Mode": "ship_mode",
            "Customer ID": "customer_id",
            "Product ID": "product_id",
            "Market": "market",
            "Sales": "sales",
            "Quantity": "quantity",
            "Discount": "discount",
            "Profit": "profit",
            "Shipping Cost": "shipping_cost",
            "Order Priority": "order_priority",
            "Order-year": "order_year",
            "Order-month": "order_month",
            "quarter": "order_quarter",
            "Ship-year": "ship_year",
            "Ship-month": "ship_month",
        }
    )
    orders["order_date"] = orders["order_date"].dt.strftime("%Y-%m-%d")
    orders["ship_date"] = orders["ship_date"].dt.strftime("%Y-%m-%d")
    for col, default in [
        ("sales", 0), ("quantity", 0), ("discount", 0),
        ("profit", 0), ("shipping_cost", 0),
    ]:
        orders[col] = orders[col].fillna(default)
    orders["order_priority"] = orders["order_priority"].fillna("")
    orders["ship_year"] = orders["ship_year"].fillna(0).astype(int)
    orders["ship_month"] = orders["ship_month"].fillna(0).astype(int)

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM orders"))
        conn.execute(text("DELETE FROM customers"))
        conn.execute(text("DELETE FROM products"))
        conn.execute(text("DELETE FROM regions"))
    customers.to_sql("customers", engine, if_exists="append", index=False)
    products.to_sql("products", engine, if_exists="append", index=False)
    regions.to_sql("regions", engine, if_exists="append", index=False)
    orders[
        [
            "row_id", "order_id", "order_date", "ship_date", "ship_mode",
            "customer_id", "product_id", "market", "sales", "quantity",
            "discount", "profit", "shipping_cost", "order_priority",
            "order_year", "order_month", "order_quarter", "ship_year", "ship_month",
        ]
    ].to_sql("orders", engine, if_exists="append", index=False)


def load_aggregates(df: pd.DataFrame, engine) -> None:
    yearly = df.groupby("Order-year").agg(
        total_sales=("Sales", "sum"),
        total_profit=("Profit", "sum"),
        total_quantity=("Quantity", "sum"),
        customer_count=("Customer ID", "nunique"),
    )
    yearly["avg_order_value"] = yearly["total_sales"] / yearly["customer_count"]
    yearly["sales_growth_rate"] = yearly["total_sales"].pct_change()
    yearly = yearly.reset_index().rename(columns={"Order-year": "order_year"})

    region_year = (
        df.groupby(["Market", "Order-year"])
        .agg(total_sales=("Sales", "sum"), total_profit=("Profit", "sum"))
        .reset_index()
        .rename(columns={"Market": "market", "Order-year": "order_year"})
    )
    month_agg = (
        df.groupby(["Order-year", "Order-month"])
        .agg(
            total_sales=("Sales", "sum"),
            total_quantity=("Quantity", "sum"),
            total_profit=("Profit", "sum"),
        )
        .reset_index()
        .rename(columns={"Order-year": "order_year", "Order-month": "order_month"})
    )
    seg_cat = (
        df.groupby(["Segment", "Category"])["Sales"]
        .sum()
        .reset_index()
        .rename(columns={"Segment": "segment", "Category": "category", "Sales": "total_sales"})
    )

    rfm_df = run_rfm(2014)
    rfm_db = rfm_df.rename(
        columns={
            "Customer ID": "customer_id",
            "recency": "recency_days",
            "frequency": "frequency",
            "monetary": "monetary",
            "r_score": "r_score",
            "f_score": "f_score",
            "m_score": "m_score",
            "value_segment": "value_segment",
        }
    )
    rfm_db["snapshot_year"] = 2014

    with engine.begin() as conn:
        for t in [
            "agg_sales_by_year",
            "agg_sales_by_region_year",
            "agg_sales_by_month",
            "agg_segment_category",
            "customer_rfm",
        ]:
            conn.execute(text(f"DELETE FROM {t}"))

    yearly.to_sql("agg_sales_by_year", engine, if_exists="append", index=False)
    region_year.to_sql("agg_sales_by_region_year", engine, if_exists="append", index=False)
    month_agg.to_sql("agg_sales_by_month", engine, if_exists="append", index=False)
    seg_cat.to_sql("agg_segment_category", engine, if_exists="append", index=False)
    rfm_db[
        [
            "snapshot_year", "customer_id", "recency_days", "frequency", "monetary",
            "r_score", "f_score", "m_score", "value_segment",
        ]
    ].to_sql("customer_rfm", engine, if_exists="append", index=False)


def validate(df: pd.DataFrame, engine) -> dict:
    with engine.connect() as conn:
        order_count = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
        sales_sum = conn.execute(text("SELECT SUM(sales) FROM orders")).scalar()
    report = {
        "csv_rows": len(df),
        "db_orders": order_count,
        "rows_match": order_count == len(df),
        "csv_sales_sum": round(float(df["Sales"].sum()), 2),
        "db_sales_sum": round(float(sales_sum), 2),
        "sales_match": abs(float(df["Sales"].sum()) - float(sales_sum)) < 0.1,
        "order_date_nulls": int(df["Order Date"].isna().sum()),
    }
    path = PROJECT_ROOT / "results" / "etl_validation.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def run() -> dict:
    """清空表后重新入库，不删除 db 文件（避免 Web 占用时 WinError 32）。"""
    engine = get_engine()
    init_schema(engine)
    df = _load_df()
    load_dimensions_and_orders(df, engine)
    load_aggregates(df, engine)
    report = validate(df, engine)
    print("ETL 校验:", report)
    return report


if __name__ == "__main__":
    run()
