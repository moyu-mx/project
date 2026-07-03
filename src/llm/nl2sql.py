"""NL2SQL 入口。"""
from __future__ import annotations

from src.llm.chat_engine import ChatResult, chat_query

async def nl2sql(question: str, mode: str = "local") -> str:
    result = await chat_query(question, mode_override=mode)
    return result.sql


async def chat(question: str, mode: str = "local") -> ChatResult:
    return await chat_query(question, mode_override=mode)
