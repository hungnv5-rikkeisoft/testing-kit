# Testing-Kit

Reusable Python + Playwright toolkit automating the project test strategy
(API, Integration/UI, System) with auto-generated checklists, HTML/JUnit
reports, and an exit-criteria gate (strategy sheet 6).

## Setup

    py -3.13 -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt
    .venv\Scripts\python -m playwright install chromium webkit
    copy config\config.example.yaml config\config.yaml   # then edit base_url
    copy config\users.example.yaml  config\users.yaml     # for permission tests

## Run

    .venv\Scripts\python scripts\run.py --layer integration   # desktop 1920 Chrome
    .venv\Scripts\python scripts\run.py --layer integration --tablet  # include iPad/Safari subset
    .venv\Scripts\python scripts\run.py --layer api
    .venv\Scripts\python scripts\run.py --layer system

Reports land in `reports/` (`*.html`, `*-junit.xml`, `*-summary.json`).
The run prints `[exit-criteria] FAILED` if pass rate < 95% or any
Critical/High bug is recorded.

## Generate checklists

    .venv\Scripts\python scripts\gen_checklist.py --sheet 1_APITesting --title "API Testing"
    .venv\Scripts\python scripts\gen_checklist.py --sheet 2_IntergrationTesting --title "Integration/UI Testing"
    .venv\Scripts\python scripts\gen_checklist.py --sheet 3_System_Testing --title "System Testing"

Output: `checklists/<sheet>.md`.

## Generate project test cases (Stage 1)

Draft test cases from design docs into the team xlsx format with strategy
coverage. Driven by the `generate-testcases` skill (AI reads the design docs);
the deterministic backbone lives in `tcformat/`:

- `tcformat/schema.py`  — YAML test-case contract (`testcases/<screen>.yaml`)
- `tcformat/strategy.py`— testing-object refs from `strategy.xlsx`
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

**From test-case YAML (Stage 3 — recommended).** Reads the `result` fields Stage 2
wrote and produces ONE workbook from the company template, all in sync from the
same YAML:

    .venv\Scripts\python scripts\gen_report.py ^
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
(pass rate < 95% or any Critical/High bug).

**From JUnit XML (toolkit test runs).** Fills sheet "3. Test Report" from a
pytest run's JUnit XML — one row per test file (module); status maps to OK
(passed) / NG (failed) / N/A (skipped):

    .venv\Scripts\python scripts\run.py --layer integration --reports reports\chrome
    .venv\Scripts\python scripts\run.py --layer integration --tablet --reports reports\safari
    .venv\Scripts\python scripts\gen_report.py ^
        --chrome reports\chrome\integration-junit.xml ^
        --safari reports\safari\integration-junit.xml ^
        --out reports\test_report.xlsx

`--safari` is optional (Chrome-only report if omitted). `--yaml` and `--chrome`
are mutually exclusive. Note: the Chrome and Safari columns are filled from
whichever JUnit XML you pass; to truly exercise both browsers, parametrize your
project tests by device profile (see `config/devices.yaml` and
`toolkit/browser.py`).

## Adapt to a new project

1. Edit `config/config.yaml` (`base_url`, thresholds if different).
2. Edit `config/devices.yaml` if the device matrix changes.
3. Replace the example tests in `tests/api`, `tests/integration`, `tests/system` with your own, reusing helpers from `toolkit/`.

## Thresholds (from strategy)

| Metric | Budget |
|--------|--------|
| API response | < 600 ms |
| Web server response | < 1.5 s |
| Full page load | < 2.5 s |
| Exit: pass rate | >= 95% |
| Exit: blocking bugs | 0 Critical/High |
