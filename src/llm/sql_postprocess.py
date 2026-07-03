"""SQL 后处理与规范化。"""
from __future__ import annotations

import re

SQL_KEYWORDS = (
    "GROUP BY",
    "ORDER BY",
    "INNER JOIN",
    "LEFT JOIN",
    "RIGHT JOIN",
    "SELECT",
    "HAVING",
    "WHERE",
    "LIMIT",
    "FROM",
    "JOIN",
    "DESC",
    "ASC",
    "AND",
    "NOT",
    "OR",
    "ON",
    "AS",
    "BY",
    "SUM",
    "COUNT",
    "AVG",
    "MAX",
    "MIN",
)

_BROKEN_FRAGMENTS = (
    (re.compile(r"\bHAV\b(?=\s+ORDER\b)", re.I), ""),
    (re.compile(r"(\w)HAV\b(?=\s+ORDER\b)", re.I), r"\1"),
)


def normalize_sql_keywords(sql: str) -> str:
    """在数字/标识符与 SQL 关键字粘连时插入空格。"""
    for kw in sorted(SQL_KEYWORDS, key=len, reverse=True):
        pattern = re.compile(rf"([\w\d\)])({re.escape(kw)})\b", re.IGNORECASE)
        sql = pattern.sub(rf"\1 \2", sql)
    for pattern, repl in _BROKEN_FRAGMENTS:
        sql = pattern.sub(repl, sql)
    sql = re.sub(r"\s+", " ", sql).strip()
    return sql


def fix_years_from_question(sql: str, question: str = "") -> str:
    """将明显 typo 年份（如 2214）修正为问题中的年份。"""
    years_in_q = re.findall(r"20[0-9]{2}", question)
    if not years_in_q:
        return sql
    return re.sub(r"\b22[0-9]{2}\b", years_in_q[0], sql)


def fix_limit(sql: str, default: int = 100) -> str:
    if re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        return re.sub(r"\bLIMIT\s+\d+\b", f"LIMIT {default}", sql, flags=re.IGNORECASE)
    return f"{sql} LIMIT {default}"


def postprocess_sql(sql: str, question: str = "") -> str:
    sql = sql.strip().strip("`").strip()
    sql = re.sub(r"^```sql\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"```\s*$", "", sql)
    sql = sql.rstrip(";").strip()
    sql = normalize_sql_keywords(sql)
    sql = fix_years_from_question(sql, question)
    sql = fix_limit(sql)
    return sql
