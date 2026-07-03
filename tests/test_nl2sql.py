"""结构化回复、模板与流水线测试。"""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.llm.response_schema import StructuredChatResponse, parse_structured_json
from src.llm.chart_templates import filter_rows, build_display_spec, build_echarts_option
from src.llm.response_schema import QueryDisplaySpec
from src.llm.chat_engine import chat_query


def test_parse_structured_json():
    raw = '{"sql":"SELECT 1","template":"bar","chart_title":"测试","x_column":"a","y_column":"b","value_min":0.1,"summary":"ok"}'
    p = parse_structured_json(raw)
    assert p is not None
    assert p.template == "bar"
    assert p.value_min == 0.1


def test_filter_rows_value_min():
    spec = QueryDisplaySpec(y_column="v", value_min=0.1)
    cols, rows, n = filter_rows(["n", "v"], [["a", 0.05], ["b", 1.2], ["c", 0.2]], spec)
    assert len(rows) == 2
    assert n == 1


def test_build_echarts_bar():
    spec = QueryDisplaySpec(template="bar", chart_title="测试", x_column="m", y_column="s", value_min=0.1)
    opt = build_echarts_option(spec, ["m", "s"], [["APAC", 100], ["EU", 200]])
    assert opt is not None
    assert opt["series"][0]["type"] == "bar"


def test_pie_labels_only_above_10_percent():
    spec = QueryDisplaySpec(template="pie", chart_title="占比", x_column="m", y_column="s", value_min=0.1)
    rows = [["APAC", 50], ["EU", 30], ["US", 15], ["CA", 5]]
    opt = build_echarts_option(spec, ["m", "s"], rows)
    assert opt is not None
    data = opt["series"][0]["data"]
    assert data[0]["label"]["show"] is True   # 50%
    assert data[1]["label"]["show"] is True   # 30%
    assert data[2]["label"]["show"] is True   # 15%
    assert data[3]["label"]["show"] is False  # 5%
    assert data[3]["labelLine"]["show"] is False


@pytest.mark.asyncio
async def test_local_chat_structured():
    result = await chat_query("2013年各区域销售额")
    assert result.display is not None
    assert result.display.template in ("bar", "horizontal_bar", "pie")
    assert result.structured_raw is not None
    assert "sql" in result.structured_raw


def test_structured_model_validation():
    m = StructuredChatResponse.model_validate({
        "sql": "SELECT 1",
        "template": "pie",
        "chart_title": "占比",
        "x_column": "a",
        "y_column": "b",
        "value_min": 0.1,
        "summary": "测试",
    })
    assert m.template == "pie"
