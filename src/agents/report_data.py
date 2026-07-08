"""报告取数：从 SQLite 聚合经营/商品/用户指标。"""
from __future__ import annotations

from dataclasses import dataclass
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


def _scalar(sql: str, params: dict | None = None) -> float | int | None:
    rows = _query(sql, params)
    if not rows:
        return None
    val = next(iter(rows[0].values()))
    return val


def _month_bounds(year: int, month: int) -> tuple[int, int, int, int]:
    prev_y, prev_m = (year, month - 1) if month > 1 else (year - 1, 12)
    yoy_y = year - 1
    return prev_y, prev_m, yoy_y, month


@dataclass
class PeriodMetrics:
    sales: float = 0.0
    profit: float = 0.0
    quantity: int = 0
    orders: int = 0
    customers: int = 0

    @property
    def aov(self) -> float:
        return self.sales / max(self.customers, 1)


def _period_metrics(
    year: int,
    month: int | None = None,
    day: int | None = None,
    week: int | None = None,
) -> PeriodMetrics:
    clauses = ["order_year = :y"]
    params: dict[str, Any] = {"y": year}
    if month is not None:
        clauses.append("order_month = :m")
        params["m"] = month
    if day is not None:
        clauses.append("CAST(strftime('%d', order_date) AS INTEGER) = :d")
        params["d"] = day
    if week is not None and month is not None:
        start_day = (week - 1) * 7 + 1
        end_day = min(week * 7, 31)
        clauses.append("CAST(strftime('%d', order_date) AS INTEGER) BETWEEN :wd0 AND :wd1")
        params["wd0"] = start_day
        params["wd1"] = end_day
    where = " AND ".join(clauses)
    row = _query(
        f"SELECT COALESCE(SUM(sales),0) AS sales, COALESCE(SUM(profit),0) AS profit, "
        f"COALESCE(SUM(quantity),0) AS quantity, COUNT(DISTINCT order_id) AS orders, "
        f"COUNT(DISTINCT customer_id) AS customers FROM orders WHERE {where}",
        params,
    )
    if not row:
        return PeriodMetrics()
    r = row[0]
    return PeriodMetrics(
        sales=float(r["sales"]),
        profit=float(r["profit"]),
        quantity=int(r["quantity"]),
        orders=int(r["orders"]),
        customers=int(r["customers"]),
    )


def _pct_change(current: float, base: float) -> str:
    if base == 0:
        return "—"
    return f"{(current - base) / base * 100:+.1f}%"


def fetch_monthly_business(year: int, month: int) -> dict[str, Any]:
    prev_y, prev_m, yoy_y, _ = _month_bounds(year, month)
    cur = _period_metrics(year, month)
    prev = _period_metrics(prev_y, prev_m)
    yoy = _period_metrics(yoy_y, month)

    daily = _query(
        "SELECT CAST(strftime('%d', order_date) AS INTEGER) AS day, "
        "SUM(sales) AS sales, SUM(profit) AS profit, COUNT(DISTINCT order_id) AS orders "
        "FROM orders WHERE order_year=:y AND order_month=:m "
        "GROUP BY day ORDER BY day",
        {"y": year, "m": month},
    )
    regions = _query(
        "SELECT market, SUM(sales) AS sales, SUM(profit) AS profit "
        "FROM orders WHERE order_year=:y AND order_month=:m "
        "GROUP BY market ORDER BY sales DESC",
        {"y": year, "m": month},
    )
    categories = _query(
        "SELECT p.category, SUM(o.sales) AS sales, SUM(o.profit) AS profit "
        "FROM orders o JOIN products p ON o.product_id=p.product_id "
        "WHERE o.order_year=:y AND o.order_month=:m "
        "GROUP BY p.category ORDER BY sales DESC",
        {"y": year, "m": month},
    )
    return {
        "period_label": f"{year}年{month}月",
        "current": cur,
        "previous": prev,
        "yoy": yoy,
        "mom": {
            "sales": _pct_change(cur.sales, prev.sales),
            "profit": _pct_change(cur.profit, prev.profit),
            "orders": _pct_change(cur.orders, prev.orders),
            "aov": _pct_change(cur.aov, prev.aov),
        },
        "yoy_pct": {
            "sales": _pct_change(cur.sales, yoy.sales),
            "profit": _pct_change(cur.profit, yoy.profit),
            "orders": _pct_change(cur.orders, yoy.orders),
            "aov": _pct_change(cur.aov, yoy.aov),
        },
        "daily": daily,
        "regions": regions,
        "categories": categories,
    }


def fetch_weekly_business(year: int, month: int, week: int) -> dict[str, Any]:
    week = max(1, min(int(week), 5))
    cur = _period_metrics(year, month, week=week)
    prev_week = week - 1 if week > 1 else 5
    prev_month, prev_year = (month, year) if week > 1 else (month - 1 if month > 1 else 12, year if month > 1 else year - 1)
    prev = _period_metrics(prev_year, prev_month, week=prev_week)

    start_day = (week - 1) * 7 + 1
    end_day = min(week * 7, 31)
    daily = _query(
        "SELECT CAST(strftime('%d', order_date) AS INTEGER) AS day, SUM(sales) AS sales "
        "FROM orders WHERE order_year=:y AND order_month=:m "
        "AND CAST(strftime('%d', order_date) AS INTEGER) BETWEEN :d0 AND :d1 "
        "GROUP BY day ORDER BY day",
        {"y": year, "m": month, "d0": start_day, "d1": end_day},
    )
    regions = _query(
        "SELECT market, SUM(sales) AS sales FROM orders "
        "WHERE order_year=:y AND order_month=:m "
        "AND CAST(strftime('%d', order_date) AS INTEGER) BETWEEN :d0 AND :d1 "
        "GROUP BY market ORDER BY sales DESC LIMIT 8",
        {"y": year, "m": month, "d0": start_day, "d1": end_day},
    )
    return {
        "period_label": f"{year}年{month}月第{week}周（{start_day}–{end_day}日）",
        "current": cur,
        "previous": prev,
        "mom": {
            "sales": _pct_change(cur.sales, prev.sales),
            "profit": _pct_change(cur.profit, prev.profit),
            "orders": _pct_change(cur.orders, prev.orders),
        },
        "daily": daily,
        "regions": regions,
    }


def fetch_daily_business(year: int, month: int, day: int) -> dict[str, Any]:
    cur = _period_metrics(year, month, day=day)
    recent = _query(
        "SELECT AVG(daily_sales) AS avg_sales FROM ("
        "  SELECT SUM(sales) AS daily_sales FROM orders "
        "  WHERE order_year=:y AND order_month=:m "
        "  AND CAST(strftime('%d', order_date) AS INTEGER) < :d "
        "  GROUP BY order_date ORDER BY order_date DESC LIMIT 7"
        ")",
        {"y": year, "m": month, "d": day},
    )
    avg7 = float(recent[0]["avg_sales"]) if recent and recent[0]["avg_sales"] else 0.0
    top_products = _query(
        "SELECT p.product_name, p.category, SUM(o.sales) AS sales, SUM(o.quantity) AS qty "
        "FROM orders o JOIN products p ON o.product_id=p.product_id "
        "WHERE o.order_year=:y AND o.order_month=:m "
        "AND CAST(strftime('%d', o.order_date) AS INTEGER)=:d "
        "GROUP BY p.product_id ORDER BY sales DESC LIMIT 5",
        {"y": year, "m": month, "d": day},
    )
    return {
        "period_label": f"{year}年{month}月{day}日",
        "current": cur,
        "avg7_sales": avg7,
        "vs_avg7": _pct_change(cur.sales, avg7),
        "top_products": top_products,
    }


def fetch_product_analysis(year: int) -> dict[str, Any]:
    top = _query(
        "SELECT p.product_name, p.category, p.sub_category, "
        "SUM(o.sales) AS sales, SUM(o.quantity) AS quantity, SUM(o.profit) AS profit "
        "FROM orders o JOIN products p ON o.product_id=p.product_id "
        "WHERE o.order_year=:y GROUP BY p.product_id "
        "ORDER BY sales DESC LIMIT 10",
        {"y": year},
    )
    bottom = _query(
        "SELECT p.product_name, p.category, SUM(o.sales) AS sales, SUM(o.quantity) AS quantity "
        "FROM orders o JOIN products p ON o.product_id=p.product_id "
        "WHERE o.order_year=:y GROUP BY p.product_id HAVING SUM(o.quantity) >= 5 "
        "ORDER BY sales ASC LIMIT 10",
        {"y": year},
    )
    categories = _query(
        "SELECT p.category, SUM(o.sales) AS sales, SUM(o.profit) AS profit, "
        "SUM(o.quantity) AS quantity "
        "FROM orders o JOIN products p ON o.product_id=p.product_id "
        "WHERE o.order_year=:y GROUP BY p.category ORDER BY sales DESC",
        {"y": year},
    )
    subcats = _query(
        "SELECT p.sub_category, SUM(o.sales) AS sales "
        "FROM orders o JOIN products p ON o.product_id=p.product_id "
        "WHERE o.order_year=:y GROUP BY p.sub_category "
        "ORDER BY sales DESC LIMIT 8",
        {"y": year},
    )
    return {"year": year, "top": top, "bottom": bottom, "categories": categories, "subcats": subcats}


def fetch_user_operations(year: int, rfm_year: int) -> dict[str, Any]:
    rfm = _query(
        "SELECT value_segment, COUNT(*) AS customer_count FROM customer_rfm "
        "WHERE snapshot_year=:y GROUP BY value_segment ORDER BY customer_count DESC",
        {"y": rfm_year},
    )
    segments = _query(
        "SELECT c.segment, COUNT(DISTINCT o.customer_id) AS customer_count, SUM(o.sales) AS sales "
        "FROM orders o JOIN customers c ON o.customer_id=c.customer_id "
        "WHERE o.order_year=:y GROUP BY c.segment ORDER BY sales DESC",
        {"y": year},
    )
    first_year = _query("SELECT customer_id, MIN(order_year) AS first_year FROM orders GROUP BY customer_id")
    new_count = sum(1 for r in first_year if int(r["first_year"]) == year)
    old_count = _query(
        "SELECT COUNT(DISTINCT customer_id) AS c FROM orders WHERE order_year=:y",
        {"y": year},
    )
    total_active = int(old_count[0]["c"]) if old_count else 0
    return {
        "year": year,
        "rfm_year": rfm_year,
        "rfm": rfm,
        "segments": segments,
        "new_customers": new_count,
        "returning_customers": max(total_active - new_count, 0),
        "total_active": total_active,
    }


def load_report_data(report_type: str, params: dict[str, Any]) -> dict[str, Any]:
    year = int(params.get("year", 2014))
    month = int(params.get("month", 12))
    day = int(params.get("day", 15))
    week = int(params.get("week", 4))
    rfm_year = int(params.get("rfm_year", year))

    if report_type == "monthly":
        return fetch_monthly_business(year, month)
    if report_type == "weekly":
        return fetch_weekly_business(year, month, week)
    if report_type == "daily":
        return fetch_daily_business(year, month, day)
    if report_type == "product":
        return fetch_product_analysis(year)
    if report_type == "user":
        return fetch_user_operations(year, rfm_year)
    raise ValueError(f"未知报告类型: {report_type}")
