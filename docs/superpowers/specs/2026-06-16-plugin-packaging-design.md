# Design — Package Testing-Kit as an installable Claude Code plugin

- **Date:** 2026-06-16
- **Status:** Approved (brainstorming) → ready for implementation plan
- **Goal:** Turn the in-repo Testing-Kit pipeline (skills + `/tk:*` commands + Python backbone) into a reusable Claude Code **plugin**, distributed through a **git marketplace repo**, installable on any machine and usable against any project with only per-project config.

## Decisions (locked)

1. **Distribution:** git marketplace repo. The Testing-Kit repo *is* the marketplace and contains a single plugin at its root. Install via `/plugin marketplace add <git-url>` then `/plugin install testing-kit`.
2. **Python backbone delivery:** bundle the source (`tcformat/`, `toolkit/`) inside the plugin; `/tk:setup` creates a venv **in the user's working project** and `pip install`s the bundled package (`pip install "${CLAUDE_PLUGIN_ROOT}"`). All runtime calls go through that project venv.
3. **Template + strategy xlsx:** bundle as **defaults** inside the package (package-data). Code resolves them via `importlib.resources` by default; `config.yaml` may override with a project-specific path.
4. **Repo layout:** plugin-at-repo-root (least file movement). Dev-only artifacts (`tests/unit/`, `demo/`, `HANDOFF.md`) stay in the source repo but are not part of the runtime contract.

## What moves where

| Bucket | Items | Destination |
|---|---|---|
| Framework (reusable) | `tk/*` commands, `generate-testcases` + `run-testcases` skills, `tcformat/`, `toolkit/`, report CLI, default `template/` + `strategy/` xlsx | **Plugin** (shipped) |
| Per-project data | `config/`, `testcases/`, `evidence/`, `reports/`, app-under-test | **User's working repo** (created by `/tk:setup`; gitignored as today) |
| Dev/example only | `tests/unit/`, `demo/`, `HANDOFF.md` | Plugin **source repo** (not installed contract) |

## Target repo layout

```
testing-kit/                         ← git repo = marketplace AND plugin
  .claude-plugin/
    marketplace.json                 ← lists one plugin: "testing-kit"
    plugin.json                      ← plugin manifest (name, version, description)
  commands/tk/*.md                   ← moved from .claude/commands/tk/
  skills/
    generate-testcases/SKILL.md      ← moved from .claude/skills/
    run-testcases/SKILL.md
  tcformat/  toolkit/                ← python core (logic unchanged)
  template/  strategy/               ← bundled default xlsx (shipped as package-data)
  pyproject.toml                     ← NEW: packages tcformat+toolkit, package-data, console scripts
  requirements.txt
  demo/  tests/unit/  HANDOFF.md     ← dev/example only
  README.md
```

The only structural moves are `.claude/commands` → `commands/` and `.claude/skills` → `skills/` (Claude Code discovers plugin commands/skills at the plugin root, not under `.claude/`). Python source stays in place.

## Key technical change — path resolution

The thing that makes the framework portable. Today, skills/scripts hardcode repo-relative paths: `./.venv/Scripts/python.exe`, `template/Format test case + Test report.xlsx`, `strategy/strategy.xlsx`. After packaging:

1. **`pyproject.toml`**
   - Packages `tcformat` + `toolkit`.
   - Declares the bundled `template/*.xlsx` and `strategy/*.xlsx` as **package data** so they ship inside the installed distribution.
   - Exposes a **console script** for the report CLI (e.g. `tk-report` → `tcformat.report_cli:main`) replacing `python scripts/gen_report.py`.
   - Pins runtime deps (`pyyaml`, `openpyxl`, `Pillow`); `pytest`/`flask` are dev/example extras, not runtime.
2. **`/tk:setup`** (rewritten): create venv in the user's project, then `pip install "${CLAUDE_PLUGIN_ROOT}"`. That single install puts `tcformat`/`toolkit` + bundled xlsx + console scripts on the project's Python path. Still verifies the Playwright MCP server is connected (unchanged) and seeds `config/` from examples.
3. **Skills/commands** call `python -m tcformat.runlog …`, `python -m tcformat.strategy …` (or a helper), `tk-report …`. These work from any cwd because the package is installed, not path-referenced — no `${CLAUDE_PLUGIN_ROOT}` needed inside the per-testcase loops.
4. **Template/strategy default** resolved inside `tcformat` via `importlib.resources` (bundled package data). A new resolver (e.g. `tcformat.resources.default_template()` / `default_strategy()`) returns the bundled path; callers in `render_xlsx`, `strategy`, and the report CLI accept an explicit path and fall back to the resolver. `config.yaml` keys (e.g. `template_path`, `strategy_path`) override when present.

Net effect: every runtime call routes through the project venv; the plugin root is touched exactly once, at setup, for `pip install`.

## Work breakdown

1. Add `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`.
2. Move `commands/` and `skills/` out of `.claude/` to the plugin root.
3. Write `pyproject.toml`: package config, package-data for the xlsx, console-script for the report CLI; split runtime vs dev deps.
4. Add `tcformat` resource resolver (`importlib.resources` default + `config.yaml` override) and update callers (`render_xlsx`, `strategy`, report CLI, and the report-data path) to stop using repo-relative `template/…` / `strategy/…` literals.
5. Convert `scripts/gen_report.py` into a `tcformat` module/console entry (`tk-report`) — or keep `gen_report.py` thin and add the entry point.
6. Rewrite `/tk:setup` to venv + `pip install ${CLAUDE_PLUGIN_ROOT}`; update the other commands + both skills to drop repo-relative `.venv` / `scripts/` / `template/` / `strategy/` paths in favor of the installed package / console scripts.
7. Update `README.md`: install-from-marketplace flow + per-project usage; note dev-vs-installed paths. Keep `tests/unit/` runnable in the source repo (they may pass an explicit bundled path).
8. **Verification:** fresh clone → `/plugin marketplace add` + `/plugin install` → `/tk:setup` in an *empty* project dir → run one screen end-to-end (Stage 1 → 2 → 3) and confirm `reports/test_report.xlsx` plus the exit-criteria gate.

## Risks / notes

- **Windows venv paths:** setup must keep using `.venv\Scripts\python` on Windows; the skills currently assume Windows. Keep that assumption but resolve the interpreter from the project venv, not a repo-relative literal.
- **`config.yaml` location:** runtime calls run from the user's project cwd, so `config/config.yaml` stays project-relative (correct — it is per-project data).
- **Unit tests** reference the template by repo-relative literal today; after the move they should use the resource resolver or an explicit bundled path so they pass both in-repo and against an installed wheel.
- **Versioning:** `plugin.json` version and `pyproject.toml` version should be kept in sync (single source of truth or a release checklist note).
- **Out of scope:** PyPI publishing, CI for the marketplace, multi-plugin marketplace. Leave room, don't build.

## Definition of done

- Repo installs as a plugin from a git marketplace URL.
- `/tk:setup` in a clean project creates a venv, installs the bundled package, seeds config, and verifies the Playwright MCP server.
- A screen runs Stage 1 → 2 → 3 end-to-end against a user project with **no code edits** — only `config/` changes — producing `reports/test_report.xlsx` with the gate enforced.
- `README.md` documents install + per-project use.
- The framework's own `pytest` suite still passes in the source repo.
