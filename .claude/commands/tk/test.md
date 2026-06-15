---
description: "Run the toolkit pytest suite for a layer (api/integration/system) and emit HTML/JUnit/JSON reports + exit-criteria gate"
argument-hint: "<api|integration|system> [--tablet] [--reports DIR]"
allowed-tools: Bash
---

# Testing-Kit — Run Toolkit Tests

Run the pytest-based toolkit suite for one layer via `scripts\run.py`.

Arguments: `$ARGUMENTS`

Steps:

1. Parse `$ARGUMENTS`:
   - required first token = layer (`api`, `integration`, or `system`).
   - optional `--tablet` to include the iPad/Safari (webkit) ~25% subset.
   - optional `--reports DIR` to direct the output (default `reports`).
2. Run on Windows:

       .venv\Scripts\python scripts\run.py --layer <layer> [--tablet] [--reports <dir>]

3. Reports land in the reports dir as `*.html`, `*-junit.xml`, `*-summary.json`.
   The run prints `[exit-criteria] FAILED` if pass rate < 95% or any Critical/High
   bug is recorded — surface that verbatim and treat a failed gate as a failure.

Tip: to feed Stage 3 from real Chrome+Safari runs, run twice into separate dirs
(`--reports reports\chrome` and `--tablet --reports reports\safari`), then
`/tk:report` with the `--chrome`/`--safari` JUnit variant.
