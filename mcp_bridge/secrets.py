from __future__ import annotations

from typing import Any, Iterable, Mapping


REDACTED = "***REDACTED***"

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "access_key",
    "secret_key",
    "secret",
    "token",
    "authorization",
    "password",
    "credential",
    "mcp_endpoint",
)


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def redact_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in mapping.items():
        if is_sensitive_key(str(key)):
            redacted[str(key)] = REDACTED
        elif isinstance(value, Mapping):
            redacted[str(key)] = redact_mapping(value)
        else:
            redacted[str(key)] = value
    return redacted


def collect_sensitive_values(mapping: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for key, value in mapping.items():
        if isinstance(value, Mapping):
            values.extend(collect_sensitive_values(value))
        elif is_sensitive_key(str(key)) and value:
            values.append(str(value))
    return values


def redact_text(text: str, sensitive_values: Iterable[str]) -> str:
    redacted = text
    for value in sensitive_values:
        if len(value) < 4:
            continue
        redacted = redacted.replace(value, REDACTED)
    return redacted


def redact_argv(argv: list[str]) -> list[str]:
    redacted = list(argv)
    index = 0
    while index < len(redacted):
        if redacted[index] == "-H" and index + 2 < len(redacted):
            header_name = redacted[index + 1]
            if is_sensitive_key(header_name):
                redacted[index + 2] = REDACTED
            index += 3
            continue
        index += 1
    return redacted
