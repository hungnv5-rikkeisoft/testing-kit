# Stage 2 — Test Execution + Evidence (Design Spec)

> Ngày: 2026-06-15. Ngôn ngữ: tiếng Việt (đồng bộ strategy/template).
> Đọc `HANDOFF.md` mục 6 và spec Stage 1 trước.

## 1. Mục tiêu

Stage 2 là khâu **CHẠY** trong pipeline 3 giai đoạn của Testing-Kit:

```
Stage 1 (SINH) → testcases/<screen>.yaml  ──►  Stage 2 (CHẠY)  ──►  Stage 3 (BÁO CÁO)
```

Một **AI agent** đọc các bước (`steps`) viết bằng ngôn ngữ tự nhiên trong
`testcases/<screen>.yaml`, điều khiển trình duyệt qua **Playwright MCP**
(`mcp__plugin_playwright_playwright__browser_*`), **chụp screenshot mỗi bước** làm
bằng chứng, chấm mỗi testcase `OK / NG / N/A` theo `expected`, rồi ghi kết quả +
đường dẫn evidence **ngược vào YAML** bằng một helper Python **tất định**.

Vì chưa có app thật, ta dựng một **demo app (HTML + Flask)** đóng vai "app dưới
test" để chứng minh pipeline end-to-end với chính `testcases/basic-information-input.yaml`
(24 testcase) đã sinh ở Stage 1.

### Quyết định đã chốt (brainstorm 2026-06-15)
1. **Demo app:** Static HTML + mini Flask backend (chạy được gần như toàn bộ 24
   testcase kể cả login/phân quyền/server-down).
2. **Runner:** Skill agent điều khiển Playwright MCP **+** helper Python tất định
   ghi sổ (TDD cho helper). Agent **không** sửa YAML tay.
3. **Chấm điểm:** 1 `status` cho mỗi testcase × mỗi browser; `N/A` kèm `note` lý do
   cho bước không tự động hoá được. Screenshot mỗi step làm evidence.
4. **Phạm vi session đầu:** Xây đủ hạ tầng + chạy end-to-end một lát cắt 3–5
   testcase tiêu biểu (1 UI, 1 FUNCTION validate, 1 XSS, +1 phân quyền).

## 2. Data flow

```
                    config/config.yaml (base_url, port)   config/users.yaml (role)
                                  │
testcases/<screen>.yaml ─► [skill run-testcases: agent + Playwright MCP] ◄─ demo app (Flask :PORT)
                                  │  mỗi step → browser_take_screenshot
                                  ▼
                    evidence/<screen-slug>/<browser>/<tc_id>/step_N.png
                                  │
                                  ▼  (agent gọi qua Bash)
                    tcformat/runlog.record_result() ─► điền `result` vào YAML
                                  │
                                  ▼
                    render_xlsx (điền cột result 11–18) ─► testcases/<screen>.xlsx có kết quả
```

YAML là **nguồn sự thật** của kết quả. Stage 3 (ngoài phạm vi) sẽ đọc `result` từ
YAML để sinh báo cáo + nhúng evidence.

## 3. Thành phần

### 3.1 Demo app — `demo/`

Một Flask app nhỏ implement đúng màn hình "Basic Information Input" để các testcase
Stage 1 chạy được.

- `demo/app.py` (Flask):
  - `GET /login`, `POST /login` — đăng nhập bằng tài khoản trong `config/users.yaml`
    (hoặc bộ user hardcode tương đương trong demo); set session cookie kèm `role`.
  - `GET /` — yêu cầu đăng nhập; nếu user thiếu quyền → trang lỗi "không có quyền"
    (phục vụ NF_07). Render màn hình Basic Information Input.
  - `GET /api/municipalities?prefecture=<id>` — trả danh sách municipality theo
    prefecture (cascading; phục vụ FN_03).
  - `POST /api/basic-info` — validate field bắt buộc (rỗng → 400 + thông báo lỗi;
    hợp lệ → 200). Phản hồi/echo dữ liệu text **an toàn XSS** (escape / textContent).
  - Data của user A không truy cập được bởi user B → từ chối/403 (phục vụ NF_08).
- Front-end (template Jinja hoặc 1 file HTML tĩnh + JS):
  - Usage: 2 button (Residential / Industrial), mặc định chưa chọn.
  - Prefecture dropdown; Municipality dropdown **disable** tới khi chọn Prefecture;
    **đổi Prefecture sẽ clear** Municipality (FN_03).
  - Submit: trống field bắt buộc → hiển thị lỗi validate (FN_02); hợp lệ → màn hình
    hoạt động đúng (FN_04). Chống double-submit (NF_09).
  - Mọi giá trị người dùng nhập hiển thị bằng `textContent` → không thực thi script
    (NF_04 XSS).
- Cổng: lấy từ `config.yaml` (`base_url`/port riêng cho demo, mặc định ví dụ
  `http://localhost:5005`). Khởi chạy bằng `scripts/with_server.py
  --server "<python> demo/app.py" --port <PORT> -- <cmd>` hoặc agent tự start nền
  qua Bash khi chạy skill.
- `flask` được thêm vào `requirements.txt` (cài vào `.venv` 3.13).

**Không tự động hoá được trên demo** (ghi `N/A` + note): so khớp Figma (UI_03),
đối chiếu font/màu qua DevTools Styles (UI_04), đo memory trình duyệt (NF_05),
nhất quán đa thiết bị nếu chỉ chạy 1 browser (UI_08).

### 3.2 Helper tất định — `tcformat/runlog.py` (TDD)

Chỉ lo phần ghi sổ tất định; **không** điều khiển trình duyệt.

```python
def evidence_dir(screen_slug: str, browser: str, tc_id: str) -> Path
# Tạo & trả về evidence/<screen-slug>/<browser>/<tc_id>/  (mkdir -p)

def record_result(yaml_path, tc_id, browser, status,
                  evidence=None, note=None, bug_id=None,
                  tester=None, date=None) -> None
# load_screen → tìm testcase theo id → set BrowserResult của `browser`
# (chrome|safari) → dump_screen ghi lại. Giữ nguyên các testcase/kết quả khác.
```

Quy tắc:
- `status` phải ∈ `{"OK", "NG", "N/A"}` (raise `SchemaError`/`ValueError` nếu sai).
- `browser` phải ∈ `{"chrome", "safari"}`.
- `tc_id` không tồn tại → raise.
- `evidence` là list đường dẫn (str) tương đối repo-root; ghi đè list cũ của lần
  chạy đó.
- Round-trip: sau `record_result`, `load_screen` đọc lại đúng giá trị đã ghi.

CLI để agent gọi qua Bash:
```
python -m tcformat.runlog evidence-dir --screen <slug> --browser chrome --id UI_01
python -m tcformat.runlog record --yaml testcases/<s>.yaml --id UI_01 \
    --browser chrome --status OK --note "" --evidence a.png --evidence b.png
```

### 3.3 Sửa schema nhỏ — `tcformat/schema.py`

- Thêm field `note: str | None = None` vào `BrowserResult` (và `_browser_result`,
  cùng `asdict`/`dump_screen` tự bao gồm).
- Thêm hằng `VALID_STATUSES = {"OK", "NG", "N/A"}`. **Validate ở `record_result`,
  KHÔNG ở `load_screen`** (để YAML cũ với `status: null` vẫn load được).
- Không phá vỡ YAML/round-trip hiện có (`tests/` Stage 1 vẫn xanh).

### 3.4 Mở rộng `render_xlsx` — điền cột result

`render_xlsx` hiện để trống cột 11–18 ("left blank for Stage 2"). Stage 2 điền các
cột result từ `tc.result` khi có giá trị (status/bug_id/note cho Chrome & Safari),
giữ trống nếu chưa chạy. Ánh xạ cột cụ thể đối chiếu template
`Format test case + Test report.xlsx` lúc implement (đọc header hàng tiêu đề result).

### 3.5 Skill — `.claude/skills/run-testcases/SKILL.md`

Quy trình agent (giống `generate-testcases` về văn phong):

1. **Chuẩn bị:** đọc `config/config.yaml` (base_url/port) + `config/users.yaml`
   (role). Bảo đảm demo app đang chạy (start nền nếu cần). Mở browser MCP.
2. **Cho mỗi testcase** (theo danh sách id được yêu cầu, hoặc tất cả):
   1. `evidence_dir(...)` để lấy thư mục evidence.
   2. Reset trạng thái: navigate `base_url`; nếu `precondition` nhắc role → login
      đúng user qua form `/login`.
   3. Thực thi **từng step NL** qua MCP (`browser_navigate/click/type/select_option/
      press_key/...`), tự chọn selector từ `browser_snapshot`.
   4. **Sau mỗi step:** `browser_take_screenshot` → `evidence/.../step_N.png`.
   5. Đánh giá `expected` (qua snapshot/console/network). Chấm:
      - `OK` nếu mọi `expected` đạt.
      - `NG` nếu có `expected` sai → ghi `note` mô tả bug (+ `bug_id` nếu có).
      - `N/A` nếu step không tự động hoá được → `note` nêu lý do.
   6. Kiểm tra phụ tất định khi phù hợp: `toolkit/checks` (console-clean cho NF_01,
      perf timing NF_02/NF_03, XSS-safe cho NF_04) — lai keyword.
   7. Gọi `python -m tcformat.runlog record ...` ghi result + evidence + note.
3. **Quy ước dừng:** step fail giữa chừng → chấm testcase `NG`, ghi note, **tiếp tục
   testcase kế** (không dừng cả phiên).
4. **Đầu ra:** YAML có `result` đã điền + cây `evidence/` + (tuỳ chọn) re-render xlsx.

## 4. Test (TDD trước)

- `tests/unit/test_runlog.py`
  - `evidence_dir` trả đúng path & tạo thư mục.
  - `record_result` round-trip status/evidence/note qua `load_screen`.
  - `tc_id` sai → raise; `status` sai → raise; `browser` sai → raise.
  - Ghi 1 testcase không đụng kết quả testcase khác.
- `tests/unit/test_schema_note.py` — round-trip field `note`.
- `tests/unit/test_render_result_cols.py` — render điền đúng cột result khi có
  `result`; vẫn trống khi chưa chạy.
- `tests/demo/test_demo_app.py` (Flask test client) — login OK/sai; cascading
  municipalities; validate field rỗng → lỗi; XSS echo an toàn (không trả script
  thô); phân quyền NF_07/NF_08 cơ bản.
- **Bằng chứng end-to-end (thủ công, không phải pytest):** chạy skill cho 3–5
  testcase → sinh evidence thật + YAML có result. Ghi lại lát cắt đã chạy.

Toàn bộ chạy bằng `./.venv/Scripts/python.exe -m pytest -q` phải xanh (gồm 41 test
cũ + test mới).

## 5. Evidence & gitignore

- Layout: `evidence/<screen-slug>/<browser>/<tc_id>/step_N.png`.
- Thêm `evidence/` vào `.gitignore` (như `reports/`, `testcases/`, `checklists/`).

## 6. Ngoài phạm vi (YAGNI cho Stage 2)

- **Stage 3** (gen_report đọc `result` từ YAML + nhúng/đính kèm evidence vào báo
  cáo) — chỉ để schema + đường dẫn evidence sẵn sàng, không implement.
- Chạy đủ 24 testcase / cả iPad-Safari trong session đầu (làm sau, skill hỗ trợ
  sẵn cả hai browser).
- Tích hợp CI/Jira, JMeter/Postman (đã YAGNI từ spec gốc).

## 7. Definition of Done (Stage 2)

- `flask` trong `requirements.txt`; `pip install` vào `.venv` thành công.
- `demo/app.py` chạy được; phục vụ màn hình Basic Information Input + các API.
- `tcformat/runlog.py` + sửa schema + mở rộng render: `pytest -q` xanh toàn bộ.
- Skill `run-testcases` mô tả đủ để agent chạy end-to-end.
- Đã chạy thật 3–5 testcase: có `evidence/.../step_N.png` + `testcases/
  basic-information-input.yaml` có `result` đã điền cho lát cắt đó.
- Cập nhật `HANDOFF.md` (Stage 2 ✅, hướng Stage 3).

## 8. Cạm bẫy lưu ý (kế thừa HANDOFF mục 8)

- Luôn dùng `.venv` 3.13 (`d:/Testing-kit/.venv/Scripts/python.exe`), không phải
  Python 3.14 bare.
- Windows cross-drive temp (C: vs D:) khi test dùng `tmp_path` + subprocess.
- httpserver/Flask bind `localhost` → ép `127.0.0.1` tránh độ trễ IPv6 Windows.
- `render_xlsx` phải xoá hết vùng mẫu template trước khi ghi (đã xử lý ở Stage 1).
- Playwright MCP do agent điều khiển trong phiên Claude Code — **không** gọi được
  từ Python thuần; helper Python chỉ ghi sổ.
