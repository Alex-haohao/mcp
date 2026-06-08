#!/usr/bin/env python
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp_bridge.config import load_bridge_config_from_env
from mcp_bridge.runtime_env import build_child_base_env
from mcp_bridge.server_command import build_server_command


SERVER_NAME = "volcengine-web-search"


async def list_tools(timeout_seconds: float) -> list[str]:
    config = load_bridge_config_from_env(cwd=ROOT_DIR)
    child_env = build_child_base_env(os.environ, python_executable=sys.executable)
    command = build_server_command(
        SERVER_NAME,
        config=config,
        base_env=child_env,
        python_executable=sys.executable,
    )
    server = StdioServerParameters(
        command=command.argv[0],
        args=command.argv[1:],
        env=command.env,
    )

    async def run_client() -> list[str]:
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return [tool.name for tool in result.tools]

    return await asyncio.wait_for(run_client(), timeout=timeout_seconds)


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")
    if not os.getenv("VOLCENGINE_SEARCH_API_KEY"):
        print("VOLCENGINE_SEARCH_API_KEY is missing")
        return 1

    timeout_seconds = float(os.getenv("VOLCENGINE_SMOKE_TIMEOUT_SECONDS", "90"))
    try:
        tools = asyncio.run(list_tools(timeout_seconds))
    except Exception as exc:
        print(f"Smoke failed: {exc}")
        return 1

    print("Volcengine search MCP tools:")
    for tool in tools:
        print(f"- {tool}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
