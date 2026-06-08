from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .config import BridgeConfig, McpServerConfig


@dataclass(frozen=True)
class ServerCommand:
    argv: list[str]
    env: dict[str, str]


def build_server_command(
    target: str,
    *,
    config: BridgeConfig,
    base_env: Mapping[str, str] | None = None,
    python_executable: str | None = None,
) -> ServerCommand:
    source_env = os.environ if base_env is None else base_env
    env = {str(key): str(value) for key, value in source_env.items()}
    python = python_executable or sys.executable

    if target in config.servers:
        server = config.servers[target]
        if not server.is_enabled(env):
            raise RuntimeError(f"Server '{target}' is disabled by config or environment")
        return _build_configured_server_command(server, env, python)

    script_path = Path(target)
    if not script_path.exists():
        raise RuntimeError(f"'{target}' is neither a configured server nor an existing script")
    return ServerCommand([python, str(script_path)], env)


def _build_configured_server_command(
    server: McpServerConfig,
    base_env: dict[str, str],
    python_executable: str,
) -> ServerCommand:
    child_env = dict(base_env)
    child_env.update({str(key): str(value) for key, value in server.env.items()})

    transport = server.transport
    if transport == "stdio":
        if not server.command:
            raise RuntimeError(f"Server '{server.name}' is missing 'command'")
        return ServerCommand([server.command, *server.args], child_env)

    if transport in ("sse", "http", "streamablehttp"):
        if not server.url:
            raise RuntimeError(f"Server '{server.name}' (type {transport}) is missing 'url'")
        argv = [python_executable, "-m", "mcp_proxy"]
        if transport in ("http", "streamablehttp"):
            argv += ["--transport", "streamablehttp"]
        for header_key, header_value in server.headers.items():
            argv += ["-H", header_key, str(header_value)]
        argv.append(server.url)
        return ServerCommand(argv, child_env)

    raise RuntimeError(f"Unsupported server type: {transport}")
