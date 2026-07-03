from web.chart_insights import build_insights
from starlette.testclient import TestClient
from web.app import app


def test_build_insights():
    ins = build_insights()
    assert len(ins) == 11
    assert "analysis" in ins["sales_growth.png"]
    assert len(ins["sales_growth.png"]["analysis"]) > 20


def test_homepage_lightbox():
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200
    html = r.text
    assert 'id="lightbox"' in html
    assert html.count("chart-thumb") == 11
    assert "chart-insights-data" in html
    assert "sales_growth" in html
