from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Mapping


def build_child_base_env(
    base_env: Mapping[str, str] | None = None,
    *,
    python_executable: str | None = None,
) -> dict[str, str]:
    """Build child-process env and keep the active Python bin dir on PATH."""
    source_env = os.environ if base_env is None else base_env
    env = {str(key): str(value) for key, value in source_env.items()}
    python = python_executable or sys.executable
    python_bin_dir = os.path.dirname(python)

    path_parts = [part for part in env.get("PATH", "").split(os.pathsep) if part]
    if python_bin_dir and python_bin_dir not in path_parts:
        env["PATH"] = os.pathsep.join([python_bin_dir, *path_parts])
    return env


def is_executable_available(executable: str, path: str | None = None) -> bool:
    has_path_separator = os.sep in executable or (os.altsep and os.altsep in executable)
    if has_path_separator:
        return Path(executable).exists()
    return shutil.which(executable, path=path) is not None


def ensure_executable_available(
    executable: str,
    env: Mapping[str, str] | None = None,
) -> None:
    source_env = os.environ if env is None else env
    if is_executable_available(executable, path=source_env.get("PATH")):
        return
    raise RuntimeError(
        f"Configured executable '{executable}' was not found in PATH. "
        "Install it or update the server command in mcp_config.json."
    )
