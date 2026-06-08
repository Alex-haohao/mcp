#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = "/opt/xiaozhi-mcp"
SERVICE_NAME = "xiaozhi-mcp"
SERVICE_USER = "xiaozhi-mcp"

RUNTIME_ENV_KEYS = {
    "MCP_ENDPOINT",
    "MCP_CONFIG",
    "MCP_CONFIG_PATH",
    "VOLCENGINE_SEARCH_API_KEY",
    "XIAOHONGSHU_MCP_URL",
}
RUNTIME_ENV_PREFIXES = (
    "VOLCENGINE_",
    "XIAOHONGSHU_",
)

RSYNC_EXCLUDES = [
    ".git/",
    ".idea/",
    ".venv/",
    ".env",
    "__pycache__/",
    "*.pyc",
    ".DS_Store",
]


@dataclass(frozen=True)
class ServerConfig:
    host: str
    username: str
    port: str
    ssh_key: str | None

    @property
    def target(self) -> str:
        return f"{self.username}@{self.host}"

    @property
    def ssh_base(self) -> list[str]:
        command = [
            "ssh",
            "-p",
            self.port,
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
        ]
        if self.ssh_key:
            command.extend(["-i", self.ssh_key])
        command.append(self.target)
        return command

    @property
    def rsync_ssh(self) -> str:
        parts = [
            "ssh",
            "-p",
            self.port,
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
        ]
        if self.ssh_key:
            parts.extend(["-i", self.ssh_key])
        return " ".join(shlex.quote(part) for part in parts)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        values[key] = value
    return values


def load_server_config(env: dict[str, str]) -> ServerConfig:
    host = env.get("SERVER_IP") or env.get("SERVER_HOST")
    if not host:
        raise RuntimeError("SERVER_IP or SERVER_HOST is required in .env")
    return ServerConfig(
        host=host,
        username=env.get("SERVER_USERNAME", "root"),
        port=env.get("SERVER_PORT", "22"),
        ssh_key=env.get("SERVER_SSH_KEY") or None,
    )


def should_upload_runtime_key(key: str, value: str) -> bool:
    if not value or key.startswith("SERVER_"):
        return False
    return key in RUNTIME_ENV_KEYS or key.startswith(RUNTIME_ENV_PREFIXES)


def quote_env_value(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise RuntimeError("runtime env values must be single-line")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_runtime_env(env: dict[str, str]) -> str:
    lines = [
        f"{key}={quote_env_value(value)}"
        for key, value in sorted(env.items())
        if should_upload_runtime_key(key, value)
    ]
    required = {"MCP_ENDPOINT", "VOLCENGINE_SEARCH_API_KEY"}
    missing = [key for key in sorted(required) if not env.get(key)]
    if missing:
        raise RuntimeError(f"missing required runtime env key(s): {', '.join(missing)}")
    return "\n".join(lines) + "\n"


def run(command: list[str], *, cwd: Path | None = None, stdin: str | None = None) -> None:
    printable = " ".join(shlex.quote(part) for part in command)
    print(f"$ {printable}")
    subprocess.run(
        command,
        cwd=cwd,
        input=stdin,
        text=True,
        check=True,
    )


def capture(command: list[str], *, cwd: Path | None = None) -> str:
    return subprocess.check_output(command, cwd=cwd, text=True).strip()


def run_local_checks() -> None:
    python = ROOT_DIR / ".venv" / "bin" / "python"
    if not python.exists():
        python = Path(sys.executable)
    run([str(python), "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT_DIR)
    run([str(python), "scripts/preflight.py"], cwd=ROOT_DIR)


def make_release_name() -> str:
    short_sha = capture(["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT_DIR)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{timestamp}-{short_sha}"


def ssh(server: ServerConfig, command: str, *, stdin: str | None = None) -> None:
    run([*server.ssh_base, command], stdin=stdin)


def rsync_code(server: ServerConfig, release_dir: str) -> None:
    command = [
        "rsync",
        "-az",
        "--delete",
    ]
    for pattern in RSYNC_EXCLUDES:
        command.extend(["--exclude", pattern])
    command.extend([
        "-e",
        server.rsync_ssh,
        "./",
        f"{server.target}:{release_dir}/",
    ])
    run(command, cwd=ROOT_DIR)


def rsync_file(server: ServerConfig, source: Path, destination: str) -> None:
    run([
        "rsync",
        "-az",
        "-e",
        server.rsync_ssh,
        str(source),
        f"{server.target}:{destination}",
    ])


def ensure_remote_sync_prerequisites(server: ServerConfig) -> None:
    ssh(
        server,
        "command -v rsync >/dev/null 2>&1 || "
        "(apt-get update && apt-get install -y rsync)",
    )


def remote_install_script(release_name: str, restart: bool) -> str:
    return f"""\
set -Eeuo pipefail

APP_DIR={shlex.quote(APP_DIR)}
RELEASE_NAME={shlex.quote(release_name)}
RELEASE_DIR="$APP_DIR/releases/$RELEASE_NAME"
SERVICE_NAME={shlex.quote(SERVICE_NAME)}
SERVICE_USER={shlex.quote(SERVICE_USER)}
RUNTIME_ENV_TMP="/tmp/$SERVICE_NAME.env.$RELEASE_NAME"

install -d -m 0755 "$APP_DIR" "$APP_DIR/releases" "$APP_DIR/shared"

if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/xiaozhi-mcp --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -m 0755 -o "$SERVICE_USER" -g "$SERVICE_USER" /var/lib/xiaozhi-mcp
install -d -m 0755 -o "$SERVICE_USER" -g "$SERVICE_USER" /var/cache/xiaozhi-mcp /var/cache/xiaozhi-mcp/uv
install -d -m 0755 -o "$SERVICE_USER" -g "$SERVICE_USER" /var/cache/xiaozhi-mcp/python
install -d -m 0755 -o "$SERVICE_USER" -g "$SERVICE_USER" /var/log/xiaozhi-mcp

install -m 0640 -o root -g "$SERVICE_USER" "$RUNTIME_ENV_TMP" "$APP_DIR/shared/.env"
rm -f "$RUNTIME_ENV_TMP"

ln -sfn ../../shared/.env "$RELEASE_DIR/.env"

missing_packages=()
command -v curl >/dev/null 2>&1 || missing_packages+=(curl)
command -v git >/dev/null 2>&1 || missing_packages+=(git)
if [ "${{#missing_packages[@]}}" -gt 0 ]; then
  apt-get update
  apt-get install -y ca-certificates "${{missing_packages[@]}}"
fi

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
  if [ -x /root/.local/bin/uv ]; then
    install -m 0755 /root/.local/bin/uv /usr/local/bin/uv
  fi
  if [ -x /root/.local/bin/uvx ]; then
    install -m 0755 /root/.local/bin/uvx /usr/local/bin/uvx
  fi
fi

cd "$RELEASE_DIR"
export UV_PYTHON_INSTALL_DIR=/var/cache/xiaozhi-mcp/python
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
chown -R "$SERVICE_USER:$SERVICE_USER" /var/cache/xiaozhi-mcp/python /var/cache/xiaozhi-mcp/uv

install -m 0644 "$RELEASE_DIR/deploy/xiaozhi-mcp.service" /etc/systemd/system/xiaozhi-mcp.service
ln -sfn "releases/$RELEASE_NAME" "$APP_DIR/current"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null

runuser -u "$SERVICE_USER" -- env \\
  HOME=/var/lib/xiaozhi-mcp \\
  UV_CACHE_DIR=/var/cache/xiaozhi-mcp/uv \\
  UV_PYTHON_INSTALL_DIR=/var/cache/xiaozhi-mcp/python \\
  PATH="$RELEASE_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin" \\
  bash -lc 'cd /opt/xiaozhi-mcp/current && .venv/bin/python scripts/preflight.py'

if [ {shlex.quote("1" if restart else "0")} = "1" ]; then
  systemctl restart "$SERVICE_NAME"
  sleep 5
  systemctl is-active --quiet "$SERVICE_NAME"
fi

find "$APP_DIR/releases" -mindepth 1 -maxdepth 1 -type d | sort -r | tail -n +6 | xargs -r rm -rf
"""


def deploy(args: argparse.Namespace) -> None:
    env = parse_env_file(ROOT_DIR / ".env")
    server = load_server_config(env)
    runtime_env = build_runtime_env(env)
    release_name = args.release_name or make_release_name()
    release_dir = f"{APP_DIR}/releases/{release_name}"

    if not args.skip_local_checks:
        run_local_checks()

    ensure_remote_sync_prerequisites(server)
    ssh(server, f"install -d -m 0755 {shlex.quote(release_dir)}")
    rsync_code(server, release_dir)

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(runtime_env)
        env_path = Path(handle.name)
    try:
        os.chmod(env_path, 0o600)
        rsync_file(server, env_path, f"/tmp/{SERVICE_NAME}.env.{release_name}")
    finally:
        env_path.unlink(missing_ok=True)

    ssh(server, "bash -s", stdin=remote_install_script(release_name, not args.no_restart))

    if not args.no_restart:
        ssh(
            server,
            f"systemctl --no-pager --full status {shlex.quote(SERVICE_NAME)} | sed -n '1,80p'",
        )
        ssh(
            server,
            f"tail -n 80 /var/log/{shlex.quote(SERVICE_NAME)}/bridge.log",
        )

    print(f"Deployed {release_name} to {server.target}:{APP_DIR}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy XiaoZhi MCP bridge to the server in .env")
    parser.add_argument("--skip-local-checks", action="store_true")
    parser.add_argument("--no-restart", action="store_true")
    parser.add_argument("--release-name")
    args = parser.parse_args()

    try:
        deploy(args)
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    except Exception as exc:
        print(f"deploy failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
