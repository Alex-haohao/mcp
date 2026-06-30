#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import secrets
import shutil
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT_DIR / "workspace" / "stackchan-secrets" / "server"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def generate_key_pair(private_key: Path, public_key: Path, force: bool) -> None:
    if private_key.exists() and public_key.exists() and not force:
        return
    if (private_key.exists() or public_key.exists()) and not force:
        raise RuntimeError(f"refusing to overwrite partial key pair: {private_key}, {public_key}")

    private_key.parent.mkdir(parents=True, exist_ok=True)
    run([
        "openssl",
        "genpkey",
        "-algorithm",
        "RSA",
        "-pkeyopt",
        "rsa_keygen_bits:2048",
        "-out",
        str(private_key),
    ])
    run([
        "openssl",
        "rsa",
        "-in",
        str(private_key),
        "-pubout",
        "-out",
        str(public_key),
    ])
    private_key.chmod(0o600)
    public_key.chmod(0o644)


def indent_pem(path: Path, spaces: int = 6) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in path.read_text(encoding="utf-8").splitlines())


def b64_file(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def write_if_missing(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        return
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def render_config(
    *,
    mysql_host: str,
    mysql_password: str,
    jwt_secret: str,
    admin_password: str,
    server_public: Path,
    server_private: Path,
    client_public: Path,
    client_private: Path,
) -> str:
    return f"""server:
  address: ":12800"
  openapiPath: "/api.json"
  swaggerPath: "/swagger"

logger:
  path: "./logs"
  file: "{{Y-m-d}}.log"
  level: "all"
  stdout: true
  rotateExpire: "7d"
  rotateBackup: 10
  rotateSize: "50M"

database:
  default:
    link: "mysql:stackchan:{mysql_password}@tcp({mysql_host}:3306)/stackChan?charset=utf8mb4&collation=utf8mb4_0900_ai_ci&parseTime=true"

jwt:
  secret: "{jwt_secret}"

admin:
  users:
    - username: "stackchan-admin"
      password: "{admin_password}"

rsa:
  server:
    public: |
{indent_pem(server_public)}
    private: |
{indent_pem(server_private)}
  client:
    public: |
{indent_pem(client_public)}
    private: |
{indent_pem(client_private)}

xiaozhi:
  secret_key: ""
  generate_license_token: ""
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate local-only StackChan server secrets.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--force", action="store_true", help="Overwrite existing generated files.")
    args = parser.parse_args()

    openssl = shutil.which("openssl")
    if not openssl:
        raise RuntimeError("openssl is required")

    out_dir = args.out_dir.expanduser().resolve()
    key_dir = out_dir / "keys"
    out_dir.mkdir(parents=True, exist_ok=True)

    server_private = key_dir / "server_private.pem"
    server_public = key_dir / "server_public.pem"
    client_private = key_dir / "client_private.pem"
    client_public = key_dir / "client_public.pem"
    blue_private = key_dir / "stackchan_blue_private.pem"
    blue_public = key_dir / "stackchan_blue_public.pem"

    generate_key_pair(server_private, server_public, args.force)
    generate_key_pair(client_private, client_public, args.force)
    generate_key_pair(blue_private, blue_public, args.force)

    jwt_secret = secrets.token_urlsafe(48)
    admin_password = secrets.token_urlsafe(24)
    mysql_password = secrets.token_urlsafe(24)
    mysql_root_password = secrets.token_urlsafe(24)

    config_systemd = render_config(
        mysql_host="127.0.0.1",
        mysql_password=mysql_password,
        jwt_secret=jwt_secret,
        admin_password=admin_password,
        server_public=server_public,
        server_private=server_private,
        client_public=client_public,
        client_private=client_private,
    )
    config_compose = render_config(
        mysql_host="mysql",
        mysql_password=mysql_password,
        jwt_secret=jwt_secret,
        admin_password=admin_password,
        server_public=server_public,
        server_private=server_private,
        client_public=client_public,
        client_private=client_private,
    )
    write_if_missing(out_dir / "config.systemd.yaml", config_systemd, args.force)
    write_if_missing(out_dir / "config.compose.yaml", config_compose, args.force)
    write_if_missing(out_dir / "config.yaml", config_systemd, args.force)

    compose_env = f"""STACKCHAN_CONFIG_PATH={out_dir / "config.compose.yaml"}
STACKCHAN_MYSQL_DATABASE=stackChan
STACKCHAN_MYSQL_USER=stackchan
STACKCHAN_MYSQL_PASSWORD={mysql_password}
STACKCHAN_MYSQL_ROOT_PASSWORD={mysql_root_password}
"""
    write_if_missing(out_dir / "compose.env", compose_env, args.force)

    app_defines = f"""STACKCHAN_SERVER_HOST=127.0.0.1:12800
STACKCHAN_SERVER_TLS=false
STACKCHAN_SERVER_PATH_PREFIX=
STACKCHAN_SERVER_PUBLIC_KEY_BASE64={b64_file(server_public)}
STACKCHAN_CLIENT_PRIVATE_KEY_BASE64={b64_file(client_private)}
STACKCHAN_BLUE_PRIVATE_KEY_BASE64={b64_file(blue_private)}
"""
    write_if_missing(out_dir / "app-dart-defines.env", app_defines, args.force)

    readme = f"""# Local StackChan Secrets

Generated local-only StackChan secrets. Do not commit this directory.

- Systemd server config: `{out_dir / "config.systemd.yaml"}`
- Compose server config: `{out_dir / "config.compose.yaml"}`
- Compatibility config copy: `{out_dir / "config.yaml"}`
- Compose env: `{out_dir / "compose.env"}`
- App dart defines: `{out_dir / "app-dart-defines.env"}`
- PEM keys: `{key_dir}`

The generated values are intentionally not printed by the generator.
"""
    readme_path = out_dir / "README.md"
    if not readme_path.exists() or args.force:
        readme_path.write_text(readme, encoding="utf-8")
        readme_path.chmod(0o600)

    print(f"Generated local StackChan secrets under: {out_dir}")
    print("Values were written to ignored local files and were not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
