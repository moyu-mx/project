"""报告 Mermaid 模板测试。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agents.report_builder import _markdown_trend_chart, _mermaid_pie


def test_trend_chart_uses_markdown_bars():
    md = _markdown_trend_chart("周内日销售额", ["8", "9", "10"], [1000.0, 2000.0, 1500.0])
    assert "mermaid" not in md
    assert "timeline" not in md
    assert "8日" in md
    assert "柱状示意" in md
    assert "█" in md


def test_pie_merges_small_slices():
    items = [
        ("A", 50.0),
        ("B", 30.0),
        ("C", 5.0),
        ("D", 5.0),
        ("E", 5.0),
        ("F", 5.0),
    ]
    md = _mermaid_pie("测试占比", items, min_label_pct=0.10)
    assert "其他" in md
    assert "pie" in md
    assert "    title " in md
