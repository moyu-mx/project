"""数据概况年份筛选 API 测试。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from starlette.testclient import TestClient

from web.app import app


def test_overview_years():
    client = TestClient(app)
    r = client.get("/api/overview/years")
    assert r.status_code == 200
    data = r.json()
    assert data["min_year"] <= data["max_year"]


def test_overview_stats_default():
    client = TestClient(app)
    r = client.get("/api/overview/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["filtered"] is False
    assert data["orders"] > 0


def test_overview_stats_filtered():
    client = TestClient(app)
    r = client.get("/api/overview/stats", params={"year_from": 2013, "year_to": 2014})
    assert r.status_code == 200
    data = r.json()
    assert data["filtered"] is True
    assert data["year_from"] == 2013
    assert data["year_to"] == 2014
    assert data["orders"] > 0
    assert data["orders"] < client.get("/api/overview/stats").json()["orders"]


def test_overview_stats_partial_year_rejected():
    client = TestClient(app)
    r = client.get("/api/overview/stats", params={"year_from": 2013})
    assert r.status_code == 400


def test_homepage_overview_year_filter():
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    html = r.text
    assert "overview-toolbar" in html
    assert 'id="overview-year-from"' in html
    assert 'id="overview-year-to"' in html
    assert 'id="overview-year-reset"' in html
