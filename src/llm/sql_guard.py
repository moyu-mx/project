"""SQL 安全校验。"""
from __future__ import annotations

import re

FORBIDDEN = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE|REPLACE|ATTACH|DETACH|PRAGMA)\b",
    re.IGNORECASE,
)
ALLOWED_START = re.compile(r"^\s*SELECT\b", re.IGNORECASE | re.DOTALL)


def validate_sql(sql: str) -> tuple[bool, str]:
    sql = sql.strip().rstrip(";")
    if not sql:
        return False, "SQL 为空"
    if ";" in sql:
        return False, "不允许多语句"
    if not ALLOWED_START.match(sql):
        return False, "仅允许 SELECT 查询"
    if FORBIDDEN.search(sql):
        return False, "包含禁止的关键字"
    if re.search(r"\bsqlite_\w+", sql, re.IGNORECASE):
        return False, "禁止访问系统表"
    return True, "ok"
