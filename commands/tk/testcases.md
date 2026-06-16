---
description: "Stage 1 — draft project test cases from design docs into the team xlsx format (generate-testcases skill)"
argument-hint: "<screen-name> [path/to/design-docs]   e.g. basic-information-input docs/design/"
---

# Testing-Kit — Stage 1: Generate Test Cases

Drive Stage 1 of the pipeline for the screen described in: `$ARGUMENTS`

This stage is AI-driven. **Invoke the `generate-testcases` skill** and point it at
the design docs for the named screen. The skill reads the design docs and produces:

- a reviewable YAML contract at `testcases/<screen>.yaml` (schema in `tcformat/schema.py`)
- the team-format xlsx at `testcases/<screen>.xlsx`
- a coverage summary checking every strategy "Đối tượng testing" has a test case

Steps:

1. Parse `$ARGUMENTS`: the first token is the screen name; the rest (if any) is the
   path to the design docs. If no design-doc path is given, ask the user where the
   design docs for this screen live before proceeding.
2. Run the `generate-testcases` skill with that screen + design docs.
3. When it finishes, report the YAML/xlsx paths and the coverage result (any
   strategy objects left uncovered).

Next step after this: `/tk:run <screen>` to execute the cases (Stage 2).
