"""MCP 对话引擎：local / api 双模式，结构化回复（SQL + 图表模板）。"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.config import CONFIG_DIR, PROMPT_PATH
from src.llm.response_schema import (
    JSON_SCHEMA_HINT,
    QueryDisplaySpec,
    StructuredChatResponse,
    TEMPLATE_LABELS,
    parse_structured_json,
)
from src.llm.sql_postprocess import postprocess_sql
from src.mcp.tools import OPENAI_TOOLS, dispatch_tool

LOCAL_RULES: list[tuple[re.Pattern, str, str, str | None, str | None]] = [
    (re.compile(r"2013.*区域|区域.*2013"), "SELECT market, SUM(sales) AS total_sales FROM orders WHERE order_year = 2013 GROUP BY market ORDER BY total_sales DESC LIMIT 100", "bar", "market", "total_sales"),
    (re.compile(r"2014.*区域|区域.*2014"), "SELECT market, total_sales FROM agg_sales_by_region_year WHERE order_year = 2014 ORDER BY total_sales DESC LIMIT 100", "bar", "market", "total_sales"),
    (re.compile(r"客单价|平均.*购买"), "SELECT order_year, avg_order_value FROM agg_sales_by_year ORDER BY order_year LIMIT 100", "line", "order_year", "avg_order_value"),
    (re.compile(r"增长率|销售额.*增长"), "SELECT order_year, total_sales, sales_growth_rate FROM agg_sales_by_year ORDER BY order_year LIMIT 100", "line", "order_year", "total_sales"),
    (re.compile(r"RFM|客户价值|价值客户"), "SELECT value_segment, COUNT(*) AS customer_count FROM customer_rfm WHERE snapshot_year = 2014 GROUP BY value_segment ORDER BY customer_count DESC LIMIT 100", "pie", "value_segment", "customer_count"),
    (re.compile(r"利润"), "SELECT order_year, order_month, SUM(profit) AS total_profit FROM orders GROUP BY order_year, order_month ORDER BY order_year, order_month LIMIT 100", "line", "order_month", "total_profit"),
    (re.compile(r"淡旺季|月度.*销售|各月"), "SELECT order_year, order_month, total_sales FROM agg_sales_by_month ORDER BY order_year, order_month LIMIT 100", "line", "order_month", "total_sales"),
    (re.compile(r"发货成本|shipping", re.I), "SELECT ship_year, ship_month, SUM(shipping_cost) AS total_cost FROM orders GROUP BY ship_year, ship_month ORDER BY ship_year, ship_month LIMIT 100", "line", "ship_month", "total_cost"),
    (re.compile(r"客户类型|segment|消费者"), "SELECT segment, SUM(total_sales) AS total_sales FROM agg_segment_category GROUP BY segment ORDER BY total_sales DESC LIMIT 100", "pie", "segment", "total_sales"),
    (re.compile(r"产品|类别|category", re.I), "SELECT category, SUM(total_sales) AS total_sales FROM agg_segment_category GROUP BY category ORDER BY total_sales DESC LIMIT 100", "bar", "category", "total_sales"),
    (re.compile(r"销售额|销售"), "SELECT order_year, total_sales FROM agg_sales_by_year ORDER BY order_year LIMIT 100", "line", "order_year", "total_sales"),
]


@dataclass
class ChatResult:
    sql: str
    mode: str
    display: QueryDisplaySpec | None = None
    tools_used: list[str] = field(default_factory=list)
    reasoning: str = ""
    structured_raw: dict | None = None


def load_llm_config() -> dict:
    path = CONFIG_DIR / "llm.yaml"
    cfg: dict = {}
    if path.exists():
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    keys_path = CONFIG_DIR / "llm_keys.yaml"
    if keys_path.exists():
        keys = yaml.safe_load(keys_path.read_text(encoding="utf-8")) or {}
        if keys.get("api_key"):
            cfg.setdefault("api", {})["api_key"] = keys["api_key"]

    env_key = (
        os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or os.environ.get("SILICONFLOW_API_KEY")
    )
    if env_key:
        cfg.setdefault("api", {})["api_key"] = env_key

    return cfg or {"mode": "local"}


def _build_system_prompt(schema_ctx: str, glossary_ctx: str) -> str:
    base = PROMPT_PATH.read_text(encoding="utf-8") if PROMPT_PATH.exists() else ""
    return f"{base}\n\n--- 数据库结构 ---\n{schema_ctx}\n\n--- 字段对照 ---\n{glossary_ctx}\n\n{JSON_SCHEMA_HINT}"


def _local_structured(question: str, tools_used: list[str]) -> tuple[StructuredChatResponse, str]:
    reasoning = ["本地模式：MCP 工具加载 schema + 本地规则匹配。"]
    tools_used.extend(["get_database_schema", "get_field_glossary"])
    schema_ctx = dispatch_tool("get_database_schema")
    dispatch_tool("get_field_glossary")
    reasoning.append(f"已通过 MCP 注入数据库结构（{len(schema_ctx)} 字符）与字段对照。")

    def _finalize(sql: str, template: str, title: str, x_col: str | None, y_col: str | None,
                  y_cols: list[str] | None = None, summary: str = "") -> StructuredChatResponse:
        processed = postprocess_sql(sql, question)
        ok, err = _mcp_validate_sql(processed, tools_used)
        if ok:
            reasoning.append("MCP validate_sql_query 校验通过。")
        else:
            reasoning.append(f"SQL 校验警告：{err[:120]}")
        return StructuredChatResponse(
            sql=processed,
            template=template,
            chart_title=title,
            x_column=x_col,
            y_column=y_col,
            y_columns=y_cols,
            value_min=0.1,
            summary=summary or f"按规则生成 SQL，推荐{TEMPLATE_LABELS.get(template, template)}展示。",
        )

    for pattern, sql, template, x_col, y_col in LOCAL_RULES:
        if pattern.search(question):
            title = question.strip().rstrip("？?")[:40]
            reasoning.append(f"命中规则：{pattern.pattern}")
            return _finalize(sql, template, title, x_col, y_col), "\n".join(reasoning)

    reasoning.append("未命中具体规则，使用默认年度销售模板。")
    fallback = _finalize(
        "SELECT order_year, total_sales, total_profit FROM agg_sales_by_year ORDER BY order_year LIMIT 100",
        "line",
        "年度销售与利润概览",
        "order_year",
        "total_sales",
        y_cols=["total_sales", "total_profit"],
        summary="未命中具体规则，返回年度销售概览。",
    )
    return fallback, "\n".join(reasoning)


def _mcp_validate_sql(sql: str, tools_used: list[str]) -> tuple[bool, str]:
    tools_used.append("validate_sql_query")
    raw = dispatch_tool("validate_sql_query", {"sql": sql})
    data = json.loads(raw)
    if data.get("ok"):
        return True, "ok"
    return False, data.get("error", "SQL 校验失败")


async def _api_structured(question: str, cfg: dict, tools_used: list[str]) -> tuple[StructuredChatResponse, str]:
    from openai import AsyncOpenAI

    api_cfg = cfg.get("api", {})
    client = AsyncOpenAI(
        api_key=api_cfg.get("api_key", ""),
        base_url=api_cfg.get("base_url") or None,
        timeout=120.0,
    )
    model = api_cfg.get("model", "gpt-4o-mini")

    schema_ctx = dispatch_tool("get_database_schema")
    glossary_ctx = dispatch_tool("get_field_glossary")
    tools_used.extend(["get_database_schema", "get_field_glossary"])

    messages: list[dict] = [
        {"role": "system", "content": _build_system_prompt(schema_ctx, glossary_ctx)},
        {"role": "user", "content": question},
    ]
    reasoning = ["API 模式：MCP 工具探索 + 结构化 JSON + SQL 校验修正。"]
    max_rounds = 8

    for round_i in range(max_rounds):
        kwargs: dict = {"model": model, "messages": messages, "temperature": 0}
        want_json = round_i >= 2
        if want_json:
            kwargs["response_format"] = {"type": "json_object"}
        else:
            kwargs["tools"] = OPENAI_TOOLS
            kwargs["tool_choice"] = "auto"

        try:
            resp = await client.chat.completions.create(**kwargs)
        except Exception as exc:
            if want_json and "response_format" in kwargs:
                reasoning.append(f"JSON 模式不可用，改为纯文本解析：{exc}")
                kwargs.pop("response_format", None)
                resp = await client.chat.completions.create(**kwargs)
            else:
                raise

        msg = resp.choices[0].message

        if msg.tool_calls:
            messages.append(msg.model_dump())
            for tc in msg.tool_calls:
                fn = tc.function.name
                args = json.loads(tc.function.arguments or "{}")
                tools_used.append(fn)
                reasoning.append(f"调用 MCP 工具 {fn}")
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": dispatch_tool(fn, args)})
            continue

        parsed = parse_structured_json(msg.content or "")
        if not parsed:
            messages.append({"role": "assistant", "content": msg.content or ""})
            messages.append({
                "role": "user",
                "content": "请严格按 JSON Schema 重新输出完整 JSON，包含 sql/template/chart_title/x_column/y_column/value_min/summary。",
            })
            continue

        parsed.sql = postprocess_sql(parsed.sql, question)
        ok, err = _mcp_validate_sql(parsed.sql, tools_used)
        if ok:
            reasoning.append("MCP validate_sql_query 校验通过。")
            return parsed, "\n".join(reasoning)

        reasoning.append(f"SQL 校验失败，请求模型修正：{err[:120]}")
        messages.append({"role": "assistant", "content": json.dumps(parsed.model_dump(), ensure_ascii=False)})
        messages.append({
            "role": "user",
            "content": (
                f"SQL 无法执行：{err}\n"
                "请修正 sql 后重新输出完整 JSON。要求：\n"
                "1. 关键字之间必须有空格（如 2014 GROUP BY，不能 2014GROUP BY）\n"
                "2. 年份与问题一致，区域用 market 字段\n"
                "3. 优先使用 agg_* 汇总表，LIMIT 100\n"
                "4. 生成后请确保语法正确，不要出现 HAV 等残缺关键字"
            ),
        })

    local_fb, fb_reason = _local_structured(question, tools_used)
    reasoning.append(f"API 多轮修正仍失败，回退本地规则。{fb_reason}")
    return local_fb, "\n".join(reasoning)


async def chat_query(question: str, mode_override: str | None = None) -> ChatResult:
    cfg = load_llm_config()
    mode = mode_override or cfg.get("mode", "local")
    tools_used: list[str] = []

    api_enabled = cfg.get("api_enabled", False)
    if mode == "api":
        if not api_enabled:
            raise ValueError("API 模式暂未开放，请选择本地模式")
        if not cfg.get("api", {}).get("api_key"):
            raise ValueError("API 模式需要配置密钥，请联系管理员")
        structured, reasoning = await _api_structured(question, cfg, tools_used)
    else:
        mode = "local"
        structured, reasoning = _local_structured(question, tools_used)

    return ChatResult(
        sql=structured.sql,
        mode=mode,
        display=structured.to_display_spec(),
        tools_used=tools_used,
        reasoning=reasoning,
        structured_raw=structured.model_dump(),
    )
