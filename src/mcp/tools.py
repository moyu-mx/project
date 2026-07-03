"""MCP 工具：本地直调 / API function calling / MCP Server 共用。"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from src.db.connection import get_engine
from src.db.query_executor import execute_query
from src.llm.sql_guard import validate_sql
from src.mcp.schema_catalog import (
    BUSINESS_RULES,
    FIELDS,
    JOIN_HINTS,
    TABLES,
    format_schema_markdown,
    list_tables,
)

OPENAI_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "列出数据库中所有表及中文说明",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_database_schema",
            "description": "获取表结构、字段中文含义与业务规则，可按表名过滤",
            "parameters": {
                "type": "object",
                "properties": {"table_name": {"type": "string", "description": "可选表名"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_field_glossary",
            "description": "易混淆字段对照：market vs country、segment 含义等",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "preview_table",
            "description": "预览表的前几行样本数据",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string"},
                    "limit": {"type": "integer", "default": 3},
                },
                "required": ["table_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_sql_query",
            "description": "校验 SQL 语法是否可执行（仅 SELECT），返回 ok 或错误信息",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string", "description": "待校验的 SELECT 语句"}},
                "required": ["sql"],
            },
        },
    },
]

MCP_TOOL_SPECS = [
    {"name": "list_tables", "description": "列出所有表", "inputSchema": {"type": "object", "properties": {}}},
    {
        "name": "get_database_schema",
        "description": "获取 schema 与字段语义",
        "inputSchema": {
            "type": "object",
            "properties": {"table_name": {"type": "string"}},
        },
    },
    {
        "name": "get_field_glossary",
        "description": "字段对照与业务规则",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "preview_table",
        "description": "预览样本数据",
        "inputSchema": {
            "type": "object",
            "properties": {"table_name": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["table_name"],
        },
    },
    {
        "name": "validate_sql_query",
        "description": "校验 SQL 语法",
        "inputSchema": {
            "type": "object",
            "properties": {"sql": {"type": "string"}},
            "required": ["sql"],
        },
    },
]


def tool_list_tables() -> str:
    return json.dumps(list_tables(), ensure_ascii=False, indent=2)


def tool_get_database_schema(table_name: str | None = None) -> str:
    if table_name and table_name not in TABLES:
        return json.dumps({"error": f"未知表: {table_name}", "available": list(TABLES.keys())}, ensure_ascii=False)
    return format_schema_markdown(table_name)


def tool_get_field_glossary() -> str:
    return json.dumps(
        {
            "market": "商店业务区域(APAC/EU/US)，在 orders.market，不是 customers.country",
            "segment": "客户类别: Consumer/Corporate/Home Office",
            "category": "产品大类: Technology/Furniture/Office Supplies",
            "order_year": "按年过滤首选字段",
            "avg_order_value": "客单价，见 agg_sales_by_year",
            "value_segment": "RFM 客户价值标签，见 customer_rfm",
            "business_rules": BUSINESS_RULES,
            "join_hints": JOIN_HINTS,
        },
        ensure_ascii=False,
        indent=2,
    )


def tool_preview_table(table_name: str, limit: int = 3) -> str:
    if table_name not in TABLES:
        return json.dumps({"error": f"未知表: {table_name}"}, ensure_ascii=False)
    limit = min(max(1, limit), 10)
    with get_engine().connect() as conn:
        rows = conn.execute(text(f"SELECT * FROM {table_name} LIMIT :lim"), {"lim": limit}).fetchall()
    if not rows:
        return json.dumps({"table": table_name, "rows": []}, ensure_ascii=False)
    data = [dict(r._mapping) for r in rows]
    return json.dumps({"table": table_name, "columns": list(rows[0]._mapping.keys()), "rows": data}, ensure_ascii=False, default=str)


def tool_validate_sql_query(sql: str) -> str:
    ok, msg = validate_sql(sql)
    if not ok:
        return json.dumps({"ok": False, "error": msg}, ensure_ascii=False)
    try:
        with get_engine().connect() as conn:
            conn.execute(text(f"EXPLAIN {sql}"))
        return json.dumps({"ok": True, "message": "SQL 语法校验通过"}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)


def dispatch_tool(name: str, arguments: dict[str, Any] | None = None) -> str:
    arguments = arguments or {}
    if name == "list_tables":
        return tool_list_tables()
    if name == "get_database_schema":
        return tool_get_database_schema(arguments.get("table_name"))
    if name == "get_field_glossary":
        return tool_get_field_glossary()
    if name == "preview_table":
        if "table_name" not in arguments:
            return json.dumps({"error": "缺少 table_name"}, ensure_ascii=False)
        return tool_preview_table(arguments["table_name"], arguments.get("limit", 3))
    if name == "validate_sql_query":
        if "sql" not in arguments:
            return json.dumps({"error": "缺少 sql"}, ensure_ascii=False)
        return tool_validate_sql_query(arguments["sql"])
    return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
