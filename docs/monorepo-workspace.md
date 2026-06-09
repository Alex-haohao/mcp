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

## Design Rules

- Keep independent AI projects under `projects/<name>` unless the code is owned by this root repository.
- Do not share dependency folders across unrelated projects. Each project keeps its own package manager, lockfile, build output, and release process.
- Root-level scripts should orchestrate repeatable workflows, not patch upstream project source files by default.
- If a generated file is needed only for a local build, keep it ignored or restore it after the build.
- Pin external projects through submodule commits so a working release can be reproduced later.
- Document every project-specific build or deployment path under `docs/` before relying on it operationally.

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

## Updating A Project Safely

Before updating a submodule:

1. Check the root repository is clean.
2. Update the submodule with a fast-forward pull.
3. Run that project's build or smoke test.
4. Commit only the submodule pointer and any required workspace docs or scripts.

For AIRI, the minimum smoke path is:

```bash
python scripts/airi_ios_testflight.py \
  --team-id KA4786U458 \
  --bundle-id com.tianhaoxi.airi.pocket \
  --skip-install \
  --skip-web-build \
  --unsigned-archive
```
