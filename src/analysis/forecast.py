"""时间序列预测：基于原始订单数据，对关键指标做 2015 年展望。"""
from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analysis import load_cleaned, save_fig
from src.analysis.forecast_config import DEFAULTS, ForecastParams
from src.config import CHARTS_DIR

FORECAST_YEAR = 2015
HISTORY_START = 2011
HISTORY_END = 2014


def _month_idx(year: int, month: int) -> int:
    return (year - HISTORY_START) * 12 + (month - 1)


def _linear_fit(x: np.ndarray, y: np.ndarray, degree: int = 1) -> tuple[np.ndarray, float, np.ndarray]:
    degree = max(1, min(int(degree), 3))
    coef = np.polyfit(x, y, degree)
    fitted = np.polyval(coef, x)
    resid = y - fitted
    n = len(y)
    dof = max(n - (degree + 1), 1)
    std = float(np.sqrt(np.sum(resid ** 2) / dof))
    return coef, std, fitted


def _predict_linear(
    coef: np.ndarray,
    x: np.ndarray,
    std: float,
    z: float = 1.96,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pred = np.polyval(coef, x)
    x_mean = np.mean(x)
    margin = z * std * (1 + 0.05 * np.abs(x - x_mean))
    return pred, pred - margin, pred + margin


def _fmt(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"{v / 1_000:.1f}K"
    return f"{v:.0f}"


def _load_history() -> pd.DataFrame:
    df = load_cleaned()
    return df[(df["Order-year"] >= HISTORY_START) & (df["Order-year"] <= HISTORY_END)].copy()


# ---------- 年度销售额：月度线性回归（已恢复） ----------


def _compute_sales_forecast(df: pd.DataFrame, report: dict, params: ForecastParams) -> None:
    """年度销售额：月度回归，外推 2015 全年。"""
    monthly = (
        df.groupby(["Order-year", "Order-month"])["Sales"]
        .sum()
        .reset_index()
    )
    monthly["t"] = monthly.apply(lambda r: _month_idx(int(r["Order-year"]), int(r["Order-month"])), axis=1)
    x = monthly["t"].to_numpy(dtype=float)
    y = monthly["Sales"].to_numpy(dtype=float)
    degree = params.sales_poly_degree if params.sales_model == "polynomial" else 1
    coef, std, _ = _linear_fit(x, y, degree)

    yearly_actual = df.groupby("Order-year")["Sales"].sum()
    years_hist = list(range(HISTORY_START, HISTORY_END + 1))
    y_vals = [float(yearly_actual.get(y, 0)) for y in years_hist]

    t_2015 = np.array([_month_idx(FORECAST_YEAR, m) for m in range(1, 13)], dtype=float)
    m_pred, m_lo, m_hi = _predict_linear(coef, t_2015, std, z=params.confidence_z)
    pred_2015 = float(m_pred.sum())
    lo_2015 = float(m_lo.sum())
    hi_2015 = float(m_hi.sum())

    if params.sales_model == "polynomial":
        method = f"月度销售额 {degree} 次多项式回归，汇总为 {FORECAST_YEAR} 年度预测"
    else:
        method = f"月度销售额一元线性回归，汇总为 {FORECAST_YEAR} 年度预测"

    report["sales_forecast"] = {
        "method": method,
        "model": params.sales_model,
        "forecast_year": FORECAST_YEAR,
        "predicted": pred_2015,
        "lower": lo_2015,
        "upper": hi_2015,
        "history": {str(y): float(yearly_actual.get(y, 0)) for y in years_hist},
        "_plot": {"years_hist": years_hist, "y_vals": y_vals, "pred_2015": pred_2015, "lo_2015": lo_2015, "hi_2015": hi_2015},
    }


def _chart_sales_forecast(df: pd.DataFrame, report: dict, params: ForecastParams) -> None:
    _compute_sales_forecast(df, report, params)
    plot = report["sales_forecast"].pop("_plot", {})
    years_hist = plot.get("years_hist", list(range(HISTORY_START, HISTORY_END + 1)))
    y_vals = plot.get("y_vals", [])
    pred_2015 = plot.get("pred_2015", 0)
    lo_2015 = plot.get("lo_2015", pred_2015)
    hi_2015 = plot.get("hi_2015", pred_2015)
    fig, ax = plt.subplots(figsize=(10, 5))
    labels = [str(y) for y in years_hist] + [str(FORECAST_YEAR)]
    xpos = np.arange(len(labels))
    ax.bar(xpos[:-1], y_vals, color="cornflowerblue", label="实际")
    ax.bar(xpos[-1], pred_2015, color="mediumseagreen", label="预测", alpha=0.85)
    ax.errorbar(
        xpos[-1], pred_2015,
        yerr=[[pred_2015 - lo_2015], [hi_2015 - pred_2015]],
        fmt="none", ecolor="darkgreen", capsize=6,
    )
    ax.set_xticks(xpos)
    ax.set_xticklabels(labels)
    ax.set_ylabel("销售额")
    ax.set_title(f"年度销售额预测（{FORECAST_YEAR} 为线性外推）")
    ax.legend()
    ax.text(xpos[-1], pred_2015 * 1.02, _fmt(pred_2015), ha="center", fontsize=9)
    save_fig("sales_forecast.png")


# ---------- 淡旺季：线性趋势 + 季节指数 ----------


def _compute_seasonality_forecast(df: pd.DataFrame, report: dict, params: ForecastParams) -> None:
    monthly = (
        df.groupby(["Order-year", "Order-month"])["Sales"]
        .sum()
        .reset_index()
    )
    monthly["t"] = monthly.apply(lambda r: _month_idx(int(r["Order-year"]), int(r["Order-month"])), axis=1)
    x = monthly["t"].to_numpy(dtype=float)
    y = monthly["Sales"].to_numpy(dtype=float)
    coef, std, _ = _linear_fit(x, y)

    month_avg = monthly.groupby("Order-month")["Sales"].mean()
    overall_mean = float(monthly["Sales"].mean())
    seasonal = (month_avg / overall_mean).to_dict()
    use_seasonal = params.seasonality_model == "linear_seasonal"

    pred_months: dict[str, float] = {}
    fc_x, fc_y, fc_lo, fc_hi = [], [], [], []
    for m in range(1, 13):
        t = _month_idx(FORECAST_YEAR, m)
        trend_val = float(np.polyval(coef, t))
        factor = float(seasonal.get(m, 1.0)) if use_seasonal else 1.0
        adj = trend_val * factor
        _, lo, hi = _predict_linear(coef, np.array([t], dtype=float), std, z=params.confidence_z)
        adj_lo = float(lo[0]) * factor
        adj_hi = float(hi[0]) * factor
        pred_months[str(m)] = adj
        fc_x.append(m)
        fc_y.append(adj)
        fc_lo.append(adj_lo)
        fc_hi.append(adj_hi)

    peak_m = max(pred_months, key=pred_months.get)
    method = (
        "月度线性趋势 + 历史季节指数（同月均值/总均值）"
        if use_seasonal
        else "月度线性趋势（不含季节指数）"
    )
    report["seasonality_forecast"] = {
        "method": method,
        "model": params.seasonality_model,
        "forecast_year": FORECAST_YEAR,
        "monthly": pred_months,
        "annual_total": sum(pred_months.values()),
        "peak_month": int(peak_m),
        "_plot": {"monthly_df": monthly, "fc_x": fc_x, "fc_y": fc_y, "fc_lo": fc_lo, "fc_hi": fc_hi},
    }


def _chart_seasonality_forecast(df: pd.DataFrame, report: dict, params: ForecastParams) -> None:
    _compute_seasonality_forecast(df, report, params)
    plot = report["seasonality_forecast"].pop("_plot", {})
    monthly = plot.get("monthly_df")
    fc_x = plot.get("fc_x", [])
    fc_y = plot.get("fc_y", [])
    fc_lo = plot.get("fc_lo", [])
    fc_hi = plot.get("fc_hi", [])

    fig, ax = plt.subplots(figsize=(10, 5))
    if monthly is not None:
        for year in range(HISTORY_START, HISTORY_END + 1):
            s = monthly[monthly["Order-year"] == year]
            ax.plot(s["Order-month"], s["Sales"], marker="o", label=str(year))
    ax.plot(fc_x, fc_y, marker="D", linestyle="--", color="gold", linewidth=2, label=f"{FORECAST_YEAR} 预测")
    ax.fill_between(fc_x, fc_lo, fc_hi, alpha=0.15, color="gold")
    ax.set_title(f"月度销售额淡旺季与 {FORECAST_YEAR} 预测")
    ax.set_xlabel("月份")
    ax.set_ylabel("销售额")
    ax.legend(loc="upper left", fontsize=8)
    save_fig("seasonality_forecast.png")


# ---------- 前六区域：各区域年度线性回归（已恢复） ----------


def _compute_region_forecast(df: pd.DataFrame, report: dict, params: ForecastParams) -> None:
    top_n = max(3, min(int(params.region_top_n), 10))
    top_markets = df.groupby("Market")["Sales"].sum().nlargest(top_n).index.tolist()
    yearly = (
        df[df["Market"].isin(top_markets)]
        .groupby(["Market", "Order-year"])["Sales"]
        .sum()
        .unstack(fill_value=0)
    )

    years = list(range(HISTORY_START, HISTORY_END + 1))
    x = np.array(years, dtype=float)
    preds: dict[str, dict] = {}
    plot_lines: list[dict] = []

    for market in top_markets:
        y_hist = np.array([float(yearly.loc[market, y]) if y in yearly.columns else 0.0 for y in years])
        coef, std, _ = _linear_fit(x, y_hist)
        pred, lo, hi = _predict_linear(coef, np.array([FORECAST_YEAR], dtype=float), std, z=params.confidence_z)
        preds[market] = {
            "predicted": float(pred[0]),
            "lower": float(lo[0]),
            "upper": float(hi[0]),
            "history": {str(y): float(y_hist[j]) for j, y in enumerate(years)},
        }
        plot_lines.append({"market": market, "years": years, "y_hist": y_hist, "pred": float(pred[0])})

    report["region_forecast"] = {
        "method": f"各区域年度销售额独立线性回归（Top {top_n}）",
        "model": params.region_model,
        "forecast_year": FORECAST_YEAR,
        "markets": preds,
        "_plot": {"top_markets": top_markets, "lines": plot_lines, "years": years},
    }


def _chart_region_forecast(df: pd.DataFrame, report: dict, params: ForecastParams) -> None:
    _compute_region_forecast(df, report, params)
    plot = report["region_forecast"].pop("_plot", {})
    top_markets = plot.get("top_markets", [])
    lines = plot.get("lines", [])
    years = plot.get("years", list(range(HISTORY_START, HISTORY_END + 1)))
    preds = report["region_forecast"]["markets"]

    fig, ax = plt.subplots(figsize=(10, 5))
    for line in lines:
        market = line["market"]
        y_hist = line["y_hist"]
        pred = line["pred"]
        ax.plot(years, y_hist, marker="o", label=f"{market}")
        ax.plot([years[-1], FORECAST_YEAR], [y_hist[-1], pred], linestyle="--", alpha=0.7)

    ax.scatter(
        [FORECAST_YEAR] * len(top_markets),
        [preds[m]["predicted"] for m in top_markets],
        marker="*", s=120, color="gold", zorder=5, label=f"{FORECAST_YEAR} 预测",
    )
    ax.set_xticks(years + [FORECAST_YEAR])
    ax.set_title(f"前六区域年度销售额与 {FORECAST_YEAR} 预测")
    ax.set_xlabel("年份")
    ax.set_ylabel("销售额")
    ax.legend(loc="upper left", fontsize=8)
    save_fig("region_forecast.png")


# ---------- 客单价：ML 融合模型（保留） ----------


def _yearly_aov(df: pd.DataFrame, years: list[int]) -> list[float]:
    return [
        float(df[df["Order-year"] == y]["Sales"].sum() / max(df[df["Order-year"] == y]["Customer ID"].nunique(), 1))
        for y in years
    ]


def _serialize_monthly_aov(monthly: pd.DataFrame) -> list[dict[str, float | int | str]]:
    """序列化月度客单价历史，供 Web 图表使用。"""
    sorted_df = monthly.sort_values("t")
    ma3 = sorted_df["aov"].rolling(3, min_periods=1).mean()
    rows: list[dict[str, float | int | str]] = []
    for i, (_, row) in enumerate(sorted_df.iterrows()):
        year = int(row["Order-year"])
        month = int(row["Order-month"])
        rows.append({
            "label": f"{year}-{month:02d}",
            "year": year,
            "month": month,
            "aov": round(float(row["aov"]), 2),
            "ma3": round(float(ma3.iloc[i]), 2),
        })
    return rows


def _monthly_sales_customers(df: pd.DataFrame) -> pd.DataFrame:
    monthly = (
        df.groupby(["Order-year", "Order-month"])
        .agg(sales=("Sales", "sum"), customers=("Customer ID", "nunique"))
        .reset_index()
    )
    monthly["t"] = monthly.apply(
        lambda r: _month_idx(int(r["Order-year"]), int(r["Order-month"])), axis=1
    )
    monthly["aov"] = monthly["sales"] / monthly["customers"].clip(lower=1)
    return monthly.sort_values("t")


AOV_FEATURE_COLS = ["t", "month_sin", "month_cos", "year_norm", "lag_1", "lag_12", "roll3", "roll6", "sales", "customers"]
SALES_FEATURE_COLS = ["t", "month_sin", "month_cos", "year_norm", "s_lag_1", "s_lag_12", "s_roll3"]
CUST_FEATURE_COLS = ["t", "month_sin", "month_cos", "year_norm", "c_lag_1", "c_lag_12", "c_roll3"]
YEAR_AOV_FEATURE_COLS = ["year_norm", "sales", "customers", "m_aov_mean", "m_aov_std", "m_sales_mean", "sales_growth", "cust_growth"]


def _enrich_series_features(monthly: pd.DataFrame) -> pd.DataFrame:
    m = monthly.sort_values("t").copy().reset_index(drop=True)
    m["month_sin"] = np.sin(2 * np.pi * m["Order-month"] / 12)
    m["month_cos"] = np.cos(2 * np.pi * m["Order-month"] / 12)
    m["year_norm"] = m["Order-year"] - HISTORY_START
    for lag in (1, 2, 3, 12):
        m[f"lag_{lag}"] = m["aov"].shift(lag)
        m[f"s_lag_{lag}"] = m["sales"].shift(lag)
        m[f"c_lag_{lag}"] = m["customers"].shift(lag)
    m["roll3"] = m["aov"].rolling(3, min_periods=1).mean()
    m["roll6"] = m["aov"].rolling(6, min_periods=1).mean()
    m["s_roll3"] = m["sales"].rolling(3, min_periods=1).mean()
    m["c_roll3"] = m["customers"].rolling(3, min_periods=1).mean()
    return m


def _build_year_aov_table(df: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    years = list(range(HISTORY_START, HISTORY_END + 1))
    prev_sales, prev_cust = None, None
    for y in years:
        sub = df[df["Order-year"] == y]
        msub = monthly[monthly["Order-year"] == y]
        sales = float(sub["Sales"].sum())
        cust = int(sub["Customer ID"].nunique())
        sg = (sales - prev_sales) / prev_sales if prev_sales else 0.0
        cg = (cust - prev_cust) / prev_cust if prev_cust else 0.0
        rows.append({
            "Order-year": y,
            "year_norm": y - HISTORY_START,
            "sales": sales,
            "customers": cust,
            "aov": sales / max(cust, 1),
            "m_aov_mean": float(msub["aov"].mean()),
            "m_aov_std": float(msub["aov"].std()),
            "m_sales_mean": float(msub["sales"].mean()),
            "sales_growth": sg,
            "cust_growth": cg,
        })
        prev_sales, prev_cust = sales, cust
    return pd.DataFrame(rows)


def _extrapolate_year_features(year_df: pd.DataFrame, forecast_year: int) -> dict:
    x = year_df["year_norm"].to_numpy(dtype=float)
    out: dict = {"Order-year": forecast_year, "year_norm": forecast_year - HISTORY_START}
    for col in YEAR_AOV_FEATURE_COLS:
        if col == "year_norm":
            continue
        y = year_df[col].to_numpy(dtype=float)
        coef = np.polyfit(x, y, 1)
        out[col] = float(np.polyval(coef, out["year_norm"]))
    out["customers"] = max(out["customers"], 1.0)
    return out


def _candidate_models(params: ForecastParams | None = None) -> dict:
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import Ridge

    p = params or DEFAULTS
    return {
        "RandomForest": RandomForestRegressor(
            n_estimators=p.rf_n_estimators,
            max_depth=p.rf_max_depth,
            min_samples_leaf=3,
            random_state=42,
        ),
        "GradientBoosting": GradientBoostingRegressor(
            n_estimators=p.gbr_n_estimators,
            max_depth=p.gbr_max_depth,
            learning_rate=p.gbr_learning_rate,
            subsample=0.9,
            random_state=42,
        ),
        "Ridge": Ridge(alpha=p.ridge_alpha),
    }


def _pick_best_model(
    x: np.ndarray,
    y: np.ndarray,
    params: ForecastParams | None = None,
) -> tuple[str, object, float]:
    from sklearn.linear_model import Ridge

    p = params or DEFAULTS
    candidates = _candidate_models(p) if len(x) > 5 else {"Ridge": Ridge(alpha=p.ridge_alpha)}
    best_name, best_model, best_mae = "", None, float("inf")
    for name, model in candidates.items():
        mae = _cv_mae(model, x, y)
        if mae < best_mae:
            best_name, best_model, best_mae = name, model, mae
    assert best_model is not None
    best_model.fit(x, y)
    return best_name, best_model, best_mae


def _resolve_model(
    choice: str,
    x: np.ndarray,
    y: np.ndarray,
    params: ForecastParams,
) -> tuple[str, object, float]:
    if choice == "auto" or len(x) <= 5:
        return _pick_best_model(x, y, params)
    from sklearn.base import clone

    candidates = _candidate_models(params)
    if choice not in candidates:
        raise ValueError(f"未知模型: {choice}")
    model = clone(candidates[choice])
    mae = _cv_mae(model, x, y)
    model.fit(x, y)
    return choice, model, mae


def _cv_mae(model, x: np.ndarray, y: np.ndarray) -> float:
    from sklearn.base import clone
    from sklearn.model_selection import TimeSeriesSplit

    n = len(x)
    if n < 3:
        return float(np.std(y)) if n else 0.0
    if n < 8:
        maes = []
        for i in range(2, n):
            m = clone(model)
            m.fit(x[:i], y[:i])
            pred = m.predict(x[i : i + 1])
            maes.append(float(np.abs(y[i] - pred[0])))
        return float(np.mean(maes)) if maes else float(np.std(y))
    tscv = TimeSeriesSplit(n_splits=min(4, max(2, n // 10)))
    maes = []
    for train_idx, test_idx in tscv.split(x):
        m = clone(model)
        m.fit(x[train_idx], y[train_idx])
        pred = m.predict(x[test_idx])
        maes.append(float(np.mean(np.abs(y[test_idx] - pred))))
    return float(np.mean(maes)) if maes else float(np.std(y))


def _row_from_history(history: list[dict], year: int, month: int) -> dict:
    rows = [r for r in history if r.get("Order-year") != year or r.get("Order-month") != month]
    aov_s = [r["aov"] for r in rows]
    sales_s = [r["sales"] for r in rows]
    cust_s = [r["customers"] for r in rows]

    def _lag(seq: list[float], n: int) -> float:
        return float(seq[-n]) if len(seq) >= n else float(np.mean(seq))

    return {
        "Order-year": year,
        "Order-month": month,
        "t": _month_idx(year, month),
        "month_sin": float(np.sin(2 * np.pi * month / 12)),
        "month_cos": float(np.cos(2 * np.pi * month / 12)),
        "year_norm": year - HISTORY_START,
        "lag_1": _lag(aov_s, 1),
        "lag_12": _lag(aov_s, 12),
        "roll3": float(np.mean(aov_s[-3:])),
        "roll6": float(np.mean(aov_s[-6:])),
        "sales": _lag(sales_s, 1),
        "customers": _lag(cust_s, 1),
        "s_lag_1": _lag(sales_s, 1),
        "s_lag_12": _lag(sales_s, 12),
        "s_roll3": float(np.mean(sales_s[-3:])),
        "c_lag_1": _lag(cust_s, 1),
        "c_lag_12": _lag(cust_s, 12),
        "c_roll3": float(np.mean(cust_s[-3:])),
        "aov": _lag(aov_s, 1),
    }


def _recursive_monthly_forecast(
    monthly: pd.DataFrame,
    model_sales: object,
    model_cust: object,
    resid_std: float,
    z: float = 1.96,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    history = monthly.to_dict("records")
    pred_sales_m: list[float] = []
    pred_cust_m: list[float] = []
    for month in range(1, 13):
        base = _row_from_history(history, FORECAST_YEAR, month)
        pred_s = float(model_sales.predict(np.array([[base[k] for k in SALES_FEATURE_COLS]], dtype=float))[0])
        pred_c = max(float(model_cust.predict(np.array([[base[k] for k in CUST_FEATURE_COLS]], dtype=float))[0]), 1.0)
        pred_aov = pred_s / pred_c
        base.update({"sales": pred_s, "customers": pred_c, "aov": pred_aov})
        history.append(base)
        pred_sales_m.append(pred_s)
        pred_cust_m.append(pred_c)
    pred_aov_m = np.array([s / c for s, c in zip(pred_sales_m, pred_cust_m)])
    margin = z * resid_std
    t_fc = np.array([_month_idx(FORECAST_YEAR, m) for m in range(1, 13)], dtype=float)
    return t_fc, pred_aov_m, np.maximum(pred_aov_m - margin, 0), pred_aov_m + margin, float(sum(pred_sales_m))


def _compute_aov_forecast(df: pd.DataFrame, report: dict, params: ForecastParams) -> None:
    monthly = _monthly_sales_customers(df)
    enriched = _enrich_series_features(monthly)
    train_df = enriched.loc[enriched["lag_12"].notna()]

    sales_x = train_df[SALES_FEATURE_COLS].to_numpy(dtype=float)
    sales_y = train_df["sales"].to_numpy(dtype=float)
    cust_x = train_df[CUST_FEATURE_COLS].to_numpy(dtype=float)
    cust_y = train_df["customers"].to_numpy(dtype=float)
    aov_x = train_df[AOV_FEATURE_COLS].to_numpy(dtype=float)
    aov_y = train_df["aov"].to_numpy(dtype=float)

    sales_name, model_sales, _ = _resolve_model(params.aov_sales_model, sales_x, sales_y, params)
    cust_name, model_cust, _ = _resolve_model(params.aov_customers_model, cust_x, cust_y, params)
    _, _, aov_mae = _resolve_model("auto", aov_x, aov_y, params)

    t_2015, pred_aov_m, aov_lo_m, aov_hi_m, pred_sales_rf = _recursive_monthly_forecast(
        monthly, model_sales, model_cust, aov_mae, z=params.confidence_z
    )

    year_df = _build_year_aov_table(df, monthly)
    year_x = year_df[YEAR_AOV_FEATURE_COLS].to_numpy(dtype=float)
    year_y = year_df["aov"].to_numpy(dtype=float)
    year_name, model_year, year_cv_mae = _resolve_model(params.aov_annual_model, year_x, year_y, params)
    feat_2015 = _extrapolate_year_features(year_df, FORECAST_YEAR)
    pred_annual_ml = float(model_year.predict(
        np.array([[feat_2015[c] for c in YEAR_AOV_FEATURE_COLS]], dtype=float)
    )[0])
    pred_annual_rf = pred_sales_rf / max(feat_2015["customers"], 1.0)
    ml_w = params.aov_fusion_ml_weight
    pred_annual = ml_w * pred_annual_ml + (1 - ml_w) * pred_annual_rf

    years = list(range(HISTORY_START, HISTORY_END + 1))
    aov_yearly = _yearly_aov(df, years)
    resid = float(np.std(year_y - model_year.predict(year_x)))
    z = params.confidence_z

    def _display_model(choice: str, resolved: str) -> str:
        return resolved if choice == "auto" else choice

    report["aov_forecast"] = {
        "method": (
            f"ML 融合：月度 {_display_model(params.aov_sales_model, sales_name)}/"
            f"{_display_model(params.aov_customers_model, cust_name)} 递归预测 + "
            f"年度 {_display_model(params.aov_annual_model, year_name)} 特征回归"
        ),
        "forecast_year": FORECAST_YEAR,
        "model_sales": _display_model(params.aov_sales_model, sales_name),
        "model_customers": _display_model(params.aov_customers_model, cust_name),
        "model_annual": _display_model(params.aov_annual_model, year_name),
        "fusion_ml_weight": ml_w,
        "cv_mae": aov_mae,
        "predicted_monthly_avg": float(np.mean(pred_aov_m)),
        "predicted_monthly": {str(m): float(pred_aov_m[i]) for i, m in enumerate(range(1, 13))},
        "lower_monthly": {str(m): float(aov_lo_m[i]) for i, m in enumerate(range(1, 13))},
        "upper_monthly": {str(m): float(aov_hi_m[i]) for i, m in enumerate(range(1, 13))},
        "lower_monthly_avg": float(np.mean(aov_lo_m)),
        "upper_monthly_avg": float(np.mean(aov_hi_m)),
        "monthly_history": _serialize_monthly_aov(monthly),
        "predicted_annual": pred_annual,
        "lower_annual": pred_annual - z * resid,
        "upper_annual": pred_annual + z * resid,
        "predicted_sales": pred_sales_rf,
        "predicted_customers": feat_2015["customers"],
        "history": {str(y): v for y, v in zip(years, aov_yearly)},
        "customer_history": {str(int(r["Order-year"])): int(r["customers"]) for _, r in year_df.iterrows()},
        "_plot": {
            "years": years,
            "aov_yearly": aov_yearly,
            "pred_annual": pred_annual,
            "resid": resid,
            "year_name": year_name,
            "year_cv_mae": year_cv_mae,
            "monthly": monthly,
            "t_2015": t_2015,
            "pred_aov_m": pred_aov_m,
            "aov_lo_m": aov_lo_m,
            "aov_hi_m": aov_hi_m,
            "sales_name": sales_name,
            "aov_mae": aov_mae,
        },
    }


def _chart_aov_forecast(df: pd.DataFrame, report: dict, params: ForecastParams) -> None:
    _compute_aov_forecast(df, report, params)
    plot = report["aov_forecast"].pop("_plot", {})
    years = plot.get("years", list(range(HISTORY_START, HISTORY_END + 1)))
    aov_yearly = plot.get("aov_yearly", [])
    pred_annual = plot.get("pred_annual", 0)
    resid = plot.get("resid", 0)
    year_name = plot.get("year_name", "")
    year_cv_mae = plot.get("year_cv_mae", 0)
    monthly = plot.get("monthly")
    t_2015 = plot.get("t_2015")
    pred_aov_m = plot.get("pred_aov_m")
    aov_lo_m = plot.get("aov_lo_m")
    aov_hi_m = plot.get("aov_hi_m")
    sales_name = plot.get("sales_name", "")
    aov_mae = plot.get("aov_mae", 0)
    z = params.confidence_z

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1, 1.15]})
    ax0 = axes[0]
    ax0.plot(years, aov_yearly, marker="s", color="green", linewidth=2, label="年度实际")
    ax0.plot([years[-1], FORECAST_YEAR], [aov_yearly[-1], pred_annual], linestyle="--", color="gold", marker="o", linewidth=2, label=f"{FORECAST_YEAR} 预测")
    ax0.fill_between([FORECAST_YEAR], [pred_annual - z * resid], [pred_annual + z * resid], alpha=0.25, color="gold")
    ax0.set_xticks(years + [FORECAST_YEAR])
    ax0.set_title(f"年度客单价（{year_name}，CV MAE≈{year_cv_mae:.0f}）")
    ax0.set_ylabel("年度客单价（元）")
    ax0.legend(loc="upper left", fontsize=8)

    ax1 = axes[1]
    if monthly is not None:
        x = monthly["t"].to_numpy(dtype=float)
        ax1.plot(x, monthly["aov"], color="green", alpha=0.3, linewidth=1, label="月度实际")
        ax1.plot(x, monthly["aov"].rolling(3, min_periods=1).mean(), color="seagreen", linewidth=1.5, label="3月均线")
    if t_2015 is not None and pred_aov_m is not None:
        ax1.plot(t_2015, pred_aov_m, linestyle="--", color="gold", marker="o", linewidth=2, label=f"{FORECAST_YEAR} 预测")
        ax1.fill_between(t_2015, aov_lo_m, aov_hi_m, alpha=0.2, color="gold")
    ax1.set_title(f"月度明细（{sales_name} 递归，MAE≈{aov_mae:.0f}）")
    ax1.set_xlabel("年份")
    ax1.set_ylabel("月度客单价（元）")
    ax1.legend(loc="upper left", fontsize=8)
    fig.suptitle(f"客单价预测 · {FORECAST_YEAR} 年约 {pred_annual:.0f} 元", fontsize=11)
    fig.tight_layout()
    save_fig("aov_forecast.png")


def compute_forecast_report(params: ForecastParams | None = None, *, save_charts: bool = False) -> dict:
    """按配置计算预测报告；save_charts=True 时同时写入 PNG。"""
    p = params or DEFAULTS
    df = _load_history()
    report: dict = {
        "forecast_year": FORECAST_YEAR,
        "data_granularity": "orders 原始月度明细聚合",
        "params": p.to_dict(),
    }
    if save_charts:
        _chart_sales_forecast(df, report, p)
        _chart_aov_forecast(df, report, p)
        _chart_seasonality_forecast(df, report, p)
        _chart_region_forecast(df, report, p)
    else:
        _compute_sales_forecast(df, report, p)
        report["sales_forecast"].pop("_plot", None)
        _compute_aov_forecast(df, report, p)
        report["aov_forecast"].pop("_plot", None)
        _compute_seasonality_forecast(df, report, p)
        report["seasonality_forecast"].pop("_plot", None)
        _compute_region_forecast(df, report, p)
        report["region_forecast"].pop("_plot", None)
    return report


def run() -> dict:
    report = compute_forecast_report(DEFAULTS, save_charts=True)
    out = CHARTS_DIR.parent / "forecast_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    run()
