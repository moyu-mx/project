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

from src.config import CHARTS_DIR, LOGS_DIR, PROJECT_ROOT
from src.db.connection import get_engine
from src.llm.chat_pipeline import run_chat_pipeline
from src.llm.chat_engine import load_llm_config

from web.chart_insights import build_insights

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


def _db_stats() -> dict:
    engine = get_engine()
    with engine.connect() as conn:
        return {
            "orders": conn.execute(text("SELECT COUNT(*) FROM orders")).scalar() or 0,
            "customers": conn.execute(text("SELECT COUNT(*) FROM customers")).scalar() or 0,
            "products": conn.execute(text("SELECT COUNT(*) FROM products")).scalar() or 0,
            "markets": conn.execute(text("SELECT COUNT(*) FROM regions")).scalar() or 0,
        }


@app.get("/")
async def index(request: Request):
    charts = {
        "sales": ["sales_growth.png", "avg_order_value.png", "profit_by_month.png", "seasonality_sales.png", "shipping_cost_trend.png"],
        "region": ["region_share.png", "region_yearly_sales_top6.png"],
        "customer": [
            "new_old_customers.png",
            "segment_yearly_count.png",
            "segment_yearly_sales.png",
            "segment_category_sales.png",
            "segment_share.png",
        ],
        "rfm": ["rfm_distribution.png"],
        "forecast": [
            "sales_forecast.png",
            "aov_forecast.png",
            "seasonality_forecast.png",
            "region_forecast.png",
        ],
    }
    try:
        stats = _db_stats()
        insights = build_insights()
    except Exception:
        stats = {"orders": "-", "customers": "-", "products": "-", "markets": "-"}
        insights = {}
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "charts": charts,
            "stats": stats,
            "insights": insights,
            "insights_json": json.dumps(insights, ensure_ascii=False),
        },
    )


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
