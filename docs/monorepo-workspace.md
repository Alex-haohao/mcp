# Monorepo Workspace

This repository is now the workspace root for independent AI projects.

## Layout

```text
.
├── mcp_bridge/                 # xiaozhi-mcp service code
├── scripts/                    # workspace and service scripts
├── docs/                       # workspace and service docs
├── workspace/projects.json     # project inventory
└── projects/
    └── airi/                   # AIRI git submodule
```

The current MCP service intentionally remains at the repository root to avoid breaking the already deployed `/opt/xiaozhi-mcp` service and its deployment script. New external projects should go under `projects/<name>`.

## Project Ownership

- Root repository: owns workspace docs, service deployment scripts, and the `xiaozhi-mcp` bridge.
- `projects/airi`: owns AIRI source code and upstream history as a Git submodule.

Using submodules keeps large upstream projects independent while still allowing this root repository to pin known-good revisions.

## Common Commands

Clone with submodules:

```bash
git clone --recurse-submodules <repo-url>
```

Initialize submodules after a normal clone:

```bash
git submodule update --init --recursive
```

Update AIRI to the latest upstream main:

```bash
git -C projects/airi fetch origin
git -C projects/airi checkout main
git -C projects/airi pull --ff-only
git add projects/airi
```

Check workspace state:

```bash
git status
git submodule status --recursive
git -C projects/airi status
```

## Adding Another AI Project

Prefer a submodule when the project has its own upstream, release cadence, issue tracker, or dependency graph:

```bash
git submodule add <repo-url> projects/<name>
```

Then add an entry to `workspace/projects.json` and document any project-specific build/deploy flow under `docs/`.

Use plain directories only for code owned by this workspace.
