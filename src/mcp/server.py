"""MCP Server：stdio 模式，供 Cursor/Claude Desktop 等客户端连接。"""
from __future__ import annotations

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.mcp.tools import MCP_TOOL_SPECS, dispatch_tool

server = Server("superstore-analytics")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name=t["name"], description=t["description"], inputSchema=t["inputSchema"])
        for t in MCP_TOOL_SPECS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = dispatch_tool(name, arguments or {})
    return [TextContent(type="text", text=result)]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
