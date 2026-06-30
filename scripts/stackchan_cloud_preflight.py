#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STACKCHAN_DIR = ROOT_DIR / "projects" / "StackChan"

DEPLOY_ENV_KEYS = (
    "SERVER_IP",
    "SERVER_HOST",
    "SERVER_USERNAME",
    "SERVER_PORT",
    "SERVER_SSH_KEY",
    "SERVER_PASSWORD",
    "STACKCHAN_PUBLIC_BASE_URL",
    "STACKCHAN_CONFIG_PATH",
    "STACKCHAN_SERVER_HOST",
    "STACKCHAN_SERVER_TLS",
    "STACKCHAN_SERVER_PATH_PREFIX",
    "STACKCHAN_MYSQL_DATABASE",
    "STACKCHAN_MYSQL_USER",
    "STACKCHAN_MYSQL_PASSWORD",
    "STACKCHAN_MYSQL_ROOT_PASSWORD",
)

APP_DART_DEFINE_KEYS = (
    "STACKCHAN_SERVER_HOST",
    "STACKCHAN_SERVER_TLS",
    "STACKCHAN_SERVER_PATH_PREFIX",
    "STACKCHAN_SERVER_PUBLIC_KEY_BASE64",
    "STACKCHAN_CLIENT_PRIVATE_KEY_BASE64",
    "STACKCHAN_BLUE_PRIVATE_KEY_BASE64",
)

REQUIRED_REMOTE_KEYS = (
    "SERVER_IP",
    "SERVER_USERNAME",
)


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str = ""


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
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def result_line(check: Check) -> str:
    suffix = f" - {check.detail}" if check.detail else ""
    return f"[{check.status}] {check.name}{suffix}"


def command_output(command: list[str], cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.returncode, proc.stdout.strip()


def parse_go_version(raw: str) -> tuple[int, ...] | None:
    match = re.search(r"go version go([0-9]+(?:\.[0-9]+){0,2})", raw)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def parse_go_mod_version(go_mod: Path) -> tuple[int, ...] | None:
    for line in go_mod.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("go "):
            return tuple(int(part) for part in line.split()[1].split("."))
    return None


def version_at_least(actual: tuple[int, ...], expected: tuple[int, ...]) -> bool:
    width = max(len(actual), len(expected))
    actual_padded = actual + (0,) * (width - len(actual))
    expected_padded = expected + (0,) * (width - len(expected))
    return actual_padded >= expected_padded


def check_local(stackchan_dir: Path, env: dict[str, str], run_server_tests: bool) -> list[Check]:
    checks: list[Check] = []
    server_dir = stackchan_dir / "server"
    app_dir = stackchan_dir / "app"

    checks.append(
        Check(
            "StackChan server directory",
            "OK" if server_dir.is_dir() else "FAIL",
            str(server_dir),
        )
    )
    checks.append(
        Check(
            "StackChan app directory",
            "OK" if app_dir.is_dir() else "FAIL",
            str(app_dir),
        )
    )

    go_bin = shutil.which("go")
    if go_bin and (server_dir / "go.mod").exists():
        code, output = command_output([go_bin, "version"])
        actual = parse_go_version(output)
        expected = parse_go_mod_version(server_dir / "go.mod")
        if actual and expected and version_at_least(actual, expected):
            checks.append(Check("Go version", "OK", output))
            if run_server_tests:
                test_code, test_output = command_output([go_bin, "test", "./..."], cwd=server_dir)
                status = "OK" if test_code == 0 else "FAIL"
                detail = "go test ./..." if test_code == 0 else test_output.splitlines()[-1]
                checks.append(Check("StackChan server tests", status, detail))
        else:
            expected_text = ".".join(str(part) for part in expected or ())
            status = "FAIL" if run_server_tests else "WARN"
            checks.append(Check("Go version", status, f"{output}; required >= {expected_text}"))
    else:
        status = "FAIL" if run_server_tests else "WARN"
        checks.append(Check("Go binary", status, "go is not available in PATH"))

    flutter_bin = shutil.which("flutter")
    if flutter_bin:
        code, output = command_output([flutter_bin, "--version"], cwd=app_dir)
        first_line = output.splitlines()[0] if output else "flutter available"
        checks.append(Check("Flutter SDK", "OK" if code == 0 else "FAIL", first_line))
    else:
        checks.append(Check("Flutter SDK", "WARN", "flutter is not available in PATH"))

    docker_bin = shutil.which("docker")
    if docker_bin:
        code, output = command_output([docker_bin, "info"])
        checks.append(
            Check(
                "Docker daemon",
                "OK" if code == 0 else "WARN",
                "running" if code == 0 else "docker CLI exists, daemon unavailable",
            )
        )
    else:
        checks.append(Check("Docker CLI", "WARN", "docker is not available in PATH"))

    configured = [key for key in DEPLOY_ENV_KEYS if env.get(key)]
    missing_remote = [key for key in REQUIRED_REMOTE_KEYS if not env.get(key)]
    checks.append(
        Check(
            "Local deployment env keys",
            "OK" if configured else "WARN",
            f"{len(configured)} configured; missing remote keys: {', '.join(missing_remote) or 'none'}",
        )
    )

    app_defines = [key for key in APP_DART_DEFINE_KEYS if env.get(key)]
    checks.append(
        Check(
            "App dart-define env keys",
            "OK" if env.get("STACKCHAN_SERVER_HOST") else "WARN",
            f"{len(app_defines)} configured",
        )
    )

    return checks


REMOTE_INVENTORY_SCRIPT = r"""
set -eu
printf 'remote.host=%s\n' "$(hostname)"
if [ -r /etc/os-release ]; then
  . /etc/os-release
  printf 'remote.os=%s\n' "${PRETTY_NAME:-unknown}"
else
  printf 'remote.os=%s\n' "$(uname -a)"
fi

check_command() {
  if command -v "$1" >/dev/null 2>&1; then
    printf 'remote.command.%s=present\n' "$1"
  else
    printf 'remote.command.%s=missing\n' "$1"
  fi
}

check_command docker
check_command go
check_command git
check_command curl
check_command openssl
check_command tar
check_command mysql
check_command nginx
check_command caddy
check_command systemctl
check_command ss

printf 'remote.machine=%s\n' "$(uname -m)"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  printf 'remote.command.docker-compose=present-v2\n'
elif command -v docker-compose >/dev/null 2>&1; then
  printf 'remote.command.docker-compose=present-v1\n'
else
  printf 'remote.command.docker-compose=missing\n'
fi

if command -v mysql >/dev/null 2>&1 && mysql -uroot -Nse 'SELECT 1' >/dev/null 2>&1; then
  printf 'remote.mysql.root_socket=ok\n'
else
  printf 'remote.mysql.root_socket=unavailable\n'
fi

if command -v systemctl >/dev/null 2>&1; then
  printf 'remote.service.xiaozhi-mcp=%s\n' "$(systemctl is-active xiaozhi-mcp 2>/dev/null || true)"
fi

if command -v curl >/dev/null 2>&1 && curl -fsS http://127.0.0.1:12800/api.json >/dev/null 2>&1; then
  printf 'remote.stackchan.api=ok\n'
else
  printf 'remote.stackchan.api=unavailable\n'
fi

if command -v curl >/dev/null 2>&1; then
  WS_STATUS="$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:12800/stackChan/ws 2>/dev/null || true)"
  printf 'remote.stackchan.ws_no_auth=%s\n' "${WS_STATUS:-unavailable}"
fi

printf 'remote.ports.begin\n'
(ss -ltnp 2>/dev/null || ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null || true) | sed -n '1,40p'
printf 'remote.ports.end\n'
"""


def run_remote_inventory(env: dict[str, str]) -> int:
    host = env.get("SERVER_IP") or env.get("SERVER_HOST")
    username = env.get("SERVER_USERNAME", "root")
    port = env.get("SERVER_PORT", "22")
    ssh_key = env.get("SERVER_SSH_KEY")
    password = env.get("SERVER_PASSWORD")

    if not host:
        print("[FAIL] Remote inventory - SERVER_IP or SERVER_HOST is missing")
        return 2

    target = f"{username}@{host}"
    remote_payload = base64.b64encode(REMOTE_INVENTORY_SCRIPT.encode("utf-8")).decode("ascii")
    remote_command = f"printf %s {remote_payload} | base64 -d | sh"
    base_ssh = [
        "ssh",
        "-p",
        port,
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=15",
        "-o",
        "NumberOfPasswordPrompts=1",
    ]

    if ssh_key:
        command = [*base_ssh, "-i", ssh_key, "-o", "BatchMode=yes", target, remote_command]
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        print(proc.stdout.rstrip())
        return proc.returncode

    if not password:
        command = [*base_ssh, "-o", "BatchMode=yes", target, remote_command]
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        print(proc.stdout.rstrip())
        return proc.returncode

    expect_bin = shutil.which("expect")
    if not expect_bin:
        print("[FAIL] Remote inventory - SERVER_PASSWORD is set but expect is not available")
        return 2

    env_with_password = os.environ.copy()
    env_with_password["STACKCHAN_REMOTE_PASSWORD"] = password
    ssh_shell_command = (
        " ".join(shlex.quote(part) for part in [*base_ssh, target])
        + " "
        + shlex.quote(remote_command)
    )
    tcl_command = "{" + ssh_shell_command.replace("\\", "\\\\").replace("}", "\\}") + "}"
    expect_script = f"""
set timeout 30
spawn -noecho sh -c {tcl_command}
expect {{
  -re "(?i)password:" {{
    send -- "$env(STACKCHAN_REMOTE_PASSWORD)\\r"
    exp_continue
  }}
  timeout {{
    exit 124
  }}
  eof
}}
set wait_result [wait]
exit [lindex $wait_result 3]
"""
    proc = subprocess.run(
        [expect_bin, "-c", expect_script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env_with_password,
    )
    print(proc.stdout.rstrip())
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight checks for StackChan app/server self-hosting.")
    parser.add_argument(
        "--stackchan-dir",
        type=Path,
        default=DEFAULT_STACKCHAN_DIR,
        help="Path to the StackChan checkout or worktree.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        action="append",
        default=None,
        help="Local env file. Can be passed multiple times. Values are never printed.",
    )
    parser.add_argument(
        "--run-server-tests",
        action="store_true",
        help="Run go test ./... when the local Go version satisfies server/go.mod.",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Run non-secret remote inventory over SSH.",
    )
    args = parser.parse_args()

    stackchan_dir = args.stackchan_dir.expanduser().resolve()
    env_files = args.env_file or [ROOT_DIR / ".env"]
    env: dict[str, str] = {}
    for env_file in env_files:
        env.update(parse_env_file(env_file.expanduser().resolve()))

    print(f"StackChan directory: {stackchan_dir}")
    for env_file in env_files:
        print(f"Env file: {env_file} ({'present' if env_file.exists() else 'missing'})")
    print()

    failed = False
    for check in check_local(stackchan_dir, env, args.run_server_tests):
        print(result_line(check))
        failed = failed or check.status == "FAIL"

    if args.remote:
        print()
        print("Remote inventory:")
        remote_code = run_remote_inventory(env)
        failed = failed or remote_code != 0

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
