"""FastAPI Web 应用。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import text
from starlette.requests import Request

from src.analysis.forecast_config import DEFAULTS, FORECAST_OPTIONS, ForecastParams, parse_forecast_params
from src.config import CHARTS_DIR, LOGS_DIR, PROJECT_ROOT
from src.db.connection import get_engine
from src.llm.chat_pipeline import run_chat_pipeline
from src.llm.chat_engine import load_llm_config

from web.chart_insights import build_insights
from web.dashboard_charts import (
    BUILDERS,
    DASHBOARD_SECTIONS,
    build_all_dashboard_charts,
    build_dashboard_chart,
    build_section_charts,
    list_rfm_years,
    _default_rfm_year,
)

FORECAST_PARAM_KEYS = frozenset(DEFAULTS.to_dict().keys())

WEB_DIR = PROJECT_ROOT / "web"
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
app = FastAPI(title="超市电商数据分析")
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

QUERY_LOG: dict[str, dict] = {}
FAVICON_PATH = WEB_DIR / "static" / "favicon.svg"


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    if FAVICON_PATH.exists():
        return FileResponse(FAVICON_PATH, media_type="image/svg+xml")
    raise HTTPException(404)


class ChatRequest(BaseModel):
    question: str
    mode: str = "local"  # local | api
    session_id: str | None = None


class FeedbackRequest(BaseModel):
    query_id: str
    correct: bool


def _year_bounds() -> dict[str, int]:
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT MIN(order_year), MAX(order_year) FROM orders WHERE order_year IS NOT NULL"
        )).fetchone()
    if not row or row[0] is None or row[1] is None:
        return {"min_year": 2011, "max_year": 2014}
    return {"min_year": int(row[0]), "max_year": int(row[1])}


def _db_stats(year_from: int | None = None, year_to: int | None = None) -> dict:
    engine = get_engine()
    with engine.connect() as conn:
        if year_from is None and year_to is None:
            return {
                "orders": conn.execute(text("SELECT COUNT(*) FROM orders")).scalar() or 0,
                "customers": conn.execute(text("SELECT COUNT(*) FROM customers")).scalar() or 0,
                "products": conn.execute(text("SELECT COUNT(*) FROM products")).scalar() or 0,
                "markets": conn.execute(text("SELECT COUNT(*) FROM regions")).scalar() or 0,
                "filtered": False,
            }

        yf = year_from if year_from is not None else year_to
        yt = year_to if year_to is not None else year_from
        if yf is None or yt is None:
            raise ValueError("请同时指定起止年份")
        if yf > yt:
            yf, yt = yt, yf
        params = {"yf": yf, "yt": yt}
        return {
            "orders": conn.execute(
                text("SELECT COUNT(*) FROM orders WHERE order_year BETWEEN :yf AND :yt"), params
            ).scalar() or 0,
            "customers": conn.execute(
                text("SELECT COUNT(DISTINCT customer_id) FROM orders WHERE order_year BETWEEN :yf AND :yt"),
                params,
            ).scalar() or 0,
            "products": conn.execute(
                text("SELECT COUNT(DISTINCT product_id) FROM orders WHERE order_year BETWEEN :yf AND :yt"),
                params,
            ).scalar() or 0,
            "markets": conn.execute(
                text("SELECT COUNT(DISTINCT market) FROM orders WHERE order_year BETWEEN :yf AND :yt"),
                params,
            ).scalar() or 0,
            "filtered": True,
            "year_from": yf,
            "year_to": yt,
        }


@app.get("/")
async def index(request: Request):
    charts = DASHBOARD_SECTIONS
    try:
        stats = _db_stats()
        insights = build_insights()
    except Exception:
        stats = {"orders": "-", "customers": "-", "products": "-", "markets": "-", "filtered": False}
        insights = {}
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "charts": charts,
            "stats": stats,
            "insights": insights,
            "insights_json": json.dumps(insights, ensure_ascii=False),
            "version": "1.4",
        },
    )


@app.get("/api/overview/years")
async def overview_years():
    return _year_bounds()


def _validate_year_range(year_from: int | None, year_to: int | None) -> tuple[int | None, int | None]:
    if year_from is None and year_to is None:
        return None, None
    if year_from is None or year_to is None:
        raise HTTPException(400, "请同时选择起止年份，或均选「全部」")
    bounds = _year_bounds()
    if year_from < bounds["min_year"] or year_to > bounds["max_year"]:
        raise HTTPException(
            400,
            f"年份需在 {bounds['min_year']}—{bounds['max_year']} 之间",
        )
    return year_from, year_to


def _validate_rfm_year(rfm_year: int | None) -> int:
    year = int(rfm_year) if rfm_year is not None else _default_rfm_year()
    available = list_rfm_years()
    if year not in available:
        raise HTTPException(400, f"RFM 年份无效，可选：{available}")
    return year


def _parse_forecast_params_from_query(query: dict[str, str]) -> ForecastParams:
    raw = {k: query[k] for k in FORECAST_PARAM_KEYS if k in query and query[k] != ""}
    try:
        return parse_forecast_params(raw or None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/dashboard/forecast/options")
async def forecast_options():
    return FORECAST_OPTIONS


@app.get("/api/overview/stats")
async def overview_stats(year_from: int | None = None, year_to: int | None = None):
    year_from, year_to = _validate_year_range(year_from, year_to)
    if year_from is None:
        return _db_stats()
    try:
        return _db_stats(year_from, year_to)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/dashboard/rfm/years")
async def rfm_years():
    years = list_rfm_years()
    return {"years": years, "default_year": _default_rfm_year()}


@app.get("/api/dashboard/charts")
async def dashboard_charts(
    request: Request,
    year_from: int | None = None,
    year_to: int | None = None,
    rfm_year: int | None = None,
):
    year_from, year_to = _validate_year_range(year_from, year_to)
    rfm_year = _validate_rfm_year(rfm_year)
    forecast_params = _parse_forecast_params_from_query(dict(request.query_params))
    return {
        "version": "1.4",
        "year_from": year_from,
        "year_to": year_to,
        "rfm_year": rfm_year,
        "forecast_params": forecast_params.to_dict(),
        "charts": build_all_dashboard_charts(year_from, year_to, rfm_year, forecast_params),
    }


@app.get("/api/dashboard/charts/section/{section}")
async def dashboard_section_charts(
    section: str,
    request: Request,
    year_from: int | None = None,
    year_to: int | None = None,
    rfm_year: int | None = None,
):
    if section not in DASHBOARD_SECTIONS:
        raise HTTPException(404, "模块不存在")
    if section == "rfm":
        rfm_year = _validate_rfm_year(rfm_year)
        return {
            "version": "1.4",
            "section": section,
            "rfm_year": rfm_year,
            "charts": build_section_charts(section, rfm_year=rfm_year),
        }
    if section == "forecast":
        forecast_params = _parse_forecast_params_from_query(dict(request.query_params))
        return {
            "version": "1.4",
            "section": section,
            "forecast_params": forecast_params.to_dict(),
            "charts": build_section_charts(section, forecast_params=forecast_params),
        }
    year_from, year_to = _validate_year_range(year_from, year_to)
    return {
        "version": "1.4",
        "section": section,
        "year_from": year_from,
        "year_to": year_to,
        "charts": build_section_charts(section, year_from, year_to),
    }


@app.get("/api/dashboard/charts/{chart_id}")
async def dashboard_chart(
    chart_id: str,
    request: Request,
    year_from: int | None = None,
    year_to: int | None = None,
    rfm_year: int | None = None,
):
    if chart_id not in BUILDERS:
        raise HTTPException(404, "图表不存在")
    year_from, year_to = _validate_year_range(year_from, year_to)
    rfm_year = _validate_rfm_year(rfm_year)
    forecast_params = _parse_forecast_params_from_query(dict(request.query_params))
    return build_dashboard_chart(chart_id, year_from, year_to, rfm_year, forecast_params)


@app.get("/charts/{name}")
async def chart(name: str):
    path = CHARTS_DIR / name
    if not path.exists():
        raise HTTPException(404, "图表不存在")
    return FileResponse(path)


@app.get("/api/chat/config")
async def chat_config():
    cfg = load_llm_config()
    return {
        "default_mode": "local",
        "api_enabled": bool(cfg.get("api_enabled", False)),
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "问题不能为空")
    mode = req.mode if req.mode in ("local", "api") else "local"
    query_id = str(uuid.uuid4())
    try:
        payload = await run_chat_pipeline(question, mode=mode)
        record = {
            "query_id": query_id,
            "question": question,
            **payload,
            "timestamp": datetime.now().isoformat(),
            "success": True,
        }
        QUERY_LOG[query_id] = record
        _append_log(record)
        return {"query_id": query_id, **payload}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        record = {
            "query_id": query_id,
            "question": question,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "success": False,
        }
        QUERY_LOG[query_id] = record
        _append_error(record)
        raise HTTPException(500, f"查询执行失败: {e}") from e


@app.post("/api/chat/feedback")
async def feedback(req: FeedbackRequest):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = LOGS_DIR / "feedback.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"query_id": req.query_id, "correct": req.correct}, ensure_ascii=False) + "\n")
    return {"ok": True}


@app.get("/api/diagnose/{query_id}")
async def diagnose(query_id: str):
    if query_id not in QUERY_LOG:
        raise HTTPException(404, "记录不存在")
    return QUERY_LOG[query_id]


def _append_log(record: dict) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with (LOGS_DIR / "nl2sql_queries.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _append_error(record: dict) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with (LOGS_DIR / "nl2sql_errors.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
