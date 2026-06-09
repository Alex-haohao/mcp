#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import shutil
import shlex
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
AIRI_DIR = ROOT_DIR / "projects" / "airi"
STAGE_POCKET_DIR = AIRI_DIR / "apps" / "stage-pocket"
IOS_PROJECT = STAGE_POCKET_DIR / "ios" / "App" / "App.xcodeproj"
BUILD_DIR = ROOT_DIR / "build" / "airi-testflight"
DERIVED_DATA_DIR = ROOT_DIR / "build" / "airi-derived-data"
CAPACITOR_SYNC_TRACKED_FILES = [
    Path("apps/stage-pocket/ios/App/CapApp-SPM/Package.swift"),
    Path(
        "apps/stage-pocket/ios/App/App.xcodeproj/project.xcworkspace/"
        "xcshareddata/swiftpm/Package.resolved"
    ),
]


def run(command: list[str], *, cwd: Path) -> None:
    print("$ " + " ".join(shlex.quote(part) for part in command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build AIRI Stage Pocket for iOS/TestFlight from the AIRI submodule."
    )
    parser.add_argument(
        "--team-id",
        default=os.getenv("AIRI_IOS_TEAM_ID"),
        help="Apple Developer Team ID. Can also be set with AIRI_IOS_TEAM_ID.",
    )
    parser.add_argument(
        "--bundle-id",
        default=os.getenv("AIRI_IOS_BUNDLE_ID"),
        help="iOS Bundle ID. Can also be set with AIRI_IOS_BUNDLE_ID.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip pnpm install when dependencies are already present.",
    )
    parser.add_argument(
        "--skip-web-build",
        action="store_true",
        help="Skip the Stage Pocket Vite production build.",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Skip Capacitor iOS sync.",
    )
    parser.add_argument(
        "--keep-synced-xcode-files",
        action="store_true",
        help=(
            "Keep tracked Xcode files changed by Capacitor sync. By default they "
            "are restored after the build when they were clean before sync."
        ),
    )
    parser.add_argument(
        "--skip-simulator-build",
        action="store_true",
        help="Skip the unsigned iOS simulator compile smoke test.",
    )
    parser.add_argument(
        "--unsigned-archive",
        action="store_true",
        help="Create an unsigned device archive. This cannot be uploaded to TestFlight.",
    )
    return parser.parse_args()


def ensure_airi_checkout() -> None:
    if not AIRI_DIR.exists() or not IOS_PROJECT.exists():
        raise RuntimeError(
            "AIRI submodule is missing. Run: git submodule update --init --recursive"
        )


def pnpm_install() -> None:
    run(
        ["pnpm", "install", "--registry=https://registry.npmjs.org/"],
        cwd=AIRI_DIR,
    )


def build_stage_pocket() -> None:
    run(["pnpm", "-F", "@proj-airi/stage-pocket", "build"], cwd=AIRI_DIR)


def sync_ios() -> None:
    run(
        ["pnpm", "-F", "@proj-airi/stage-pocket", "exec", "cap", "sync", "ios"],
        cwd=AIRI_DIR,
    )


def tracked_files_are_clean(paths: list[Path]) -> bool:
    rel_paths = [str(path) for path in paths]
    return (
        subprocess.run(
            ["git", "diff", "--quiet", "--", *rel_paths],
            cwd=AIRI_DIR,
            check=False,
        ).returncode
        == 0
        and subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", *rel_paths],
            cwd=AIRI_DIR,
            check=False,
        ).returncode
        == 0
    )


def restore_tracked_files(paths: list[Path]) -> None:
    run(["git", "restore", "--", *[str(path) for path in paths]], cwd=AIRI_DIR)


def build_simulator() -> None:
    run(
        [
            "xcodebuild",
            "-project",
            str(IOS_PROJECT.relative_to(AIRI_DIR)),
            "-scheme",
            "App",
            "-configuration",
            "Debug",
            "-sdk",
            "iphonesimulator",
            "-destination",
            "generic/platform=iOS Simulator",
            "-derivedDataPath",
            str(DERIVED_DATA_DIR),
            "CODE_SIGNING_ALLOWED=NO",
            "build",
        ],
        cwd=AIRI_DIR,
    )


def build_signing_settings(*, team_id: str, bundle_id: str, unsigned: bool) -> list[str]:
    settings = [
        f"DEVELOPMENT_TEAM={team_id}",
        f"PRODUCT_BUNDLE_IDENTIFIER={bundle_id}",
        "CODE_SIGN_STYLE=Automatic",
        "PROVISIONING_PROFILE_SPECIFIER=",
    ]
    if unsigned:
        settings.append("CODE_SIGN_IDENTITY=")
    return settings


def archive_ios(*, team_id: str, bundle_id: str, unsigned: bool) -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = BUILD_DIR / "AIRI.xcarchive"
    if archive_path.exists():
        shutil.rmtree(archive_path)

    run(
        [
            "xcodebuild",
            "-project",
            str(IOS_PROJECT.relative_to(AIRI_DIR)),
            "-scheme",
            "App",
            "-configuration",
            "Release",
            "-destination",
            "generic/platform=iOS",
            "-archivePath",
            str(archive_path),
            "-derivedDataPath",
            str(DERIVED_DATA_DIR),
            "-allowProvisioningUpdates",
            *build_signing_settings(
                team_id=team_id,
                bundle_id=bundle_id,
                unsigned=unsigned,
            ),
            "archive",
        ],
        cwd=AIRI_DIR,
    )


def main() -> int:
    args = parse_args()
    try:
        ensure_airi_checkout()
        if not args.team_id:
            raise RuntimeError("--team-id or AIRI_IOS_TEAM_ID is required")
        if not args.bundle_id:
            raise RuntimeError("--bundle-id or AIRI_IOS_BUNDLE_ID is required")

        if not args.skip_install:
            pnpm_install()
        if not args.skip_web_build:
            build_stage_pocket()
        should_restore_sync_files = (
            not args.skip_sync
            and not args.keep_synced_xcode_files
            and tracked_files_are_clean(CAPACITOR_SYNC_TRACKED_FILES)
        )

        try:
            if not args.skip_sync:
                sync_ios()
            if not args.skip_simulator_build:
                build_simulator()
            archive_ios(
                team_id=args.team_id,
                bundle_id=args.bundle_id,
                unsigned=args.unsigned_archive,
            )
        finally:
            if should_restore_sync_files:
                restore_tracked_files(CAPACITOR_SYNC_TRACKED_FILES)
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    except Exception as exc:
        print(f"airi ios build failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
