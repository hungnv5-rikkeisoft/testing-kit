---
name: generate-testcases
description: Use when generating project test cases from design docs into the team xlsx format with full strategy coverage. Triggers - "sinh test case", "generate test cases", "tạo testcase cho màn hình".
---

# Generate Test Cases (AI hybrid)

Draft project test cases from design documents into the shared YAML contract,
then render the team-format xlsx and verify 100% strategy coverage.

## Inputs you gather first
1. Design docs for the screen: text/markdown spec, business rules, DB/API design.
2. Figma or screenshot images (read them multimodally if provided).
3. Strategy testing objects for the relevant level(s):
   run `./.venv/Scripts/python.exe -c "from tcformat.strategy import list_objects; import json; print(json.dumps(list_objects('strategy/strategy.xlsx','2_IntergrationTesting'), ensure_ascii=False))"`
   (swap the sheet for 1_APITesting / 3_System_Testing as needed).

## Process
1. For EACH strategy testing object relevant to the screen, write at least one
   testcase whose `strategy_ref` equals that object's `ref` (e.g. "2.3.1#1").
   Add screen-specific cases beyond the checklist where the design warrants.
2. Each testcase follows the schema in `tcformat/schema.py`: id, section
   (UI/FUNCTION/...), main_item, type (UT|IT|ST), priority (Low|Medium|High),
   strategy_ref, precondition, steps (NL, ordered), expected (NL, ordered).
   Write steps/expected concretely enough that a browser agent can execute them.
3. Save `testcases/<screen-slug>.yaml`. Validate + render + check coverage:
   ```
   ./.venv/Scripts/python.exe -c "
   from tcformat.schema import load_screen
   from tcformat.render_xlsx import render
   from tcformat.coverage import check_coverage
   from tcformat.strategy import list_objects
   sc = load_screen('testcases/<screen-slug>.yaml')
   render([sc], 'template/Format test case + Test report.xlsx', 'testcases/<screen-slug>.xlsx')
   refs = {o['ref'] for o in list_objects('strategy/strategy.xlsx','2_IntergrationTesting') if o['ref']}
   rep = check_coverage(sc, refs)
   print('missing:', sorted(rep.missing)); print('unknown:', sorted(rep.unknown))
   "
   ```
4. If `missing` is non-empty, add testcases for those refs and repeat. If
   `unknown` is non-empty, fix the wrong `strategy_ref` values. Stop when both
   are empty.

## Output
- `testcases/<screen-slug>.yaml` (the contract, reviewable/diffable)
- `testcases/<screen-slug>.xlsx` (team format, sheet "4.x <screen>")
- A short coverage summary (objects covered, any screen-specific extras)
