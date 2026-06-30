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
  scripts/stackchan_prepare_local_secrets.py

git diff --check
```

StackChan app worktree:

```bash
cd .worktrees/StackChan-server-app/app
flutter analyze --no-fatal-infos --no-fatal-warnings
flutter test --reporter compact
```

The official app currently has existing analyzer warnings/infos. Treat a
non-fatal analyzer pass as the current gate for this branch, and do not broaden
the branch into a full official-app lint cleanup unless we intentionally open a
separate cleanup phase.

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
3. Verify the phone app can load the server, login/bind as expected, and observe
   authenticated WebSocket status.
4. Add a domain and TLS certificate before treating the staging server as
   production. After TLS is enabled, switch App builds to
   `STACKCHAN_SERVER_TLS=true` and verify `wss://`.
5. Only after app/server/device auth is green, add custom API or MCP integration
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
