from web.chart_insights import build_insights
from starlette.testclient import TestClient
from web.app import app


def test_build_insights():
    ins = build_insights()
    assert len(ins) == 13
    assert "analysis" in ins["sales_growth.png"]
    assert len(ins["sales_growth.png"]["analysis"]) > 20
    assert "segment_category_sales.png" in ins
    assert "region_yearly_sales_top6.png" in ins


def test_homepage_lightbox():
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200
    html = r.text
    assert 'id="lightbox"' in html
    assert html.count("chart-thumb") == 13
    assert "chart-insights-data" in html
    assert "sales_growth" in html
    assert "segment_category_sales.png" in html
    assert "region_yearly_sales_top6.png" in html
