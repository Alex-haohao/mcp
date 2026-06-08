from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class ConfigError(RuntimeError):
    """Raised when bridge configuration cannot be loaded or validated."""


_ENV_PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def discover_config_path(
    environ: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
) -> Path | None:
    env = os.environ if environ is None else environ
    current_dir = Path(cwd or os.getcwd())
    candidates = [
        env.get("MCP_CONFIG"),
        env.get("MCP_CONFIG_PATH"),
        str(current_dir / "mcp_config.json"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None


def expand_env_placeholders(value: Any, environ: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        missing: list[str] = []

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            env_value = environ.get(key)
            if env_value is None:
                missing.append(key)
                return match.group(0)
            return str(env_value)

        expanded = _ENV_PLACEHOLDER_RE.sub(replace, value)
        if missing:
            names = ", ".join(sorted(set(missing)))
            raise ConfigError(f"Missing required environment variable(s): {names}")
        return expanded
    if isinstance(value, list):
        return [expand_env_placeholders(item, environ) for item in value]
    if isinstance(value, dict):
        return {
            str(key): expand_env_placeholders(item, environ)
            for key, item in value.items()
        }
    return value


def _raw_server_is_enabled(entry: Any, environ: Mapping[str, str]) -> bool:
    if not isinstance(entry, dict):
        return True
    if bool(entry.get("disabled")):
        return False
    if entry.get("enabled") is False:
        return False

    enabled_if_env = entry.get("enabledIfEnv")
    if not enabled_if_env:
        return True
    required = [enabled_if_env] if isinstance(enabled_if_env, str) else list(enabled_if_env)
    return all(bool(environ.get(str(name))) for name in required)


def _expand_config(raw: dict[str, Any], environ: Mapping[str, str]) -> dict[str, Any]:
    expanded = dict(raw)
    servers = raw.get("mcpServers") or {}
    if not isinstance(servers, dict):
        raise ConfigError("'mcpServers' must be an object")

    expanded_servers: dict[str, Any] = {}
    for name, entry in servers.items():
        if _raw_server_is_enabled(entry, environ):
            expanded_servers[str(name)] = expand_env_placeholders(entry, environ)
        else:
            expanded_servers[str(name)] = entry
    expanded["mcpServers"] = expanded_servers
    return expanded


class McpServerConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = ""
    type: str = "stdio"
    transportType: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    disabled: bool = False
    enabled: bool | None = None
    enabledIfEnv: str | list[str] | None = None
    allowedTools: list[str] = Field(default_factory=list)
    blockedTools: list[str] = Field(default_factory=list)
    policy: dict[str, Any] = Field(default_factory=dict)

    @field_validator("args", mode="before")
    @classmethod
    def normalize_args(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("'args' must be a list")
        return [str(item) for item in value]

    @field_validator("allowedTools", "blockedTools", mode="before")
    @classmethod
    def normalize_tool_names(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("tool policy lists must be lists")
        return [str(item) for item in value]

    @field_validator("headers", "env", mode="before")
    @classmethod
    def normalize_string_mapping(cls, value: Any) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("value must be an object")
        return {str(key): str(item) for key, item in value.items()}

    @property
    def transport(self) -> str:
        return (self.transportType or self.type or "stdio").lower()

    def is_enabled(self, environ: Mapping[str, str]) -> bool:
        if self.disabled:
            return False
        if self.enabled is False:
            return False
        if not self.enabledIfEnv:
            return True
        required = [self.enabledIfEnv] if isinstance(self.enabledIfEnv, str) else self.enabledIfEnv
        return all(bool(environ.get(name)) for name in required)


class BridgeConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    mcpServers: dict[str, McpServerConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def assign_server_names(self) -> "BridgeConfig":
        for name, server in self.mcpServers.items():
            server.name = name
        return self

    @property
    def servers(self) -> dict[str, McpServerConfig]:
        return self.mcpServers

    def enabled_servers(self, environ: Mapping[str, str]) -> list[McpServerConfig]:
        return [server for server in self.mcpServers.values() if server.is_enabled(environ)]


def load_bridge_config(
    path: str | Path | None,
    environ: Mapping[str, str] | None = None,
) -> BridgeConfig:
    env = os.environ if environ is None else environ
    if path is None:
        return BridgeConfig()

    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Failed to read config {config_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Failed to parse config {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Config root must be an object")

    try:
        expanded = _expand_config(raw, env)
        return BridgeConfig.model_validate(expanded)
    except ValidationError as exc:
        raise ConfigError(f"Invalid config {config_path}: {exc}") from exc


def load_bridge_config_from_env(
    environ: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
) -> BridgeConfig:
    env = os.environ if environ is None else environ
    return load_bridge_config(discover_config_path(env, cwd), env)
