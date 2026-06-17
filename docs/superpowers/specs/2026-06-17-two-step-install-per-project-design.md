# Two-step install & per-project usage — design

- **Date:** 2026-06-17
- **Status:** Approved (pending user spec review)
- **Topic:** Make Testing-Kit installable once (shared plugin code) and usable per project (own config + data), closing the isolation gaps. Keep the current architecture.

## Problem

`D:\Testing-kit` doubles as both the **plugin source/dev repo** and a **usage sandbox**: plugin code (`commands/`, `skills/`, `tcformat/`, `toolkit/`) and per-run artifacts (`config/`, `testcases/`, `evidence/`, `reports/`, `.venv/`) sit in the same folder. This creates the impression that config is "baked into the plugin" and cannot be split per project.

Technically, config is **already per-project** by design (see table below). The real issues are operational: there is no clean, repeatable two-step workflow, and a few isolation gaps let artifacts land in the wrong place or stay inconsistent.

## Current reality (kept as-is)

| Component | Location | Scope |
|---|---|---|
| Plugin code (`commands/`, `skills/`, `tcformat/`, `toolkit/`) | `${CLAUDE_PLUGIN_ROOT}` (install cache) | **Shared** across projects |
| `config.yaml`, `users.yaml` | project CWD (copied by `/tk:setup`) | **Per project** |
| `testcases/`, `evidence/`, `reports/` | project CWD (relative paths) | **Per project** |
| strategy.xlsx + template.xlsx | bundled package data (`tcformat/data/`), overridable via `config.yaml` | shared, override per project |

Confirmed during survey:
- `config.yaml` / `users.yaml` are gitignored; only `*.example.yaml` + `devices.yaml` are tracked.
- No Python code reads `devices.yaml`; it is reference-only material for the AI (skills read `config.yaml` / `users.yaml`).
- `config.yaml` is consumed by Python only via optional `--config` override flags (`report_cli.py`, `strategy.py`) for `template_path` / `strategy_path`.

## Decisions (locked)

- **Python install model:** keep a **per-project `.venv`** (current `/tk:setup` behavior). Absolute isolation, version pinned per project. *(Rejected: shared pipx/venv; run-from-plugin.)*
- **Per-project layout:** keep working dirs **scattered at the project root** (`config/`, `testcases/`, `evidence/`, `reports/`). *(Rejected: consolidated `qa/` folder; fully separate test dir.)*
- **`devices.yaml`:** rename tracked file to **`config/devices.example.yaml`** and **copy it in `/tk:setup`** to `config/devices.yaml`, consistent with `config.yaml` / `users.yaml`.
- **Source-repo guard:** `/tk:setup` performs a **hard abort** if run inside the plugin's own source repo.

## Design

### Step 1 — Install the plugin (once per machine/user)

Two channels:

- **Team / shared (for distribution):** push the repo to its remote, then
  - `/plugin marketplace add https://github.com/hungnv5-rikkeisoft/testing-kit.git`
  - `/plugin install testing-kit`
- **Local (plugin author, offline):**
  - `/plugin marketplace add D:\Testing-kit`
  - `/plugin install testing-kit`

After install, plugin code lives in the Claude plugin cache (`${CLAUDE_PLUGIN_ROOT}`) and is shared by every project. Nothing project-specific is stored there.

### Step 2 — Per project (every app under test)

1. Open Claude Code with **CWD = the target project**.
2. `/tk:setup` — creates per-project `.venv`, pip-installs the bundled framework from `${CLAUDE_PLUGIN_ROOT}`, seeds `config/`, `testcases/`, `evidence/`, `reports/` from bundled examples.
3. Edit `config/config.yaml` (`base_url`, thresholds, optional `template_path` / `strategy_path`) and `config/users.yaml`.
4. Run the pipeline: `/tk:testcases` → `/tk:run` → `/tk:report` (or `/tk:pipeline`).

### Hardening fixes

1. **CWD safety checkpoint (hard abort).**
   `/tk:setup` resolves the working directory, prints it and the list of dirs/files it will create, and **aborts** if it detects it is running inside the plugin's own source repo. Detection signal: presence of the plugin manifest at `./.claude-plugin/plugin.json` with `"name": "testing-kit"` (i.e. CWD is the source checkout, not a consumer project). On abort, instruct the user to `cd` into their actual project. The run/report commands keep using project-relative paths; the guard lives in setup where scaffolding happens.

2. **`devices.yaml` consistency.**
   - Rename the tracked `config/devices.yaml` → `config/devices.example.yaml`.
   - In `/tk:setup` step 4, add: `if (!(Test-Path config\devices.yaml)) { copy "$env:CLAUDE_PLUGIN_ROOT\config\devices.example.yaml" config\devices.yaml }`.
   - Add `config/devices.yaml` to `.gitignore` (alongside `config/config.yaml`, `config/users.yaml`).

3. **Dev-repo vs usage separation (documented + enforced).**
   - README states `D:\Testing-kit` is the plugin **source/dev** repo, not a place to run real project tests; its `config/`/`testcases/`/`evidence/` are dev fixtures.
   - The guard in fix #1 enforces this for `/tk:setup`.

4. **Docs.**
   - Rewrite README "Install" and add a "Two-step workflow" section reflecting Steps 1 & 2.
   - Include the shared-vs-per-project table to make the boundary explicit.

## Out of scope (YAGNI — explicitly rejected)

- Shared/global venv (pipx or one shared venv).
- Consolidated `qa/` working folder, or a fully separate test directory.
- Changing the path-resolution mechanism.

## Acceptance criteria

1. Install the plugin from a local path.
2. In a **fresh empty directory**, run `/tk:setup`: `.venv` + `config/` (incl. `devices.yaml`) + `testcases/` + `evidence/` + `reports/` are created **there**; the plugin cache is untouched.
3. Running `/tk:setup` **inside `D:\Testing-kit`** aborts with a clear "you are in the plugin source repo, cd into your project" message.
4. Run one screen end-to-end (Stage 1 → 2 → 3); `reports/test_report.xlsx` lands in that project dir with the exit-criteria gate enforced.
5. Repeat steps 2 & 4 in a **second directory** to prove isolation — neither project's artifacts leak into the other or into the plugin cache.
6. README documents the two-step workflow and the shared-vs-per-project boundary.

## Affected files

- `commands/tk/setup.md` — add CWD guard (abort) + `devices.yaml` copy.
- `config/devices.yaml` → rename to `config/devices.example.yaml`.
- `.gitignore` — add `config/devices.yaml`.
- `README.md` — Install + Two-step workflow + boundary table.
