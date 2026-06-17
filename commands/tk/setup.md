---
description: Bootstrap the Testing-Kit environment (venv, dependencies, Playwright MCP check, config files)
argument-hint: "[--force]   # --force recreates the venv from scratch"
allowed-tools: Bash, Read, Edit
---

# Testing-Kit — Environment Setup

Bootstrap the user's project so the pipeline can run. Arguments: `$ARGUMENTS`

The Testing-Kit framework is installed as a plugin; its files live at
`${CLAUDE_PLUGIN_ROOT}`. This command sets up a per-project Python venv, installs
the bundled package into it, verifies the Playwright MCP server, and seeds config.
Run on Windows (PowerShell). Skip satisfied steps unless `--force` was passed
(then recreate `.venv` first).

1. **Virtual env** — if `.venv\` does not exist (or `--force`):

       py -3.13 -m venv .venv

2. **Install the bundled framework** into the project venv from the plugin root.
   In PowerShell the plugin root is `$env:CLAUDE_PLUGIN_ROOT`:

       .venv\Scripts\python -m pip install --upgrade pip
       .venv\Scripts\python -m pip install "$env:CLAUDE_PLUGIN_ROOT"

   This installs `tcformat`/`toolkit`, the bundled template+strategy xlsx, and the
   `tk-report` / `tk-strategy` console scripts into `.venv`.

3. **Playwright MCP server** — Stage 2 (`/tk:run`) drives the live browser through
   the Playwright MCP server (no Python Playwright dependency). Verify it is
   connected:

       claude mcp list

   Look for a `playwright` entry reporting `Connected`. If missing/not connected,
   tell the user to install it (plugin/user-scoped, not in this repo) and that
   Stage 2 cannot run until it is — do **not** install or reconfigure it here.

4. **Project directories + config** — create the per-project working dirs if absent
   and seed config from the bundled examples (never overwrite existing config):

       mkdir config, testcases, evidence, reports -Force | Out-Null
       if (!(Test-Path config\config.yaml))  { copy "$env:CLAUDE_PLUGIN_ROOT\config\config.example.yaml"  config\config.yaml }
       if (!(Test-Path config\users.yaml))   { copy "$env:CLAUDE_PLUGIN_ROOT\config\users.example.yaml"   config\users.yaml }
       if (!(Test-Path config\devices.yaml)) { copy "$env:CLAUDE_PLUGIN_ROOT\config\devices.example.yaml" config\devices.yaml }

5. After copying, open `config\config.yaml` and tell the user to set `base_url`
   (and any thresholds/`template_path`/`strategy_path` overrides). Report which
   files were created vs. already present.

Finish with a one-line status: env ready / what still needs the user's input
(e.g. editing `base_url`).
