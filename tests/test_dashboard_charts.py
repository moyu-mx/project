"""仪表盘动态图表测试。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from starlette.testclient import TestClient

from web.app import app
from web.dashboard_charts import BUILDERS, build_dashboard_chart


def test_dashboard_builders_count():
    assert len(BUILDERS) == 17


def test_build_sales_growth_option():
    payload = build_dashboard_chart("sales_growth.png")
    assert payload["echarts_option"] is not None
    assert payload["template"] == "bar"
    assert "series" in payload["echarts_option"]


def test_build_region_share_pie():
    payload = build_dashboard_chart("region_share.png")
    assert payload["template"] == "pie"
    assert payload["echarts_option"]["series"][0]["type"] == "pie"


def test_dashboard_api():
    client = TestClient(app)
    r = client.get("/api/dashboard/charts")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "1.4"
    assert len(data["charts"]) == 17
    assert data["charts"]["sales_growth.png"]["echarts_option"] is not None


def test_sales_charts_filtered_by_year():
    client = TestClient(app)
    full = client.get("/api/dashboard/charts/section/sales").json()
    filtered = client.get(
        "/api/dashboard/charts/section/sales",
        params={"year_from": 2013, "year_to": 2014},
    ).json()
    full_years = full["charts"]["sales_growth.png"]["echarts_option"]["xAxis"]["data"]
    filt_years = filtered["charts"]["sales_growth.png"]["echarts_option"]["xAxis"]["data"]
    assert len(filt_years) < len(full_years)
    assert filt_years == ["2013", "2014"]
    assert filtered["year_from"] == 2013
    assert filtered["year_to"] == 2014


def test_region_charts_filtered_by_year():
    client = TestClient(app)
    filtered = client.get(
        "/api/dashboard/charts/section/region",
        params={"year_from": 2013, "year_to": 2014},
    ).json()
    top6 = filtered["charts"]["region_yearly_sales_top6.png"]["echarts_option"]
    years = {str(y) for s in top6["series"] for y in s["data"] if y is not None}
    x_years = set(top6["xAxis"]["data"])
    assert x_years <= {"2013", "2014"}
    assert filtered["year_from"] == 2013


def test_rfm_year_selector():
    client = TestClient(app)
    years_resp = client.get("/api/dashboard/rfm/years")
    assert years_resp.status_code == 200
    years = years_resp.json()["years"]
    assert len(years) >= 1
    year = years[0]
    data = client.get("/api/dashboard/charts/section/rfm", params={"rfm_year": year}).json()
    assert data["rfm_year"] == year
    assert data["charts"]["rfm_distribution.png"]["rfm_year"] == year
    assert str(year) in data["charts"]["rfm_distribution.png"]["title"]


def test_shipping_cost_series_match_year_filter():
    client = TestClient(app)
    for yf, yt, expected in [(2013, 2014, {"2013", "2014"}), (2011, 2012, {"2011", "2012"})]:
        data = client.get(
            "/api/dashboard/charts/shipping_cost_trend.png",
            params={"year_from": yf, "year_to": yt},
        ).json()
        names = {s["name"] for s in data["echarts_option"]["series"]}
        assert names == expected
    all_data = client.get("/api/dashboard/charts/shipping_cost_trend.png").json()
    all_names = {s["name"] for s in all_data["echarts_option"]["series"]}
    assert "2015" not in all_names


def test_forecast_options_api():
    client = TestClient(app)
    resp = client.get("/api/dashboard/forecast/options")
    assert resp.status_code == 200
    data = resp.json()
    assert data["defaults"]["sales_model"] == "linear"
    assert any(g["id"] == "aov" for g in data["groups"])


def test_forecast_section_dynamic_params():
    client = TestClient(app)
    default = client.get("/api/dashboard/charts/section/forecast").json()
    assert default["forecast_params"]["sales_model"] == "linear"
    sales = default["charts"]["sales_forecast.png"]
    assert sales["echarts_option"] is not None
    assert sales.get("analysis")

    poly = client.get(
        "/api/dashboard/charts/section/forecast",
        params={"sales_model": "polynomial", "sales_poly_degree": 3},
    ).json()
    assert poly["forecast_params"]["sales_model"] == "polynomial"
    assert poly["forecast_params"]["sales_poly_degree"] == 3
    assert "多项式" in poly["charts"]["sales_forecast.png"]["analysis"]


def test_forecast_invalid_param_rejected():
    client = TestClient(app)
    resp = client.get(
        "/api/dashboard/charts/section/forecast",
        params={"sales_model": "invalid"},
    )
    assert resp.status_code == 400


def test_aov_forecast_shows_monthly_timeline():
    client = TestClient(app)
    data = client.get("/api/dashboard/charts/aov_forecast.png").json()
    option = data["echarts_option"]
    assert len(option["xAxis"]["data"]) >= 60
    names = {s["name"] for s in option["series"]}
    assert "月度客单价" in names
    assert "3 月均线" in names
    assert any(str(y) in str(name) for name in names for y in (2015,))
    actual = next(s for s in option["series"] if s["name"] == "月度客单价")
    assert len(actual["data"]) >= 60
    assert actual["data"][0] is not None
    assert actual["data"][-1] is None
