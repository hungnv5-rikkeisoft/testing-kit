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
