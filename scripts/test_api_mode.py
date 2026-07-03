"""Quick test for DeepSeek API mode."""
import asyncio

from src.llm.chat_engine import chat_query, load_llm_config


async def main() -> None:
    cfg = load_llm_config()
    print("api_enabled:", cfg.get("api_enabled"))
    print("has_key:", bool(cfg.get("api", {}).get("api_key")))
    print("model:", cfg.get("api", {}).get("model"))
    result = await chat_query("2014 region sales by market", mode_override="api")
    print("mode:", result.mode)
    print("sql:", result.sql[:200])
    print("tools:", result.tools_used)
    print("reasoning:", result.reasoning[:300])


if __name__ == "__main__":
    asyncio.run(main())
