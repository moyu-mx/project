"""仪表盘预置图表：从数据库/预测报告生成 ECharts 配置（与 API 查询模板一致）。"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import text

from src.config import CHARTS_DIR
from src.db.connection import get_engine
from src.llm.chart_templates import build_echarts_option
from src.llm.echarts_style import apply_legend_label_style
from src.llm.response_schema import QueryDisplaySpec, TEMPLATE_LABELS
from src.analysis.forecast_config import DEFAULTS, ForecastParams, parse_forecast_params
from src.analysis.forecast import compute_forecast_report
from web.chart_insights import CHART_META, build_forecast_chart_analysis

FORECAST_REPORT = CHARTS_DIR.parent / "forecast_report.json"

FORECAST_CHART_IDS = frozenset({
    "sales_forecast.png",
    "aov_forecast.png",
    "seasonality_forecast.png",
    "region_forecast.png",
})

FORECAST_KIND_MAP = {
    "sales_forecast.png": "sales_forecast",
    "aov_forecast.png": "aov_forecast",
    "seasonality_forecast.png": "seasonality_forecast",
    "region_forecast.png": "region_forecast",
}

_forecast_report_cache: dict[str, dict] = {}


def clear_forecast_report_cache() -> None:
    _forecast_report_cache.clear()


def _get_forecast_report(params: ForecastParams | None = None) -> dict:
    p = params or DEFAULTS
    key = p.cache_key()
    if key not in _forecast_report_cache:
        _forecast_report_cache[key] = compute_forecast_report(p, save_charts=False)
    return _forecast_report_cache[key]

SEGMENT_CN = {
    "Consumer": "个人消费者",
    "Corporate": "企业客户",
    "Home Office": "居家办公",
}
CATEGORY_CN = {
    "Technology": "科技产品",
    "Furniture": "家具产品",
    "Office Supplies": "办公用品",
}

SALES_CHART_IDS = frozenset({
    "sales_growth.png",
    "avg_order_value.png",
    "profit_by_month.png",
    "seasonality_sales.png",
    "shipping_cost_trend.png",
})

REGION_CHART_IDS = frozenset({
    "region_share.png",
    "region_yearly_sales_top6.png",
})

RFM_CHART_IDS = frozenset({"rfm_distribution.png"})

YEAR_RANGE_CHART_IDS = SALES_CHART_IDS | REGION_CHART_IDS


@dataclass(frozen=True)
class YearRange:
    """数据概况年份筛选；未指定时使用库内全部订单年份。"""

    year_from: int | None = None
    year_to: int | None = None

    @property
    def active(self) -> bool:
        return self.year_from is not None and self.year_to is not None

    def bounds(self) -> tuple[int, int]:
        if self.active:
            yf, yt = int(self.year_from), int(self.year_to)
            return (yf, yt) if yf <= yt else (yt, yf)
        yf, yt = _default_year_bounds()
        return yf, yt

    def sql_params(self) -> dict[str, int]:
        yf, yt = self.bounds()
        return {"yf": yf, "yt": yt}


def _default_year_bounds() -> tuple[int, int]:
    _, rows = _query("SELECT MIN(order_year), MAX(order_year) FROM orders WHERE order_year IS NOT NULL")
    if rows and rows[0][0] is not None and rows[0][1] is not None:
        return int(rows[0][0]), int(rows[0][1])
    return 2011, 2014


def _default_rfm_year() -> int:
    _, rows = _query("SELECT MAX(snapshot_year) FROM customer_rfm")
    if rows and rows[0][0] is not None:
        return int(rows[0][0])
    return 2014


def list_rfm_years() -> list[int]:
    _, rows = _query("SELECT DISTINCT snapshot_year FROM customer_rfm ORDER BY snapshot_year")
    return [int(r[0]) for r in rows] if rows else [_default_rfm_year()]


@dataclass(frozen=True)
class DashboardChartDef:
    chart_id: str
    section: str
    builder: Callable[[], dict[str, Any]]


def _title(chart_id: str, fallback: str = "") -> str:
    return CHART_META.get(chart_id, {}).get("title", fallback or chart_id.replace(".png", ""))


def _query(sql: str, params: dict | None = None) -> tuple[list[str], list[list]]:
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), params or {})
        if not result.returns_rows:
            return [], []
        columns = list(result.keys())
        rows = [list(r) for r in result.fetchall()]
    return columns, rows


def _payload(chart_id: str, template: str, option: dict | None, title: str | None = None) -> dict[str, Any]:
    return {
        "chart_id": chart_id,
        "title": title or _title(chart_id),
        "template": template,
        "template_label": TEMPLATE_LABELS.get(template, template),
        "echarts_option": apply_legend_label_style(option),
    }


def _spec_payload(chart_id: str, spec: QueryDisplaySpec, columns: list[str], rows: list[list]) -> dict[str, Any]:
    return _payload(chart_id, spec.template, build_echarts_option(spec, columns, rows), spec.chart_title)


def _group_small_regions(rows: list[list], threshold: float = 0.01) -> list[list]:
    total = sum(float(r[1]) for r in rows) or 1.0
    main: list[list] = []
    other = 0.0
    for market, sales in rows:
        if float(sales) / total >= threshold:
            main.append([market, float(sales)])
        else:
            other += float(sales)
    if other > 0:
        main.append(["其他", other])
    return sorted(main, key=lambda r: r[1], reverse=True)


def _pivot_line(title: str, rows: list[list], series_idx: int, x_idx: int, y_idx: int, x_name: str = "月份") -> dict:
    x_vals = sorted({int(r[x_idx]) for r in rows})
    series_keys = sorted({r[series_idx] for r in rows})
    lookup = {(r[series_idx], int(r[x_idx])): float(r[y_idx]) for r in rows}
    series = [
        {
            "name": str(key),
            "type": "line",
            "smooth": True,
            "data": [lookup.get((key, x), 0) for x in x_vals],
        }
        for key in series_keys
    ]
    return {
        "title": {"text": title, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "legend": {"type": "scroll", "top": 4},
        "grid": {"left": "8%", "right": "4%", "bottom": "12%", "containLabel": True},
        "xAxis": {"type": "category", "name": x_name, "data": [str(x) for x in x_vals]},
        "yAxis": {"type": "value"},
        "series": series,
    }


def _grouped_bar(title: str, rows: list[list], x_idx: int, series_idx: int, y_idx: int, x_labels: dict | None = None) -> dict:
    x_vals = sorted({r[x_idx] for r in rows}, key=lambda v: str(v))
    series_keys = sorted({r[series_idx] for r in rows}, key=lambda v: str(v))
    lookup = {(r[x_idx], r[series_idx]): float(r[y_idx]) for r in rows}
    categories = [x_labels.get(x, str(x)) if x_labels else str(x) for x in x_vals]
    series = [
        {
            "name": str(key),
            "type": "bar",
            "data": [lookup.get((x, key), 0) for x in x_vals],
        }
        for key in series_keys
    ]
    return {
        "title": {"text": title, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "legend": {"type": "scroll", "top": 4},
        "grid": {"left": "8%", "right": "4%", "bottom": "12%", "containLabel": True},
        "xAxis": {"type": "category", "data": categories},
        "yAxis": {"type": "value"},
        "series": series,
    }


def _stacked_bar(title: str, categories: list[str], series_data: dict[str, list[float]]) -> dict:
    return {
        "title": {"text": title, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"top": 4},
        "grid": {"left": "8%", "right": "4%", "bottom": "12%", "containLabel": True},
        "xAxis": {"type": "category", "data": categories},
        "yAxis": {"type": "value"},
        "series": [
            {"name": name, "type": "bar", "stack": "total", "data": values}
            for name, values in series_data.items()
        ],
    }


def _load_forecast_report(params: ForecastParams | None = None) -> dict:
    try:
        return _get_forecast_report(params)
    except Exception:
        if FORECAST_REPORT.exists():
            try:
                return json.loads(FORECAST_REPORT.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
    return {}


def _forecast_payload(
    chart_id: str,
    template: str,
    option: dict | None,
    report: dict,
    title: str | None = None,
) -> dict[str, Any]:
    kind = FORECAST_KIND_MAP.get(chart_id, "")
    payload = _payload(chart_id, template, option, title)
    payload["analysis"] = build_forecast_chart_analysis(kind, report) if kind else ""
    return payload


def _build_sales_growth(yr: YearRange | None = None) -> dict:
    chart_id = "sales_growth.png"
    title = _title(chart_id)
    params = (yr or YearRange()).sql_params()
    _, rows = _query(
        "SELECT order_year, total_sales, sales_growth_rate FROM agg_sales_by_year "
        "WHERE order_year BETWEEN :yf AND :yt ORDER BY order_year",
        params,
    )
    years = [str(int(r[0])) for r in rows]
    sales = [float(r[1]) for r in rows]
    growth = [None if r[2] is None else round(float(r[2]) * 100, 2) for r in rows]
    option = {
        "title": {"text": title, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["销售额", "增长率"]},
        "xAxis": {"type": "category", "data": years},
        "yAxis": [
            {"type": "value", "name": "销售额"},
            {"type": "value", "name": "增长率%", "axisLabel": {"formatter": "{value}%"}},
        ],
        "series": [
            {"name": "销售额", "type": "bar", "data": sales, "itemStyle": {"color": "#6495ED"}},
            {"name": "增长率", "type": "line", "yAxisIndex": 1, "data": growth, "itemStyle": {"color": "#FF4500"}},
        ],
    }
    return _payload(chart_id, "bar", option, title)


def _build_avg_order_value(yr: YearRange | None = None) -> dict:
    chart_id = "avg_order_value.png"
    title = _title(chart_id)
    params = (yr or YearRange()).sql_params()
    columns, rows = _query(
        "SELECT order_year, avg_order_value FROM agg_sales_by_year "
        "WHERE order_year BETWEEN :yf AND :yt ORDER BY order_year",
        params,
    )
    spec = QueryDisplaySpec(template="line", chart_title=title, x_column="order_year", y_column="avg_order_value")
    return _spec_payload(chart_id, spec, columns, rows)


def _build_profit_by_month(yr: YearRange | None = None) -> dict:
    chart_id = "profit_by_month.png"
    title = _title(chart_id)
    params = (yr or YearRange()).sql_params()
    _, rows = _query(
        "SELECT order_year, order_month, SUM(profit) AS total_profit FROM orders "
        "WHERE order_year BETWEEN :yf AND :yt GROUP BY order_year, order_month ORDER BY order_year, order_month",
        params,
    )
    option = _pivot_line(title, rows, 0, 1, 2)
    return _payload(chart_id, "line", option, title)


def _build_seasonality_sales(yr: YearRange | None = None) -> dict:
    chart_id = "seasonality_sales.png"
    title = _title(chart_id)
    params = (yr or YearRange()).sql_params()
    _, rows = _query(
        "SELECT order_year, order_month, total_sales FROM agg_sales_by_month "
        "WHERE order_year BETWEEN :yf AND :yt ORDER BY order_year, order_month",
        params,
    )
    option = _pivot_line(title, rows, 0, 1, 2)
    return _payload(chart_id, "line", option, title)


def _build_shipping_cost_trend(yr: YearRange | None = None) -> dict:
    chart_id = "shipping_cost_trend.png"
    title = _title(chart_id)
    params = (yr or YearRange()).sql_params()
    _, rows = _query(
        "SELECT order_year, order_month, SUM(shipping_cost) AS total_cost FROM orders "
        "WHERE order_year BETWEEN :yf AND :yt GROUP BY order_year, order_month ORDER BY order_year, order_month",
        params,
    )
    option = _pivot_line(title, rows, 0, 1, 2)
    return _payload(chart_id, "line", option, title)


def _build_region_share(yr: YearRange | None = None) -> dict:
    chart_id = "region_share.png"
    title = _title(chart_id)
    params = (yr or YearRange()).sql_params()
    _, rows = _query(
        "SELECT market, SUM(total_sales) AS total_sales FROM agg_sales_by_region_year "
        "WHERE order_year BETWEEN :yf AND :yt GROUP BY market ORDER BY total_sales DESC",
        params,
    )
    grouped = _group_small_regions([[r[0], r[1]] for r in rows])
    columns, data_rows = ["market", "total_sales"], grouped
    spec = QueryDisplaySpec(template="pie", chart_title=title, x_column="market", y_column="total_sales")
    return _spec_payload(chart_id, spec, columns, data_rows)


def _build_region_yearly_sales_top6(yr: YearRange | None = None) -> dict:
    chart_id = "region_yearly_sales_top6.png"
    title = _title(chart_id)
    params = (yr or YearRange()).sql_params()
    _, top_rows = _query(
        "SELECT market FROM agg_sales_by_region_year WHERE order_year BETWEEN :yf AND :yt "
        "GROUP BY market ORDER BY SUM(total_sales) DESC LIMIT 6",
        params,
    )
    markets = [r[0] for r in top_rows]
    if not markets:
        return _payload(chart_id, "bar", None, title)
    placeholders = ", ".join(f":m{i}" for i in range(len(markets)))
    query_params = {**params, **{f"m{i}": m for i, m in enumerate(markets)}}
    _, rows = _query(
        f"SELECT order_year, market, total_sales FROM agg_sales_by_region_year "
        f"WHERE order_year BETWEEN :yf AND :yt AND market IN ({placeholders}) ORDER BY order_year, market",
        query_params,
    )
    option = _grouped_bar(title, rows, 0, 1, 2)
    return _payload(chart_id, "bar", option, title)


def _build_new_old_customers() -> dict:
    chart_id = "new_old_customers.png"
    title = _title(chart_id)
    _, first_rows = _query("SELECT customer_id, MIN(order_year) AS first_year FROM orders GROUP BY customer_id")
    first_map = {r[0]: int(r[1]) for r in first_rows}
    _, order_rows = _query(
        "SELECT DISTINCT order_year, customer_id FROM orders WHERE order_year BETWEEN 2011 AND 2014 ORDER BY order_year"
    )
    stats: dict[int, dict[str, set[str]]] = defaultdict(lambda: {"new": set(), "old": set()})
    for year, cid in order_rows:
        y = int(year)
        if first_map.get(cid) == y:
            stats[y]["new"].add(cid)
        else:
            stats[y]["old"].add(cid)
    years = sorted(stats)
    option = _stacked_bar(
        title,
        [str(y) for y in years],
        {
            "新客户": [len(stats[y]["new"]) for y in years],
            "老客户": [len(stats[y]["old"]) for y in years],
        },
    )
    return _payload(chart_id, "bar", option, title)


def _build_segment_share() -> dict:
    chart_id = "segment_share.png"
    title = _title(chart_id)
    columns, rows = _query("SELECT segment, COUNT(*) AS customer_count FROM customers GROUP BY segment ORDER BY customer_count DESC")
    spec = QueryDisplaySpec(template="pie", chart_title=title, x_column="segment", y_column="customer_count")
    return _spec_payload(chart_id, spec, columns, rows)


def _build_segment_yearly_count() -> dict:
    chart_id = "segment_yearly_count.png"
    title = _title(chart_id)
    _, rows = _query(
        "SELECT o.order_year, c.segment, COUNT(DISTINCT o.customer_id) AS customer_count "
        "FROM orders o JOIN customers c ON o.customer_id = c.customer_id "
        "WHERE o.order_year BETWEEN 2011 AND 2014 GROUP BY o.order_year, c.segment ORDER BY o.order_year, c.segment"
    )
    option = _grouped_bar(title, rows, 0, 1, 2)
    return _payload(chart_id, "bar", option, title)


def _build_segment_yearly_sales() -> dict:
    chart_id = "segment_yearly_sales.png"
    title = _title(chart_id)
    _, rows = _query(
        "SELECT o.order_year, c.segment, SUM(o.sales) AS total_sales "
        "FROM orders o JOIN customers c ON o.customer_id = c.customer_id "
        "WHERE o.order_year BETWEEN 2011 AND 2014 GROUP BY o.order_year, c.segment ORDER BY o.order_year, c.segment"
    )
    option = _grouped_bar(title, rows, 0, 1, 2)
    return _payload(chart_id, "bar", option, title)


def _build_segment_category_sales() -> dict:
    chart_id = "segment_category_sales.png"
    title = _title(chart_id)
    _, rows = _query(
        "SELECT category, segment, SUM(total_sales) AS total_sales FROM agg_segment_category "
        "WHERE category IN ('Technology', 'Furniture', 'Office Supplies') "
        "GROUP BY category, segment ORDER BY category, segment"
    )
    display_rows = [[CATEGORY_CN.get(r[0], r[0]), SEGMENT_CN.get(r[1], r[1]), r[2]] for r in rows]
    option = _grouped_bar(title, display_rows, 0, 1, 2)
    return _payload(chart_id, "bar", option, title)


def _build_rfm_distribution(rfm_year: int | None = None) -> dict:
    chart_id = "rfm_distribution.png"
    year = int(rfm_year) if rfm_year is not None else _default_rfm_year()
    title = f"RFM 客户价值分布（{year}）"
    columns, rows = _query(
        "SELECT value_segment, COUNT(*) AS customer_count FROM customer_rfm "
        "WHERE snapshot_year = :year GROUP BY value_segment ORDER BY customer_count DESC",
        {"year": year},
    )
    spec = QueryDisplaySpec(template="pie", chart_title=title, x_column="value_segment", y_column="customer_count")
    payload = _spec_payload(chart_id, spec, columns, rows)
    payload["rfm_year"] = year
    return payload


def _build_sales_forecast(report: dict | None = None) -> dict:
    chart_id = "sales_forecast.png"
    report = report or _load_forecast_report()
    title = _title(chart_id)
    block = report.get("sales_forecast") or {}
    history = block.get("history") or {}
    if not history:
        return _forecast_payload(chart_id, "bar", None, report, title)
    fy = str(block.get("forecast_year", 2015))
    years = [str(y) for y in sorted(history, key=int)]
    values = [float(history[y]) for y in years]
    pred = float(block.get("predicted", 0))
    lo, hi = float(block.get("lower", pred)), float(block.get("upper", pred))
    labels = years + [fy]
    option = {
        "title": {"text": title, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["实际", "预测"]},
        "xAxis": {"type": "category", "data": labels},
        "yAxis": {"type": "value", "name": "销售额"},
        "series": [
            {"name": "实际", "type": "bar", "data": values + [None], "itemStyle": {"color": "#6495ED"}},
            {
                "name": "预测",
                "type": "bar",
                "data": [None] * len(values) + [pred],
                "itemStyle": {"color": "#3CB371"},
            },
        ],
        "graphic": [
            {
                "type": "text",
                "left": "center",
                "top": "90%",
                "style": {"text": f"{fy} 预测区间: {lo:,.0f} — {hi:,.0f}", "fill": "#888", "fontSize": 11},
            }
        ],
    }
    return _forecast_payload(chart_id, "bar", option, report, title)


def _query_monthly_aov_history() -> list[dict[str, float | int | str]]:
    """从订单表聚合月度客单价（报告缺字段时的兜底）。"""
    _, rows = _query(
        "SELECT order_year, order_month, SUM(sales) AS total_sales, "
        "COUNT(DISTINCT customer_id) AS customer_count FROM orders "
        "WHERE order_year BETWEEN 2011 AND 2014 "
        "GROUP BY order_year, order_month ORDER BY order_year, order_month"
    )
    history: list[dict[str, float | int | str]] = []
    aov_vals: list[float] = []
    for year, month, sales, customers in rows:
        aov = float(sales) / max(int(customers), 1)
        aov_vals.append(aov)
        ma3 = sum(aov_vals[-3:]) / min(len(aov_vals), 3)
        history.append({
            "label": f"{int(year)}-{int(month):02d}",
            "year": int(year),
            "month": int(month),
            "aov": round(aov, 2),
            "ma3": round(ma3, 2),
        })
    return history


def _build_aov_forecast(report: dict | None = None) -> dict:
    chart_id = "aov_forecast.png"
    report = report or _load_forecast_report()
    title = _title(chart_id)
    block = report.get("aov_forecast") or {}
    fy = int(report.get("forecast_year", block.get("forecast_year", 2015)))
    monthly_hist = block.get("monthly_history") or _query_monthly_aov_history()
    fc_monthly = block.get("predicted_monthly") or {}
    fc_lower = block.get("lower_monthly") or {}
    fc_upper = block.get("upper_monthly") or {}
    if not monthly_hist and not fc_monthly:
        return _forecast_payload(chart_id, "line", None, report, title)

    hist_labels = [str(h["label"]) for h in monthly_hist]
    fc_labels = [f"{fy}-{m:02d}" for m in range(1, 13)]
    x_labels = hist_labels + fc_labels
    n_hist = len(hist_labels)

    actual = [float(h["aov"]) for h in monthly_hist] + [None] * 12
    ma3 = [float(h.get("ma3", h["aov"])) for h in monthly_hist] + [None] * 12
    forecast = [None] * n_hist + [float(fc_monthly.get(str(m), 0)) for m in range(1, 13)]
    band_base = [None] * n_hist + [
        float(fc_lower.get(str(m), forecast[n_hist + i - 1] or 0)) for i, m in enumerate(range(1, 13), start=1)
    ]
    band_width = [None] * n_hist + [
        max(
            float(fc_upper.get(str(m), forecast[n_hist + i - 1] or 0))
            - float(fc_lower.get(str(m), forecast[n_hist + i - 1] or 0)),
            0,
        )
        for i, m in enumerate(range(1, 13), start=1)
    ]

    pred_annual = block.get("predicted_annual")
    cv_mae = block.get("cv_mae")
    model_sales = block.get("model_sales", "")
    summary = ""
    if pred_annual is not None:
        summary = f"{fy} 年度客单价约 {float(pred_annual):,.0f} 元"
        if cv_mae is not None:
            summary += f" · 月度 MAE≈{float(cv_mae):.0f}"

    option = {
        "title": {"text": title, "textStyle": {"fontSize": 14}},
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "cross"},
        },
        "legend": {
            "type": "scroll",
            "top": 4,
            "data": ["月度客单价", "3 月均线", "预测区间", f"{fy} 预测"],
        },
        "grid": {"left": "6%", "right": "3%", "top": "16%", "bottom": "14%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": x_labels,
            "boundaryGap": False,
            "axisLabel": {"interval": 5, "rotate": 35, "fontSize": 10},
        },
        "yAxis": {"type": "value", "name": "客单价（元）", "scale": True},
        "series": [
            {
                "name": "月度客单价",
                "type": "line",
                "data": actual,
                "showSymbol": False,
                "lineStyle": {"width": 1, "color": "rgba(60, 179, 113, 0.45)"},
                "itemStyle": {"color": "rgba(60, 179, 113, 0.45)"},
            },
            {
                "name": "3 月均线",
                "type": "line",
                "data": ma3,
                "showSymbol": False,
                "smooth": True,
                "lineStyle": {"width": 2, "color": "#2E8B57"},
                "itemStyle": {"color": "#2E8B57"},
            },
            {
                "name": "_band_base",
                "type": "line",
                "data": band_base,
                "stack": "forecast-band",
                "symbol": "none",
                "lineStyle": {"opacity": 0},
                "silent": True,
                "tooltip": {"show": False},
            },
            {
                "name": "预测区间",
                "type": "line",
                "data": band_width,
                "stack": "forecast-band",
                "symbol": "none",
                "lineStyle": {"opacity": 0},
                "areaStyle": {"color": "rgba(255, 215, 0, 0.22)"},
            },
            {
                "name": f"{fy} 预测",
                "type": "line",
                "data": forecast,
                "smooth": True,
                "symbolSize": 5,
                "lineStyle": {"type": "dashed", "width": 2.5, "color": "#FFD700"},
                "itemStyle": {"color": "#FFD700"},
                "markArea": {
                    "silent": True,
                    "itemStyle": {"color": "rgba(255, 215, 0, 0.06)"},
                    "data": [[{"xAxis": fc_labels[0]}, {"xAxis": fc_labels[-1]}]] if fc_labels else [],
                },
            },
        ],
    }
    if summary:
        option["graphic"] = [
            {
                "type": "text",
                "right": "3%",
                "top": "10%",
                "style": {"text": summary, "fill": "#94a3b8", "fontSize": 11},
            }
        ]
        if model_sales:
            option["graphic"].append(
                {
                    "type": "text",
                    "left": "center",
                    "top": "92%",
                    "style": {
                        "text": f"月度模型 {model_sales} 递归 · 左段历史 / 右段 {fy} 展望",
                        "fill": "#64748b",
                        "fontSize": 10,
                    },
                }
            )
    return _forecast_payload(chart_id, "line", option, report, title)


def _build_seasonality_forecast(report: dict | None = None) -> dict:
    chart_id = "seasonality_forecast.png"
    report = report or _load_forecast_report()
    title = _title(chart_id)
    _, hist_rows = _query(
        "SELECT order_year, order_month, total_sales FROM agg_sales_by_month "
        "WHERE order_year BETWEEN 2011 AND 2014 ORDER BY order_year, order_month"
    )
    fc_block = report.get("seasonality_forecast") or {}
    fc_monthly = fc_block.get("monthly") or {}
    fy = int(fc_block.get("forecast_year", 2015))
    option = _pivot_line(title, hist_rows, 0, 1, 2)
    if fc_monthly:
        fc_data = [float(fc_monthly.get(str(m), 0)) for m in range(1, 13)]
        option["series"].append(
            {
                "name": f"{fy} 预测",
                "type": "line",
                "smooth": True,
                "data": fc_data,
                "lineStyle": {"type": "dashed", "color": "#FFD700", "width": 2},
                "itemStyle": {"color": "#FFD700"},
            }
        )
    return _forecast_payload(chart_id, "line", option, report, title)


def _build_region_forecast(report: dict | None = None) -> dict:
    chart_id = "region_forecast.png"
    report = report or _load_forecast_report()
    fc_block = report.get("region_forecast") or {}
    markets = fc_block.get("markets") or {}
    top_n = len(markets) or 6
    title = _title(chart_id) if top_n == 6 else f"前{top_n}区域销售额预测"
    if not markets:
        return _forecast_payload(chart_id, "line", None, report, title)
    fy = int(fc_block.get("forecast_year", 2015))
    series: list[dict] = []
    all_years: set[int] = set()
    for market, info in markets.items():
        hist = info.get("history") or {}
        years = sorted(int(y) for y in hist)
        all_years.update(years)
        vals = [float(hist[str(y)]) for y in years]
        line_data = vals + [float(info.get("predicted", vals[-1] if vals else 0))]
        series.append(
            {
                "name": market,
                "type": "line",
                "smooth": True,
                "data": line_data,
            }
        )
    years_sorted = sorted(all_years)
    x_labels = [str(y) for y in years_sorted] + [str(fy)]
    for s in series:
        while len(s["data"]) < len(x_labels):
            s["data"].append(None)
        if len(s["data"]) > len(x_labels):
            s["data"] = s["data"][: len(x_labels)]
    option = {
        "title": {"text": title, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "legend": {"type": "scroll", "top": 4},
        "grid": {"left": "8%", "right": "4%", "bottom": "12%", "containLabel": True},
        "xAxis": {"type": "category", "data": x_labels, "name": "年份"},
        "yAxis": {"type": "value", "name": "销售额"},
        "series": series,
    }
    return _forecast_payload(chart_id, "line", option, report, title)


BUILDERS: dict[str, Callable[[], dict[str, Any]]] = {
    "sales_growth.png": _build_sales_growth,
    "avg_order_value.png": _build_avg_order_value,
    "profit_by_month.png": _build_profit_by_month,
    "seasonality_sales.png": _build_seasonality_sales,
    "shipping_cost_trend.png": _build_shipping_cost_trend,
    "region_share.png": _build_region_share,
    "region_yearly_sales_top6.png": _build_region_yearly_sales_top6,
    "new_old_customers.png": _build_new_old_customers,
    "segment_share.png": _build_segment_share,
    "segment_yearly_count.png": _build_segment_yearly_count,
    "segment_yearly_sales.png": _build_segment_yearly_sales,
    "segment_category_sales.png": _build_segment_category_sales,
    "rfm_distribution.png": _build_rfm_distribution,
    "sales_forecast.png": _build_sales_forecast,
    "aov_forecast.png": _build_aov_forecast,
    "seasonality_forecast.png": _build_seasonality_forecast,
    "region_forecast.png": _build_region_forecast,
}

DASHBOARD_SECTIONS: dict[str, list[str]] = {
    "sales": [
        "sales_growth.png",
        "avg_order_value.png",
        "profit_by_month.png",
        "seasonality_sales.png",
        "shipping_cost_trend.png",
    ],
    "region": ["region_share.png", "region_yearly_sales_top6.png"],
    "customer": [
        "new_old_customers.png",
        "segment_yearly_count.png",
        "segment_yearly_sales.png",
        "segment_category_sales.png",
        "segment_share.png",
    ],
    "rfm": ["rfm_distribution.png"],
    "forecast": [
        "sales_forecast.png",
        "aov_forecast.png",
        "seasonality_forecast.png",
        "region_forecast.png",
    ],
}


def build_dashboard_chart(
    chart_id: str,
    year_from: int | None = None,
    year_to: int | None = None,
    rfm_year: int | None = None,
    forecast_params: ForecastParams | None = None,
) -> dict[str, Any]:
    builder = BUILDERS.get(chart_id)
    if not builder:
        raise KeyError(f"未知图表: {chart_id}")
    try:
        if chart_id in YEAR_RANGE_CHART_IDS:
            return builder(YearRange(year_from, year_to))
        if chart_id in RFM_CHART_IDS:
            return builder(rfm_year)
        if chart_id in FORECAST_CHART_IDS:
            report = _get_forecast_report(forecast_params)
            return builder(report)
        return builder()
    except Exception as exc:
        return _payload(chart_id, "table", None, _title(chart_id)) | {"error": str(exc)}


def build_section_charts(
    section: str,
    year_from: int | None = None,
    year_to: int | None = None,
    rfm_year: int | None = None,
    forecast_params: ForecastParams | None = None,
) -> dict[str, dict[str, Any]]:
    chart_ids = DASHBOARD_SECTIONS.get(section, [])
    if section == "rfm":
        return {cid: build_dashboard_chart(cid, rfm_year=rfm_year) for cid in chart_ids}
    if section in ("sales", "region"):
        return {cid: build_dashboard_chart(cid, year_from, year_to) for cid in chart_ids}
    if section == "forecast":
        p = forecast_params or DEFAULTS
        report = _get_forecast_report(p)
        return {cid: BUILDERS[cid](report) for cid in chart_ids}
    return {cid: build_dashboard_chart(cid) for cid in chart_ids}


def build_all_dashboard_charts(
    year_from: int | None = None,
    year_to: int | None = None,
    rfm_year: int | None = None,
    forecast_params: ForecastParams | None = None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for chart_id in BUILDERS:
        if chart_id in YEAR_RANGE_CHART_IDS:
            result[chart_id] = build_dashboard_chart(chart_id, year_from, year_to)
        elif chart_id in RFM_CHART_IDS:
            result[chart_id] = build_dashboard_chart(chart_id, rfm_year=rfm_year)
        elif chart_id in FORECAST_CHART_IDS:
            result[chart_id] = build_dashboard_chart(chart_id, forecast_params=forecast_params)
        else:
            result[chart_id] = build_dashboard_chart(chart_id)
    return result
