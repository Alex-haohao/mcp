# Server Deployment Runbook

This project is deployed as a long-running systemd service on the cloud server.

## Production Layout

- App root: `/opt/xiaozhi-mcp`
- Releases: `/opt/xiaozhi-mcp/releases/<timestamp>-<git-sha>`
- Current release: `/opt/xiaozhi-mcp/current`
- Runtime env: `/opt/xiaozhi-mcp/shared/.env`
- Service user: `xiaozhi-mcp`
- Service state: `/var/lib/xiaozhi-mcp`
- uv cache: `/var/cache/xiaozhi-mcp/uv`
- uv-managed Python: `/var/cache/xiaozhi-mcp/python`
- Log file: `/var/log/xiaozhi-mcp/bridge.log`
- systemd unit: `/etc/systemd/system/xiaozhi-mcp.service`

The release directory contains code and its Python virtual environment. The virtual environment uses a uv-managed Python under `/var/cache/xiaozhi-mcp/python`, not the system Python. The shared `.env` is kept outside releases so code updates do not overwrite credentials.

## Local Prerequisites

`.env` must contain deployment connection values:

```dotenv
SERVER_IP=<server-ip>
SERVER_USERNAME=root
SERVER_PORT=22
```

SSH key authentication should be configured before normal deployments:

```bash
ssh-copy-id -i ~/.ssh/id_rsa.pub root@$SERVER_IP
```

The deployment script uploads only runtime keys. It does not upload `SERVER_*` values.

Required runtime values:

```dotenv
MCP_ENDPOINT=<xiaozhi-mcp-endpoint>
VOLCENGINE_SEARCH_API_KEY=<volcengine-web-search-key>
```

Optional runtime value:

```dotenv
XIAOHONGSHU_MCP_URL=http://127.0.0.1:18060/mcp
```

## Deploy

Run from the repository root:

```bash
.venv/bin/python scripts/deploy_server.py
```

The script performs local unit tests, local preflight, rsyncs the code to a new release, creates a Python 3.12 virtual environment with `uv`, installs dependencies, updates the `current` symlink, reloads systemd, restarts the service, and prints recent logs.

## Check Production

```bash
ssh root@$SERVER_IP 'systemctl status xiaozhi-mcp --no-pager'
ssh root@$SERVER_IP 'tail -n 100 /var/log/xiaozhi-mcp/bridge.log'
```

Expected enabled servers with the current default `.env`:

- `volcengine-web-search`
- `weibo`

`xiaohongshu-mcp` remains disabled until `XIAOHONGSHU_MCP_URL` is configured and the Xiaohongshu MCP service is running.

## Rollback

List releases:

```bash
ssh root@$SERVER_IP 'ls -1 /opt/xiaozhi-mcp/releases'
```

Switch to a known-good release:

```bash
ssh root@$SERVER_IP 'ln -sfn releases/<release-name> /opt/xiaozhi-mcp/current && systemctl restart xiaozhi-mcp'
```

## Xiaohongshu Phase

Run Xiaohongshu MCP as a separate local service on the server, then set:

```dotenv
XIAOHONGSHU_MCP_URL=http://127.0.0.1:18060/mcp
```

Keep login and cookie management admin-only. The bridge config currently exposes only read-oriented tools to XiaoZhi and blocks write tools such as publishing, commenting, liking, and favoriting.
