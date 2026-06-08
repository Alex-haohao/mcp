#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import json
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
from mcp_bridge.tool_output import tool_result_to_text
from mcp_bridge.tool_policy import ToolPolicy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call one configured MCP server tool through the same local command path as the bridge."
    )
    parser.add_argument("server", help="Configured server name from mcp_config.json.")
    parser.add_argument("tool", help="Tool name to call.")
    parser.add_argument(
        "--arguments",
        default="{}",
        help="JSON object passed as tool arguments. Default: {}.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.getenv("MCP_CALL_TIMEOUT_SECONDS", "90")),
    )
    return parser.parse_args()


def parse_arguments(raw: str) -> dict:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("--arguments must be a JSON object")
    return value


async def call_tool(
    server_name: str,
    tool_name: str,
    arguments: dict,
    timeout_seconds: float,
):
    config = load_bridge_config_from_env(cwd=ROOT_DIR)
    server_config = config.servers.get(server_name)
    if server_config is None:
        raise RuntimeError(f"Unknown MCP server: {server_name}")
    if not server_config.is_enabled(os.environ):
        raise RuntimeError(f"MCP server is not enabled: {server_name}")

    policy = ToolPolicy.from_server(server_config)
    if not policy.is_allowed(tool_name):
        raise RuntimeError(f"Tool is not allowed by bridge policy: {tool_name}")

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

    async def run_client():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(tool_name, arguments=arguments)

    return await asyncio.wait_for(run_client(), timeout=timeout_seconds)


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")
    args = parse_args()
    try:
        arguments = parse_arguments(args.arguments)
        result = asyncio.run(
            call_tool(args.server, args.tool, arguments, args.timeout_seconds)
        )
    except Exception as exc:
        print(f"Call failed: {exc}")
        return 1

    print(tool_result_to_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

