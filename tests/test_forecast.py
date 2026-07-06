"""预测模块测试。"""
from pathlib import Path

from src.analysis.forecast import FORECAST_YEAR, run
from src.config import CHARTS_DIR


def test_forecast_run_generates_charts_and_report():
    report = run()
    assert report["forecast_year"] == FORECAST_YEAR
    assert "sales_forecast" in report
    assert "线性" in report["sales_forecast"]["method"]
    assert "线性" in report["region_forecast"]["method"]
    assert "季节指数" in report["seasonality_forecast"]["method"]
    assert "ML" in report["aov_forecast"]["method"]
    assert report["sales_forecast"]["predicted"] > 0
    assert report["aov_forecast"]["predicted_annual"] > report["aov_forecast"]["history"]["2014"]
    assert report["aov_forecast"]["cv_mae"] < 80
    assert 550 < report["aov_forecast"]["predicted_monthly_avg"] < 850
    for name in (
        "sales_forecast.png",
        "aov_forecast.png",
        "seasonality_forecast.png",
        "region_forecast.png",
    ):
        assert (CHARTS_DIR / name).exists()
    assert (CHARTS_DIR.parent / "forecast_report.json").exists()
