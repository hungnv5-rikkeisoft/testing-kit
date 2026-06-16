---
description: Bootstrap the Testing-Kit environment (venv, dependencies, Playwright browsers, config files)
argument-hint: "[--force]   # --force recreates the venv from scratch"
allowed-tools: Bash, Read, Edit
---

# Testing-Kit — Environment Setup

Bootstrap this project so the pipeline can run. Arguments: `$ARGUMENTS`

Do the following on Windows (PowerShell). Skip steps that are already satisfied
unless `--force` was passed, in which case recreate `.venv` first.

1. **Virtual env** — if `.venv\` does not exist (or `--force`):

       py -3.13 -m venv .venv

2. **Dependencies**:

       .venv\Scripts\python -m pip install -r requirements.txt

3. **Playwright browsers** (chromium for desktop, webkit for the iPad subset):

       .venv\Scripts\python -m playwright install chromium webkit

4. **Playwright MCP server** — Stage 2 (`/tk:run`) drives the live browser
   through the Playwright MCP server, not the Python package above. Verify it
   is connected:

       claude mcp list

   Look for a `playwright` entry reporting `✔ Connected`. If it is missing or
   not connected, tell the user to install it (it is plugin/user-scoped, not in
   this repo) and that Stage 2 cannot run until it is — do **not** attempt to
   install or reconfigure it from here.

5. **Config files** — copy the examples only if the real files are missing
   (never overwrite an existing `config\config.yaml` / `config\users.yaml`):

       copy config\config.example.yaml config\config.yaml
       copy config\users.example.yaml  config\users.yaml

6. After copying, open `config\config.yaml` and tell the user to set `base_url`
   (and any thresholds that differ from the strategy). Report which files were
   created vs. already present.

Finish with a one-line status: env ready / what still needs the user's input
(e.g. editing `base_url`).
