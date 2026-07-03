"""组装对话查询完整响应：执行 SQL、过滤、图表配置。"""
from __future__ import annotations

from src.db.query_executor import execute_query
from src.llm.chart_templates import (
    align_spec_to_columns,
    build_display_spec,
    build_echarts_option,
    filter_rows,
)
from src.llm.chat_engine import ChatResult, chat_query
from src.llm.response_schema import TEMPLATE_LABELS
from src.llm.sql_guard import validate_sql


async def run_chat_pipeline(question: str, mode: str = "local") -> dict:
    chat_result = await chat_query(question, mode_override=mode)

    ok, msg = validate_sql(chat_result.sql)
    if not ok:
        raise ValueError(f"SQL 校验失败: {msg}")

    raw = execute_query(chat_result.sql)
    columns, rows = raw["columns"], raw["rows"]

    spec = chat_result.display
    if spec is None:
        spec = build_display_spec(question, chat_result.sql, columns, rows)
    else:
        spec = align_spec_to_columns(spec, columns, rows)
        if not spec.summary:
            spec = spec.model_copy(update={
                "summary": build_display_spec(question, chat_result.sql, columns, rows).summary
            })

    columns, rows, filtered_out = filter_rows(columns, rows, spec)
    spec = align_spec_to_columns(spec, columns, rows)

    if not rows:
        spec = spec.model_copy(update={"template": "table", "summary": spec.summary + "（过滤后无符合条件的数据）"})

    echarts_option = build_echarts_option(spec, columns, rows)

    return {
        "sql": chat_result.sql,
        "mode": chat_result.mode,
        "tools_used": chat_result.tools_used,
        "reasoning": chat_result.reasoning,
        "structured": chat_result.structured_raw,
        "display": {
            "template": spec.template,
            "template_label": TEMPLATE_LABELS.get(spec.template, spec.template),
            "chart_title": spec.chart_title,
            "x_column": spec.x_column,
            "y_column": spec.y_column,
            "y_columns": spec.y_columns,
            "value_min": spec.value_min,
            "summary": spec.summary,
        },
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "filtered_out": filtered_out,
        "elapsed_ms": raw["elapsed_ms"],
        "echarts_option": echarts_option,
    }
