---
description: "Stage 3 — generate the team Test Report xlsx from test-case YAML (one synced workbook + exit-criteria gate)"
argument-hint: "<screen-or-yaml> [more-yaml...] [--project-name \"Name\"] [--out path]"
allowed-tools: Bash
---

# Testing-Kit — Stage 3: Generate Test Report

Build the unified team Test Report from the `result` fields Stage 2 wrote.

Arguments: `$ARGUMENTS`

Steps:

1. Parse `$ARGUMENTS` into:
   - one or more **YAML inputs** — accept either a bare screen name (resolve to
     `testcases/<screen>.yaml`) or an explicit `testcases/...yaml` path. Pass each
     with its own `--yaml`.
   - optional `--project-name "..."` (sets the banner on sheet "1. Record of Change";
     defaults to `Project Name`).
   - optional `--out path` (defaults to `reports\test_report.xlsx`).
2. Run, on Windows (one `--yaml` per screen):

       .venv\Scripts\tk-report --yaml testcases\<screen>.yaml --out reports\test_report.xlsx

3. The command **exits non-zero if the exit-criteria gate fails** (pass rate < 95%
   or any Critical/High bug). Surface that result clearly — do not call a failed gate
   a success. Report pass rate, executed/planned counts, and the output workbook path.

The output workbook contains: sheet **"4.x <screen>"** (testcase detail + results),
sheet **"3. Test Report"** (per-screen rows, totals, exit-criteria block), and sheet
**"Evidence"** (one row per screenshot).
