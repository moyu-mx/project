"""数据洞察 Agent 取数：聚合 KPI、品类/区域波动、复购等指标。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from src.db.connection import get_engine


def _query(sql: str, params: dict | None = None) -> list[dict[str, Any]]:
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), params or {})
        if not result.returns_rows:
            return []
        keys = list(result.keys())
        return [dict(zip(keys, row)) for row in result.fetchall()]


def _pct_change(cur: float, prev: float) -> float | None:
    if prev == 0:
        return None
    return (cur - prev) / prev * 100


def fetch_insight_context(year: int, month: int) -> dict[str, Any]:
    """构建指定年月的洞察分析上下文。"""
    prev_y, prev_m = (year, month - 1) if month > 1 else (year - 1, 12)

    def _period(y: int, m: int) -> dict[str, float | int]:
        rows = _query(
            "SELECT COALESCE(SUM(sales),0) AS sales, COALESCE(SUM(profit),0) AS profit, "
            "COUNT(DISTINCT order_id) AS orders, COUNT(DISTINCT customer_id) AS customers, "
            "COALESCE(AVG(discount),0) AS avg_discount "
            "FROM orders WHERE order_year=:y AND order_month=:m",
            {"y": y, "m": m},
        )
        r = rows[0] if rows else {}
        sales = float(r.get("sales") or 0)
        customers = int(r.get("customers") or 0)
        return {
            "sales": sales,
            "profit": float(r.get("profit") or 0),
            "orders": int(r.get("orders") or 0),
            "customers": customers,
            "avg_discount": float(r.get("avg_discount") or 0),
            "aov": sales / max(customers, 1),
        }

    cur = _period(year, month)
    prev = _period(prev_y, prev_m)
    yoy = _period(year - 1, month)

    categories = _query(
        "SELECT p.category, SUM(o.sales) AS sales, SUM(o.profit) AS profit "
        "FROM orders o JOIN products p ON o.product_id=p.product_id "
        "WHERE o.order_year=:y AND o.order_month=:m GROUP BY p.category",
        {"y": year, "m": month},
    )
    prev_categories = {
        r["category"]: float(r["sales"])
        for r in _query(
            "SELECT p.category, SUM(o.sales) AS sales FROM orders o "
            "JOIN products p ON o.product_id=p.product_id "
            "WHERE o.order_year=:y AND o.order_month=:m GROUP BY p.category",
            {"y": prev_y, "m": prev_m},
        )
    }
    category_mom: list[dict[str, Any]] = []
    for row in categories:
        cat = row["category"]
        sales = float(row["sales"])
        prev_sales = prev_categories.get(cat, 0.0)
        chg = _pct_change(sales, prev_sales)
        category_mom.append({
            "category": cat,
            "sales": sales,
            "profit": float(row["profit"]),
            "mom_pct": chg,
            "prev_sales": prev_sales,
        })
    category_mom.sort(key=lambda x: x["mom_pct"] if x["mom_pct"] is not None else 0)

    regions = _query(
        "SELECT market, SUM(sales) AS sales, SUM(profit) AS profit, "
        "AVG(discount) AS avg_discount, COUNT(DISTINCT customer_id) AS customers "
        "FROM orders WHERE order_year=:y AND order_month=:m "
        "GROUP BY market ORDER BY sales DESC",
        {"y": year, "m": month},
    )
    all_discounts = [float(r["avg_discount"]) for r in regions if r.get("avg_discount") is not None]
    avg_discount_all = sum(all_discounts) / len(all_discounts) if all_discounts else 0.0

    region_stats: list[dict[str, Any]] = []
    for r in regions:
        sales = float(r["sales"])
        profit = float(r["profit"])
        region_stats.append({
            "market": r["market"],
            "sales": sales,
            "profit": profit,
            "profit_rate": profit / sales if sales else 0,
            "avg_discount": float(r["avg_discount"] or 0),
            "customers": int(r["customers"] or 0),
            "discount_vs_avg": float(r["avg_discount"] or 0) - avg_discount_all,
        })

    repurchase = _query(
        "SELECT o.market, "
        "COUNT(DISTINCT o.customer_id) AS active, "
        "COUNT(DISTINCT CASE WHEN fy.first_year < :y THEN o.customer_id END) AS repeat_customers "
        "FROM orders o "
        "JOIN (SELECT customer_id, MIN(order_year) AS first_year FROM orders GROUP BY customer_id) fy "
        "ON o.customer_id=fy.customer_id "
        "WHERE o.order_year=:y AND o.order_month=:m "
        "GROUP BY o.market",
        {"y": year, "m": month},
    )
    repurchase_prev = {
        r["market"]: {
            "rate": int(r["repeat_customers"]) / max(int(r["active"]), 1),
            "active": int(r["active"]),
        }
        for r in _query(
            "SELECT o.market, COUNT(DISTINCT o.customer_id) AS active, "
            "COUNT(DISTINCT CASE WHEN fy.first_year < :y THEN o.customer_id END) AS repeat_customers "
            "FROM orders o "
            "JOIN (SELECT customer_id, MIN(order_year) AS first_year FROM orders GROUP BY customer_id) fy "
            "ON o.customer_id=fy.customer_id "
            "WHERE o.order_year=:y AND o.order_month=:m GROUP BY o.market",
            {"y": prev_y, "m": prev_m},
        )
    }
    repurchase_stats: list[dict[str, Any]] = []
    for r in repurchase:
        market = r["market"]
        active = int(r["active"] or 0)
        returning = int(r["repeat_customers"] or 0)
        rate = returning / max(active, 1)
        prev_rate = repurchase_prev.get(market, {}).get("rate")
        repurchase_stats.append({
            "market": market,
            "repurchase_rate": rate,
            "active_customers": active,
            "repurchase_mom_pp": (rate - prev_rate) * 100 if prev_rate is not None else None,
            "sales_rank": next((i + 1 for i, x in enumerate(region_stats) if x["market"] == market), 99),
        })

    return {
        "period_label": f"{year}年{month}月",
        "year": year,
        "month": month,
        "current": cur,
        "previous": prev,
        "yoy": yoy,
        "mom_pct": {
            "sales": _pct_change(cur["sales"], prev["sales"]),
            "profit": _pct_change(cur["profit"], prev["profit"]),
            "orders": _pct_change(cur["orders"], prev["orders"]),
        },
        "category_mom": category_mom,
        "regions": region_stats,
        "avg_discount_all": avg_discount_all,
        "repurchase": repurchase_stats,
    }
