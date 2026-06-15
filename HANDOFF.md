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
  │ Stage 3: BÁO CÁO + đính kèm evidence          ⬜ CHƯA LÀM (đã có gen_report nền)
  ▼  reports/test_report.xlsx (sheet "3. Test Report")
```

## 2. Trạng thái hiện tại

- **Test suite: 63 passed** (`./.venv/Scripts/python.exe -m pytest -q`).
- Git: Stage 2 nằm trên branch `stage2-test-execution` (rẽ từ `main`). Stage 1 + nền ở `main`.
  - `8ce9d0c` init → `4f9b6d6` toolkit nền → `df654e8` gen_report → `7c1612c` Stage 1 (trên main)
  - Branch `stage2-test-execution`: spec + plan + Task 1–6 (schema note, runlog, render result cols,
    flask dep, demo app, skill run-testcases). Chạy `git log --oneline` để xem chi tiết.

### Đã hoàn thành
- **Nền tảng** (`toolkit/`): config (YAML, ngưỡng chiến lược), browser (Playwright + device profiles),
  api_client (status/schema/<600ms/business-code), checks (ui/security/perf), report (exit-criteria).
  `conftest.py` sinh `reports/summary.json` + cổng exit-criteria. `scripts/run.py` CLI chạy theo layer.
- **Báo cáo** (`scripts/gen_report.py`): JUnit XML → điền sheet "3. Test Report" của template.
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

### Chưa làm
- **Stage 3** (xem mục 6) — đọc `result` từ YAML → gen_report + nhúng/đính kèm evidence.

## 3. Môi trường (QUAN TRỌNG)

- Máy Windows, project ở **ổ D:** (`d:\Testing-kit`). Temp của Python ở **ổ C:** → lưu ý
  lỗi cross-drive khi viết test dùng `tmp_path` chạy pytest subprocess (xem `tests/unit/test_conftest_summary.py`
  đã xử lý bằng cách root temp dir trong repo).
- **Có 2 Python:** bare `python` = 3.14 (THIẾU wheel cho playwright/pytest-httpserver). PHẢI dùng
  **venv 3.13** đã tạo sẵn: `d:/Testing-kit/.venv/Scripts/python.exe`. Mọi lệnh python/pytest dùng đường dẫn này.
- Nếu `.venv` bị xóa, tạo lại:
  ```
  py -3.13 -m venv .venv
  ./.venv/Scripts/python.exe -m pip install -r requirements.txt
  ./.venv/Scripts/python.exe -m playwright install chromium webkit
  ```
- Scripts (`scripts/gen_checklist.py`) tự thêm repo-root vào `sys.path` để import `tcformat` khi chạy trực tiếp.
- IDE có thể báo "Cannot find module pytest/playwright" — đó là false positive (VS Code trỏ Python 3.14), bỏ qua.
- httpserver test ép IPv4 (`tests/api/conftest.py`) để tránh độ trễ ~2s IPv6 loopback của Windows.

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
| `toolkit/` | Helpers tái dùng cho Stage 2 (browser/checks) + báo cáo |
| `scripts/run.py`, `gen_report.py`, `gen_checklist.py` | CLI chạy test / báo cáo / checklist |
| `docs/superpowers/specs/`, `docs/superpowers/plans/` | Spec & plan từng stage |

**Thư mục sinh tự động (gitignore):** `reports/`, `testcases/`, `checklists/`, `.venv/`.

## 5. Lệnh hay dùng

```bash
# Chạy toàn bộ test
./.venv/Scripts/python.exe -m pytest -q

# Chạy theo layer + xuất báo cáo
./.venv/Scripts/python.exe scripts/run.py --layer integration
./.venv/Scripts/python.exe scripts/run.py --layer integration --tablet

# Sinh checklist từ chiến lược
./.venv/Scripts/python.exe scripts/gen_checklist.py --sheet 2_IntergrationTesting --title "Integration/UI Testing"

# JUnit -> sheet "3. Test Report"
./.venv/Scripts/python.exe scripts/gen_report.py --chrome reports/integration-junit.xml --out reports/test_report.xlsx

# Stage 1: sinh test case (dùng skill generate-testcases trong Claude Code, hoặc thủ công)
./.venv/Scripts/python.exe -c "from tcformat.schema import load_screen; from tcformat.render_xlsx import render; from tcformat.coverage import check_coverage; from tcformat.strategy import list_objects; sc=load_screen('testcases/<screen>.yaml'); render([sc],'template/Format test case + Test report.xlsx','testcases/<screen>.xlsx'); refs={o['ref'] for o in list_objects('strategy/strategy.xlsx','2_IntergrationTesting') if o['ref']}; rep=check_coverage(sc,refs); print('missing',sorted(rep.missing),'unknown',sorted(rep.unknown))"
```

Ví dụ output Stage 1 đã chạy (regenerate được, đang gitignore):
`testcases/basic-information-input.yaml` + `.xlsx` (24 testcase, coverage 100%).

## 6. Việc tiếp theo: Stage 3 (báo cáo + đính kèm evidence)

Stage 2 đã ghi `result` (status/tester/date/note/evidence cho chrome|safari) vào `testcases/<screen>.yaml`.
Stage 3 đọc các `result` đó để sinh báo cáo team và đính kèm/nhúng evidence.

**Gợi ý phạm vi Stage 3 (cần brainstorm + spec + plan như các stage trước):**
1. Đọc `result` từ YAML (đã có `schema.load_screen`) → tổng hợp pass-rate, đếm OK/NG/N·A theo browser,
   số bug, áp cổng exit-criteria (≥95% pass, 0 Critical/High) — tái dùng `toolkit/report`.
2. Sinh/điền sheet "3. Test Report" của template từ YAML (hiện `gen_report.py` đi từ JUnit XML — cân nhắc
   thêm đường đi từ YAML, hoặc map result YAML → cùng định dạng).
3. Đính kèm evidence: nhúng ảnh `evidence/<screen>/<browser>/<id>/step_N.png` vào xlsx (openpyxl `add_image`)
   hoặc liên kết đường dẫn; quyết định nhúng-thật vs link khi brainstorm.
4. (Tuỳ chọn) chạy thêm các testcase còn lại / trên iPad-Safari bằng skill `run-testcases` trước khi báo cáo.

**Bắt đầu Stage 3 bằng:** skill `superpowers:brainstorming` (chốt: nhúng ảnh vs link, nguồn dữ liệu YAML vs JUnit)
→ `writing-plans` → `subagent-driven-development` (giống Stage 1/2).

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
