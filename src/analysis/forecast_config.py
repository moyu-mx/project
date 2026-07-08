"""预测模块可配置参数与选项元数据。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass(frozen=True)
class ForecastParams:
    sales_model: str = "linear"
    sales_poly_degree: int = 2
    seasonality_model: str = "linear_seasonal"
    region_model: str = "linear"
    region_top_n: int = 6
    aov_sales_model: str = "auto"
    aov_customers_model: str = "auto"
    aov_annual_model: str = "auto"
    aov_fusion_ml_weight: float = 0.55
    confidence_z: float = 1.96
    rf_n_estimators: int = 200
    rf_max_depth: int = 4
    gbr_n_estimators: int = 200
    gbr_max_depth: int = 3
    gbr_learning_rate: float = 0.06
    ridge_alpha: float = 8.0

    def cache_key(self) -> str:
        return "|".join(f"{f.name}={getattr(self, f.name)}" for f in fields(self))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SALES_MODELS = ("linear", "polynomial")
SEASONALITY_MODELS = ("linear_seasonal", "linear_trend")
REGION_MODELS = ("linear",)
AOV_MODELS = ("auto", "RandomForest", "GradientBoosting", "Ridge")

DEFAULTS = ForecastParams()

FORECAST_OPTIONS: dict[str, Any] = {
    "defaults": DEFAULTS.to_dict(),
    "groups": [
        {
            "id": "sales",
            "label": "年度销售额",
            "fields": [
                {
                    "name": "sales_model",
                    "label": "模型",
                    "type": "select",
                    "default": "linear",
                    "recommended": "linear",
                    "options": [
                        {"value": "linear", "label": "线性回归（推荐）"},
                        {"value": "polynomial", "label": "多项式回归"},
                    ],
                },
                {
                    "name": "sales_poly_degree",
                    "label": "多项式阶数",
                    "type": "number",
                    "default": 2,
                    "recommended": 2,
                    "min": 2,
                    "max": 3,
                    "visible_when": {"sales_model": "polynomial"},
                },
            ],
        },
        {
            "id": "seasonality",
            "label": "淡旺季",
            "fields": [
                {
                    "name": "seasonality_model",
                    "label": "模型",
                    "type": "select",
                    "default": "linear_seasonal",
                    "recommended": "linear_seasonal",
                    "options": [
                        {"value": "linear_seasonal", "label": "线性趋势 + 季节指数（推荐）"},
                        {"value": "linear_trend", "label": "纯线性趋势"},
                    ],
                },
            ],
        },
        {
            "id": "region",
            "label": "区域预测",
            "fields": [
                {
                    "name": "region_model",
                    "label": "模型",
                    "type": "select",
                    "default": "linear",
                    "recommended": "linear",
                    "options": [{"value": "linear", "label": "分区域线性回归（推荐）"}],
                },
                {
                    "name": "region_top_n",
                    "label": "Top 区域数",
                    "type": "number",
                    "default": 6,
                    "recommended": 6,
                    "min": 3,
                    "max": 10,
                },
            ],
        },
        {
            "id": "aov",
            "label": "客单价 ML",
            "fields": [
                {
                    "name": "aov_sales_model",
                    "label": "月度销售额模型",
                    "type": "select",
                    "default": "auto",
                    "recommended": "auto",
                    "options": [
                        {"value": "auto", "label": "自动选型（推荐）"},
                        {"value": "RandomForest", "label": "Random Forest"},
                        {"value": "GradientBoosting", "label": "Gradient Boosting"},
                        {"value": "Ridge", "label": "Ridge 回归"},
                    ],
                },
                {
                    "name": "aov_customers_model",
                    "label": "月度客户数模型",
                    "type": "select",
                    "default": "auto",
                    "recommended": "auto",
                    "options": [
                        {"value": "auto", "label": "自动选型（推荐）"},
                        {"value": "RandomForest", "label": "Random Forest"},
                        {"value": "GradientBoosting", "label": "Gradient Boosting"},
                        {"value": "Ridge", "label": "Ridge 回归"},
                    ],
                },
                {
                    "name": "aov_annual_model",
                    "label": "年度客单价模型",
                    "type": "select",
                    "default": "auto",
                    "recommended": "auto",
                    "options": [
                        {"value": "auto", "label": "自动选型（推荐）"},
                        {"value": "RandomForest", "label": "Random Forest"},
                        {"value": "GradientBoosting", "label": "Gradient Boosting"},
                        {"value": "Ridge", "label": "Ridge 回归"},
                    ],
                },
                {
                    "name": "aov_fusion_ml_weight",
                    "label": "年度 ML 融合权重",
                    "type": "number",
                    "default": 0.55,
                    "recommended": 0.55,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                },
            ],
        },
        {
            "id": "common",
            "label": "通用",
            "fields": [
                {
                    "name": "confidence_z",
                    "label": "置信区间 Z 值",
                    "type": "number",
                    "default": 1.96,
                    "recommended": 1.96,
                    "min": 1.0,
                    "max": 3.0,
                    "step": 0.1,
                },
            ],
        },
        {
            "id": "ml_advanced",
            "label": "ML 高级参数",
            "collapsible": True,
            "fields": [
                {
                    "name": "rf_n_estimators",
                    "label": "RF 树数量",
                    "type": "number",
                    "default": 200,
                    "recommended": 200,
                    "min": 50,
                    "max": 500,
                },
                {
                    "name": "rf_max_depth",
                    "label": "RF 最大深度",
                    "type": "number",
                    "default": 4,
                    "recommended": 4,
                    "min": 2,
                    "max": 12,
                },
                {
                    "name": "gbr_n_estimators",
                    "label": "GBR 树数量",
                    "type": "number",
                    "default": 200,
                    "recommended": 200,
                    "min": 50,
                    "max": 500,
                },
                {
                    "name": "gbr_max_depth",
                    "label": "GBR 最大深度",
                    "type": "number",
                    "default": 3,
                    "recommended": 3,
                    "min": 2,
                    "max": 8,
                },
                {
                    "name": "gbr_learning_rate",
                    "label": "GBR 学习率",
                    "type": "number",
                    "default": 0.06,
                    "recommended": 0.06,
                    "min": 0.01,
                    "max": 0.3,
                    "step": 0.01,
                },
                {
                    "name": "ridge_alpha",
                    "label": "Ridge Alpha",
                    "type": "number",
                    "default": 8.0,
                    "recommended": 8.0,
                    "min": 0.1,
                    "max": 100.0,
                    "step": 0.1,
                },
            ],
        },
    ],
}


def parse_forecast_params(raw: dict[str, Any] | None) -> ForecastParams:
    """从查询参数字典解析并校验预测配置。"""
    if not raw:
        return DEFAULTS

    def _str(key: str, default: str, allowed: tuple[str, ...]) -> str:
        val = str(raw.get(key, default)).strip()
        if val not in allowed:
            raise ValueError(f"参数 {key} 无效，可选：{list(allowed)}")
        return val

    def _int(key: str, default: int, lo: int, hi: int) -> int:
        try:
            val = int(raw.get(key, default))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"参数 {key} 必须为整数") from exc
        if val < lo or val > hi:
            raise ValueError(f"参数 {key} 需在 {lo}—{hi} 之间")
        return val

    def _float(key: str, default: float, lo: float, hi: float) -> float:
        try:
            val = float(raw.get(key, default))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"参数 {key} 必须为数字") from exc
        if val < lo or val > hi:
            raise ValueError(f"参数 {key} 需在 {lo}—{hi} 之间")
        return val

    sales_model = _str("sales_model", DEFAULTS.sales_model, SALES_MODELS)
    sales_poly_degree = _int("sales_poly_degree", DEFAULTS.sales_poly_degree, 2, 3)
    if sales_model != "polynomial":
        sales_poly_degree = DEFAULTS.sales_poly_degree

    return ForecastParams(
        sales_model=sales_model,
        sales_poly_degree=sales_poly_degree,
        seasonality_model=_str("seasonality_model", DEFAULTS.seasonality_model, SEASONALITY_MODELS),
        region_model=_str("region_model", DEFAULTS.region_model, REGION_MODELS),
        region_top_n=_int("region_top_n", DEFAULTS.region_top_n, 3, 10),
        aov_sales_model=_str("aov_sales_model", DEFAULTS.aov_sales_model, AOV_MODELS),
        aov_customers_model=_str("aov_customers_model", DEFAULTS.aov_customers_model, AOV_MODELS),
        aov_annual_model=_str("aov_annual_model", DEFAULTS.aov_annual_model, AOV_MODELS),
        aov_fusion_ml_weight=_float(
            "aov_fusion_ml_weight", DEFAULTS.aov_fusion_ml_weight, 0.0, 1.0
        ),
        confidence_z=_float("confidence_z", DEFAULTS.confidence_z, 1.0, 3.0),
        rf_n_estimators=_int("rf_n_estimators", DEFAULTS.rf_n_estimators, 50, 500),
        rf_max_depth=_int("rf_max_depth", DEFAULTS.rf_max_depth, 2, 12),
        gbr_n_estimators=_int("gbr_n_estimators", DEFAULTS.gbr_n_estimators, 50, 500),
        gbr_max_depth=_int("gbr_max_depth", DEFAULTS.gbr_max_depth, 2, 8),
        gbr_learning_rate=_float("gbr_learning_rate", DEFAULTS.gbr_learning_rate, 0.01, 0.3),
        ridge_alpha=_float("ridge_alpha", DEFAULTS.ridge_alpha, 0.1, 100.0),
    )
