#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import os
import shlex
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STACKCHAN_DIR = ROOT_DIR / ".worktrees" / "StackChan-server-app"
DEFAULT_SECRET_DIR = ROOT_DIR / "workspace" / "stackchan-secrets" / "server"
APP_DIR = "/opt/stackchan-server"
SERVICE_NAME = "stackchan-server"


@dataclass(frozen=True)
class Remote:
    host: str
    username: str
    port: str
    ssh_key: str | None
    password: str | None

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
            "StrictHostKeyChecking=accept-new",
            "-o",
            "ConnectTimeout=20",
            "-o",
            "NumberOfPasswordPrompts=1",
        ]
        if self.ssh_key:
            command.extend(["-i", self.ssh_key])
        return command


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


def load_env(paths: list[Path]) -> dict[str, str]:
    env: dict[str, str] = {}
    for path in paths:
        env.update(parse_env_file(path.expanduser().resolve()))
    return env


def load_remote(env: dict[str, str]) -> Remote:
    host = env.get("SERVER_IP") or env.get("SERVER_HOST")
    if not host:
        raise RuntimeError("SERVER_IP or SERVER_HOST is required")
    return Remote(
        host=host,
        username=env.get("SERVER_USERNAME", "root"),
        port=env.get("SERVER_PORT", "22"),
        ssh_key=env.get("SERVER_SSH_KEY") or None,
        password=env.get("SERVER_PASSWORD") or None,
    )


def quote_env_value(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise RuntimeError("env values must be single-line")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_remote_compose_env(env: dict[str, str]) -> str:
    required = [
        "STACKCHAN_MYSQL_DATABASE",
        "STACKCHAN_MYSQL_USER",
        "STACKCHAN_MYSQL_PASSWORD",
        "STACKCHAN_MYSQL_ROOT_PASSWORD",
    ]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise RuntimeError(f"missing StackChan compose env key(s): {', '.join(missing)}")

    values = {
        "STACKCHAN_CONFIG_PATH": f"{APP_DIR}/shared/config.yaml",
        "STACKCHAN_SERVER_PORT": env.get("STACKCHAN_SERVER_PORT", "12800"),
        "STACKCHAN_MYSQL_DATABASE": env["STACKCHAN_MYSQL_DATABASE"],
        "STACKCHAN_MYSQL_USER": env["STACKCHAN_MYSQL_USER"],
        "STACKCHAN_MYSQL_PASSWORD": env["STACKCHAN_MYSQL_PASSWORD"],
        "STACKCHAN_MYSQL_ROOT_PASSWORD": env["STACKCHAN_MYSQL_ROOT_PASSWORD"],
    }
    return "\n".join(f"{key}={quote_env_value(value)}" for key, value in values.items()) + "\n"


def short_sha(stackchan_dir: Path) -> str:
    result = subprocess.check_output(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=stackchan_dir,
        text=True,
    )
    return result.strip()


def make_release_name(stackchan_dir: Path) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{timestamp}-{short_sha(stackchan_dir)}"


def should_include(path: Path) -> bool:
    parts = set(path.parts)
    if ".git" in parts or "__pycache__" in parts:
        return False
    name = path.name
    if name.endswith(".pyc") or name == ".DS_Store":
        return False
    return True


def create_server_archive(stackchan_dir: Path, archive_path: Path) -> None:
    server_dir = stackchan_dir / "server"
    if not server_dir.is_dir():
        raise RuntimeError(f"missing server directory: {server_dir}")

    with tarfile.open(archive_path, "w:gz") as archive:
        for path in server_dir.rglob("*"):
            rel = path.relative_to(server_dir)
            if should_include(rel):
                archive.add(path, arcname=str(rel), recursive=False)


def run_local(command: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def run_expect(command: list[str], password: str) -> subprocess.CompletedProcess[str]:
    expect_bin = shutil_which("expect")
    if not expect_bin:
        raise RuntimeError("expect is required for password-based remote operations")
    shell_command = " ".join(shlex.quote(part) for part in command)
    tcl_command = "{" + shell_command.replace("\\", "\\\\").replace("}", "\\}") + "}"
    script = f"""
set timeout 1800
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
    env = os.environ.copy()
    env["STACKCHAN_REMOTE_PASSWORD"] = password
    return subprocess.run(
        [expect_bin, "-c", script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        check=False,
    )


def shutil_which(name: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def remote_command(remote: Remote, script: str) -> subprocess.CompletedProcess[str]:
    payload = base64.b64encode(script.encode("utf-8")).decode("ascii")
    command = [
        *remote.ssh_base,
        remote.target,
        f"printf %s {payload} | base64 -d | bash",
    ]
    if remote.ssh_key or not remote.password:
        return run_local(command)
    return run_expect(command, remote.password)


def upload_file(remote: Remote, source: Path, destination: str) -> subprocess.CompletedProcess[str]:
    command = [
        "scp",
        "-P",
        remote.port,
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=20",
        "-o",
        "NumberOfPasswordPrompts=1",
    ]
    if remote.ssh_key:
        command.extend(["-i", remote.ssh_key])
    command.extend([str(source), f"{remote.target}:{destination}"])

    if remote.ssh_key or not remote.password:
        return run_local(command)
    return run_expect(command, remote.password)


def fail_if_bad(proc: subprocess.CompletedProcess[str], label: str) -> None:
    if proc.returncode == 0:
        return
    output = proc.stdout.strip()
    raise RuntimeError(f"{label} failed with exit code {proc.returncode}\n{output}")


def remote_install_script(release_name: str, archive_remote: str, config_remote: str, env_remote: str) -> str:
    return f"""\
set -Eeuo pipefail

APP_DIR={shlex.quote(APP_DIR)}
SERVICE_NAME={shlex.quote(SERVICE_NAME)}
RELEASE_NAME={shlex.quote(release_name)}
RELEASE_DIR="$APP_DIR/releases/$RELEASE_NAME"
ARCHIVE={shlex.quote(archive_remote)}
CONFIG_TMP={shlex.quote(config_remote)}
ENV_TMP={shlex.quote(env_remote)}

install -d -m 0755 "$APP_DIR" "$APP_DIR/releases" "$APP_DIR/shared"
rm -rf "$RELEASE_DIR"
install -d -m 0755 "$RELEASE_DIR"
tar -xzf "$ARCHIVE" -C "$RELEASE_DIR"

install -m 0400 "$CONFIG_TMP" "$APP_DIR/shared/config.yaml"
chown 10001:10001 "$APP_DIR/shared/config.yaml"
install -m 0600 "$ENV_TMP" "$APP_DIR/shared/compose.env"
rm -f "$ARCHIVE" "$CONFIG_TMP" "$ENV_TMP"

if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg apparmor docker.io
elif ! command -v apparmor_parser >/dev/null 2>&1; then
  apt-get update
  apt-get install -y apparmor
fi

if ! docker compose version >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
  apt-get update
  apt-get install -y docker-compose-plugin || apt-get install -y docker-compose
fi

systemctl enable --now docker

ln -sfn "releases/$RELEASE_NAME" "$APP_DIR/current"

if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
else
  COMPOSE="docker-compose"
fi

cd "$APP_DIR/current/ops/compose"
$COMPOSE --env-file "$APP_DIR/shared/compose.env" up -d --build

for i in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:12800/api.json >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

curl -fsS http://127.0.0.1:12800/api.json >/dev/null
curl -fsS http://127.0.0.1:12800/file/music/stackchan_music.mp3 >/dev/null
WS_STATUS="$(curl -sS -o /dev/null -w '%{{http_code}}' http://127.0.0.1:12800/stackChan/ws || true)"
if [ "$WS_STATUS" != "401" ]; then
  echo "unexpected websocket unauthenticated status: $WS_STATUS" >&2
  exit 1
fi

$COMPOSE --env-file "$APP_DIR/shared/compose.env" ps
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy self-hosted StackChan server with Docker Compose.")
    parser.add_argument("--stackchan-dir", type=Path, default=DEFAULT_STACKCHAN_DIR)
    parser.add_argument("--config-file", type=Path, default=DEFAULT_SECRET_DIR / "config.compose.yaml")
    parser.add_argument(
        "--env-file",
        type=Path,
        action="append",
        default=None,
        help="Env file. Pass multiple times. Defaults to root .env and generated compose.env.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    stackchan_dir = args.stackchan_dir.expanduser().resolve()
    config_file = args.config_file.expanduser().resolve()
    env_files = args.env_file or [ROOT_DIR / ".env", DEFAULT_SECRET_DIR / "compose.env"]
    env = load_env(env_files)
    remote = load_remote(env)
    compose_env = build_remote_compose_env(env)
    release_name = make_release_name(stackchan_dir)

    if not config_file.exists():
        raise RuntimeError(f"missing config file: {config_file}")

    print(f"Deploy target: {remote.username}@{remote.host}:{remote.port}")
    print(f"StackChan source: {stackchan_dir}")
    print(f"Release: {release_name}")
    print("Secrets will be uploaded to /opt/stackchan-server/shared and will not be printed.")

    if args.dry_run:
        return 0

    with tempfile.TemporaryDirectory(prefix="stackchan-deploy-") as tmp:
        tmp_dir = Path(tmp)
        archive = tmp_dir / "stackchan-server.tar.gz"
        env_file = tmp_dir / "compose.env"
        create_server_archive(stackchan_dir, archive)
        env_file.write_text(compose_env, encoding="utf-8")
        env_file.chmod(0o600)

        remote_tmp_dir = f"/tmp/stackchan-deploy-{release_name}"
        fail_if_bad(remote_command(remote, f"set -e; rm -rf {shlex.quote(remote_tmp_dir)}; install -d -m 0700 {shlex.quote(remote_tmp_dir)}"), "create remote temp dir")
        archive_remote = f"{remote_tmp_dir}/server.tar.gz"
        config_remote = f"{remote_tmp_dir}/config.yaml"
        env_remote = f"{remote_tmp_dir}/compose.env"

        fail_if_bad(upload_file(remote, archive, archive_remote), "upload server archive")
        fail_if_bad(upload_file(remote, config_file, config_remote), "upload server config")
        fail_if_bad(upload_file(remote, env_file, env_remote), "upload compose env")

        install_script = remote_install_script(release_name, archive_remote, config_remote, env_remote)
        proc = remote_command(remote, install_script)
        fail_if_bad(proc, "remote deploy")
        print(proc.stdout.rstrip())

    print("StackChan server deployment completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
