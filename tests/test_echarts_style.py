"""ECharts 图例与注记样式测试。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.llm.echarts_style import apply_chat_chart_style, apply_legend_label_style


def test_legend_and_pie_label_white():
    option = {
        "legend": {"data": ["A", "B"]},
        "series": [{
            "type": "pie",
            "data": [
                {"name": "A", "value": 60, "label": {"show": True, "formatter": "{b}"}},
                {"name": "B", "value": 40, "label": {"show": False}},
            ],
        }],
    }
    styled = apply_legend_label_style(option)
    assert styled["legend"]["textStyle"]["color"] == "#ffffff"
    assert styled["series"][0]["data"][0]["label"]["color"] == "#ffffff"
    assert styled["series"][0]["data"][1]["label"]["show"] is False
    assert "title" not in styled


def test_remove_inner_title():
    option = {"title": {"text": "测试标题"}, "series": [{"type": "bar", "data": [1]}]}
    styled = apply_legend_label_style(option)
    assert "title" not in styled


def test_chat_chart_style_keeps_colorful_legend():
    option = {
        "title": {"text": "查询结果"},
        "legend": {"data": ["A", "B"], "textStyle": {"color": "#ffffff"}},
        "series": [{
            "type": "pie",
            "data": [
                {"name": "A", "value": 60, "label": {"show": True, "formatter": "{b}", "color": "#ffffff"}},
                {"name": "B", "value": 40, "label": {"show": False}},
            ],
        }],
    }
    styled = apply_chat_chart_style(option)
    assert "title" not in styled
    assert styled["legend"]["show"] is True
    assert styled["legend"].get("textStyle") in (None, {})
    assert "color" not in styled["series"][0]["data"][0]["label"]
    assert styled["series"][0]["data"][0]["label"]["show"] is True
