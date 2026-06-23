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
   run `./.venv/Scripts/tk-strategy --sheet 2_IntergrationTesting`
   (swap for 1_APITesting / 3_System_Testing as needed). Output is JSON.
   For any screen that calls an API, ALSO pull `1_APITesting` so HTTP-code
   techniques get generated.
4. The technique checklist (element kind -> techniques): bundled at
   `tcformat/data/checklists.yaml`, overridable via the `checklists_path`
   config key. This is the fan-out matrix — do not hand-wave it.

## Process

1. **Build the element inventory FIRST.** From the design docs / Figma, write
   `testcases/<screen-slug>.inventory.yaml` listing EVERY interactive element
   and api endpoint (schema: `tcformat/inventory.py`):
   - `kind`: button | input | select | link | api | screen
   - selects: `options_source` (`db:<table>.<col>` or `hardcode:[...]`),
     `default`, `depends_on`
   - apis: `method`, `path`, `params`
   Pause and have a human confirm the inventory is complete (e.g. all preset
   buttons present) before writing cases — a missing element here becomes
   missing coverage downstream.

   **(Advisory) Đối chiếu với app thật:** nếu app đang chạy, dùng Playwright MCP
   `browser_snapshot` chụp cây element của màn, lưu thành JSON
   `{elements:[{role,name}], forms:[{action,method}]}`, rồi chạy:
   ```bash
   ./.venv/Scripts/tk-inventory-audit --inventory testcases/<screen>.inventory.yaml \
       --snapshot <snapshot.json> --out reports/<screen>_inventory-audit.md
   ```
   Đối chiếu các cảnh báo SUSPECTED MISSING / STALE / FORM-WITHOUT-API trước khi
   chốt inventory. Đây là advisory (luôn exit 0) — không tự sửa, người/AI quyết định.

2. **Fan out into cases.** For EACH strategy testing object relevant to the
   screen, AND for EACH (element x technique) implied by the checklist
   (element kinds + the once-per-screen `screen` techniques), write a testcase.
   Rules:
   - ONE element / ONE scenario per testcase (never group multiple buttons or
     multiple validation techniques into one case).
   - Tag every case with `category`, `technique`, and `target` (the element id,
     or `screen` for cross-cutting cases). Keep `strategy_ref` where the case
     maps to a strategy object.
   - Write steps/expected concretely enough for a browser agent to execute.
   - An `expected` item may be a plain string OR a structured assertion dict
     (mọi key optional): `{field, value, enabled, required, button_state,
     request, redirect}`. Một dict mô tả ĐÚNG MỘT subject (`field`); nhiều field
     → nhiều phần tử trong list. Ưu tiên dạng dict cho case Validation/Function
     khi một assertion chính xác (giá trị field, enabled/required, lời gọi API,
     redirect) rõ hơn câu chữ. Khi render xlsx nó được *làm phẳng* thành text
     (vd `Field A = XXX; Field B disabled`) nên format deliverable KHÔNG đổi.

3. **Validate + render + check coverage refs (breadth):**
   ```
   ./.venv/Scripts/python.exe -c "
   from tcformat.schema import load_screen
   from tcformat.render_xlsx import render
   from tcformat.coverage import check_coverage
   from tcformat.strategy import list_objects
   from tcformat.resources import default_template, default_strategy
   sc = load_screen('testcases/<screen-slug>.yaml')
   render([sc], default_template(), 'testcases/<screen-slug>.xlsx')
   refs = {o['ref'] for o in list_objects(default_strategy(),'2_IntergrationTesting') if o['ref']}
   cov = check_coverage(sc, refs)
   print('missing refs:', sorted(cov.missing)); print('unknown refs:', sorted(cov.unknown))
   "
   ```
   Lặp lại cho đến khi `missing` và `unknown` đều rỗng.

4. **Kiểm tra độ phủ chiều sâu (bắt buộc — cổng Stage 1):** Sau khi sinh case, chạy:
   ```bash
   ./.venv/Scripts/tk-coverage --screen testcases/<screen>.yaml --config config.yaml
   ```
   `tk-coverage` nay chạy **completeness lint (hard gate)** TRƯỚC depth:
   - R1: nếu có testcase với assertion `request`/`redirect` thì inventory phải có
     element `kind: api` (hoặc khai báo `absent.api: "<lý do>"`).
   - R3: mọi `target` của testcase phải là `screen` hoặc id element có thật.
   Vi phạm → exit non-zero, section "INVENTORY COMPLETENESS" liệt kê cách sửa
   (thêm element, hoặc thêm `absent.<kind>: "<lý do>"` vào inventory).

   CLI exit **non-zero** khi còn ô element×technique chưa có case và chưa justify.
   Nếu fail: bổ sung test case cho ô thiếu, HOẶC thêm `skip_techniques: [<technique>, ...]`
   (kèm lý do rõ ràng) cho element trong `testcases/<screen>.inventory.yaml`, rồi chạy lại.
   **Chỉ chuyển sang Stage 2 khi `tk-coverage` exit 0.**
   Cảnh báo (`unknown techniques`, `kinds without checklist`) cần xem và xử lý — sửa tag sai
   hoặc bổ sung kind vào `checklists.yaml` — nhưng KHÔNG chặn gate.

5. **Critic review (bán-tự-động — bước cuối Stage 1):** Chạy:
   ```bash
   ./.venv/Scripts/tk-critic --screen testcases/<screen>.yaml --config config.yaml \
       [--out reports/<screen>_critic.md]
   ```
   - **Cổng nhẹ:** nếu có `depends_on` chưa-liên-kết (exit 1), bổ sung case kiểm tương
     tác field con↔cha (case target field con, có nhắc tới field cha) rồi chạy lại.
     _(Lưu ý: kiểm tra liên kết là heuristic khớp substring id/label của field cha trong
     text của case — với id/label ngắn, một dấu `✓ đã có case` vẫn nên được người liếc
     mắt kiểm lại.)_
   - **Phần phán đoán (AI):** với mỗi nhóm gắn `⚠ NGOÀI MA TRẬN` (đặc biệt `BusinessRule`,
     `UI`) và các ràng buộc required-theo-mode / liên field, **tự đối chiếu design doc** và
     bổ sung case còn thiếu — ma trận cơ học (`tk-coverage`) KHÔNG bắt được các nhóm này.
   - Chỉ kết thúc Stage 1 khi `tk-coverage` exit 0 **và** đã review xong các nhóm `⚠` của critic.

## Output

- `testcases/<screen-slug>.inventory.yaml` (element inventory, reviewable)
- `testcases/<screen-slug>.yaml` (the contract, reviewable/diffable; cases
  tagged with category/technique/target)
- `testcases/<screen-slug>.xlsx` (team format, sheet "4.x <screen>")
- A short coverage summary: objects covered (bước 3); depth_rate và justified
  depth gaps từ `tk-coverage` (bước 4).
- `reports/<screen>_critic.md` (tuỳ chọn, từ `--out`): checklist review theo nhóm
  + nhóm cần AI/người phán đoán + depends_on chưa liên kết.
