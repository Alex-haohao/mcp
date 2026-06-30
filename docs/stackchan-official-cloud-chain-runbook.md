# StackChan Official Cloud Chain Runbook

This runbook is the source of truth for the self-hosted StackChan app/server
workflow in this workspace.

## Goal

Use the official StackChan architecture and keep our changes easy to rebase onto
new upstream releases:

```text
StackChan mobile app
  -> HTTPS/WSS reverse proxy
  -> self-hosted official StackChan Server
  -> official StackChan firmware/device WebSocket client
```

Do not make phone-to-device direct WebSocket control the primary architecture.
Direct LAN/BLE flows can remain useful for setup or diagnostics, but the
maintained product path should stay compatible with the official app/server/
device chain.

## Repository Boundaries

- Root workspace docs and scripts live in this repository.
- Official StackChan source lives under `projects/StackChan`.
- When `projects/StackChan` has avatar or firmware work in progress, use an
  isolated worktree for app/server changes:

```bash
mkdir -p .worktrees
git -C projects/StackChan fetch upstream
git -C projects/StackChan worktree add \
  .worktrees/StackChan-server-app \
  -b codex/server-app \
  upstream/main
```

This keeps app/server work separate from avatar work and gives us a clean branch
that can be rebased onto `upstream/main`.

## Secret Policy

Never commit real credentials, host-specific config, private keys, JWT secrets,
database passwords, admin passwords, XiaoZhi tokens, or generated production
`config.yaml` files.

Allowed in git:

- Placeholder examples such as `.env.example`.
- Docker Compose, Caddy, and config templates with fake values.
- Scripts that read local `.env` and redact values.

Local-only locations:

- Workspace root `.env` for deployment variables.
- `workspace/stackchan-secrets/` for generated PEM files and config drafts.
- Cloud server paths such as `/opt/stackchan-server/shared/config.yaml`.

The root `.gitignore` excludes `.env`, `.worktrees/`,
`workspace/stackchan-cloud/`, and `workspace/stackchan-secrets/`.

Generate local-only initial secrets:

```bash
scripts/stackchan_prepare_local_secrets.py
```

This creates ignored files under `workspace/stackchan-secrets/server/`,
including:

- `config.systemd.yaml` for an existing host MySQL service at `127.0.0.1`.
- `config.compose.yaml` for Docker Compose where the DB host is `mysql`.
- RSA PEM files.
- Compose env values.
- App `--dart-define` values.

The script prints paths only, not secret values.

## Current App Configuration Decision

The official app source had a hardcoded backend placeholder in
`app/lib/network/urls.dart`. For self-hosting, the app should receive endpoint
settings at build time:

```bash
flutter run \
  --dart-define=STACKCHAN_SERVER_HOST=stackchan.example.com \
  --dart-define=STACKCHAN_SERVER_TLS=true
```

For local HTTP testing:

```bash
flutter run \
  --dart-define=STACKCHAN_SERVER_HOST=192.168.1.100:12800 \
  --dart-define=STACKCHAN_SERVER_TLS=false
```

RSA PEM values should be injected as base64-encoded PEM to avoid multiline shell
quoting issues:

```bash
--dart-define=STACKCHAN_SERVER_PUBLIC_KEY_BASE64=<base64-pem>
--dart-define=STACKCHAN_CLIENT_PRIVATE_KEY_BASE64=<base64-pem>
--dart-define=STACKCHAN_BLUE_PRIVATE_KEY_BASE64=<base64-pem>
```

The server private key stays on the server. The app only receives values needed
by the official client protocol.

## Firmware Secret Alignment

Official firmware plus the official App works because the distributed binary
pair is built as one matched production chain: the App, server, firmware server
URL, and BLE/RSA handshake behavior all agree. The open-source
`firmware/main/hal/utils/secret_logic/secret_logic.cpp` contains weak
placeholder defaults such as `hi-stack-chan`; a self-built firmware that uses
those defaults will not match our self-hosted App/server keys.

For this workspace, keep the upstream-friendly pattern:

- Track only a small firmware override file and the generator script.
- Store real PEM material and host URL in ignored local files.
- Regenerate local firmware config whenever server keys or host URL change.

Generate the ignored firmware config:

```bash
scripts/stackchan_generate_firmware_secrets.py \
  --stackchan-dir projects/StackChan \
  --server-url http://162.211.181.150
```

This writes:

```text
projects/StackChan/firmware/main/hal/local_secret_config.h
projects/StackChan/firmware/sdkconfig.defaults.local
projects/StackChan/firmware/sdkconfig
```

All three files must stay ignored. The tracked firmware override is
`firmware/main/hal/local_secret_logic.cpp`; when `local_secret_config.h` is
present, it replaces the weak defaults with:

- `get_server_url()` returning the local server URL;
- `generate_auth_token()` using RSA-OAEP/SHA256 and the local server public key;
- `generate_handshake_token()` using RSA-OAEP/SHA256 and the local
  `stackchan_blue_public.pem` key.

The mobile App add-device flow writes a BLE `handshake` command and expects a
`notifyState` response whose `data.state` is base64 RSA-OAEP/SHA256 ciphertext.
After decryption, the App takes the first 12 characters as the device MAC. If
the firmware returns the placeholder string, the App shows
`Failed to process device data` before any backend bind request is sent.

Flash after regeneration:

```bash
cd projects/StackChan/firmware
source /Users/tianhaoxi/esp/esp-idf-v5.5.4/export.sh
idf.py build
idf.py -p /dev/cu.usbmodem101 flash
```

Device-side BLE advertising does not start at boot. Enter the setup flow until
the screen says `Look for me in the app to start setup.`; that state calls
`startAppConfigServer()` and advertises service UUID
`e2e5e5ff-1234-5678-1234-56789abcdef0`.

## iOS Device Signing

Keep the official iOS signing defaults in source control and use a local
override for real-device deployment. The StackChan app branch parameterizes the
Runner target with:

```text
STACKCHAN_IOS_DEVELOPMENT_TEAM
STACKCHAN_IOS_BUNDLE_IDENTIFIER
STACKCHAN_IOS_DISPLAY_NAME
```

`Runner/Info.plist` keeps `CFBundleIdentifier` as
`$(PRODUCT_BUNDLE_IDENTIFIER)` so the local override reaches the built app
bundle. It also reads `CFBundleDisplayName` from
`$(STACKCHAN_IOS_DISPLAY_NAME)` so the local build can be visually separated
from an official app already installed on the same phone.

The tracked default file is
`app/ios/Flutter/StackChanSigning.xcconfig`, which keeps the official
`NG678HLKHZ` / `com.m5stack.StackChan` values. For this local workstation,
create the ignored file `app/ios/Flutter/Signing.local.xcconfig`:

```text
STACKCHAN_IOS_DEVELOPMENT_TEAM=77NLS6U772
STACKCHAN_IOS_BUNDLE_IDENTIFIER=com.tianhaoxi.stackchan
STACKCHAN_IOS_DISPLAY_NAME=StackChan Dev
```

Verify the resolved settings before installing to a phone:

```bash
cd .worktrees/StackChan-server-app/app
xcodebuild -workspace ios/Runner.xcworkspace \
  -scheme Runner \
  -configuration Debug \
  -showBuildSettings | rg "DEVELOPMENT_TEAM|PRODUCT_BUNDLE_IDENTIFIER|STACKCHAN_IOS"
```

Install through the root Flutter wrapper so the current self-hosted server and
RSA dart-define values are injected without printing secrets:

```bash
scripts/stackchan_app_flutter.py --host 162.211.181.150 --tls false build-ios-release
xcrun devicectl device install app \
  --device 00008150-000C18EE0A87801C \
  .worktrees/StackChan-server-app/app/build/ios/iphoneos/Runner.app
xcrun devicectl device process launch \
  --device 00008150-000C18EE0A87801C \
  com.tianhaoxi.stackchan \
  --terminate-existing
```

Use `xcrun devicectl list devices` if the device identifier changes. The local
iPhone may also appear with a CoreDevice identifier such as
`5555F2DC-40D5-589B-9A59-F9EE7A21EAD4`; either identifier can be used when
`devicectl` accepts it.

As of 2026-07-01, the signed release path is the verified path on the local
machine:

- Toolchain: Flutter 3.44.4 stable, Xcode 26.6, iPhone OS 26.5.1.
- Debug `flutter run`/debug install can white-screen and exit before Dart UI is
  usable. Crash logs showed `CameraPlugin.register(with:)` in
  `camera_avfoundation` via `swift_getObjectType`.
- The first startup crash seen in the default debug app was
  `VSyncClient initWithTaskRunner` from `FlutterViewController.viewDidLoad`; an
  experimental explicit-engine Runner change moved the crash but was not needed
  for release, so it was discarded to keep the official app patch small.
- The full app is not currently a reliable Apple Silicon iOS 26 simulator smoke:
  the dependency set reports missing arm64 simulator support for Google MLKit,
  MLImage, MLKitVision, MLKitFaceDetection, DartCvIOS, OpenCV, and related pods.

Verify that the installed release app remains alive:

```bash
xcrun devicectl device info processes \
  --device 00008150-000C18EE0A87801C | rg "stackchan|Runner|com\\.tianhaoxi"
xcrun devicectl device info files \
  --device 00008150-000C18EE0A87801C \
  --domain-type systemCrashLogs | rg "Runner-" | tail
```

## Research Notes

Sources checked on 2026-06-30:

- Official product docs: <https://docs.m5stack.com/en/StackChan>
- Official source mirror: <https://github.com/m5stack/StackChan>
- Official product/community positioning: <https://github.com/m5stack/StackChan-BSP>
- Community gateway/self-hosting discussion:
  <https://www.reddit.com/r/StackChan/comments/1ta11ak/new_firmware_131/>
- Community MCP/App workflow discussion:
  <https://www.reddit.com/r/M5Stack/comments/1tbyj0e/ive_just_got_my_stackchan_lately_are_there_any/>
- Community fully self-hosted alternative for comparison:
  <https://github.com/BrettKinny/dotty-stackchan>

Practical conclusions:

- The official product path is firmware + StackChan World app + StackChan server
  behavior, including AI Agent, remote video, remote Avatar, and OTA. We should
  preserve that chain.
- Community experience points to gateway/server self-hosting as the useful
  extension path. Phone-to-device direct WebSocket should remain diagnostic or
  experimental, not the maintained architecture.
- Fully self-hosted community forks are valuable references, but they replace
  more of the official stack. Use them as design input only after the official
  server/app path is stable.
- The public GitHub repository can lag behind internal development and app
  releases. Before rebasing or deploying, always fetch `upstream/main` and read
  recent upstream commits instead of assuming older local conclusions still hold.

## Server Deployment Shape

Use official server code with a thin ops wrapper instead of rewriting official
deployment manifests.

Recommended single-host layout:

```text
/opt/stackchan-server/
  current/                  # current release or compose checkout
  shared/
    config.yaml             # real production config, not in git
    .env                    # compose/runtime env, not in git
  data/
    mysql/                  # if using local containerized MySQL
```

Preferred public surface:

- `https://stackchan.example.com/` for HTTP APIs and admin UI.
- `wss://stackchan.example.com/stackChan/ws` for app/device WebSocket.
- Reverse proxy terminates TLS and forwards to `127.0.0.1:12800`.

The worktree branch contains additive ops assets under `server/ops/`:

- Dockerfile for the official Go server.
- Compose topology for server + MySQL.
- systemd service example for an existing Linux host.
- nginx and Caddy reverse proxy examples.
- Placeholder config template.

Current cloud inventory showed an existing Debian host with nginx, MySQL, and
systemd already available. Docker and Caddy were not installed. The existing
MySQL root socket was not available to the deployment user, so the default
bring-up path is Docker Compose with an isolated StackChan MySQL container. This
avoids changing permissions or passwords on the server's existing MySQL service.

## App Login Chain

The StackChan app login is not a local-only username/password check. The
self-hosted server forwards `/stackChan/v2/user/login` to the configured
`m5stack.loginUrl`; after a successful remote response, the server stores the
user locally and issues its own JWT for app APIs.

Required non-secret login config:

```yaml
m5stack:
  loginUrl: "https://forum.m5stack.com/api/v3/utilities/login"
  registrationUrl: ""
  registrationToken: ""
  issuer: "stackchan-self-hosted"
  audience: "stackchan-app"
```

`registrationUrl` and `registrationToken` are still placeholders unless we add
a real account-registration path. Existing M5Stack/forum accounts should use the
login path above. For new accounts, use the official registration page:

```text
https://community.m5stack.com/register
```

The self-hosted server intentionally returns a clear validation message when app
registration is attempted without `registrationUrl` and `registrationToken`
configured. This avoids the previous generic `Business Validation Failed`
response and keeps registration credentials out of the self-hosted stack until a
real M5Stack registration integration is available.

Failure mode seen on 2026-07-01: if the `m5stack` block is missing, `/api.json`
and `/stackChan/apps` still look healthy, but login returns a confusing
`{"code":300,"message":", ","data":null}` because the server posts to an empty
remote login URL. After adding `m5stack.loginUrl`, a probe with fake credentials
returns the expected M5Stack/NodeBB error:

```json
{"code":300,"message":"[[error:invalid-login-credentials]]","data":null}
```

That response means the self-hosted server is correctly reaching M5Stack auth;
use a real M5Stack account in the phone app for the full login test.

## Cloud Preflight

Run the non-secret local checks:

```bash
scripts/stackchan_cloud_preflight.py \
  --stackchan-dir .worktrees/StackChan-server-app
```

After generating local StackChan secrets, include the generated env fragments:

```bash
scripts/stackchan_cloud_preflight.py \
  --stackchan-dir .worktrees/StackChan-server-app \
  --env-file .env \
  --env-file workspace/stackchan-secrets/server/compose.env \
  --env-file workspace/stackchan-secrets/server/app-dart-defines.env
```

Run remote inventory after local `.env` has `SERVER_IP` and
`SERVER_USERNAME`:

```bash
scripts/stackchan_cloud_preflight.py \
  --stackchan-dir .worktrees/StackChan-server-app \
  --remote
```

The script prints whether values are present, not the values themselves. If
`SERVER_SSH_KEY` is configured, it uses key-based SSH. If only
`SERVER_PASSWORD` is configured, it uses local `expect` without printing the
password.

## Bring-Up Plan

1. Keep avatar work isolated in its existing branch/thread.
2. Use `.worktrees/StackChan-server-app` for server/app changes from
   `upstream/main`.
3. Run local preflight and fix local tool gaps.
4. Generate RSA keys and JWT/admin/database secrets into local-only storage.
5. Create cloud server directories and install Docker/Compose if missing.
6. Deploy StackChan Server staging with the isolated Compose stack.
7. Add nginx TLS/public routing after the local `127.0.0.1:12800` service is
   healthy.
8. Verify:
   - `https://<host>/api.json`
   - `https://<host>/file/music/stackchan_music.mp3`
   - `wss://<host>/stackChan/ws`
9. Build the app with `--dart-define` values and verify login, binding, and
   WebSocket device online/offline status.
10. Update firmware server settings only after the app/server path is green.
11. Add custom MCP/API integration behind the server path, not inside the first
    firmware bring-up.

Deploy the Compose staging stack:

```bash
scripts/stackchan_deploy_compose.py
```

The script uploads only the StackChan `server/` source, generated local-only
`config.compose.yaml`, and generated Compose env values. The server binds
StackChan to `127.0.0.1:12800`; nginx/public routing is a separate step.

Configure the nginx public route:

```bash
scripts/stackchan_configure_nginx.py
```

On the current staging server this exposes:

- `http://162.211.181.150/api.json`
- `http://162.211.181.150/file/music/stackchan_music.mp3`
- `http://162.211.181.150/stackChan/ws`

Use these App build settings for the current HTTP staging endpoint:

```bash
--dart-define=STACKCHAN_SERVER_HOST=162.211.181.150
--dart-define=STACKCHAN_SERVER_TLS=false
```

Keep the RSA dart-define values in
`workspace/stackchan-secrets/server/app-dart-defines.env`; do not paste them
into source files.

## Deployment Notes From First Bring-Up

- The existing server MySQL root socket was not usable, so the staging stack
  uses an isolated MySQL container instead of modifying the host MySQL service.
- The official server `go.sum` did not contain all module checksums required for
  container build. The Dockerfile runs `go mod tidy` inside the build layer
  rather than writing generated dependency churn back into the repo.
- GoFrame did not read the config while it was mounted as `0600 root:root`.
  The image now uses fixed UID/GID `10001`, and deployment chowns the mounted
  config to that ID with mode `0400`.
- The upstream checkout did not include `web/management`, while the server calls
  `SetServerRoot("web/management")`. The image creates an empty directory so
  API and WebSocket routes can start; if upstream later ships admin assets, copy
  them into that path.

## Current Staging State

As of 2026-06-30, the cloud staging path is running with the official
app/server/device architecture preserved:

```text
StackChan App build-time config
  -> nginx on the cloud server
  -> Docker Compose StackChan Server on 127.0.0.1:12800
  -> isolated MySQL 8.4 container
```

Public staging endpoint:

- `http://162.211.181.150/api.json`
- `http://162.211.181.150/file/music/stackchan_music.mp3`
- `http://162.211.181.150/stackChan/ws`

Latest smoke result:

- `/api.json`: HTTP 200.
- `/file/music/stackchan_music.mp3`: HTTP 200.
- `/stackChan/ws` without auth: HTTP 401, expected because the real app/device
  session must authenticate.
- `/stackChan/v2/user/login` with fake credentials: HTTP 200 with
  `code=300` and `[[error:invalid-login-credentials]]`, expected because this
  proves the request reached the configured M5Stack login endpoint.
- Firmware/App add-device BLE handshake on 2026-07-01: passed. The self-built
  firmware returned `notifyState` type `4`, and local decryption with
  `stackchan_blue_private.pem` produced `441BF6DF62F8|<timestamp>`.

Local environment state:

- Flutter 3.44.4 is installed and available.
- Local Go is still older than `server/go.mod` requires; server tests should run
  in the remote/container Go toolchain or after upgrading local Go.
- Local Docker CLI exists, but the local daemon is not running. The staging
  deploy path uses the remote Docker daemon.

## Verification Commands

Root workspace:

```bash
python3 -m py_compile \
  scripts/stackchan_cloud_preflight.py \
  scripts/stackchan_configure_nginx.py \
  scripts/stackchan_deploy_compose.py \
  scripts/stackchan_generate_firmware_secrets.py \
  scripts/stackchan_prepare_local_secrets.py

git diff --check
```

StackChan app worktree:

```bash
cd .worktrees/StackChan-server-app/app
flutter analyze --no-fatal-infos --no-fatal-warnings
flutter test --reporter compact
```

Use the root wrapper when the App should be built or tested against the current
cloud staging endpoint without exposing RSA values on the command line:

```bash
scripts/stackchan_app_flutter.py --host 162.211.181.150 --tls false pub-get
scripts/stackchan_app_flutter.py --host 162.211.181.150 --tls false test -- --reporter compact
scripts/stackchan_app_flutter.py --host 162.211.181.150 --tls false build-ios-release
```

The wrapper reads `workspace/stackchan-secrets/server/app-dart-defines.env`,
writes an ignored `app-dart-defines.generated.env`, and passes it to Flutter via
`--dart-define-from-file`.

The official app currently has existing analyzer warnings/infos. Treat a
non-fatal analyzer pass as the current gate for this branch, and do not broaden
the branch into a full official-app lint cleanup unless we intentionally open a
separate cleanup phase.

Flutter 3.44 enables Swift Package Manager integration by default. The current
StackChan dependency set fails iOS build during SwiftPM generation for
`opus_codec_ios`, so the app branch disables SwiftPM at the project level and
continues using CocoaPods. This follows Flutter's documented single-project
escape hatch and should be revisited when upstream dependencies support SwiftPM
cleanly.

iOS build also requires CocoaPods 1.16.2 or newer with Xcode 26 project files.
Older CocoaPods/xcodeproj versions fail on `PBXFileSystemSynchronizedRootGroup`.
The App branch removes the hardcoded git mirror source from `ios/Podfile` so
CocoaPods can use its default CDN instead of cloning a full Specs repository.

The obsolete generated counter widget test was replaced with logic tests for:

- backend URL construction;
- TLS/WSS switching;
- reverse-proxy path-prefix normalization;
- empty-key fail-closed behavior when build-time RSA values are missing.

Cloud staging:

```bash
scripts/stackchan_cloud_preflight.py \
  --stackchan-dir .worktrees/StackChan-server-app \
  --env-file .env \
  --env-file workspace/stackchan-secrets/server/compose.env \
  --env-file workspace/stackchan-secrets/server/app-dart-defines.env \
  --remote

curl -sS -o /tmp/stackchan-api.json -w '%{http_code}' \
  http://162.211.181.150/api.json

curl -sS -o /tmp/stackchan-music.mp3 -w '%{http_code}' \
  http://162.211.181.150/file/music/stackchan_music.mp3

curl -sS -o /tmp/stackchan-ws.txt -w '%{http_code}' \
  http://162.211.181.150/stackChan/ws
```

## Next Steps

1. Point a local app build at the staging endpoint using
   `STACKCHAN_SERVER_HOST=162.211.181.150` and `STACKCHAN_SERVER_TLS=false`.
2. Use the generated local-only RSA dart-define values from
   `workspace/stackchan-secrets/server/app-dart-defines.env`; do not copy them
   into source files.
3. On the device, enter `Look for me in the app to start setup.` before adding
   the device. BLE advertising only starts in that setup state.
4. Verify the phone app can load the server, login/bind as expected, and observe
   authenticated WebSocket status.
5. Add a domain and TLS certificate before treating the staging server as
   production. After TLS is enabled, switch App builds to
   `STACKCHAN_SERVER_TLS=true` and verify `wss://`.
6. Only after app/server/device auth is green, add custom API or MCP integration
   behind the server path. Keep firmware reflashing out of this phase unless a
   device-local capability truly requires firmware changes.

## Upstream Sync Checklist

Before changing app/server code:

```bash
git -C projects/StackChan fetch upstream
git -C .worktrees/StackChan-server-app status --short --branch
git -C .worktrees/StackChan-server-app log --oneline --left-right --cherry-pick HEAD...upstream/main
git -C .worktrees/StackChan-server-app diff --name-status upstream/main...HEAD
```

After upstream updates:

```bash
git -C .worktrees/StackChan-server-app rebase upstream/main
scripts/stackchan_cloud_preflight.py --stackchan-dir .worktrees/StackChan-server-app
```

Keep commits small:

- One commit for app endpoint/key injection.
- One commit for server ops templates.
- One commit for root docs/scripts.

If an official file must be edited, keep the edit narrow and document why the
extension point was needed.

## Known Local Gaps

At the time this runbook was added:

- Local Go was older than the version required by `server/go.mod`.
- Flutter was not available in local `PATH`.
- Docker CLI existed, but the Docker daemon was not running.

These are environment gaps, not architecture blockers. The preflight script
surfaces them so they are fixed before deployment.
