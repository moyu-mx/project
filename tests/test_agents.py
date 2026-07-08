"""Agent 报告生成测试。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from starlette.testclient import TestClient

from src.agents.report_builder import generate_report_markdown
from web.app import app


def test_generate_monthly_report():
    result = generate_report_markdown("monthly", {"year": 2014, "month": 12})
    assert "月度电商经营报告" in result["title"]
    assert result["filename"].endswith(".md")
    assert "```mermaid" in result["markdown"]
    assert "| 指标 |" in result["markdown"]


def test_generate_product_report():
    result = generate_report_markdown("product", {"year": 2014})
    assert "商品分析报告" in result["title"]
    assert "爆款 TOP10" in result["markdown"]
    assert "滞销" in result["markdown"]


def test_generate_user_report():
    result = generate_report_markdown("user", {"year": 2014, "rfm_year": 2014})
    assert "用户运营报告" in result["title"]
    assert "RFM" in result["markdown"]


def test_generate_daily_report():
    result = generate_report_markdown("daily", {"year": 2014, "month": 12, "day": 15})
    assert "日度经营快照" in result["title"]
    assert "当日 KPI" in result["markdown"]


def test_agents_api():
    client = TestClient(app)
    opts = client.get("/api/agents/options")
    assert opts.status_code == 200
    data = opts.json()
    assert any(a["id"] == "report" for a in data["agents"])
    assert len(data["report_types"]) == 5

    resp = client.post(
        "/api/agents/report/generate",
        json={"report_type": "weekly", "year": 2014, "month": 11, "week": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["markdown"]
    assert "周度" in body["title"]
