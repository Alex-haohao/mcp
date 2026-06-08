#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp_bridge.config import ConfigError, load_bridge_config_from_env
from mcp_bridge.runtime_env import build_child_base_env, is_executable_available
from mcp_bridge.server_command import build_server_command


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")
    errors: list[str] = []

    if sys.version_info < (3, 12):
        errors.append("Python 3.12+ is required")

    if not os.getenv("MCP_ENDPOINT"):
        errors.append("MCP_ENDPOINT is missing")

    try:
        config = load_bridge_config_from_env(cwd=ROOT_DIR)
    except ConfigError as exc:
        errors.append(str(exc))
        config = None

    if config is not None:
        enabled_servers = config.enabled_servers(os.environ)
        if not enabled_servers:
            errors.append("No enabled mcpServers found")
        else:
            child_env = build_child_base_env(os.environ, python_executable=sys.executable)
            print("Enabled servers:")
            for server in enabled_servers:
                print(f"- {server.name}")
                try:
                    command = build_server_command(
                        server.name,
                        config=config,
                        base_env=child_env,
                        python_executable=sys.executable,
                    )
                except Exception as exc:
                    errors.append(f"{server.name}: {exc}")
                    continue
                if not is_executable_available(command.argv[0], path=command.env.get("PATH")):
                    errors.append(f"{server.name}: executable '{command.argv[0]}' is not available")

    if errors:
        print("Preflight failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
