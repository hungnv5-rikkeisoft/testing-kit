# Two-step Install & Per-project Usage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Testing-Kit cleanly installable once (shared plugin code) and usable per project (own config + data), by closing four isolation gaps without changing the kept architecture.

**Architecture:** Keep the current design (per-project `.venv`, working dirs scattered at the project root, CWD-relative path resolution). Add a hard CWD guard to `/tk:setup`, make `devices.yaml` per-project like the other config files, and document the two-step workflow. No Python source logic changes.

**Tech Stack:** Claude Code plugin (markdown commands + skills), PowerShell scaffolding in `/tk:setup`, Python package `tcformat`/`toolkit` (unchanged), Git.

## Global Constraints

- Source-repo guard signal (verbatim): CWD is the plugin source repo iff `./.claude-plugin/plugin.json` exists AND its `"name"` is `"testing-kit"`. On match, `/tk:setup` must **hard abort** before creating/copying anything.
- `/tk:setup` runs on Windows / PowerShell.
- Plugin root in PowerShell is `$env:CLAUDE_PLUGIN_ROOT`; never hard-code an absolute plugin path.
- Never overwrite an existing per-project config file (`config.yaml`, `users.yaml`, `devices.yaml`) — copy only when absent.
- Real install URL (verbatim): `https://github.com/hungnv5-rikkeisoft/testing-kit.git`.
- Spec of record: `docs/superpowers/specs/2026-06-17-two-step-install-per-project-design.md`.
- Git policy: do NOT run `git add`/`commit`/`push` without the user's explicit confirmation. Each task's "Commit" step is a checkpoint that REQUIRES asking first; plain commit message, no Claude attribution trailer.

## File Structure

- `config/devices.yaml` → renamed to `config/devices.example.yaml` (tracked template; the live `config/devices.yaml` becomes a per-project, gitignored copy).
- `.gitignore` — add `config/devices.yaml` next to the other live config files.
- `commands/tk/setup.md` — add the hard CWD guard (step 0) and the `devices.yaml` copy line (step 4).
- `README.md` — Install section + new "Two-step workflow" section + shared-vs-per-project boundary table + dev-repo note.

Tasks are ordered so each ends with an independently checkable deliverable. Because these are plugin command/docs files (not Python units), each task's "test" is a concrete manual verification, not pytest.

---

### Task 1: Make `devices.yaml` a per-project file

**Files:**
- Rename: `config/devices.yaml` → `config/devices.example.yaml`
- Modify: `.gitignore` (add `config/devices.yaml`)

**Interfaces:**
- Consumes: nothing.
- Produces: a tracked template `config/devices.example.yaml`; `config/devices.yaml` is now an ignored, per-project file. Task 2 (setup) copies the example → the live file.

- [ ] **Step 1: Rename the tracked template with git (preserves history)**

```bash
git mv config/devices.yaml config/devices.example.yaml
```

- [ ] **Step 2: Verify the rename**

Run: `git status --short config/`
Expected: shows `R  config/devices.yaml -> config/devices.example.yaml` (rename staged). `config/devices.example.yaml` exists on disk; `config/devices.yaml` no longer tracked.

- [ ] **Step 3: Add the live file to `.gitignore`**

In `.gitignore`, find the block:

```
# Real config (keep the *.example.yaml templates)
config/config.yaml
config/users.yaml
```

Replace it with:

```
# Real config (keep the *.example.yaml templates)
config/config.yaml
config/users.yaml
config/devices.yaml
```

- [ ] **Step 4: Verify the ignore rule**

Run: `git check-ignore config/devices.yaml`
Expected: prints `config/devices.yaml` (it is now ignored).

- [ ] **Step 5: Commit (ASK USER FIRST — git policy)**

```bash
git add config/devices.example.yaml .gitignore
git commit -m "refactor: make devices.yaml a per-project file (track devices.example.yaml)"
```

---

### Task 2: Seed `devices.yaml` in `/tk:setup`

**Files:**
- Modify: `commands/tk/setup.md` (step 4 — directory + config seeding block)

**Interfaces:**
- Consumes: `config/devices.example.yaml` from Task 1.
- Produces: `/tk:setup` copies `devices.example.yaml` → `config/devices.yaml` when absent, consistent with `config.yaml`/`users.yaml`.

- [ ] **Step 1: Add the devices copy line**

In `commands/tk/setup.md`, find the seeding block:

```
       mkdir config, testcases, evidence, reports -Force | Out-Null
       if (!(Test-Path config\config.yaml)) { copy "$env:CLAUDE_PLUGIN_ROOT\config\config.example.yaml" config\config.yaml }
       if (!(Test-Path config\users.yaml))  { copy "$env:CLAUDE_PLUGIN_ROOT\config\users.example.yaml"  config\users.yaml }
```

Replace it with:

```
       mkdir config, testcases, evidence, reports -Force | Out-Null
       if (!(Test-Path config\config.yaml))  { copy "$env:CLAUDE_PLUGIN_ROOT\config\config.example.yaml"  config\config.yaml }
       if (!(Test-Path config\users.yaml))   { copy "$env:CLAUDE_PLUGIN_ROOT\config\users.example.yaml"   config\users.yaml }
       if (!(Test-Path config\devices.yaml)) { copy "$env:CLAUDE_PLUGIN_ROOT\config\devices.example.yaml" config\devices.yaml }
```

- [ ] **Step 2: Verify the copy command in isolation**

Run (PowerShell, from any empty temp dir, with the env var pointing at the repo):
```powershell
$env:CLAUDE_PLUGIN_ROOT = "D:\Testing-kit"
mkdir config -Force | Out-Null
if (!(Test-Path config\devices.yaml)) { copy "$env:CLAUDE_PLUGIN_ROOT\config\devices.example.yaml" config\devices.yaml }
Test-Path config\devices.yaml
```
Expected: prints `True`; `config\devices.yaml` content matches `devices.example.yaml`.

- [ ] **Step 3: Commit (ASK USER FIRST — git policy)**

```bash
git add commands/tk/setup.md
git commit -m "feat(setup): seed per-project devices.yaml from devices.example.yaml"
```

---

### Task 3: Hard CWD guard in `/tk:setup`

**Files:**
- Modify: `commands/tk/setup.md` (insert a new guard step before step 1 "Virtual env")

**Interfaces:**
- Consumes: nothing.
- Produces: `/tk:setup` aborts (creates/copies nothing) when run inside the plugin source repo.

- [ ] **Step 1: Add the guard step**

In `commands/tk/setup.md`, immediately after the intro paragraph that ends "... Skip satisfied steps unless `--force` was passed (then recreate `.venv` first)." and before the numbered list, insert:

```markdown
0. **Source-repo guard (abort if wrong directory).** Before creating or copying
   anything, confirm the CWD is a consumer project, not the plugin's own source
   checkout. In PowerShell:

       $inSource = (Test-Path .\.claude-plugin\plugin.json) -and `
         ((Get-Content .\.claude-plugin\plugin.json -Raw | ConvertFrom-Json).name -eq 'testing-kit')
       if ($inSource) {
         Write-Host "ABORT: this is the Testing-Kit plugin source repo, not a project to test."
         Write-Host "cd into your actual project directory, then run /tk:setup again."
       }

   If `$inSource` is true, **STOP**: do not run any later step, do not create the
   venv or seed config. Report the abort to the user and tell them to `cd` into
   their target project. Otherwise continue to step 1.
```

Then renumber nothing else — the existing steps stay 1–5; the guard is step 0.

- [ ] **Step 2: Verify the guard logic detects the source repo**

Run (PowerShell, from `D:\Testing-kit`):
```powershell
(Test-Path .\.claude-plugin\plugin.json) -and ((Get-Content .\.claude-plugin\plugin.json -Raw | ConvertFrom-Json).name -eq 'testing-kit')
```
Expected: prints `True` (guard would abort here).

- [ ] **Step 3: Verify the guard passes in a normal project**

Run (PowerShell, from an empty temp dir without `.claude-plugin/`):
```powershell
(Test-Path .\.claude-plugin\plugin.json) -and ((Get-Content .\.claude-plugin\plugin.json -Raw | ConvertFrom-Json).name -eq 'testing-kit')
```
Expected: prints `False` (guard would continue to setup).

- [ ] **Step 4: Commit (ASK USER FIRST — git policy)**

```bash
git add commands/tk/setup.md
git commit -m "feat(setup): hard-abort when run inside the plugin source repo"
```

---

### Task 4: Document the two-step workflow in README

**Files:**
- Modify: `README.md` (Install section + new "Two-step workflow" + boundary table + dev-repo note)

**Interfaces:**
- Consumes: behavior from Tasks 1–3 (devices seeding, guard).
- Produces: user-facing documentation of Step 1 / Step 2 and the shared-vs-per-project boundary.

- [ ] **Step 1: Replace the Install section**

In `README.md`, replace the current `## Install (as a Claude Code plugin)` section (the numbered list ending at the `config/config.yaml` edit note, before `## Run a screen`) with:

```markdown
## Two-step workflow

Testing-Kit is **install-once, configure-per-project**. The plugin code is shared
across every project; each project keeps its own config and test data.

| Component | Location | Scope |
| --- | --- | --- |
| Plugin code (`commands/`, `skills/`, `tcformat/`, `toolkit/`) | plugin cache (`${CLAUDE_PLUGIN_ROOT}`) | shared across projects |
| `config.yaml`, `users.yaml`, `devices.yaml` | your project dir (seeded by `/tk:setup`) | per project |
| `testcases/`, `evidence/`, `reports/`, `.venv/` | your project dir | per project |
| strategy.xlsx + template.xlsx | bundled in the package, override via `config.yaml` | shared, override per project |

### Step 1 — Install the plugin (once)

Team / shared (from git):

    /plugin marketplace add https://github.com/hungnv5-rikkeisoft/testing-kit.git
    /plugin install testing-kit

Local (plugin author, offline) — point the marketplace at this repo's path:

    /plugin marketplace add D:\Testing-kit
    /plugin install testing-kit

Nothing project-specific is stored in the plugin cache.

### Step 2 — Per project

1.  Open Claude Code with the working directory set to your target project.
2.  Bootstrap the project:

        /tk:setup

    Creates a per-project `.venv`, installs the bundled framework, verifies the
    Playwright MCP server, and seeds `config/`, `testcases/`, `evidence/`,
    `reports/`. **Running `/tk:setup` inside this plugin's own source repo aborts**
    — it is for consumer projects only.
3.  Edit `config/config.yaml` (`base_url`, thresholds, optional
    `template_path`/`strategy_path`), `config/users.yaml`, and `config/devices.yaml`.
4.  Run the pipeline (next section).

> **Note:** `D:\Testing-kit` is the plugin's source/dev repo, not a place to run
> real tests. Its `config/`/`testcases/`/`evidence/` are dev fixtures.
```

- [ ] **Step 2: Verify README references are consistent**

Run: `grep -n "devices.yaml\|/tk:setup\|marketplace add\|source/dev repo" README.md`
Expected: the new section appears; `devices.yaml` is listed as per-project and mentioned in the Step 2 edit list; the dev-repo note is present.

- [ ] **Step 3: Verify the old single-step Install block is gone**

Run: `grep -n "## Install (as a Claude Code plugin)" README.md`
Expected: no matches (replaced by "## Two-step workflow").

- [ ] **Step 4: Commit (ASK USER FIRST — git policy)**

```bash
git add README.md
git commit -m "docs: document two-step install + per-project boundary"
```

---

### Task 5: End-to-end isolation verification

**Files:**
- None (verification only). No commit.

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: evidence that two projects stay isolated and the guard works.

- [ ] **Step 1: Guard aborts in the source repo**

Run `/tk:setup` from `D:\Testing-kit`.
Expected: it aborts with the "plugin source repo" message; no `.venv`/config created or modified by the command.

- [ ] **Step 2: Fresh project A scaffolds correctly**

In a new empty dir `D:\tmp\projA`, run `/tk:setup`.
Expected: `.venv\`, `config\config.yaml`, `config\users.yaml`, `config\devices.yaml`, `testcases\`, `evidence\`, `reports\` all created **in `projA`**; the plugin cache is unchanged.

- [ ] **Step 3: Second project B proves isolation**

In another empty dir `D:\tmp\projB`, run `/tk:setup`, set a different `base_url`.
Expected: `projB` gets its own `.venv`/config; editing `projB\config\config.yaml` does not affect `projA`.

- [ ] **Step 4: One screen end-to-end in project A**

In `projA`, run Stage 1 → 2 → 3 for one screen (or `/tk:pipeline`).
Expected: `projA\reports\test_report.xlsx` is produced with the exit-criteria gate enforced; nothing written into `projB` or the plugin cache.

---

## Self-Review

**Spec coverage:**
- Step 1 install (git + local) → Task 4 README. ✓
- Step 2 per-project flow → Task 4 README; behavior from Tasks 2–3. ✓
- Fix #1 CWD hard-abort guard → Task 3 + verified Task 5 Step 1. ✓
- Fix #2 devices.example.yaml rename + copy + gitignore → Tasks 1–2. ✓
- Fix #3 dev-repo vs usage separation → Task 3 guard + Task 4 note. ✓
- Fix #4 docs (two-step + boundary table) → Task 4. ✓
- Acceptance criteria 1–6 → Task 5 (+ Task 4 for #6). ✓

**Placeholder scan:** No TBD/TODO; every code/command step shows exact content. ✓

**Type/identifier consistency:** Guard signal (`./.claude-plugin/plugin.json`, `name == "testing-kit"`) identical in spec, Global Constraints, Task 3, and Task 5. File names (`devices.example.yaml`, `config/devices.yaml`) consistent across Tasks 1, 2, 4. ✓
