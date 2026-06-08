#!/usr/bin/env python
from __future__ import annotations

import argparse
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
from mcp_bridge.tool_policy import ToolPolicy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start one configured MCP server and list bridge-visible tools."
    )
    parser.add_argument("server", help="Configured server name from mcp_config.json.")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.getenv("MCP_SMOKE_TIMEOUT_SECONDS", "90")),
    )
    return parser.parse_args()


async def list_tools(server_name: str, timeout_seconds: float) -> list[str]:
    config = load_bridge_config_from_env(cwd=ROOT_DIR)
    server_config = config.servers.get(server_name)
    if server_config is None:
        raise RuntimeError(f"Unknown MCP server: {server_name}")
    if not server_config.is_enabled(os.environ):
        raise RuntimeError(f"MCP server is not enabled: {server_name}")

    child_env = build_child_base_env(os.environ, python_executable=sys.executable)
    command = build_server_command(
        server_name,
        config=config,
        base_env=child_env,
        python_executable=sys.executable,
    )
    params = StdioServerParameters(
        command=command.argv[0],
        args=command.argv[1:],
        env=command.env,
    )
    policy = ToolPolicy.from_server(server_config)

    async def run_client() -> list[str]:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                tool_names = [tool.name for tool in result.tools]
                return policy.filter_tool_names(tool_names)

    return await asyncio.wait_for(run_client(), timeout=timeout_seconds)


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")
    args = parse_args()
    try:
        tools = asyncio.run(list_tools(args.server, args.timeout_seconds))
    except Exception as exc:
        print(f"Smoke failed: {exc}")
        return 1

    print(f"{args.server} bridge-visible tools:")
    for tool in tools:
        print(f"- {tool}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

