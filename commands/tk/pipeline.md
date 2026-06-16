---
description: "Run the full Testing-Kit pipeline end to end for a screen: Stage 1 (generate) → Stage 2 (run) → Stage 3 (report)"
argument-hint: "<screen-name> [path/to/design-docs] [chrome|safari] [--project-name \"Name\"]"
allowed-tools: Bash, Read, Edit
---

# Testing-Kit — Full Pipeline

Orchestrate the three stages back to back for one screen. Arguments: `$ARGUMENTS`

Parse `$ARGUMENTS`: first token = **screen name**; then optionally a **design-docs
path**, a **browser** (`chrome`/`safari`, default `chrome`), and `--project-name`.

Run the stages in order, **stopping and reporting if any stage fails** (do not push
forward on a broken stage). Pause for the user between stages 1 and 2 so they can
review the drafted test cases before execution.

### Preflight
- Confirm `.venv\` exists and `config\config.yaml` has a reachable `base_url`.
  If the env isn't set up, tell the user to run `/tk:setup` first and stop.

### Stage 1 — Generate test cases
Invoke the `generate-testcases` skill for the screen + design docs (ask for the
design-docs path if not provided). Produces `testcases/<screen>.yaml` + `.xlsx` and a
coverage summary. **Show the coverage result and pause for user review/approval**
before continuing.

### Stage 2 — Run test cases
Invoke the `run-testcases` skill for `<screen>` on the chosen browser. Writes
`result.*` back into the YAML and per-step screenshots under `evidence/<screen>/...`.
Report the OK/NG/N·A tally.

### Stage 3 — Generate report
Run:

    .venv\Scripts\tk-report --yaml testcases\<screen>.yaml --out reports\test_report.xlsx

Add `--project-name "..."` if given. This exits non-zero if the exit-criteria gate
fails (pass rate < 95% or any Critical/High bug).

### Wrap-up
Summarize: coverage, pass rate, exit-criteria PASS/FAIL, and the paths to the YAML,
evidence folder, and `reports\test_report.xlsx`. If the gate failed, say so plainly.
