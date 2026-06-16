# Testing-Kit

Reusable Python + Playwright toolkit automating the project test strategy as a
**3-stage, skill-driven pipeline** (generate → run → report) joined by one YAML
test-case format, producing the team xlsx report with an exit-criteria gate
(strategy sheet 6).

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

## Slash commands (Claude Code)

Inside Claude Code you can drive the whole pipeline with `/tk:*` commands instead
of typing the CLI by hand. They live in `.claude/commands/tk/` (committed, shared)
and wrap the exact commands documented below.

| Command | Does | Wraps |
|---------|------|-------|
| `/tk:setup [--force]` | venv + deps + Playwright browsers + config copy | [Setup](#setup) |
| `/tk:testcases <screen> [docs]` | **Stage 1** — draft test cases from design docs | `generate-testcases` skill |
| `/tk:run <screen> [chrome\|safari]` | **Stage 2** — execute test cases, capture evidence | `run-testcases` skill |
| `/tk:report <screen…> [--project-name] [--out]` | **Stage 3** — build the team report xlsx | `tk-report` |
| `/tk:pipeline <screen> [docs] [browser]` | Full Stage 1 → 2 → 3 end to end (pauses for review after Stage 1) | the whole chain |

Screen arguments accept a bare name (resolved to `testcases/<screen>.yaml`) or an
explicit path. The report/pipeline commands preserve the exit-criteria gate —
a failed gate (pass rate < 95% or any Critical/High bug) is reported as a failure.

The raw CLI below remains the source of truth and works outside Claude Code.

## Setup

    py -3.13 -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt
    copy config\config.example.yaml config\config.yaml   # then edit base_url
    copy config\users.example.yaml  config\users.yaml     # for permission tests

Stage 2 drives the browser through the **Playwright MCP** server (not a Python
package); see `/tk:setup` to verify it is connected.

## Run the pipeline

Drive the three stages with the `/tk:*` commands (table above) or directly:
Stage 1 via the `generate-testcases` skill, Stage 2 via the `run-testcases`
skill, Stage 3 via the `tk-report --yaml` console script (see below). The
framework's own unit suite runs with `.venv\Scripts\python -m pytest -q`.

## Generate project test cases (Stage 1)

Draft test cases from design docs into the team xlsx format with strategy
coverage. Driven by the `generate-testcases` skill (AI reads the design docs);
the deterministic backbone lives in `tcformat/`:

- `tcformat/schema.py`  — YAML test-case contract (`testcases/<screen>.yaml`)
- `tcformat/strategy.py`— testing-object refs from the strategy xlsx (bundled
  under `tcformat/data/`, resolved via `tcformat.resources`; exposed as the
  `tk-strategy` CLI)
- `tcformat/coverage.py`— checks every strategy object has a testcase
- `tcformat/render_xlsx.py` — renders YAML → testcase sheet "4.x" (standalone
  `testcases/<screen>.xlsx`, and reused by the Stage 3 report via `render_into`)

Invoke in Claude Code: run the `generate-testcases` skill and point it at the
screen's design docs. Output: a reviewable YAML contract + the team-format xlsx,
with a coverage summary.

## Run test cases (Stage 2)

Execute the generated test cases against the running web app and record results
back into the same YAML. Driven by the `run-testcases` skill (an agent drives
Playwright MCP, taking a screenshot per step):

- results (`OK` / `NG` / `N/A`, tester, date, note, bug id) are written into
  `result.{chrome,safari}` of `testcases/<screen>.yaml`
- per-step screenshots are saved to `evidence/<screen>/<browser>/<id>/step_N.png`
- the deterministic bookkeeping helper is `tcformat/runlog.py`
  (`python -m tcformat.runlog evidence-dir|record ...`)

## Generate the team Test Report (xlsx)

Reads the `result` fields Stage 2 wrote and produces ONE workbook from the
team template, all in sync from the same YAML. The template ships bundled under
`tcformat/data/` (resolved via `tcformat.resources`); override it in
`config/config.yaml` with `template_path` if needed:

    .venv\Scripts\tk-report ^
        --yaml testcases\basic-information-input.yaml ^
        --out reports\test_report.xlsx

Pass `--yaml` once per screen. The output `reports\test_report.xlsx` contains:

- sheet **"4.x &lt;screen&gt;"** — testcase detail + result columns
- sheet **"3. Test Report"** — one row per screen, totals, and an exit-criteria
  block (PASS/FAIL, pass rate, executed/planned). Pass rate counts only executed
  runs; NG bug severity is mapped from each test case's priority.
- sheet **"Evidence"** — one row per screenshot: id/browser/step, the embedded
  image, a hyperlink to the original, and the note.

The command prints a summary and exits non-zero if the exit-criteria gate fails
(pass rate < 95% or any Critical/High bug). Use `--project-name "Your Project"`
to set the banner on sheet "1. Record of Change" (defaults to `Project Name`).
The Chrome and Safari report columns come from `result.chrome` / `result.safari`
in the YAML, written by Stage 2.

## Adapt to a new project

1. Edit `config/config.yaml` (`base_url`, thresholds if different).
2. Edit `config/devices.yaml` if the device matrix changes.
3. Generate the screen's test cases (Stage 1), run them against your app (Stage 2), and report (Stage 3) — no framework code changes needed.

## Thresholds (from strategy)

| Metric | Budget |
|--------|--------|
| API response | < 600 ms |
| Web server response | < 1.5 s |
| Full page load | < 2.5 s |
| Exit: pass rate | >= 95% |
| Exit: blocking bugs | 0 Critical/High |
