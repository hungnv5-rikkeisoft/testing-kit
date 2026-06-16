# Testing-Kit — Session Handoff

> Cập nhật: 2026-06-15. Tài liệu này để một session/agent khác tiếp nối công việc.
> Đọc file này trước, rồi mới mở spec/plan chi tiết.

## 1. Toolkit này là gì

Toolkit tự động hóa kiểm thử web theo chiến lược QA của team (`strategy/strategy.xlsx`)
và template báo cáo của team (`template/Format test case + Test report.xlsx`).
Mục tiêu cuối là một **pipeline 3 giai đoạn** nối qua một "định dạng test case" chung (YAML):

```
Tài liệu thiết kế + strategy.xlsx
  │ Stage 1: SINH test case (AI hybrid)          ✅ XONG
  ▼  testcases/<screen>.yaml  ◄──►  testcases/<screen>.xlsx (template sheet 4.x)
  │ Stage 2: CHẠY test case (agent + Playwright MCP, screenshot mỗi bước)  ✅ XONG
  ▼  điền result + evidence/<screen>/<browser>/<TestcaseID>/step_N.png
  │ Stage 3: BÁO CÁO + đính kèm evidence          ✅ XONG
  ▼  reports/test_report.xlsx (sheet "3. Test Report" + sheet "Evidence" nhúng ảnh)
```

## 2. Trạng thái hiện tại

- **Test suite: 47 passed** (`./.venv/Scripts/python.exe -m pytest -q`).
- Git: Stage 3 nằm trên branch `stage3-reporting` (rẽ từ `main`). Stage 2 ở `stage2-test-execution`. Stage 1 + nền ở `main`.
  - `8ce9d0c` init → `4f9b6d6` toolkit nền → `df654e8` gen_report → `7c1612c` Stage 1 (trên main)
  - Branch `stage2-test-execution`: spec + plan + Task 1–6 (schema note, runlog, render result cols,
    flask dep, demo app, skill run-testcases). Chạy `git log --oneline` để xem chi tiết.

### Đã hoàn thành
- **Nền tảng** (`toolkit/`): `config.py` (YAML, ngưỡng chiến lược) + `report.py` (`Summary` + cổng
  exit-criteria), dùng lại bởi `tcformat/report_data.py`.
  > Lưu ý: lớp pytest-theo-layer cũ (`scripts/run.py`, `conftest.py`, `toolkit/browser|api_client|checks`,
  > `tests/{api,integration,system,demo}`) **đã bị gỡ** — không phải kiến trúc hiện tại. Việc chạy test
  > giờ do skill `run-testcases` (Playwright MCP) đảm nhiệm, không qua pytest.
- **Báo cáo** (`scripts/gen_report.py --yaml`): đọc result trong YAML → điền workbook template (Stage 3).
- **Stage 1** (`tcformat/`): schema YAML, strategy refs, coverage, render xlsx + skill `generate-testcases`.
  Đã chạy thử end-to-end: 1 màn hình mẫu → 24 testcase, coverage 100%, xlsx đúng format.
- **Stage 2** (chạy test case + evidence):
  - `tcformat/runlog.py` — helper tất định: `evidence_dir()` + `record_result()` ghi result/evidence/note
    ngược vào YAML (CLI `python -m tcformat.runlog record|evidence-dir`). `schema.py` thêm field `note`
    + hằng `VALID_STATUSES`/`VALID_BROWSERS`. `render_xlsx` điền cột result K..R từ YAML.
  - `demo/app.py` — Flask demo "Basic Information Input" (login/role/cascading/validate/XSS) làm app dưới test.
  - Skill `.claude/skills/run-testcases/SKILL.md` — quy trình agent + Playwright MCP, screenshot mỗi step.
  - Đã chạy end-to-end thật lát cắt 4 testcase (UI_02, FN_02, FN_03, NF_04) trên Chrome → 6 ảnh
    `evidence/basic-information-input/chrome/<ID>/step_N.png` + result điền vào YAML + xlsx (tất cả OK).
- **Stage 3** (báo cáo + evidence):
  - `tcformat/report_data.py` — `aggregate(screens)` đếm OK/NG/N·A trên **lượt đã chạy** (status≠null),
    map `priority`→severity (High/Medium/Low), dựng `toolkit.report.Summary` + áp cổng exit-criteria.
  - `tcformat/report_sheet.py` — helper ghi sheet "3. Test Report" (find header / clear region /
    write_screen_row), dùng bởi `tcformat/report_xlsx.py`.
  - `tcformat/report_xlsx.py` — `write_report()` ghi sheet "3. Test Report" (tổng hợp + khối exit-criteria
    PASS/FAIL, pass-rate, executed/planned) và sheet **"Evidence"** (nhúng ảnh `add_image` + caption +
    hyperlink mở full-size; ảnh thiếu file → "(file missing)", không crash).
  - `scripts/gen_report.py --yaml <screen>.yaml` — đường CLI Stage 3 (duy nhất), in tóm tắt và **exit
    non-zero nếu cổng fail**.
  - Đã chạy thật trên `basic-information-input.yaml`: executed 4/48, pass 100%, 6 ảnh nhúng, exit PASS.

### Chưa làm
- (Tuỳ chọn) Chạy nốt các testcase còn lại / trên iPad-Safari bằng skill `run-testcases` rồi regenerate
  báo cáo cuối. Hiện mới chạy 4 lượt Chrome nên độ phủ thực thi còn thấp (báo cáo ghi rõ executed/planned).

## 3. Môi trường (QUAN TRỌNG)

- Máy Windows, project ở **ổ D:** (`d:\Testing-kit`). Temp của Python ở **ổ C:** → lưu ý
  lỗi cross-drive khi viết test dùng `tmp_path` chạy pytest subprocess (xem `tests/unit/test_conftest_summary.py`
  đã xử lý bằng cách root temp dir trong repo).
- **Có 2 Python:** bare `python` = 3.14 (một số wheel có thể thiếu). Dùng
  **venv 3.13** đã tạo sẵn: `d:/Testing-kit/.venv/Scripts/python.exe`. Mọi lệnh python/pytest dùng đường dẫn này.
- Nếu `.venv` bị xóa, tạo lại:
  ```
  py -3.13 -m venv .venv
  ./.venv/Scripts/python.exe -m pip install -r requirements.txt
  ```
  (Stage 2 dùng Playwright **MCP**, không cài package Python playwright.)
- Scripts trong `scripts/` tự thêm repo-root vào `sys.path` để import `tcformat` khi chạy trực tiếp.
- IDE có thể báo "Cannot find module pytest" — đó là false positive (VS Code trỏ Python 3.14), bỏ qua.

## 4. Cấu trúc & file chính

| Thư mục/file | Vai trò |
|---|---|
| `strategy/strategy.xlsx` | Chiến lược test (8 sheet: API/Integration/System/Env/Deploy/Metrics) |
| `template/Format test case + Test report.xlsx` | Template team: sheet "3. Test Report", "4.1.*" testcase, "5. Checklist" |
| `tcformat/schema.py` | Contract YAML test case (`Screen`/`Testcase`/`Result`) + validate |
| `tcformat/strategy.py` | `list_objects(xlsx,sheet)`, `all_refs(xlsx)` → ref dạng `"2.3.1#1"` |
| `tcformat/coverage.py` | `check_coverage(screen, refs)` → covered/missing/unknown |
| `tcformat/render_xlsx.py` | `render(screens, template, out)` → xlsx sheet "4.x" |
| `.claude/skills/generate-testcases/SKILL.md` | Quy trình AI sinh test case (Stage 1) |
| `toolkit/` | Core dùng chung: `config.py` (ngưỡng) + `report.py` (exit-criteria) |
| `scripts/gen_report.py` | CLI Stage 3: YAML → workbook báo cáo |
| `docs/superpowers/specs/`, `docs/superpowers/plans/` | Spec & plan từng stage |

**Thư mục sinh tự động (gitignore):** `reports/`, `testcases/`, `.venv/`.

## 5. Lệnh hay dùng

```bash
# Chạy toàn bộ unit test của framework
./.venv/Scripts/python.exe -m pytest -q

# Stage 3: YAML -> báo cáo team (sheet "3. Test Report" + "Evidence")
./.venv/Scripts/python.exe scripts/gen_report.py --yaml testcases/basic-information-input.yaml --out reports/test_report.xlsx

# Stage 1: sinh test case (dùng skill generate-testcases trong Claude Code, hoặc thủ công)
./.venv/Scripts/python.exe -c "from tcformat.schema import load_screen; from tcformat.render_xlsx import render; from tcformat.coverage import check_coverage; from tcformat.strategy import list_objects; sc=load_screen('testcases/<screen>.yaml'); render([sc],'template/Format test case + Test report.xlsx','testcases/<screen>.xlsx'); refs={o['ref'] for o in list_objects('strategy/strategy.xlsx','2_IntergrationTesting') if o['ref']}; rep=check_coverage(sc,refs); print('missing',sorted(rep.missing),'unknown',sorted(rep.unknown))"
```

Ví dụ output Stage 1 đã chạy (regenerate được, đang gitignore):
`testcases/basic-information-input.yaml` + `.xlsx` (24 testcase, coverage 100%).

## 6. Stage 3 — báo cáo + đính kèm evidence (ĐÃ XONG)

Stage 2 ghi `result` (status/tester/date/note/evidence cho chrome|safari) vào `testcases/<screen>.yaml`.
Stage 3 đọc các `result` đó → sinh báo cáo team + nhúng evidence. Cách dùng:

```bash
# Sinh báo cáo từ YAML (1 hoặc nhiều --yaml). Exit non-zero nếu cổng exit-criteria fail.
./.venv/Scripts/python.exe scripts/gen_report.py --yaml testcases/basic-information-input.yaml \
    --out reports/test_report.xlsx
```

Output `reports/test_report.xlsx` là **MỘT workbook** chứa đủ (cùng nguồn YAML nên luôn đồng bộ):
- sheet **"4.x &lt;screen&gt;"** — chi tiết testcase + cột result (tái dùng `render_xlsx.render_into`),
- sheet **"3. Test Report"** — 1 dòng/màn hình + Total + khối exit-criteria PASS/FAIL, pass-rate, executed/planned,
- sheet **"Evidence"** — mỗi ảnh-step 1 dòng: ID/browser/step, ảnh nhúng, hyperlink mở full-size, note.

Quyết định thiết kế + chi tiết: spec/plan `...-stage3-report-evidence*`.

**Việc tiếp theo (tuỳ chọn):** tăng độ phủ thực thi — chạy nốt testcase còn lại / trên iPad-Safari bằng
skill `run-testcases`, rồi chạy lại lệnh trên để regenerate báo cáo cuối.

**Chạy lại Stage 2 (tham chiếu):** start demo `./.venv/Scripts/python.exe demo/app.py` (127.0.0.1:5005),
rồi dùng skill `run-testcases` với `testcases/basic-information-input.yaml`. Helper:
`python -m tcformat.runlog evidence-dir|record ...`. Tài khoản demo: a@example.com/a, b@example.com/b,
admin@example.com/admin, noperm@example.com/n.

## 7. Quy ước làm việc

- **Quy trình:** brainstorming → writing-plans → subagent-driven-development (skills `superpowers:*`). TDD, file nhỏ tập trung.
- **Git:** chỉ commit/add/push khi user xác nhận rõ ràng. **Không** thêm trailer `Co-Authored-By: Claude`. Message thuần.
  Branch mặc định: nên hỏi user trước khi tạo branch/PR.
- **Ngôn ngữ:** user trao đổi bằng tiếng Việt.
- Spec/plan các stage nằm ở `docs/superpowers/specs/` và `docs/superpowers/plans/`:
  - `2026-06-15-testing-kit-design.md` + `2026-06-15-testing-kit.md` (nền tảng)
  - `2026-06-15-stage1-testcase-generation-design.md` + `...-stage1-testcase-generation.md` (Stage 1)
  - `2026-06-15-stage2-test-execution-design.md` + `2026-06-15-stage2-test-execution.md` (Stage 2)

## 8. Cạm bẫy đã gặp (đừng lặp lại)

- Dùng nhầm Python 3.14 → import fail. Luôn dùng `.venv` 3.13.
- Playwright MCP lưu screenshot theo đường dẫn `filename` tương đối repo-root (output dir = repo-root),
  nên truyền thẳng `evidence/<screen>/<browser>/<id>/step_N.png` là ảnh nằm đúng chỗ.
- Console error khi chạy Stage 2 có thể chỉ là `favicon.ico 404` hoặc HTTP 400 từ test validate rỗng —
  không phải lỗi JS. Lọc đúng nguyên nhân trước khi chấm NG.
- argparse in `__doc__`/help ra console cp932 → tránh ký tự non-ASCII (em-dash) trong docstring module có CLI.
- pytest subprocess + `tmp_path` trên Windows cross-drive (C: vs D:) → conftest không load. Root temp dir trong repo.
- `report.session` không tồn tại trong pytest hook → dùng plugin-class (xem `conftest.py`).
- httpserver bind `localhost` → IPv6 chậm trên Windows → ép `127.0.0.1`.
- `render_xlsx` phải xóa HẾT vùng mẫu của template (tới hết `ws.max_row`), nếu không còn dòng mẫu `FUNCTION_0x` thừa.
