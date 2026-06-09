#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import plistlib
import re
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
ARCHIVE_PATH = BUILD_DIR / "AIRI.xcarchive"
EXPORT_DIR = BUILD_DIR / "export"
EXPORT_OPTIONS_PATH = BUILD_DIR / "ExportOptions.plist"
CAPACITOR_SYNC_TRACKED_FILES = [
    Path("apps/stage-pocket/ios/App/CapApp-SPM/Package.swift"),
    Path(
        "apps/stage-pocket/ios/App/App.xcodeproj/project.xcworkspace/"
        "xcshareddata/swiftpm/Package.resolved"
    ),
]
ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_dotenv_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].lstrip()

    key, separator, value = stripped.partition("=")
    if not separator:
        return None

    key = key.strip()
    if not ENV_KEY_PATTERN.match(key):
        return None

    value = value.strip()
    if value.startswith(("'", '"')):
        try:
            parsed = shlex.split(value, comments=False, posix=True)
        except ValueError:
            parsed = [value.strip(value[0])]
        value = parsed[0] if parsed else ""
    else:
        value = value.split(" #", 1)[0].strip()
    return key, value


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = parse_dotenv_line(line)
        if parsed is None:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)


def first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def run(command: list[str], *, cwd: Path) -> None:
    print("$ " + " ".join(shlex.quote(part) for part in command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def parse_args() -> argparse.Namespace:
    load_dotenv(ROOT_DIR / ".env")
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
        "--signing-style",
        choices=("automatic", "manual"),
        default=os.getenv("AIRI_IOS_SIGNING_STYLE", "automatic"),
        help="Xcode signing style for a signed archive. Defaults to automatic.",
    )
    parser.add_argument(
        "--provisioning-profile",
        default=os.getenv("AIRI_IOS_PROVISIONING_PROFILE"),
        help="Provisioning profile name or UUID. Required for manual signed archives.",
    )
    parser.add_argument(
        "--code-sign-identity",
        default=os.getenv("AIRI_IOS_CODE_SIGN_IDENTITY"),
        help="Code signing identity override. Manual signing defaults to Apple Distribution.",
    )
    parser.add_argument(
        "--authentication-key-path",
        default=first_env("AIRI_ASC_API_KEY_PATH", "APP_STORE_CONNECT_API_KEY_PATH"),
        help="App Store Connect API .p8 key path for xcodebuild/altool.",
    )
    parser.add_argument(
        "--authentication-key-id",
        default=first_env("AIRI_ASC_API_KEY_ID", "APP_STORE_CONNECT_API_KEY_ID"),
        help="App Store Connect API key ID.",
    )
    parser.add_argument(
        "--authentication-key-issuer-id",
        default=first_env("AIRI_ASC_ISSUER_ID", "APP_STORE_CONNECT_ISSUER_ID"),
        help="App Store Connect API issuer ID.",
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
    parser.add_argument(
        "--skip-archive",
        action="store_true",
        help="Skip archive creation and use the existing archive path.",
    )
    parser.add_argument(
        "--export-ipa",
        action="store_true",
        help="Export the signed archive to an App Store Connect IPA.",
    )
    parser.add_argument(
        "--upload-testflight",
        action="store_true",
        help="Upload the exported IPA to App Store Connect/TestFlight with altool.",
    )
    parser.add_argument(
        "--wait-for-processing",
        action="store_true",
        help="Ask altool to wait for upload or processing completion when supported.",
    )
    parser.add_argument(
        "--internal-testing-only",
        action="store_true",
        help="Mark exported build as TestFlight internal testing only.",
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


def build_authentication_args(
    *,
    key_path: str | None,
    key_id: str | None,
    issuer_id: str | None,
) -> list[str]:
    provided = [bool(key_path), bool(key_id), bool(issuer_id)]
    if any(provided) and not all(provided):
        raise RuntimeError(
            "App Store Connect authentication requires key path, key ID, and issuer ID"
        )
    if not all(provided):
        return []
    return [
        "-authenticationKeyPath",
        str(Path(key_path).expanduser()),
        "-authenticationKeyID",
        str(key_id),
        "-authenticationKeyIssuerID",
        str(issuer_id),
    ]


def require_app_store_connect_authentication(
    *,
    key_path: str | None,
    key_id: str | None,
    issuer_id: str | None,
) -> None:
    if not all([key_path, key_id, issuer_id]):
        raise RuntimeError(
            "TestFlight upload requires App Store Connect key path, key ID, and issuer ID"
        )
    build_authentication_args(key_path=key_path, key_id=key_id, issuer_id=issuer_id)


def build_signing_settings(
    *,
    team_id: str,
    bundle_id: str,
    unsigned: bool,
    signing_style: str = "automatic",
    provisioning_profile: str | None = None,
    code_sign_identity: str | None = None,
) -> list[str]:
    if signing_style not in {"automatic", "manual"}:
        raise RuntimeError("signing style must be automatic or manual")
    if signing_style == "manual" and not unsigned and not provisioning_profile:
        raise RuntimeError("--provisioning-profile is required for manual signed archives")

    settings = [
        f"DEVELOPMENT_TEAM={team_id}",
        f"PRODUCT_BUNDLE_IDENTIFIER={bundle_id}",
        f"CODE_SIGN_STYLE={signing_style.title()}",
        f"PROVISIONING_PROFILE_SPECIFIER={provisioning_profile or ''}",
    ]
    if unsigned:
        settings.append("CODE_SIGN_IDENTITY=")
    elif signing_style == "manual":
        settings.append(f"CODE_SIGN_IDENTITY={code_sign_identity or 'Apple Distribution'}")
    elif code_sign_identity:
        settings.append(f"CODE_SIGN_IDENTITY={code_sign_identity}")
    return settings


def archive_ios(
    *,
    team_id: str,
    bundle_id: str,
    unsigned: bool,
    signing_style: str,
    provisioning_profile: str | None,
    code_sign_identity: str | None,
    authentication_args: list[str],
) -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if ARCHIVE_PATH.exists():
        shutil.rmtree(ARCHIVE_PATH)

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
            str(ARCHIVE_PATH),
            "-derivedDataPath",
            str(DERIVED_DATA_DIR),
            "-allowProvisioningUpdates",
            *authentication_args,
            *build_signing_settings(
                team_id=team_id,
                bundle_id=bundle_id,
                unsigned=unsigned,
                signing_style=signing_style,
                provisioning_profile=provisioning_profile,
                code_sign_identity=code_sign_identity,
            ),
            "archive",
        ],
        cwd=AIRI_DIR,
    )


def build_export_options(
    *,
    team_id: str,
    bundle_id: str,
    signing_style: str,
    provisioning_profile: str | None,
    destination: str = "export",
    internal_testing_only: bool = False,
) -> dict[str, object]:
    if signing_style not in {"automatic", "manual"}:
        raise RuntimeError("signing style must be automatic or manual")
    if signing_style == "manual" and not provisioning_profile:
        raise RuntimeError("--provisioning-profile is required for manual IPA export")

    options: dict[str, object] = {
        "method": "app-store-connect",
        "destination": destination,
        "teamID": team_id,
        "signingStyle": signing_style,
        "stripSwiftSymbols": True,
        "uploadSymbols": True,
        "manageAppVersionAndBuildNumber": True,
    }
    if internal_testing_only:
        options["testFlightInternalTestingOnly"] = True
    if signing_style == "manual":
        options["provisioningProfiles"] = {bundle_id: provisioning_profile}
    return options


def write_export_options(options: dict[str, object]) -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    with EXPORT_OPTIONS_PATH.open("wb") as plist_file:
        plistlib.dump(options, plist_file)


def export_ipa(
    *,
    team_id: str,
    bundle_id: str,
    signing_style: str,
    provisioning_profile: str | None,
    authentication_args: list[str],
    internal_testing_only: bool,
) -> None:
    if not ARCHIVE_PATH.exists():
        raise RuntimeError(f"archive does not exist: {ARCHIVE_PATH}")
    if EXPORT_DIR.exists():
        shutil.rmtree(EXPORT_DIR)
    write_export_options(
        build_export_options(
            team_id=team_id,
            bundle_id=bundle_id,
            signing_style=signing_style,
            provisioning_profile=provisioning_profile,
            internal_testing_only=internal_testing_only,
        )
    )
    run(
        [
            "xcodebuild",
            "-exportArchive",
            "-archivePath",
            str(ARCHIVE_PATH),
            "-exportPath",
            str(EXPORT_DIR),
            "-exportOptionsPlist",
            str(EXPORT_OPTIONS_PATH),
            "-allowProvisioningUpdates",
            *authentication_args,
        ],
        cwd=ROOT_DIR,
    )


def find_exported_ipa() -> Path:
    ipa_paths = sorted(EXPORT_DIR.glob("*.ipa"))
    if len(ipa_paths) != 1:
        raise RuntimeError(f"expected exactly one IPA in {EXPORT_DIR}, found {len(ipa_paths)}")
    return ipa_paths[0]


def upload_testflight(
    *,
    ipa_path: Path,
    key_path: str | None,
    key_id: str | None,
    issuer_id: str | None,
    wait: bool,
) -> None:
    require_app_store_connect_authentication(
        key_path=key_path,
        key_id=key_id,
        issuer_id=issuer_id,
    )
    command = [
        "xcrun",
        "altool",
        "--upload-package",
        str(ipa_path),
        "--api-key",
        str(key_id),
        "--api-issuer",
        str(issuer_id),
        "--p8-file-path",
        str(Path(str(key_path)).expanduser()),
        "--show-progress",
    ]
    if wait:
        command.append("--wait")
    run(command, cwd=ROOT_DIR)


def main() -> int:
    args = parse_args()
    try:
        ensure_airi_checkout()
        if not args.team_id:
            raise RuntimeError("--team-id or AIRI_IOS_TEAM_ID is required")
        if not args.bundle_id:
            raise RuntimeError("--bundle-id or AIRI_IOS_BUNDLE_ID is required")
        if args.unsigned_archive and (args.export_ipa or args.upload_testflight):
            raise RuntimeError("unsigned archives cannot be exported or uploaded to TestFlight")
        if args.upload_testflight:
            args.export_ipa = True
            require_app_store_connect_authentication(
                key_path=args.authentication_key_path,
                key_id=args.authentication_key_id,
                issuer_id=args.authentication_key_issuer_id,
            )

        authentication_args = build_authentication_args(
            key_path=args.authentication_key_path,
            key_id=args.authentication_key_id,
            issuer_id=args.authentication_key_issuer_id,
        )

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
            if not args.skip_archive:
                archive_ios(
                    team_id=args.team_id,
                    bundle_id=args.bundle_id,
                    unsigned=args.unsigned_archive,
                    signing_style=args.signing_style,
                    provisioning_profile=args.provisioning_profile,
                    code_sign_identity=args.code_sign_identity,
                    authentication_args=authentication_args,
                )
        finally:
            if should_restore_sync_files:
                restore_tracked_files(CAPACITOR_SYNC_TRACKED_FILES)
        if args.export_ipa:
            export_ipa(
                team_id=args.team_id,
                bundle_id=args.bundle_id,
                signing_style=args.signing_style,
                provisioning_profile=args.provisioning_profile,
                authentication_args=authentication_args,
                internal_testing_only=args.internal_testing_only,
            )
        if args.upload_testflight:
            upload_testflight(
                ipa_path=find_exported_ipa(),
                key_path=args.authentication_key_path,
                key_id=args.authentication_key_id,
                issuer_id=args.authentication_key_issuer_id,
                wait=args.wait_for_processing,
            )
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    except Exception as exc:
        print(f"airi ios build failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
