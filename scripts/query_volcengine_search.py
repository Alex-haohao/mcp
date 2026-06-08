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
from mcp_bridge.tool_output import tool_result_to_text


SERVER_NAME = "volcengine-web-search"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one real Volcengine web_search MCP query. This consumes search quota."
    )
    parser.add_argument("query", help="Search query, 1-100 characters for the official MCP server.")
    parser.add_argument("--count", type=int, default=3, help="Result count. Default: 3.")
    parser.add_argument(
        "--search-type",
        choices=("web", "image"),
        default="web",
        help="Search type. Default: web.",
    )
    parser.add_argument(
        "--time-range",
        default=None,
        help="Optional time range, such as OneDay, OneWeek, OneMonth, OneYear, or YYYY-MM-DD..YYYY-MM-DD.",
    )
    parser.add_argument(
        "--auth-level",
        type=int,
        choices=(0, 1),
        default=0,
        help="Authority level. 0 is default, 1 requests more authoritative sources.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.getenv("VOLCENGINE_QUERY_TIMEOUT_SECONDS", "90")),
        help="Request timeout. Default: 90.",
    )
    return parser.parse_args()


async def call_search(args: argparse.Namespace):
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
    arguments = {
        "Query": args.query,
        "Count": args.count,
        "SearchType": args.search_type,
        "AuthLevel": args.auth_level,
    }
    if args.time_range:
        arguments["TimeRange"] = args.time_range

    async def run_client():
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool("web_search", arguments=arguments)

    return await asyncio.wait_for(run_client(), timeout=args.timeout_seconds)


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")
    if not os.getenv("VOLCENGINE_SEARCH_API_KEY"):
        print("VOLCENGINE_SEARCH_API_KEY is missing")
        return 1

    args = parse_args()
    try:
        result = asyncio.run(call_search(args))
    except Exception as exc:
        print(f"Search failed: {exc}")
        return 1

    print(tool_result_to_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

