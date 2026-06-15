# Stage 1 — Sinh Test Case (AI Hybrid) — Thiết kế

- **Mã tài liệu:** TK-S1
- **Ngày tạo:** 2026-06-15
- **Căn cứ:** `strategy/strategy.xlsx`, `template/Format test case + Test report.xlsx`, plugin `webapp-testing`
- **Trạng thái:** Đã duyệt thiết kế, chờ review spec

## 0. Bối cảnh pipeline tổng thể (3 giai đoạn)

Toolkit là một pipeline tự động hóa kiểm thử hướng test-case, nối nhau qua **một định dạng test case chung (YAML)**:

```
Tài liệu thiết kế (text/md, DB/API, Figma/ảnh) + strategy.xlsx (đối tượng testing)
   │  Stage 1: SINH (AI hybrid)        ← TÀI LIỆU NÀY
   ▼
 testcases/<screen>.yaml  ◄──►  testcases/<screen>.xlsx (format template sheet 4.x)
   │  Stage 2: CHẠY (agent + Playwright MCP, screenshot mỗi bước)
   ▼
 results + evidence/<TestcaseID>/step_N.png
   │  Stage 3: BÁO CÁO
   ▼
 reports/test_report.xlsx (sheet "3. Test Report") + evidence links
```

Mỗi giai đoạn có spec/plan riêng, làm tăng dần. Tài liệu này chỉ đặc tả **Stage 1**. Định dạng YAML (mục 3) là hợp đồng chung cho cả 3 giai đoạn; Stage 1 chỉ ghi các trường đầu vào (định nghĩa test case), để trống các trường `result` cho Stage 2.

## 1. Mục tiêu Stage 1

Sinh test case dự án theo **đúng format template** của team, bằng cách AI đọc tài liệu thiết kế và soạn test case, **đảm bảo phủ 100% các "Đối tượng testing"** trong chiến lược. Đầu ra: YAML (review/diff được) + xlsx (đúng template, tester dùng được).

## 2. Phạm vi

- **Trong phạm vi:** schema + validator cho YAML test case; renderer YAML → xlsx template; bộ trích "đối tượng testing" từ strategy.xlsx + kiểm coverage; skill `generate-testcases` điều phối AI; demo trên một screen design mẫu.
- **Ngoài phạm vi (giai đoạn sau):** chạy test (Stage 2), capture evidence, báo cáo (Stage 3). Không tự động đọc Figma trong code — phần đọc ảnh/Figma là việc của AI trong skill (multimodal), không phải code tất định.

## 3. Định dạng test case chung (YAML contract)

Một file/màn hình: `testcases/<screen-slug>.yaml`.

```yaml
screen: "Basic Information Input"   # tên màn hình (template C1)
test_level: IT                      # IT | ST | UT (template C2)
created_by: "AI-draft"              # optional
source_docs:                        # optional, để truy vết
  - "docs/design/basic-info.md"
testcases:
  - id: UI_01                       # TestcaseID (template cột B)
    section: UI                     # UI | FUNCTION | ... (gom nhóm trong sheet)
    main_item: "Di chuyển màn hình" # Main item (C)
    middle_item: "Login thành công" # Middle item (D)
    minor_item: ""                  # Minor Item (E)
    type: IT                        # UT|IT|ST (template "Type", cột I)
    priority: High                  # Low|Medium|High (cột J)
    strategy_ref: "2.3.1#1"         # trỏ đối tượng testing trong strategy.xlsx
    precondition: "User đã có tài khoản"      # Pre-condition (F)
    steps:                          # Step (G) — danh sách bước NL
      - "User đăng nhập vào hệ thống"
      - "Click menu Basic Info"
    expected:                       # Expect (H)
      - "Hiển thị màn hình Basic Information"
    result:                         # Stage 2 điền; Stage 1 để mặc định null
      chrome: { status: null, bug_id: null, tester: null, date: null, evidence: [] }
      safari: { status: null, bug_id: null, tester: null, date: null, evidence: [] }
```

**Quy ước `strategy_ref`:** `"<section>#<stt>"`, vd `2.3.1#1` = sheet `2_IntergrationTesting`, mục `2.3.1`, đối tượng STT 1. Đây là khóa nối coverage.

**Giá trị hợp lệ:** `test_level`/`type` ∈ {UT, IT, ST}; `priority` ∈ {Low, Medium, High}; `status` (Stage 2) ∈ {OK, NG, N/A, null}.

## 4. Thành phần & giao diện

### 4.1 `tcformat/schema.py`
- **Làm gì:** dataclass `Testcase`, `Screen`, `Result`; `load_screen(path)->Screen` (parse YAML, validate), `dump_screen(screen, path)`; `SchemaError` khi sai (thiếu id, type/priority ngoài tập hợp lệ, id trùng).
- **Phụ thuộc:** `pyyaml`.

### 4.2 `tcformat/strategy.py`
- **Làm gì:** `list_objects(xlsx, sheet)->list[dict]` trả về `{ref, section, stt, object, how}` bằng cách quét sheet: nhận diện dòng section (vd text khớp `^\d\.\d\.\d`), lấy STT ở cột A, object ở cột C, how ở cột J. `all_refs(xlsx)->set[str]` gộp 3 sheet (1/2/3).
- **Phụ thuộc:** `openpyxl`. (Tổng quát hóa logic đã có trong `scripts/gen_checklist.py`; sẽ refactor `gen_checklist` dùng chung bộ trích này để DRY.)

### 4.3 `tcformat/coverage.py`
- **Làm gì:** `check_coverage(screen, strategy_refs)->CoverageReport` với `covered`, `missing` (refs chưa có testcase), `unknown` (strategy_ref không khớp đối tượng nào). `coverage_rate` = covered/total.
- **Dùng thế nào:** Stage 1 chạy sau khi sinh để liệt kê đối tượng còn thiếu → AI bổ sung tới khi `missing == []`.

### 4.4 `tcformat/render_xlsx.py`
- **Làm gì:** `render(screens, template_path, out_path)` → tạo xlsx: với mỗi screen, **clone sheet test case mẫu** (`4.1. ...`) trong template làm khung có sẵn style, đổi tên thành `4.x <screen>`, điền C1=screen, C2=test_level, và các dòng testcase từ dòng dữ liệu (No tự đánh số; ghép `steps`/`expected` bằng xuống dòng; điền section divider khi `section` đổi). Xóa các dòng mẫu thừa.
- **Phụ thuộc:** `openpyxl`, `schema.py`.
- **Lưu ý:** chỉ điền vùng dữ liệu + ô metadata; giữ nguyên block summary và header của template (không phá format).

### 4.5 Skill `generate-testcases` (`.claude/skills/generate-testcases/SKILL.md`)
- **Làm gì:** quy trình cho AI (không phải code tất định):
  1. Đọc đầu vào: tài liệu thiết kế (text/md/DB/API) + ảnh/Figma (multimodal) + danh sách đối tượng testing (`tcformat/strategy.list_objects`).
  2. Soạn test case theo schema YAML (mục 3), mỗi đối tượng testing có ≥1 testcase mang `strategy_ref` tương ứng.
  3. Ghi `testcases/<screen>.yaml`, render xlsx (`render_xlsx.render`), chạy `coverage.check_coverage`.
  4. Nếu còn `missing`/`unknown` → bổ sung/sửa, lặp tới khi phủ đủ.
- **Đầu ra:** YAML + xlsx + bản tóm tắt coverage.

## 5. Luồng dữ liệu

```
design docs + strategy objects ─►(AI, skill)─► <screen>.yaml ─►(render_xlsx)─► <screen>.xlsx
                                                     │
                                       (coverage.check vs strategy.all_refs)
                                                     ▼
                                          báo cáo coverage (missing/unknown)
```

## 6. Xử lý lỗi

- YAML sai schema → `SchemaError` nêu rõ trường/giá trị sai, dừng sớm.
- `strategy_ref` không khớp đối tượng nào → liệt vào `unknown` (không chặn render, nhưng cảnh báo).
- Template thiếu sheet mẫu `4.1.*` → lỗi rõ ràng yêu cầu kiểm tra template.
- Tên screen trùng khi render nhiều màn hình → thêm hậu tố để tránh đè sheet.

## 7. Chiến lược kiểm thử (cho chính Stage 1)

- `schema.py`: unit test load/dump round-trip + các case sai (thiếu id, priority lạ, id trùng) raise `SchemaError`.
- `strategy.py`: unit test trên 1 xlsx mẫu thu nhỏ (dựng bằng openpyxl) → trả đúng refs; và 1 test "khói" trên `strategy/strategy.xlsx` thật xác nhận `all_refs` không rỗng và chứa `2.3.1#1`.
- `coverage.py`: unit test covered/missing/unknown với dữ liệu dựng sẵn.
- `render_xlsx.py`: render 1 screen mẫu (2–3 testcase) → mở lại xlsx, xác nhận sheet `4.x`, C1/C2 đúng, các dòng testcase có TestcaseID/Step/Expect/Type/Priority đúng vị trí cột.
- Demo end-to-end (không bắt buộc trong CI): một file design mẫu trong `tests/fixtures/design-sample.md` → chạy skill (thủ công) → YAML + xlsx + coverage 100%.

## 8. Tiêu chí hoàn thành (DoD)

- `pytest` xanh cho toàn bộ unit test của `tcformat/`.
- `render_xlsx` tạo được xlsx mở bằng Excel/openpyxl, đúng format template, từ một YAML mẫu.
- `coverage.check_coverage` phát hiện đúng đối tượng thiếu.
- Skill `generate-testcases` có tài liệu quy trình đầy đủ; demo sinh được bộ test case phủ 100% cho 1 màn hình mẫu.
- `scripts/gen_checklist.py` được refactor dùng chung `tcformat/strategy` (không trùng lặp logic trích).

## 9. Điểm mở rộng (giai đoạn sau)

- Stage 2: harness agent đọc YAML, điều khiển Playwright MCP theo `steps`, chụp screenshot mỗi bước, đánh giá `expected` → điền `result`.
- Stage 3: đọc `result` từ YAML/xlsx → `gen_report.py` (đã có) + nhúng/đính kèm evidence.
