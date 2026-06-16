---
name: run-testcases
description: Use when executing generated test cases against a web app via Playwright MCP, capturing per-step screenshots and recording OK/NG/N·A results. Triggers - "chạy test case", "run testcases", "execute test cases".
---

# Run Test Cases (Stage 2 — agent + Playwright MCP)

Drive the natural-language `steps` in `testcases/<screen>.yaml` against a running
web app via Playwright MCP, screenshot every step as evidence, judge each
testcase against its `expected`, and record results back into the YAML with the
deterministic helper `tcformat.runlog`.

## Inputs you gather first
1. Testcase file: `testcases/<screen-slug>.yaml` (+ which testcase IDs to run; default all).
2. Target + accounts: `config/config.yaml` (base_url/port) and `config/users.yaml`
   (role accounts). For the bundled demo app, start it first and use it as the target:
   `./.venv/Scripts/python.exe demo/app.py`  (serves http://127.0.0.1:5005) — run in
   the background. Demo accounts: `a@example.com`/`a`, `b@example.com`/`b`,
   `admin@example.com`/`admin`, `noperm@example.com`/`n` (no permission).
3. Browser: `chrome` (chromium) is the primary run; `safari` (webkit) is an optional
   ~25% subset (testcases marked tablet).

## Process — for EACH testcase
1. Make/observe the evidence dir (also creates parents):
   `./.venv/Scripts/python.exe -m tcformat.runlog evidence-dir --screen <slug> --browser chrome --id <ID>`
2. Reset state: `browser_navigate` to base_url. If `precondition` names a role/login,
   log in the matching user from `config/users.yaml` (or the demo accounts) via the
   app's `/login` form before running steps.
3. Execute each `step` in order via Playwright MCP tools
   (`browser_navigate` / `browser_click` / `browser_type` / `browser_select_option` /
   `browser_press_key` / ...). Read `browser_snapshot` to choose selectors at runtime —
   the steps are natural language, so map them to concrete actions yourself.
4. After EACH step: `browser_take_screenshot` saving to
   `evidence/<slug>/chrome/<ID>/step_<N>.png` (N starts at 1).
5. Judge the `expected` list:
   - All expected met → status `OK`.
   - An expected fails → status `NG`; pass a `--note` describing the bug (and a
     `--bug-id` if you have one).
   - A step is not automatable in this environment (compare to Figma, inspect
     DevTools Styles, measure browser memory) → status `N/A` with a `--note` giving
     the reason; still screenshot whatever is visible.
6. Optional deterministic aux checks when they sharpen a verdict: console-clean for
   NF_01, response/load timing for NF_02/NF_03, XSS-safe echo for NF_04. Use
   `browser_console_messages` / `browser_network_requests` to gather evidence for these.
7. Record the result (one call per testcase per browser):
   ```
   ./.venv/Scripts/python.exe -m tcformat.runlog record \
       --yaml testcases/<slug>.yaml --id <ID> --browser chrome \
       --status OK|NG|N/A --note "..." \
       --evidence evidence/<slug>/chrome/<ID>/step_1.png \
       --evidence evidence/<slug>/chrome/<ID>/step_2.png
   ```
   (`--status` accepts exactly `OK`, `NG`, or `N/A`; `--browser` is `chrome` or `safari`.)

## Stop rule
A failing step does NOT abort the whole run: mark that testcase `NG`, note it, and
move on to the next testcase. Only stop if the target app itself is unreachable —
then record the remaining testcases as not-run (skip) and report why.

## Output
- `testcases/<slug>.yaml` with `result` filled for the IDs you ran.
- `evidence/<slug>/chrome/<ID>/step_N.png` trees (gitignored — they are run evidence).
- Optionally re-render the xlsx to surface the result columns:
  ```
  ./.venv/Scripts/python.exe -c "from tcformat.schema import load_screen; from tcformat.render_xlsx import render; from tcformat.resources import default_template; sc=load_screen('testcases/<slug>.yaml'); render([sc],default_template(),'testcases/<slug>.xlsx'); print('rendered')"
  ```

## Notes
- Always use `./.venv/Scripts/python.exe` (the bundled venv 3.13), never bare `python`.
- The `runlog` helper is the ONLY way to write results — never hand-edit the YAML's
  `result` blocks, so the schema stays valid and round-trips cleanly.
- Stage 3 (reporting) reads these `result` blocks + evidence paths from the YAML.
