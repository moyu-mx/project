"""Minimal DeepSeek connectivity test."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm.chat_engine import load_llm_config


async def main() -> None:
    cfg = load_llm_config()
    print("has_key:", bool(cfg.get("api", {}).get("api_key")), flush=True)
    from openai import AsyncOpenAI

    api_cfg = cfg["api"]
    client = AsyncOpenAI(
        api_key=api_cfg["api_key"],
        base_url=api_cfg["base_url"],
        timeout=60.0,
    )
    resp = await client.chat.completions.create(
        model=api_cfg["model"],
        messages=[{"role": "user", "content": "Reply with JSON: {\"ok\": true}"}],
        temperature=0,
        max_tokens=50,
    )
    print("content:", resp.choices[0].message.content, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
