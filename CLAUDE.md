# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goals

**Testing-Kit** is a reusable, config-driven test-automation framework built with **Python + Playwright + pytest**. It automates web-app testing per the project's test strategy (`strategy/strategy.xlsx`, "Chiến lược kiểm thử CLKT v1.0.0") and covers four areas:

1. **Integration / UI testing** (strategy sheet `2_IntergrationTesting`)
2. **System testing — user flows** (sheet `3_System_Testing`)
3. **API testing** (sheet `1_APITesting`)
4. **Reporting & exit criteria** (sheet `6_Chỉ số & Báo cáo`)

It also auto-generates tester checklists from the "Đối tượng testing" (test targets) in the strategy.

Core principle: the framework is **not tied to any one app**. Switching projects should require only editing config files (URLs, thresholds, accounts, devices) — no code changes.

**Out of scope (YAGNI for v1):** Jira/CI integrations, JMeter/Postman collections, 3D performance testing (FPS/render). Leave extension points only — do not implement.

## Current State

The repo is currently **design-phase**: it contains the approved design spec and source spreadsheets, but **no code has been implemented yet**.

- `docs/superpowers/specs/2026-06-15-testing-kit-design.md` — the authoritative design spec (in Vietnamese). **Read this before implementing anything.**
- `strategy/strategy.xlsx` — the test strategy that drives thresholds, the device matrix, and checklist generation.
- `template/Format test case + Test report.xlsx` — the required test-case / test-report output format.

When building, follow the directory layout, component interfaces, and Definition of Done in §4–§10 of the design spec rather than inventing a new structure.

## Planned Architecture

Data flow (per spec §6):

```
config.yaml ─► pytest fixtures (browser/device/user) ─► tests call toolkit.checks.* & api_client
            ─► results ─► pytest collector ─► reports/ (HTML/JUnit/JSON) ─► exit-criteria gate
strategy.xlsx ─► scripts/gen_checklist.py ─► checklists/*.md   (independent flow)
```

- `toolkit/` is the reusable core library: `config.py` (load/validate YAML), `browser.py` (Playwright fixtures + device profiles), `api_client.py` (status/schema/timing assertions), and `checks/` (`ui_checks`, `security_checks`, `perf_checks`).
- `tests/` holds per-project tests plus samples that run against `tests/fixtures/sample.html` — **toolkit helpers must be testable without a real app** (file:// or a static server).
- `conftest.py` provides shared fixtures and a `pytest_sessionfinish` hook that aggregates results into `reports/summary.json` and enforces the exit-criteria gate (non-zero exit on failure).
- `scripts/` holds the CLI orchestrator (`run.py`), the checklist generator (`gen_checklist.py`), and `with_server.py` (server lifecycle, reused from the `webapp-testing` plugin).

## Key Thresholds & Gates (from the strategy)

These are encoded as config defaults, not hard-coded values — but they are the source of truth:

- API response `< 600ms`; web response `< 1.5s`; page load `< 2.5s`.
- **Exit criteria:** `>= 95%` pass rate **and** `0` Critical/High bugs. The pytest session must exit non-zero if either fails.
- **Device matrix (sheet 4):** Desktop FULL HD 1920px / Windows / Chrome (chromium) for full GUI+function; iPad gen5 / Safari (webkit) / 1536×2048, marked `@pytest.mark.tablet` for a ~25% selective subset.
- **API code rules (sheet 1.3.3):** 200 → validate required/optional response body; 400/401/403 → check code + completeness only; business errors 1–99 ride on HTTP 200 with a code header.

## Definition of Done (spec §10)

- `pip install -r requirements.txt` + `playwright install` succeed.
- `pytest` runs the sample suite green against `sample.html` and produces a full `reports/`.
- `scripts/gen_checklist.py` generates checklists for all three layers from `strategy.xlsx`.
- `README.md` documents how to configure a new project and run each layer.

## Conventions

- Spec and strategy artifacts are in Vietnamese; keep terminology consistent with them when generating checklists/reports.
- Read `.xlsx` via `openpyxl` when available; fall back to raw XML parsing if not (the spec notes this was already validated during survey).
- Fail fast on bad/missing config; skip tests with a recorded reason when a server/URL is unreachable (do not let it count as a pass).

## Working Style

This project follows the Karpathy guidelines: think before coding (surface assumptions, ask when unclear), keep changes simple and surgical, and define verifiable success criteria before implementing.
