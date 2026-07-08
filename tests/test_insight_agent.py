"""Agent2 数据洞察推理测试。"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from starlette.testclient import TestClient

from src.agents.anomaly_detect import detect_anomalies
from src.agents.insight_builder import build_insight_markdown
from src.agents.insight_data import fetch_insight_context
from src.agents.insight_engine import generate_insights
from web.app import app


def test_fetch_insight_context():
    ctx = fetch_insight_context(2014, 3)
    assert ctx["period_label"] == "2014年3月"
    assert "sales" in ctx["current"]
    assert len(ctx["category_mom"]) >= 1
    assert len(ctx["regions"]) >= 1


def test_detect_anomalies():
    ctx = fetch_insight_context(2014, 12)
    anomalies = detect_anomalies(ctx)
    assert isinstance(anomalies, list)
    for a in anomalies:
        assert a["type"] in ("volatility", "risk", "opportunity")
        assert "detail" in a


def test_local_insight_pipeline():
    payload = asyncio.run(generate_insights(2014, 3, mode="local"))
    assert payload["insights"]["mode"] == "local"
    assert len(payload["insights"]["volatility"]) >= 1
    assert len(payload["insights"]["anomalies"]) >= 1
    assert len(payload["insights"]["opportunities"]) >= 1

    md = build_insight_markdown(payload)
    assert "数据洞察推理报告" in md["title"]
    assert "## 一、波动原因" in md["markdown"]
    assert "## 二、异常预警" in md["markdown"]
    assert "## 三、机会点" in md["markdown"]
    assert md["filename"].endswith(".md")


def test_insight_api():
    client = TestClient(app)
    opts = client.get("/api/agents/options")
    assert opts.status_code == 200
    assert any(a["id"] == "insight" for a in opts.json()["agents"])

    resp = client.post(
        "/api/agents/insight/generate",
        json={"year": 2014, "month": 6, "mode": "local"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["markdown"]
    assert "洞察" in body["title"]
    assert body["insights"]["volatility"]
