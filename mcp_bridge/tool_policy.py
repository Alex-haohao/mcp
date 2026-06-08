from __future__ import annotations

import json
from dataclasses import dataclass

from .config import McpServerConfig


@dataclass(frozen=True)
class ToolPolicy:
    allowed_tools: frozenset[str]
    blocked_tools: frozenset[str]

    @classmethod
    def from_server(cls, server: McpServerConfig | None) -> "ToolPolicy":
        if server is None:
            return cls(frozenset(), frozenset())
        return cls(
            frozenset(server.allowedTools),
            frozenset(server.blockedTools),
        )

    @property
    def active(self) -> bool:
        return bool(self.allowed_tools or self.blocked_tools)

    def is_allowed(self, tool_name: str) -> bool:
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return False
        return tool_name not in self.blocked_tools

    def filter_tool_names(self, tool_names: list[str]) -> list[str]:
        if not self.active:
            return tool_names
        return [name for name in tool_names if self.is_allowed(name)]

    def filter_tools(self, tools: list[dict]) -> list[dict]:
        if not self.active:
            return tools
        return [tool for tool in tools if self.is_allowed(str(tool.get("name", "")))]

    def filter_process_message(self, message: str) -> str:
        if not self.active:
            return message
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return message

        result = payload.get("result")
        if not isinstance(result, dict):
            return message
        tools = result.get("tools")
        if not isinstance(tools, list):
            return message

        payload["result"]["tools"] = self.filter_tools(
            [tool for tool in tools if isinstance(tool, dict)]
        )
        suffix = "\n" if message.endswith("\n") else ""
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + suffix

    def blocked_request_response(self, message: str) -> str | None:
        if not self.active:
            return None
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return None

        if payload.get("method") != "tools/call":
            return None
        params = payload.get("params")
        if not isinstance(params, dict):
            return None
        tool_name = str(params.get("name", ""))
        if self.is_allowed(tool_name):
            return None

        response = {
            "jsonrpc": payload.get("jsonrpc", "2.0"),
            "id": payload.get("id"),
            "error": {
                "code": -32001,
                "message": f"Tool '{tool_name}' is not allowed by bridge policy",
            },
        }
        return json.dumps(response, ensure_ascii=False, separators=(",", ":"))

