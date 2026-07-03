"""SQL 后处理测试。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.llm.sql_postprocess import postprocess_sql
from src.mcp.tools import tool_validate_sql_query
import json


def test_fix_glued_keywords_and_year():
    broken = (
        "SELECT r.market, SUM(o.sales) AS total_sales FROM orders o "
        "JOIN regions r ON o.market = r.market WHERE order_year = 2214GROUP BY r.marketHAV "
        "ORDER BY total_sales DESC LIMIT 11"
    )
    fixed = postprocess_sql(broken, "2014年各区域销售额")
    assert "2214" not in fixed
    assert "2014" in fixed
    assert "GROUP BY" in fixed
    assert "HAV" not in fixed
    assert fixed.endswith("LIMIT 100") or "LIMIT 100" in fixed
    result = json.loads(tool_validate_sql_query(fixed))
    assert result["ok"] is True
