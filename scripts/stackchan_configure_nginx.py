#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
from pathlib import Path
from urllib.parse import urlparse

from stackchan_deploy_compose import ROOT_DIR, load_env, load_remote, remote_command


DEFAULT_CONF_PATH = "/www/server/panel/vhost/nginx/stackchan-server.conf"


def public_host(env: dict[str, str]) -> str:
    value = (
        env.get("STACKCHAN_PUBLIC_HOST")
        or env.get("STACKCHAN_PUBLIC_BASE_URL")
        or env.get("STACKCHAN_SERVER_HOST")
        or env.get("SERVER_IP")
        or env.get("SERVER_HOST")
    )
    if not value:
        raise RuntimeError("STACKCHAN_PUBLIC_HOST, STACKCHAN_PUBLIC_BASE_URL, or SERVER_IP is required")
    parsed = urlparse(value if "://" in value else f"http://{value}")
    host = parsed.netloc or parsed.path
    host = host.split("/")[0]
    if ":" in host:
        host = host.split(":", 1)[0]
    if not host:
        raise RuntimeError(f"could not derive public host from: {value}")
    return host


def nginx_config(host: str) -> str:
    return f"""server {{
    listen 80;
    server_name {host};

    client_max_body_size 100m;

    location /stackChan/ws {{
        proxy_pass http://127.0.0.1:12800;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }}

    location /stackChan/ {{
        proxy_pass http://127.0.0.1:12800;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    location /file/ {{
        proxy_pass http://127.0.0.1:12800;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    location = /api.json {{
        proxy_pass http://127.0.0.1:12800;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    location /swagger {{
        proxy_pass http://127.0.0.1:12800;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    location / {{
        return 404;
    }}
}}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure nginx reverse proxy for StackChan server.")
    parser.add_argument("--env-file", type=Path, action="append", default=None)
    parser.add_argument("--conf-path", default=DEFAULT_CONF_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env_files = args.env_file or [ROOT_DIR / ".env"]
    env = load_env(env_files)
    remote = load_remote(env)
    host = public_host(env)
    config = nginx_config(host)

    print(f"Configuring nginx host: {host}")
    print(f"Remote config path: {args.conf_path}")

    if args.dry_run:
        print(config)
        return 0

    script = f"""\
set -Eeuo pipefail
CONF_PATH={shlex.quote(args.conf_path)}
install -d -m 0755 "$(dirname "$CONF_PATH")"
cat > "$CONF_PATH" <<'NGINX'
{config}NGINX
nginx -t
systemctl reload nginx
curl -fsS -H {shlex.quote('Host: ' + host)} http://127.0.0.1/api.json >/dev/null
curl -fsS -H {shlex.quote('Host: ' + host)} http://127.0.0.1/file/music/stackchan_music.mp3 >/dev/null
WS_STATUS="$(curl -sS -o /dev/null -w '%{{http_code}}' -H {shlex.quote('Host: ' + host)} http://127.0.0.1/stackChan/ws || true)"
if [ "$WS_STATUS" != "401" ]; then
  echo "unexpected nginx websocket unauthenticated status: $WS_STATUS" >&2
  exit 1
fi
echo "nginx-stackchan-ok"
"""
    proc = remote_command(remote, script)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.returncode != 0:
        raise RuntimeError(f"nginx configuration failed with exit code {proc.returncode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
