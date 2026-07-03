"""SQL 执行与结果格式化。"""
from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.db.connection import get_engine


def execute_query(sql: str, engine: Engine | None = None) -> dict[str, Any]:
    engine = engine or get_engine()
    start = time.perf_counter()
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        if not result.returns_rows:
            raise ValueError("查询未返回结果集")
        columns = list(result.keys())
        rows = [list(r) for r in result.fetchall()]
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "elapsed_ms": elapsed_ms,
    }
