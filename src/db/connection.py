"""数据库连接。"""
from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.config import CONFIG_DIR, DB_PATH, SQL_SCHEMA


def get_engine(db_path: Path | None = None) -> Engine:
    db_path = db_path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # timeout 避免 Windows 下 db 被占用时立即失败
    return create_engine(
        f"sqlite:///{db_path.as_posix()}?timeout=30",
        future=True,
        connect_args={"check_same_thread": False},
    )


def init_schema(engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    ddl = SQL_SCHEMA.read_text(encoding="utf-8")
    with engine.begin() as conn:
        for stmt in ddl.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))


def load_db_config() -> dict:
    path = CONFIG_DIR / "db.yaml"
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}
