"""Agent 与报告类型配置。"""
from __future__ import annotations

from typing import Any

AGENTS: list[dict[str, str]] = [
    {"id": "chat", "label": "智能查询", "description": "自然语言 NL2SQL + 动态图表"},
    {
        "id": "report",
        "label": "Agent1 · 分析报告",
        "description": "生成 Markdown 经营/商品/用户报告并下载",
    },
    {
        "id": "insight",
        "label": "Agent2 · 数据洞察推理",
        "description": "波动原因、异常预警、机会点智能解读",
    },
]

REPORT_TYPES: list[dict[str, Any]] = [
    {
        "id": "monthly",
        "label": "月报 · 月度电商经营总结",
        "needs_period": True,
        "period_fields": ["year", "month"],
    },
    {
        "id": "weekly",
        "label": "周报 · 周度经营快报",
        "needs_period": True,
        "period_fields": ["year", "month", "week"],
    },
    {
        "id": "daily",
        "label": "日报 · 日度经营快照",
        "needs_period": True,
        "period_fields": ["year", "month", "day"],
    },
    {
        "id": "product",
        "label": "商品分析报告",
        "needs_period": True,
        "period_fields": ["year"],
    },
    {
        "id": "user",
        "label": "用户运营报告",
        "needs_period": True,
        "period_fields": ["year", "rfm_year"],
    },
]

DEFAULTS = {
    "year": 2014,
    "month": 12,
    "day": 15,
    "week": 4,
    "rfm_year": 2014,
}

YEAR_MIN, YEAR_MAX = 2011, 2014


def agent_options() -> dict[str, Any]:
    return {
        "agents": AGENTS,
        "report_types": REPORT_TYPES,
        "defaults": DEFAULTS,
        "year_range": {"min": YEAR_MIN, "max": YEAR_MAX},
    }
