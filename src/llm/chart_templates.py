"""图表模板推断、列映射与结果过滤（value > 0.1）。"""
from __future__ import annotations

import re
from typing import Any

from src.llm.response_schema import QueryDisplaySpec, TEMPLATE_LABELS

NUMERIC_NAME_HINTS = (
    "sales", "profit", "quantity", "total", "amount", "cost", "count", "cnt",
    "value", "rate", "growth", "monetary", "frequency", "avg", "sum",
    "销售额", "利润", "数量", "金额", "成本", "客单价", "增长率",
)

TIME_NAME_HINTS = ("year", "month", "quarter", "date", "年", "月", "季度")


def _is_numeric(val: Any) -> bool:
    if val is None:
        return False
    try:
        float(val)
        return True
    except (TypeError, ValueError):
        return False


def detect_columns(columns: list[str], rows: list[list]) -> tuple[str | None, str | None, list[str]]:
    """推断 x 维度列、主 y 数值列、全部数值列。"""
    if not columns or not rows:
        return None, None, []

    numeric_indices: list[int] = []
    for i, col in enumerate(columns):
        sample = [row[i] for row in rows[:20] if i < len(row)]
        if sample and sum(_is_numeric(v) for v in sample) / len(sample) > 0.7:
            numeric_indices.append(i)

    numeric_cols = [columns[i] for i in numeric_indices]
    non_numeric = [c for i, c in enumerate(columns) if i not in numeric_indices]

    x_col = non_numeric[0] if non_numeric else (columns[0] if len(columns) > 1 else None)
    y_col = numeric_cols[0] if numeric_cols else None

    # 若仅两列，第一列作 x
    if len(columns) == 2 and numeric_indices == [1]:
        x_col, y_col = columns[0], columns[1]

    return x_col, y_col, numeric_cols


def infer_template(question: str, columns: list[str], rows: list[list], x_col: str | None, y_col: str | None) -> str:
    q = question
    n_rows = len(rows)

    if any(k in q for k in ("占比", "比例", "构成", "分布", "份额")) and x_col and y_col and n_rows <= 10:
        return "pie"
    if any(k in q for k in ("趋势", "变化", "月度", "年度", "每月", "每月", "增长", "淡旺季")):
        if x_col and any(h in (x_col or "").lower() for h in TIME_NAME_HINTS):
            return "line"
        if y_col and len(columns) >= 2:
            return "line"
    if any(k in q for k in ("对比", "排名", "各区域", "各年", "各类", "多少")):
        if n_rows > 8:
            return "horizontal_bar"
        return "bar"
    if len(columns) > 3 or not y_col:
        return "table"
    if n_rows > 12:
        return "horizontal_bar"
    if x_col and y_col:
        return "bar"
    return "table"


def infer_chart_title(question: str, x_col: str | None, y_col: str | None) -> str:
    q = question.strip().rstrip("？?")
    if len(q) <= 30:
        return q
    if y_col:
        y_label = y_col.replace("_", " ")
        if x_col:
            return f"按 {x_col} 的 {y_label}"
        return y_label
    return "查询结果"


def infer_summary(question: str, rows: list, y_col: str | None, columns: list[str]) -> str:
    if not rows or not y_col or y_col not in columns:
        return f"共查询到 {len(rows)} 条有效数据（数值 > 0.1）。"
    idx = columns.index(y_col)
    vals = [float(r[idx]) for r in rows if idx < len(r) and _is_numeric(r[idx])]
    if not vals:
        return f"共 {len(rows)} 条记录。"
    return f"共 {len(rows)} 条有效数据，{y_col} 合计 {sum(vals):,.2f}，最大 {max(vals):,.2f}。"


def build_display_spec(question: str, sql: str, columns: list[str], rows: list[list]) -> QueryDisplaySpec:
    x_col, y_col, numeric_cols = detect_columns(columns, rows)
    template = infer_template(question, columns, rows, x_col, y_col)

    # 折线图：时间 + 数值，或多数值列
    y_columns = None
    if template == "line" and len(numeric_cols) > 1:
        y_columns = numeric_cols
        y_col = numeric_cols[0]

    if template == "pie" and len(rows) > 10:
        template = "bar"

    title = infer_chart_title(question, x_col, y_col)
    summary = infer_summary(question, rows, y_col, columns)

    return QueryDisplaySpec(
        template=template,
        chart_title=title,
        x_column=x_col,
        y_column=y_col,
        y_columns=y_columns,
        value_min=0.1,
        summary=summary,
    )


def align_spec_to_columns(spec: QueryDisplaySpec, columns: list[str], rows: list[list]) -> QueryDisplaySpec:
    """校验并修正列名，确保 spec 与查询结果一致。"""
    x_col, y_col, numeric_cols = detect_columns(columns, rows)
    updates: dict = {}

    if spec.x_column and spec.x_column not in columns:
        updates["x_column"] = x_col
    elif not spec.x_column:
        updates["x_column"] = x_col

    if spec.y_column and spec.y_column not in columns:
        updates["y_column"] = y_col
    elif not spec.y_column:
        updates["y_column"] = y_col

    if spec.y_columns:
        valid = [c for c in spec.y_columns if c in columns]
        updates["y_columns"] = valid if valid else None

    if spec.template not in TEMPLATE_LABELS:
        updates["template"] = "table"

    if not spec.chart_title:
        updates["chart_title"] = infer_chart_title("", updates.get("x_column", x_col), updates.get("y_column", y_col))

    return spec.model_copy(update=updates) if updates else spec


def filter_rows(
    columns: list[str],
    rows: list[list],
    spec: QueryDisplaySpec,
) -> tuple[list[str], list[list], int]:
    """仅保留主数值列 > value_min 的行。返回 (columns, filtered_rows, filtered_count)。"""
    y_col = spec.y_column
    if not y_col or y_col not in columns:
        _, y_col, _ = detect_columns(columns, rows)
    if not y_col or y_col not in columns:
        return columns, rows, 0

    idx = columns.index(y_col)
    original = len(rows)
    filtered: list[list] = []
    for row in rows:
        if idx >= len(row):
            continue
        if not _is_numeric(row[idx]):
            continue
        if float(row[idx]) > spec.value_min:
            filtered.append(row)

    return columns, filtered, original - len(filtered)


def build_echarts_option(spec: QueryDisplaySpec, columns: list[str], rows: list[list]) -> dict | None:
    """生成 ECharts option，供前端直接 setOption。"""
    if spec.template == "table" or not rows:
        return None

    x_col, y_col = spec.x_column, spec.y_column
    if not x_col or x_col not in columns:
        return None

    xi = columns.index(x_col)
    categories = [str(r[xi]) if xi < len(r) else "" for r in rows]

    if spec.template == "pie":
        if not y_col or y_col not in columns:
            return None
        yi = columns.index(y_col)
        data = [{"name": categories[i], "value": float(rows[i][yi])} for i in range(len(rows)) if yi < len(rows[i])]
        total = sum(item["value"] for item in data)
        pie_data = []
        for item in data:
            pct = item["value"] / total if total else 0
            show_label = pct >= 0.1
            pie_data.append({
                **item,
                "label": {
                    "show": show_label,
                    "formatter": "{b}\n{d}%",
                },
                "labelLine": {"show": show_label},
            })
        return {
            "title": {"text": spec.chart_title, "left": "center", "textStyle": {"fontSize": 14}},
            "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
            "legend": {"type": "scroll", "orient": "vertical", "left": "left", "top": "middle"},
            "series": [{"type": "pie", "radius": "55%", "center": ["58%", "50%"], "data": pie_data}],
        }

    if spec.template in ("bar", "horizontal_bar", "line"):
        series = []
        cols = spec.y_columns if spec.template == "line" and spec.y_columns else ([y_col] if y_col else [])
        cols = [c for c in cols if c and c in columns]
        if not cols and y_col and y_col in columns:
            cols = [y_col]
        if not cols:
            return None

        chart_type = "line" if spec.template == "line" else "bar"
        for c in cols:
            ci = columns.index(c)
            series.append({
                "name": c,
                "type": chart_type,
                "data": [float(r[ci]) if ci < len(r) and _is_numeric(r[ci]) else 0 for r in rows],
                "smooth": spec.template == "line",
            })

        if spec.template == "horizontal_bar":
            return {
                "title": {"text": spec.chart_title, "textStyle": {"fontSize": 14}},
                "tooltip": {"trigger": "axis"},
                "grid": {"left": "18%", "right": "8%"},
                "xAxis": {"type": "value"},
                "yAxis": {"type": "category", "data": categories, "inverse": True},
                "series": series,
            }

        return {
            "title": {"text": spec.chart_title, "textStyle": {"fontSize": 14}},
            "tooltip": {"trigger": "axis"},
            "legend": {"data": cols} if len(cols) > 1 else {},
            "xAxis": {"type": "category", "data": categories, "axisLabel": {"rotate": 30 if len(categories) > 6 else 0}},
            "yAxis": {"type": "value"},
            "series": series,
        }

    return None
