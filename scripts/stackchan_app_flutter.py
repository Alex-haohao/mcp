#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STACKCHAN_DIR = ROOT_DIR / ".worktrees" / "StackChan-server-app"
DEFAULT_SECRET_DIR = ROOT_DIR / "workspace" / "stackchan-secrets" / "server"
DEFAULT_DEFINES_FILE = DEFAULT_SECRET_DIR / "app-dart-defines.env"
DEFAULT_GENERATED_FILE = DEFAULT_SECRET_DIR / "app-dart-defines.generated.env"

APP_DEFINE_KEYS = (
    "STACKCHAN_SERVER_HOST",
    "STACKCHAN_SERVER_TLS",
    "STACKCHAN_SERVER_PATH_PREFIX",
    "STACKCHAN_SERVER_PUBLIC_KEY_BASE64",
    "STACKCHAN_CLIENT_PRIVATE_KEY_BASE64",
    "STACKCHAN_BLUE_PRIVATE_KEY_BASE64",
)

DEFINE_ACTIONS = {"test", "run", "build-ios-debug", "build-ios-release", "build-macos-debug"}


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def render_env(values: dict[str, str]) -> str:
    lines = []
    for key in APP_DEFINE_KEYS:
        lines.append(f"{key}={values.get(key, '')}")
    return "\n".join(lines) + "\n"


def ensure_generated_defines(
    *,
    defines_file: Path,
    generated_file: Path,
    host: str | None,
    tls: str | None,
    path_prefix: str | None,
) -> tuple[Path, dict[str, str]]:
    values = parse_env_file(defines_file)
    if host is not None:
        values["STACKCHAN_SERVER_HOST"] = host
    if tls is not None:
        normalized_tls = tls.strip().lower()
        if normalized_tls not in {"true", "false"}:
            raise RuntimeError("--tls must be true or false")
        values["STACKCHAN_SERVER_TLS"] = normalized_tls
    if path_prefix is not None:
        values["STACKCHAN_SERVER_PATH_PREFIX"] = path_prefix

    missing = [key for key in APP_DEFINE_KEYS if not values.get(key) and key != "STACKCHAN_SERVER_PATH_PREFIX"]
    if missing:
        raise RuntimeError(
            "missing StackChan app dart-define key(s): "
            + ", ".join(missing)
            + f"; generate them with {ROOT_DIR / 'scripts' / 'stackchan_prepare_local_secrets.py'}"
        )

    generated_file.parent.mkdir(parents=True, exist_ok=True)
    generated_file.write_text(render_env(values), encoding="utf-8")
    generated_file.chmod(0o600)
    return generated_file, values


def redacted_summary(values: dict[str, str], defines_file: Path) -> str:
    required_keys = [key for key in APP_DEFINE_KEYS if key != "STACKCHAN_SERVER_PATH_PREFIX"]
    present = [key for key in required_keys if values.get(key)]
    return "\n".join(
        [
            f"defines_file={defines_file}",
            f"STACKCHAN_SERVER_HOST={values.get('STACKCHAN_SERVER_HOST', '')}",
            f"STACKCHAN_SERVER_TLS={values.get('STACKCHAN_SERVER_TLS', '')}",
            f"STACKCHAN_SERVER_PATH_PREFIX={values.get('STACKCHAN_SERVER_PATH_PREFIX', '')}",
            f"required_keys={len(present)}/{len(required_keys)}",
        ]
    )


def run(command: list[str], cwd: Path) -> int:
    printable = " ".join(shlex.quote(part) for part in command)
    print(f"Running in {cwd}: {printable}")
    return subprocess.run(command, cwd=cwd, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Flutter commands for the StackChan app.")
    parser.add_argument(
        "action",
        choices=[
            "pub-get",
            "analyze",
            "test",
            "build-ios-debug",
            "build-ios-release",
            "build-macos-debug",
            "run",
            "doctor",
            "print-config",
        ],
    )
    parser.add_argument("flutter_args", nargs=argparse.REMAINDER, help="Extra arguments passed after the Flutter subcommand.")
    parser.add_argument("--stackchan-dir", type=Path, default=DEFAULT_STACKCHAN_DIR)
    parser.add_argument("--defines-file", type=Path, default=DEFAULT_DEFINES_FILE)
    parser.add_argument("--generated-defines-file", type=Path, default=DEFAULT_GENERATED_FILE)
    parser.add_argument("--host", help="Override STACKCHAN_SERVER_HOST for this generated defines file.")
    parser.add_argument("--tls", help="Override STACKCHAN_SERVER_TLS for this generated defines file: true or false.")
    parser.add_argument("--path-prefix", help="Override STACKCHAN_SERVER_PATH_PREFIX for this generated defines file.")
    args = parser.parse_args()

    flutter = shutil.which("flutter")
    if not flutter:
        raise RuntimeError("flutter is not available in PATH")

    stackchan_dir = args.stackchan_dir.expanduser().resolve()
    app_dir = stackchan_dir / "app"
    if not app_dir.is_dir():
        raise RuntimeError(f"missing StackChan app directory: {app_dir}")

    defines_file = args.defines_file.expanduser().resolve()
    generated_file = args.generated_defines_file.expanduser().resolve()

    values: dict[str, str] = {}
    defines_arg: list[str] = []
    if args.action in DEFINE_ACTIONS or args.action == "print-config":
        generated_file, values = ensure_generated_defines(
            defines_file=defines_file,
            generated_file=generated_file,
            host=args.host,
            tls=args.tls,
            path_prefix=args.path_prefix,
        )
        defines_arg = [f"--dart-define-from-file={generated_file}"]
        print(redacted_summary(values, generated_file))

    extra = list(args.flutter_args)
    if extra and extra[0] == "--":
        extra = extra[1:]

    if args.action == "print-config":
        return 0
    if args.action == "doctor":
        return run([flutter, "doctor", *extra], app_dir)
    if args.action == "pub-get":
        return run([flutter, "pub", "get", *extra], app_dir)
    if args.action == "analyze":
        return run([flutter, "analyze", "--no-fatal-infos", "--no-fatal-warnings", *extra], app_dir)
    if args.action == "test":
        return run([flutter, "test", *defines_arg, *extra], app_dir)
    if args.action == "build-ios-debug":
        return run([flutter, "build", "ios", "--debug", "--no-codesign", *defines_arg, *extra], app_dir)
    if args.action == "build-ios-release":
        return run([flutter, "build", "ios", "--release", *defines_arg, *extra], app_dir)
    if args.action == "build-macos-debug":
        return run([flutter, "build", "macos", "--debug", *defines_arg, *extra], app_dir)
    if args.action == "run":
        return run([flutter, "run", *defines_arg, *extra], app_dir)
    raise AssertionError(f"unhandled action: {args.action}")


if __name__ == "__main__":
    raise SystemExit(main())
