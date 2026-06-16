# Testing-Kit Plugin Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repackage the in-repo Testing-Kit pipeline as an installable Claude Code plugin distributed via a git marketplace, so it runs against any project with only per-project `config/` changes.

**Architecture:** Bundle the Python backbone (`tcformat/`, `toolkit/`) and the default template/strategy xlsx inside the plugin. `/tk:setup` creates a venv in the *user's* project and `pip install`s the bundled package; every runtime call routes through that venv. Repo-relative path literals are replaced by an `importlib.resources` resolver (`tcformat/resources.py`) plus console scripts (`tk-report`, `tk-strategy`). Commands/skills move from `.claude/` to the plugin root.

**Tech Stack:** Python 3.13, setuptools (pyproject), openpyxl, pyyaml, Pillow, pytest; Claude Code plugin + marketplace manifests (JSON).

---

## File Structure

**Create:**
- `pyproject.toml` — packages `tcformat`+`toolkit`, package-data for xlsx, console scripts.
- `tcformat/resources.py` — resolver: bundled default + explicit/config override for template & strategy paths.
- `tcformat/report_cli.py` — Stage-3 report CLI (logic moved out of `scripts/gen_report.py`).
- `tcformat/data/template/Format test case + Test report.xlsx` — moved from `template/`.
- `tcformat/data/strategy/strategy.xlsx` — moved from `strategy/`.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`.
- `commands/tk/*.md`, `skills/generate-testcases/SKILL.md`, `skills/run-testcases/SKILL.md` — moved from `.claude/`.

**Modify:**
- `tcformat/strategy.py` — add `main()` CLI (default path via resolver).
- `scripts/gen_report.py` — reduce to a thin shim re-exporting `tcformat.report_cli`.
- `tests/unit/test_*.py` — replace `TEMPLATE`/strategy path literals with the resolver.
- `README.md`, `CLAUDE.md` — install-from-marketplace + new paths.

**Delete (after move):**
- `template/`, `strategy/` (root copies), `.claude/commands/`, `.claude/skills/`.

---

## Task 1: Resource resolver + move bundled xlsx into the package

**Files:**
- Create: `tcformat/data/template/Format test case + Test report.xlsx` (moved)
- Create: `tcformat/data/strategy/strategy.xlsx` (moved)
- Create: `tcformat/resources.py`
- Test: `tests/unit/test_resources.py`

- [ ] **Step 1: Move the xlsx into the package (git mv preserves history)**

```bash
mkdir -p tcformat/data/template tcformat/data/strategy
git mv "template/Format test case + Test report.xlsx" "tcformat/data/template/Format test case + Test report.xlsx"
git mv "strategy/strategy.xlsx" "tcformat/data/strategy/strategy.xlsx"
# remove now-empty root dirs if anything remains
rmdir template strategy 2>/dev/null || true
```

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_resources.py
import os
from tcformat.resources import (
    default_template, default_strategy, template_path, strategy_path)


def test_defaults_point_at_existing_bundled_files():
    assert os.path.isfile(default_template())
    assert os.path.isfile(default_strategy())
    assert default_template().endswith("Format test case + Test report.xlsx")


def test_explicit_overrides_default():
    assert template_path("/x/custom.xlsx") == "/x/custom.xlsx"
    assert strategy_path("/x/s.xlsx") == "/x/s.xlsx"


def test_config_override(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("base_url: http://x\ntemplate_path: /from/cfg.xlsx\n",
                   encoding="utf-8")
    assert template_path(None, str(cfg)) == "/from/cfg.xlsx"
    # explicit beats config
    assert template_path("/explicit.xlsx", str(cfg)) == "/explicit.xlsx"
    # missing key falls back to bundled default
    assert strategy_path(None, str(cfg)) == default_strategy()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/unit/test_resources.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tcformat.resources'`

- [ ] **Step 4: Write `tcformat/resources.py`**

```python
"""Locate the bundled default template/strategy xlsx, with override hooks.

Resolution order for a path: explicit argument > config.yaml key > bundled
default shipped as package data. Bundled files live under tcformat/data/ and
are resolved via importlib.resources (works when pip-installed from a source
directory, which is how /tk:setup installs the plugin).
"""
from __future__ import annotations
from importlib.resources import files
from pathlib import Path

TEMPLATE_NAME = "Format test case + Test report.xlsx"
STRATEGY_NAME = "strategy.xlsx"


def default_template() -> str:
    return str(files("tcformat").joinpath("data", "template", TEMPLATE_NAME))


def default_strategy() -> str:
    return str(files("tcformat").joinpath("data", "strategy", STRATEGY_NAME))


def _from_config(config_path, key):
    if not config_path:
        return None
    p = Path(config_path)
    if not p.exists():
        return None
    import yaml
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data.get(key)


def template_path(explicit=None, config_path=None) -> str:
    return explicit or _from_config(config_path, "template_path") or default_template()


def strategy_path(explicit=None, config_path=None) -> str:
    return explicit or _from_config(config_path, "strategy_path") or default_strategy()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/unit/test_resources.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add tcformat/resources.py tcformat/data tests/unit/test_resources.py
git commit -m "feat: bundle template/strategy as package data with resolver"
```
(Confirm with the user before running `git add`/`git commit` — per project git policy.)

---

## Task 2: `pyproject.toml` (packaging + package-data + console scripts)

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "testing-kit"
version = "0.1.0"
description = "Config-driven web test-automation pipeline (Playwright MCP + xlsx reporting)"
requires-python = ">=3.11"
dependencies = ["pyyaml>=6", "openpyxl>=3.1", "Pillow>=10"]

[project.optional-dependencies]
dev = ["pytest>=8", "flask>=3"]

[project.scripts]
tk-report = "tcformat.report_cli:main"
tk-strategy = "tcformat.strategy:main"

[tool.setuptools]
packages = ["tcformat", "toolkit"]
include-package-data = true

[tool.setuptools.package-data]
tcformat = ["data/template/*.xlsx", "data/strategy/*.xlsx"]
```

- [ ] **Step 2: Verify the package builds and installs editable into the venv**

Run:
```bash
.venv/Scripts/python -m pip install -e .
.venv/Scripts/python -c "import tcformat, toolkit, os; from tcformat.resources import default_template; print('OK', os.path.isfile(default_template()))"
```
Expected: `OK True` (console scripts `tk-report`/`tk-strategy` are NOT yet defined as modules — added in Tasks 3-4; install of `-e .` still succeeds because entry points resolve lazily at call time).

> Note: `tk-report`/`tk-strategy` entry points reference modules created in Tasks 3 and 4. Running those console scripts before those tasks will error; that is expected. Re-run `pip install -e .` is not required after adding the modules (editable install picks them up), but a fresh `pip install .` would be needed for a non-editable env.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: add pyproject packaging with console scripts and package-data"
```

---

## Task 3: Report CLI module (`tcformat/report_cli.py`) + shim

**Files:**
- Create: `tcformat/report_cli.py`
- Modify: `scripts/gen_report.py` (reduce to shim)
- Test: `tests/unit/test_report_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_report_cli.py
from PIL import Image as PILImage
from tcformat.schema import Screen, Testcase, Result, BrowserResult, dump_screen
from tcformat.report_cli import build_report_from_yaml, main
from tcformat.resources import default_template


def _png(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    PILImage.new("RGB", (600, 400), "white").save(path)


def test_build_report_uses_bundled_template(tmp_path):
    rel = "evidence/s/chrome/UI_01/step_1.png"
    _png(tmp_path / rel)
    sc = Screen(screen="S", test_level="IT", testcases=[
        Testcase(id="UI_01", section="UI", main_item="x", type="IT",
                 priority="High",
                 result=Result(chrome=BrowserResult(status="OK", evidence=[rel]))),
    ])
    yml = tmp_path / "s.yaml"
    dump_screen(sc, yml)
    out = tmp_path / "reports" / "test_report.xlsx"
    data = build_report_from_yaml([str(yml)], default_template(), str(out),
                                  base_dir=str(tmp_path))
    assert data.executed == 1 and data.exit_ok is True
    assert out.exists()


def test_main_exits_zero_on_pass(tmp_path):
    rel = "evidence/s/chrome/UI_01/step_1.png"
    _png(tmp_path / rel)
    sc = Screen(screen="S", test_level="IT", testcases=[
        Testcase(id="UI_01", section="UI", main_item="x", type="IT",
                 priority="High",
                 result=Result(chrome=BrowserResult(status="OK", evidence=[rel]))),
    ])
    yml = tmp_path / "s.yaml"
    dump_screen(sc, yml)
    out = tmp_path / "reports" / "r.xlsx"
    try:
        main(["--yaml", str(yml), "--out", str(out)])
    except SystemExit as e:
        assert e.code == 0
    else:
        raise AssertionError("main did not raise SystemExit")
```

> The report writer resolves evidence paths against `base_dir`. `main()` uses the process cwd as `base_dir`; this test passes absolute `--out` and an evidence path that is relative to cwd. Run pytest from the repo root so the relative `evidence/...` PNG written under `tmp_path` resolves — to keep the test cwd-independent, the test only asserts on `build_report_from_yaml` for evidence; `test_main_exits_zero_on_pass` may emit an evidence-missing warning but still exits 0 because the result status is OK. If the writer hard-fails on a missing image, change the second test to `chdir(tmp_path)` first.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/unit/test_report_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tcformat.report_cli'`

- [ ] **Step 3: Write `tcformat/report_cli.py`**

```python
"""Stage 3 — build the team's Test Report workbook from test-case YAML.

Aggregates the `result` fields Stage 2 wrote into testcases/<screen>.yaml and
renders ONE workbook from the team template (testcase sheets + "3. Test Report"
+ "Evidence"). Installed as the `tk-report` console script.
"""
from __future__ import annotations
import argparse

from tcformat.resources import template_path


def build_report_from_yaml(yaml_paths, template, out_path, base_dir=".",
                           project_name="Project Name"):
    """Aggregate testcase YAML(s) and write the report workbook.

    Returns the ReportData (caller uses .exit_ok for the process exit code)."""
    from tcformat.schema import load_screen
    from tcformat.report_data import aggregate
    from tcformat.report_xlsx import write_report
    screens = [load_screen(p) for p in yaml_paths]
    data = aggregate(screens)
    write_report(data, screens, template, out_path, base_dir=base_dir,
                 project_name=project_name)
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yaml", action="append", required=True,
                    help="testcase YAML with results (repeatable)")
    ap.add_argument("--template", default=None,
                    help="override template xlsx (default: bundled / config)")
    ap.add_argument("--config", default=None,
                    help="config.yaml to read template_path override from")
    ap.add_argument("--out", default="reports/test_report.xlsx")
    ap.add_argument("--project-name", dest="project_name", default="Project Name")
    args = ap.parse_args(argv)

    tmpl = template_path(args.template, args.config)
    data = build_report_from_yaml(args.yaml, tmpl, args.out,
                                  project_name=args.project_name)
    s = data.summary
    print(f"Wrote report -> {args.out} (executed {data.executed}/{data.planned}, "
          f"OK {s.passed} NG {s.failed}, pass {s.pass_rate:.0%}, "
          f"exit {'PASS' if data.exit_ok else 'FAIL'})")
    raise SystemExit(0 if data.exit_ok else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Reduce `scripts/gen_report.py` to a shim**

```python
"""Backward-compatible shim. Real logic lives in tcformat.report_cli.

Kept so existing `python scripts/gen_report.py ...` invocations and imports
still work; new callers use the `tk-report` console script.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tcformat.report_cli import build_report_from_yaml, main  # noqa: E402,F401

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/unit/test_report_cli.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add tcformat/report_cli.py scripts/gen_report.py tests/unit/test_report_cli.py
git commit -m "refactor: move Stage 3 report logic into tcformat.report_cli (tk-report)"
```

---

## Task 4: Strategy CLI (`tk-strategy`)

**Files:**
- Modify: `tcformat/strategy.py` (add `main()`)
- Test: `tests/unit/test_strategy_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_strategy_cli.py
import json
from tcformat.strategy import main


def test_strategy_cli_prints_json(capsys):
    main(["--sheet", "2_IntergrationTesting"])
    out = capsys.readouterr().out
    objs = json.loads(out)
    assert isinstance(objs, list) and objs
    assert any(o.get("ref") == "2.3.1#1" for o in objs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/unit/test_strategy_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'main' from 'tcformat.strategy'`

- [ ] **Step 3: Add `main()` to `tcformat/strategy.py`**

Append to the end of the file (after `all_refs`):

```python
def main(argv=None):
    import argparse
    import json
    from tcformat.resources import strategy_path
    ap = argparse.ArgumentParser(
        description="List strategy testing objects (refs) for a sheet as JSON.")
    ap.add_argument("--sheet", required=True,
                    help="e.g. 1_APITesting | 2_IntergrationTesting | 3_System_Testing")
    ap.add_argument("--xlsx", default=None, help="override strategy xlsx path")
    ap.add_argument("--config", default=None,
                    help="config.yaml to read strategy_path override from")
    args = ap.parse_args(argv)
    path = strategy_path(args.xlsx, args.config)
    print(json.dumps(list_objects(path, args.sheet), ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/unit/test_strategy_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tcformat/strategy.py tests/unit/test_strategy_cli.py
git commit -m "feat: add tk-strategy CLI for listing strategy objects as JSON"
```

---

## Task 5: Repoint existing unit tests to the resolver

**Files:**
- Modify: `tests/unit/test_gen_report_yaml.py`, `tests/unit/test_render_result_cols.py`, `tests/unit/test_report_sheet.py`, `tests/unit/test_report_xlsx.py`, `tests/unit/test_tc_render.py`, `tests/unit/test_tc_strategy.py`

- [ ] **Step 1: Replace the template literal in the five report/render tests**

In each of `test_gen_report_yaml.py`, `test_render_result_cols.py`, `test_report_sheet.py`, `test_report_xlsx.py`, `test_tc_render.py`, replace the line:

```python
TEMPLATE = "template/Format test case + Test report.xlsx"
```

with:

```python
from tcformat.resources import default_template
TEMPLATE = default_template()
```

(Place the import with the other imports at the top; keep the `TEMPLATE = ...` where it was so the rest of each test is unchanged.)

- [ ] **Step 2: Fix the strategy literal + the gen_report import**

In `test_tc_strategy.py`, change:

```python
    refs = all_refs("strategy/strategy.xlsx")
```
to:
```python
    from tcformat.resources import default_strategy
    refs = all_refs(default_strategy())
```

In `test_gen_report_yaml.py`, change the import:
```python
from scripts.gen_report import build_report_from_yaml
```
to:
```python
from tcformat.report_cli import build_report_from_yaml
```

- [ ] **Step 3: Run the full suite**

Run: `.venv/Scripts/python -m pytest tests/unit -q`
Expected: PASS (all pre-existing tests green; no reference to the old `template/` or `strategy/` root paths remains)

- [ ] **Step 4: Commit**

```bash
git add tests/unit
git commit -m "test: resolve template/strategy via tcformat.resources (post-move)"
```

---

## Task 6: Plugin + marketplace manifests

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Write `.claude-plugin/plugin.json`**

```json
{
  "name": "testing-kit",
  "version": "0.1.0",
  "description": "Config-driven web test-automation pipeline: generate test cases -> run via Playwright MCP -> report in the team xlsx format, with an exit-criteria gate.",
  "author": { "name": "Hungnv5" },
  "keywords": ["testing", "playwright", "qa", "test-automation", "xlsx"]
}
```

- [ ] **Step 2: Write `.claude-plugin/marketplace.json`**

```json
{
  "name": "testing-kit",
  "owner": { "name": "Hungnv5" },
  "plugins": [
    {
      "name": "testing-kit",
      "source": "./",
      "description": "Config-driven web test-automation pipeline (generate -> run -> report)."
    }
  ]
}
```

- [ ] **Step 3: Validate JSON**

Run:
```bash
.venv/Scripts/python -c "import json; json.load(open('.claude-plugin/plugin.json')); json.load(open('.claude-plugin/marketplace.json')); print('valid')"
```
Expected: `valid`

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin
git commit -m "feat: add plugin.json + marketplace.json manifests"
```

---

## Task 7: Move commands + skills to the plugin root and repoint their paths

**Files:**
- Move: `.claude/commands/tk/*.md` → `commands/tk/*.md`
- Move: `.claude/skills/*/SKILL.md` → `skills/*/SKILL.md`
- Modify (path references): `skills/generate-testcases/SKILL.md`, `skills/run-testcases/SKILL.md`, `commands/tk/report.md`, `commands/tk/pipeline.md`

- [ ] **Step 1: Move the directories (preserve history)**

```bash
mkdir -p commands skills
git mv .claude/commands/tk commands/tk
git mv .claude/skills/generate-testcases skills/generate-testcases
git mv .claude/skills/run-testcases skills/run-testcases
```

- [ ] **Step 2: Repoint `skills/generate-testcases/SKILL.md`**

Replace the strategy-listing command (the `Inputs you gather first` step 3) so it uses the installed console script instead of an inline path literal:

```
3. Strategy testing objects for the relevant level(s):
   run `./.venv/Scripts/tk-strategy --sheet 2_IntergrationTesting`
   (swap the sheet for 1_APITesting / 3_System_Testing as needed). Output is JSON.
```

And in the `Process` step 3 code block, replace the two literals so it relies on the bundled defaults:

```
   ./.venv/Scripts/python.exe -c "
   from tcformat.schema import load_screen
   from tcformat.render_xlsx import render
   from tcformat.coverage import check_coverage
   from tcformat.strategy import list_objects
   from tcformat.resources import default_template, default_strategy
   sc = load_screen('testcases/<screen-slug>.yaml')
   render([sc], default_template(), 'testcases/<screen-slug>.xlsx')
   refs = {o['ref'] for o in list_objects(default_strategy(),'2_IntergrationTesting') if o['ref']}
   rep = check_coverage(sc, refs)
   print('missing:', sorted(rep.missing)); print('unknown:', sorted(rep.unknown))
   "
```

- [ ] **Step 3: Repoint `skills/run-testcases/SKILL.md`**

In the "Output" re-render snippet, replace the template literal with the resolver:

```
  ./.venv/Scripts/python.exe -c "from tcformat.schema import load_screen; from tcformat.render_xlsx import render; from tcformat.resources import default_template; sc=load_screen('testcases/<slug>.yaml'); render([sc],default_template(),'testcases/<slug>.xlsx'); print('rendered')"
```

(The `tcformat.runlog` evidence/record commands are unchanged — they already use `python -m tcformat.runlog`, which works once the package is installed in the project venv.)

- [ ] **Step 4: Repoint `commands/tk/report.md`**

Replace the run command (step 2) with the console script:

```
       .venv\Scripts\tk-report --yaml testcases\<screen>.yaml --out reports\test_report.xlsx
```

- [ ] **Step 5: Repoint `commands/tk/pipeline.md` Stage 3**

Replace the Stage-3 run line:

```
    .venv\Scripts\tk-report --yaml testcases\<screen>.yaml --out reports\test_report.xlsx
```

- [ ] **Step 6: Verify no stale paths remain in commands/skills**

Run:
```bash
grep -rn "scripts.gen_report\|scripts\\\\gen_report\|template/Format\|strategy/strategy" commands skills || echo "clean"
```
Expected: `clean`

- [ ] **Step 7: Commit**

```bash
git add commands skills
git rm -r .claude/commands .claude/skills 2>/dev/null || true
git commit -m "refactor: move commands+skills to plugin root, repoint to installed package"
```

---

## Task 8: Rewrite `/tk:setup` for plugin-based install

**Files:**
- Modify: `commands/tk/setup.md`

- [ ] **Step 1: Rewrite the body of `commands/tk/setup.md`**

Keep the frontmatter (`description`, `argument-hint`, `allowed-tools: Bash, Read, Edit`). Replace the numbered body with:

```markdown
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
       if (!(Test-Path config\config.yaml)) { copy "$env:CLAUDE_PLUGIN_ROOT\config\config.example.yaml" config\config.yaml }
       if (!(Test-Path config\users.yaml))  { copy "$env:CLAUDE_PLUGIN_ROOT\config\users.example.yaml"  config\users.yaml }

5. After copying, open `config\config.yaml` and tell the user to set `base_url`
   (and any thresholds/`template_path`/`strategy_path` overrides). Report which
   files were created vs. already present.

Finish with a one-line status: env ready / what still needs the user's input
(e.g. editing `base_url`).
```

- [ ] **Step 2: Ensure the bundled example configs exist in the plugin**

Confirm `config/config.example.yaml` and `config/users.example.yaml` exist at the plugin root (they ship with the plugin). If only real `config.yaml`/`users.yaml` exist, create example copies:

Run:
```bash
ls config/config.example.yaml config/users.example.yaml 2>/dev/null || echo "MISSING examples"
```
If `MISSING examples`, create them from the current real config with secrets blanked (base_url left as a placeholder), then `git add config/*.example.yaml`.

- [ ] **Step 3: Commit**

```bash
git add commands/tk/setup.md config/config.example.yaml config/users.example.yaml
git commit -m "feat: /tk:setup installs bundled framework into project venv"
```

---

## Task 9: Update docs (`README.md`, `CLAUDE.md`)

**Files:**
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1: Update `README.md`**

Add an **Install** section near the top documenting the plugin flow, and update any
`python scripts/gen_report.py` / `template/…` / `strategy/…` references to the new
console scripts and bundled defaults:

```markdown
## Install (as a Claude Code plugin)

1. Add the marketplace (point at this repo's git URL):

       /plugin marketplace add <git-url-of-this-repo>

2. Install the plugin:

       /plugin install testing-kit

3. In your project directory, bootstrap the environment:

       /tk:setup

   This creates `.venv`, installs the bundled framework, verifies the Playwright
   MCP server, and seeds `config/`. Then edit `config/config.yaml` (`base_url`,
   thresholds, optional `template_path`/`strategy_path` overrides).

## Run a screen

       /tk:testcases <screen> <design-docs-path>     # Stage 1
       /tk:run <screen> [chrome|safari]              # Stage 2
       /tk:report <screen>                           # Stage 3  (or /tk:pipeline for all three)
```

- [ ] **Step 2: Update `CLAUDE.md` path references**

Update the lines that cite `strategy/strategy.xlsx` and `template/Format test case + Test report.xlsx` to note they are now bundled under `tcformat/data/` and resolved via `tcformat.resources` (overridable through `config.yaml` `template_path`/`strategy_path`). Update the architecture/`scripts/` bullet to mention `tcformat/report_cli.py` (`tk-report`) replacing the standalone `scripts/gen_report.py`.

- [ ] **Step 3: Verify docs have no stale runnable paths**

Run:
```bash
grep -rn "scripts/gen_report.py\|python scripts" README.md || echo "readme clean"
```
Expected: `readme clean` (or only historical mentions clearly labeled as legacy)

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document plugin install + bundled-path/console-script changes"
```

---

## Task 10: End-to-end verification (fresh-install simulation)

**Files:** none (verification only)

- [ ] **Step 1: Full unit suite from a clean editable install**

Run:
```bash
.venv/Scripts/python -m pip install -e .
.venv/Scripts/python -m pytest tests/unit -q
```
Expected: all green; console scripts resolve.

- [ ] **Step 2: Console scripts work from an unrelated cwd**

Run (from a temp dir to prove cwd-independence of bundled data):
```bash
cd "$(mktemp -d)" && "OLDPWD_VENV"/Scripts/tk-strategy --sheet 2_IntergrationTesting | head -c 80; cd -
```
(Replace `OLDPWD_VENV` with the absolute path to the repo `.venv`.) Expected: JSON array printed — bundled strategy resolved without a `strategy/` cwd.

- [ ] **Step 3: Simulate a consumer project end-to-end**

In a scratch directory, create `config/config.yaml` with a reachable `base_url` (use the bundled `demo/app.py` from the plugin if you want a target), then run one screen through Stage 1 → 2 → 3 using the `/tk:*` commands (or invoke the skills directly). Confirm `reports/test_report.xlsx` is produced and `tk-report` exits non-zero only when the exit-criteria gate fails.

Expected: `reports/test_report.xlsx` exists with sheets `3. Test Report` + `Evidence`; exit code reflects the gate.

- [ ] **Step 4: Final commit (version tag note)**

```bash
git commit --allow-empty -m "chore: plugin packaging verified end-to-end (v0.1.0)"
```
(Optional: tag `v0.1.0`. Confirm with the user before tagging/pushing.)

---

## Self-Review notes (coverage vs spec)

- Spec §"What moves where" → Tasks 1, 7 (move commands/skills + xlsx); dev-only files left in place. ✔
- Spec §"Target repo layout" → Tasks 6, 7 (manifests + commands/skills at root). ✔
- Spec §"Key technical change — path resolution": pyproject (Task 2), package-data + resolver (Task 1), console script (Tasks 3, 4), setup `pip install ${CLAUDE_PLUGIN_ROOT}` (Task 8), importlib.resources default + config override (Task 1). ✔
- Spec §"Work breakdown" items 1-8 → Tasks 6, 7, 2, 1, 3, 8, 9, 10 respectively. ✔
- Spec §"Risks": Windows venv paths kept (`.venv\Scripts\…` in Task 8); `config.yaml` stays project-relative; unit tests repointed (Task 5); versioning note (plugin.json + pyproject both 0.1.0, Tasks 2/6). ✔
- Per global git policy: every commit step is gated on user confirmation; no auto-commit.
```
