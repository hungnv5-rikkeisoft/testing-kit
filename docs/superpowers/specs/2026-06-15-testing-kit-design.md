# Testing-Kit — Thiết kế Toolkit Tự động hóa Kiểm thử

- **Mã tài liệu:** TK-DESIGN
- **Ngày tạo:** 2026-06-15
- **Nguồn căn cứ:** `strategy/strategy.xlsx` (Chiến lược kiểm thử CLKT v1.0.0) + plugin `webapp-testing` (Python Playwright)
- **Trạng thái:** Đã duyệt thiết kế, chờ review spec

## 1. Mục tiêu

Xây dựng một **framework tái sử dụng** (config-driven) bằng **Python + Playwright** để tự động hóa kiểm thử web app theo đúng Chiến lược kiểm thử của dự án, bao trùm 4 phần:

1. **Integration / UI testing** (sheet `2_IntergrationTesting`)
2. **System testing — user flows** (sheet `3_System_Testing`)
3. **API testing** (sheet `1_APITesting`)
4. **Báo cáo & Exit criteria** (sheet `6_Chỉ số & Báo cáo`)

Đồng thời **tự sinh checklist test case** từ các "Đối tượng testing" trong chiến lược để tester sử dụng.

Framework không gắn cứng với một app cụ thể: chuyển dự án chỉ cần đổi file cấu hình (URL, ngưỡng, tài khoản, thiết bị).

## 2. Phạm vi áp dụng

- **Trong phạm vi:** thư viện helper tái sử dụng, bộ test mẫu (chạy được trên HTML tĩnh mẫu, không cần app thật), trình sinh checklist, trình tạo báo cáo + cổng exit-criteria, CLI điều phối.
- **Ngoài phạm vi (YAGNI):** tích hợp Jira/CI cụ thể, JMeter/Postman collection, kiểm thử hiệu năng 3D (FPS/render) — chỉ chừa chỗ mở rộng, không triển khai ở bản này.

## 3. Lựa chọn kiến trúc

**Phương án được chọn: Framework dựa trên `pytest`.**

Lý do: pytest cung cấp sẵn đếm pass/fail, `parametrize` theo ma trận thiết bị, fixture cho browser & đăng nhập theo role, xuất JUnit XML + HTML — khớp gần như 1-1 với nhu cầu báo cáo & exit-criteria của sheet 6. Hai phương án còn lại (script Python thuần; Playwright Test runner Node/TS) bị loại vì lần lượt tốn công tự code lại phần báo cáo, và trái với lựa chọn "Python Playwright".

## 4. Cấu trúc thư mục

```
testing-kit/                     (gốc tại d:\Testing-kit)
├── config/
│   ├── config.example.yaml      # base_url, môi trường, timeout, ngưỡng hiệu năng, exit criteria
│   ├── devices.yaml             # ma trận sheet 4: Desktop 1920 Chrome, iPad gen5 Safari
│   └── users.example.yaml       # tài khoản theo role (test phân quyền)
├── toolkit/                     # THƯ VIỆN tái sử dụng (cốt lõi)
│   ├── __init__.py
│   ├── config.py                # load + validate YAML, áp giá trị mặc định từ chiến lược
│   ├── browser.py               # fixture Playwright, device profiles, helper điều hướng
│   ├── api_client.py            # gọi API + assert status/cấu trúc/thời gian (<600ms)
│   └── checks/
│       ├── __init__.py
│       ├── ui_checks.py         # bố cục, đủ component, responsive, console-log sạch, timing
│       ├── security_checks.py   # payload XSS/HTML, kiểm tra phân quyền A xem data B
│       └── perf_checks.py       # ngưỡng hiệu năng API/web
├── tests/                       # test theo dự án (kèm ví dụ mẫu)
│   ├── api/
│   ├── integration/
│   ├── system/
│   └── fixtures/sample.html     # trang HTML tĩnh để chứng minh helper hoạt động
├── checklists/                  # đầu ra: checklist sinh tự động
├── reports/                     # đầu ra: HTML + JUnit + JSON + exit-criteria
├── scripts/
│   ├── gen_checklist.py         # đọc strategy.xlsx → sinh checklist theo "Đối tượng testing"
│   ├── run.py                   # CLI: chọn layer/env, chạy, xuất báo cáo
│   └── with_server.py           # tái dùng từ plugin webapp-testing (quản lý vòng đời server)
├── conftest.py                  # fixtures pytest dùng chung + hook tổng hợp báo cáo
├── pytest.ini
├── requirements.txt
└── README.md
```

## 5. Thành phần & giao diện

Mỗi đơn vị có một mục đích rõ ràng, giao tiếp qua interface gọn để test độc lập.

### 5.1 `toolkit/config.py`
- **Làm gì:** đọc YAML, validate, áp giá trị mặc định bám chiến lược.
- **Dùng thế nào:** `cfg = load_config(path)` → object có `base_url`, `timeouts`, `thresholds`, `exit_criteria`, `devices`, `users`.
- **Phụ thuộc:** `pyyaml`.
- **Ngưỡng mặc định (từ chiến lược):** API `< 600ms`; web response `< 1.5s`; page load `< 2.5s`; exit `>= 95%` pass và `0` bug Critical/High.

### 5.2 `toolkit/browser.py`
- **Làm gì:** khởi tạo Playwright (chromium/webkit headless), áp device profile, helper `goto_and_wait` (chờ `networkidle`).
- **Dùng thế nào:** fixture `page` (parametrize theo `devices.yaml`).
- **Phụ thuộc:** `playwright`, `config.py`.

### 5.3 `toolkit/api_client.py`
- **Làm gì:** encode quy tắc check code trả về của sheet 1.3.3 (200 kiểm response body required/optional; 400/401/403 chỉ kiểm code + đủ trường hợp; business error 1–99 với HTTP 200 + header code), kiểm cấu trúc response, đo thời gian phản hồi.
- **Dùng thế nào:** `client.get(...).assert_status(200).assert_schema(schema).assert_under_ms(600)`.
- **Phụ thuộc:** `requests`, `config.py`.

### 5.4 `toolkit/checks/ui_checks.py`
- **Làm gì:** helper cho UI/Integration (sheet 2.3.1–2.3.3): đủ số lượng component, kiểm responsive đa kích thước, console log không có lỗi JS, đo Network timing, kiểm validate input.
- **Dùng thế nào:** `assert_components_present(page, selectors)`, `assert_console_clean(page)`, `assert_responsive(page, sizes)`, `measure_load_time(page)`.
- **Phụ thuộc:** `playwright` page, `config.py`.

### 5.5 `toolkit/checks/security_checks.py`
- **Làm gì:** bộ payload XSS/HTML injection sẵn (vd `<script>alert('Hello')</script>`), helper nhập payload và xác nhận không thực thi/hiển thị đúng; kiểm phân quyền (đăng nhập user B mở URL data user A → báo lỗi/không có quyền).
- **Dùng thế nào:** `assert_no_xss(page, input_selector)`, `assert_permission_denied(page, url, user)`.

### 5.6 `toolkit/checks/perf_checks.py`
- **Làm gì:** tiện ích kiểm ngưỡng hiệu năng dùng chung cho web & API, trả kết quả đo để báo cáo tổng hợp.

### 5.7 `scripts/gen_checklist.py`
- **Làm gì:** đọc `strategy/strategy.xlsx`, trích các dòng "Đối tượng testing" + "Cách thức thực hiện và xác nhận" của từng layer (sheet 1/2/3) → sinh checklist Markdown (và tùy chọn xlsx) trong `checklists/`.
- **Dùng thế nào:** `python scripts/gen_checklist.py --layer integration --out checklists/`.
- **Phụ thuộc:** đọc xlsx qua thư viện nhẹ (`openpyxl` nếu có, fallback parse XML như đã làm khi khảo sát).

### 5.8 `conftest.py` + báo cáo
- **Làm gì:** fixtures dùng chung (config, page, api_client, user theo role); hook `pytest_sessionfinish` tổng hợp JSON (tổng case, pass/fail %, bug, coverage theo module) và áp **cổng exit-criteria** — exit code khác 0 nếu `< 95%` pass hoặc còn bug Critical/High.
- **Đầu ra:** `reports/report.html` (pytest-html), `reports/junit.xml`, `reports/summary.json`.

## 6. Luồng dữ liệu

```
config.yaml ─► fixtures (browser/device/user) ─► test gọi toolkit.checks.* & api_client
            ─► kết quả ─► pytest collector ─► reports/ (HTML/JUnit/JSON) ─► exit-criteria gate
strategy.xlsx ─► gen_checklist.py ─► checklists/*.md   (luồng độc lập)
```

## 7. Ma trận thiết bị (sheet 4)

Test mẫu được `@pytest.mark.parametrize` theo `devices.yaml`:
- **Desktop (FULL HD 1920px) – Windows – Chrome (chromium)** — test full GUI + Function.
- **iPad gen5 – Safari (webkit) – iOS, 1536×2048** — đánh dấu `@pytest.mark.tablet`, dùng cho tập chọn lọc ~25%.

## 8. Xử lý lỗi

- Config thiếu/sai schema → báo lỗi rõ ràng, dừng sớm (fail fast).
- Server/URL không truy cập được → test skip có lý do, ghi vào báo cáo (đúng mục 2.3.3 "không kết nối được server").
- Helper assert thất bại → thông điệp nêu rõ kỳ vọng vs thực tế + ngưỡng tham chiếu.

## 9. Chiến lược kiểm thử cho chính toolkit

- Mỗi helper trong `toolkit/` có unit test nhỏ chạy trên `tests/fixtures/sample.html` (file:// hoặc server tĩnh) để chứng minh hoạt động mà **không cần app thật**.
- `gen_checklist.py` có test xác nhận sinh đúng số mục từ một xlsx mẫu thu nhỏ.
- `api_client.py` test với một HTTP server giả lập cục bộ (vd `http.server` hoặc `pytest-httpserver`).

## 10. Tiêu chí hoàn thành (Definition of Done)

- `pip install -r requirements.txt` + `playwright install` chạy được.
- `pytest` chạy bộ test mẫu xanh trên `sample.html`, sinh `reports/` đầy đủ.
- `scripts/gen_checklist.py` sinh checklist cho cả 3 layer từ `strategy.xlsx`.
- README mô tả cách cấu hình cho một dự án mới và cách chạy từng layer.

## 11. Điểm mở rộng tương lai (không làm bản này)

- Tích hợp CI (GitHub Actions/Jenkins) đọc `junit.xml`.
- Kết nối Jira tạo bug tự động từ test fail.
- Kiểm thử hiệu năng 3D (FPS, render time, model size) — mục 6.1 chiến lược.
- Sinh báo cáo daily/sprint tổng hợp nhiều lần chạy.
