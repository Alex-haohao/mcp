# XiaoZhi MCP Bridge

This repository is also the local AI workspace root. Independent AI projects are tracked in `workspace/projects.json`, with external upstream projects placed under `projects/`.

Current workspace projects:

- `xiaozhi-mcp`: this root Python service.
- `airi`: AIRI upstream submodule at `projects/airi`.

Workspace docs:

- [docs/monorepo-workspace.md](docs/monorepo-workspace.md)
- [docs/airi-testflight-runbook.md](docs/airi-testflight-runbook.md)

Cloud-hosted MCP bridge for StackChan/XiaoZhi. The bridge connects to `MCP_ENDPOINT`, starts configured local or remote MCP servers, and pipes MCP traffic between XiaoZhi and those servers.

The current production target is Volcengine Web Search through the official Volcengine MCP server.

## Current Tooling

- `volcengine-web-search`: official Volcengine web-search MCP server, launched with `uvx`.
- `weibo`: Weibo MCP server from `qinyuanpei/mcp-server-weibo`, launched with pinned `mcp-server-weibo==1.1.0`.
- `xiaohongshu-mcp`: Xiaohongshu MCP HTTP service from `xpzouying/xiaohongshu-mcp`, enabled only when `XIAOHONGSHU_MCP_URL` is set and restricted to read-only tools.
- `remote-sse-server` / `remote-http-server`: disabled examples for remote MCP transports.

## Requirements

- Python 3.12 or 3.13.
- Project dependencies from `requirements.txt`.
- `uvx` available in `PATH` for the Volcengine official MCP server.
- `.env` containing the XiaoZhi endpoint and Volcengine search key.

Install Python dependencies:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

`requirements.txt` includes `uv`, so `uvx` is available when the virtual environment is active. If you prefer installing `uv` globally on the server, use:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Environment

Create `.env` locally or on the server. Start from `.env.example`:

```dotenv
MCP_ENDPOINT=<your_xiaozhi_mcp_endpoint>
VOLCENGINE_SEARCH_API_KEY=<your_volcengine_web_search_api_key>
XIAOHONGSHU_MCP_URL=
```

Keep Agent Plan model credentials separate from the web-search credential. The current bridge only needs `VOLCENGINE_SEARCH_API_KEY` for the search MCP server.

## Run

Start all enabled servers:

```bash
python mcp_pipe.py
```

Start only Volcengine search:

```bash
python mcp_pipe.py volcengine-web-search
```

If `VOLCENGINE_SEARCH_API_KEY` is not set, `volcengine-web-search` is skipped because `mcp_config.json` uses `enabledIfEnv`.

## Preflight

Run the local preflight before deployment:

```bash
.venv/bin/python scripts/preflight.py
```

It checks Python version, `MCP_ENDPOINT`, enabled MCP servers, and configured executables such as `uvx`. It does not call the Volcengine API.

After `VOLCENGINE_SEARCH_API_KEY` is configured, run the MCP smoke check:

```bash
.venv/bin/python scripts/smoke_volcengine_search.py
```

This starts the official Volcengine MCP server and lists its tools. It does not perform a search request.

To run one real search query after the key is configured:

```bash
.venv/bin/python scripts/query_volcengine_search.py "今日火山引擎 Agent Plan 联网搜索"
```

This consumes Volcengine web-search quota.

List tools for any configured server:

```bash
.venv/bin/python scripts/smoke_mcp_server.py weibo
.venv/bin/python scripts/smoke_mcp_server.py xiaohongshu-mcp
```

Call one MCP tool directly:

```bash
.venv/bin/python scripts/call_mcp_tool.py weibo get_trendings --arguments '{"limit":1}'
```

## Configuration

The bridge loads config from:

1. `MCP_CONFIG`
2. `MCP_CONFIG_PATH`
3. `./mcp_config.json`

Supported server transports:

- `stdio`: launches a local process.
- `sse`: proxies a remote SSE MCP server through `mcp_proxy`.
- `http` / `streamablehttp`: proxies a remote streamable HTTP MCP server through `mcp_proxy`.

Config values support `${ENV_VAR}` placeholders. Secrets should stay in `.env`, not in `mcp_config.json`.

Example:

```json
{
  "mcpServers": {
    "volcengine-web-search": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/volcengine/mcp-server@69d102e079ca74acedd5ec48eeeb24b148efb36e#subdirectory=server/mcp_server_askecho_search_infinity",
        "mcp-server-askecho-search-infinity"
      ],
      "env": {
        "ASK_ECHO_SEARCH_INFINITY_API_KEY": "${VOLCENGINE_SEARCH_API_KEY}"
      },
      "enabledIfEnv": "VOLCENGINE_SEARCH_API_KEY"
    }
  }
}
```

## Tests

Run logic tests:

```bash
python -m unittest discover -s tests
```

The tests cover config loading, environment interpolation, secret redaction, and MCP child-process command construction.

## Deployment

Use the deployment script for the cloud server:

```bash
.venv/bin/python scripts/deploy_server.py
```

It deploys into release directories under `/opt/xiaozhi-mcp`, keeps runtime secrets in `/opt/xiaozhi-mcp/shared/.env`, installs the systemd unit from `deploy/xiaozhi-mcp.service`, and restarts `xiaozhi-mcp`.

Server deployment operations are documented in:

[docs/server-deployment-runbook.md](docs/server-deployment-runbook.md)

A full architecture plan is documented in:

[docs/volcengine-agent-plan-mcp-architecture.md](docs/volcengine-agent-plan-mcp-architecture.md)

Social platform MCP integration details are documented in:

[docs/social-mcp-integration-plan.md](docs/social-mcp-integration-plan.md)

## AIRI iOS/TestFlight

AIRI is pinned as a submodule:

```bash
git submodule update --init --recursive
```

Build AIRI Stage Pocket for iOS/TestFlight:

```bash
python scripts/airi_ios_testflight.py \
  --team-id <APPLE_TEAM_ID> \
  --bundle-id <IOS_BUNDLE_ID> \
  --export-ipa \
  --upload-testflight
```

The current local build has verified the AIRI iOS simulator build and an unsigned device archive. A TestFlight upload still requires Xcode to have access to your Apple Developer account and App Store signing assets.
