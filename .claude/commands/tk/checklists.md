---
description: Generate tester checklists from strategy.xlsx for all three layers (API, Integration/UI, System)
argument-hint: "[1_APITesting|2_IntergrationTesting|3_System_Testing]  # omit to generate all three"
allowed-tools: Bash
---

# Testing-Kit — Generate Checklists

Generate the tester checklists from `strategy/strategy.xlsx` into `checklists/`.

Argument: `$ARGUMENTS`

- If **no argument** is given, generate all three layers:

      .venv\Scripts\python scripts\gen_checklist.py --sheet 1_APITesting --title "API Testing"
      .venv\Scripts\python scripts\gen_checklist.py --sheet 2_IntergrationTesting --title "Integration/UI Testing"
      .venv\Scripts\python scripts\gen_checklist.py --sheet 3_System_Testing --title "System Testing"

- If a **single sheet name** is given as the argument, run only that one. Use a
  sensible `--title` derived from the sheet (API Testing / Integration-UI Testing /
  System Testing).

Output lands in `checklists/<sheet>.md`. After running, list the files that were
written and their checklist item counts if easy to see.
