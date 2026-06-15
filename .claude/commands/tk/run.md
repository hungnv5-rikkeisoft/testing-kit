---
description: "Stage 2 — execute generated test cases against the running web app via Playwright, recording OK/NG/N·A + screenshots (run-testcases skill)"
argument-hint: "<screen-name> [chrome|safari]   e.g. basic-information-input chrome"
---

# Testing-Kit — Stage 2: Run Test Cases

Drive Stage 2 of the pipeline for: `$ARGUMENTS`

This stage is agent-driven via Playwright MCP. **Invoke the `run-testcases` skill**
for the named screen. It executes each test case step-by-step and writes back into
the same `testcases/<screen>.yaml`:

- results (`OK` / `NG` / `N/A`, tester, date, note, bug id) into `result.{chrome,safari}`
- a screenshot per step at `evidence/<screen>/<browser>/<id>/step_N.png`

Steps:

1. Parse `$ARGUMENTS`: first token = screen name; optional second token = browser
   (`chrome` or `safari`, default `chrome`).
2. Confirm `testcases/<screen>.yaml` exists (it must — run `/tk:testcases <screen>`
   first if not). Confirm the target web app `base_url` in `config\config.yaml` is
   reachable; if not, skip with a recorded reason rather than marking a pass.
3. Run the `run-testcases` skill for that screen + browser.
4. Report a pass/fail tally and where the evidence was saved.

Next step after this: `/tk:report testcases/<screen>.yaml` to build the report (Stage 3).
