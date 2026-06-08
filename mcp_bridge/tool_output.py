from __future__ import annotations

from typing import Any


def tool_result_to_text(result: Any) -> str:
    """Return a readable text representation for MCP CallToolResult."""
    content = getattr(result, "content", None)
    if not content:
        return ""

    parts: list[str] = []
    for item in content:
        item_type = getattr(item, "type", None)
        if item_type == "text":
            parts.append(str(getattr(item, "text", "")))
        else:
            parts.append(repr(item))
    return "\n".join(part for part in parts if part)

