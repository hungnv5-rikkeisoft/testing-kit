# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goals

**Testing-Kit** is a reusable, config-driven test-automation framework built with **Python + Playwright**. It automates web-app testing per the project's test strategy (`strategy/strategy.xlsx`, "Chiến lược kiểm thử CLKT v1.0.0") and covers four areas:

1. **Integration / UI testing** (strategy sheet `2_IntergrationTesting`)
2. **System testing — user flows** (sheet `3_System_Testing`)
3. **API testing** (sheet `1_APITesting`)
4. **Reporting & exit criteria** (sheet `6_Chỉ số & Báo cáo`)

Core principle: the framework is **not tied to any one app**. Switching projects should require only editing config files (URLs, thresholds, accounts, devices) — no code changes.

**Out of scope (YAGNI for v1):** Jira/CI integrations, JMeter/Postman collections, 3D performance testing (FPS/render). Leave extension points only — do not implement.

## Current State

The framework is **implemented as a 3-stage, skill-driven pipeline** around a shared YAML test-case format. See `HANDOFF.md` for the full status and the per-stage specs/plans under `docs/superpowers/`.

- `docs/superpowers/specs/2026-06-15-testing-kit-design.md` — the original design spec (in Vietnamese). Note: the pytest-per-layer execution model in older specs has been **removed** in favour of the skill-driven pipeline below.
- The test strategy xlsx — drives thresholds and the device matrix. Ships bundled under `tcformat/data/` and is resolved via `tcformat.resources` (config-overridable via `strategy_path`).
- The team template xlsx ("Format test case + Test report") — the required test-case / test-report output format. Ships bundled under `tcformat/data/` and is resolved via `tcformat.resources` (config-overridable via `template_path`).

## Architecture

The framework is a **3-stage pipeline** joined by one YAML test-case contract (`testcases/<screen>.yaml`):

```
design docs + strategy.xlsx
  │ Stage 1 — generate test cases (generate-testcases skill, AI hybrid)
  ▼  testcases/<screen>.yaml  ◄──►  testcases/<screen>.xlsx (template sheet 4.x)
  │ Stage 2 — run test cases (run-testcases skill: agent + Playwright MCP, screenshot/step)
  ▼  result + evidence/<screen>/<browser>/<TestcaseID>/step_N.png written back into the YAML
  │ Stage 3 — report + embed evidence (tk-report --yaml)
  ▼  reports/test_report.xlsx (sheet "3. Test Report" + "Evidence", exit-criteria gate)
```

- `tcformat/` is the deterministic backbone: `schema.py` (YAML contract), `strategy.py` (strategy refs), `coverage.py`, `render_xlsx.py`, `runlog.py` (Stage 2 result/evidence bookkeeping), `report_data.py`/`report_sheet.py`/`report_xlsx.py` (Stage 3 aggregation + workbook).
- `toolkit/` is the small shared core: `config.py` (load/validate YAML + thresholds) and `report.py` (`Summary` + exit-criteria evaluation), reused by `tcformat/report_data.py`.
- Stage 3 logic lives in `tcformat/report_cli.py`, exposed as the `tk-report` console script (`scripts/gen_report.py` remains a thin backward-compat shim). `scripts/` also holds `with_server.py` (server lifecycle helper, reused from the `webapp-testing` plugin).
- `demo/app.py` is a Flask app standing in for the app-under-test in Stage 2.
- `tests/unit/` holds the framework's own pytest unit tests (covering `tcformat/` and `toolkit/`); they need no running app.

## Key Thresholds & Gates (from the strategy)

These are encoded as config defaults, not hard-coded values — but they are the source of truth:

- API response `< 600ms`; web response `< 1.5s`; page load `< 2.5s`.
- **Exit criteria:** `>= 95%` pass rate **and** `0` Critical/High bugs. The Stage 3 report (`tk-report --yaml`) exits non-zero if either fails (gate in `tcformat/report_data.py` via `toolkit.report`/`toolkit.config`).
- **Device matrix (sheet 4):** Desktop FULL HD 1920px / Windows / Chrome (chromium) for full GUI+function; iPad gen5 / Safari (webkit) / 1536×2048 for a ~25% selective subset. Per-screen results are recorded in the YAML under `result.chrome` / `result.safari`.
- **API code rules (sheet 1.3.3):** 200 → validate required/optional response body; 400/401/403 → check code + completeness only; business errors 1–99 ride on HTTP 200 with a code header.

## Definition of Done

- `pip install -r requirements.txt` succeeds (Stage 2 uses the Playwright MCP server, no Python Playwright dep).
- `pytest` runs the framework's unit suite green (covering `tcformat/` and `toolkit/`).
- A screen runs end to end through Stage 1 → 2 → 3 and produces `reports/test_report.xlsx` with the exit-criteria gate enforced.
- `README.md` documents how to configure a new project and run each stage.

## Conventions

- Spec and strategy artifacts are in Vietnamese; keep terminology consistent with them when generating test cases/reports.
- Read `.xlsx` via `openpyxl` when available; fall back to raw XML parsing if not (the spec notes this was already validated during survey).
- Fail fast on bad/missing config; skip tests with a recorded reason when a server/URL is unreachable (do not let it count as a pass).

## Working Style

This project follows the Karpathy guidelines: think before coding (surface assumptions, ask when unclear), keep changes simple and surgical, and define verifiable success criteria before implementing.
