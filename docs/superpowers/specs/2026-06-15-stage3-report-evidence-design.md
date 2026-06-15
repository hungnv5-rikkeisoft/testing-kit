# Stage 3 — Báo cáo + đính kèm evidence (Design)

> Ngày: 2026-06-15. Stage cuối của pipeline 3 giai đoạn (xem `HANDOFF.md`).
> Đọc trước: spec nền `2026-06-15-testing-kit-design.md`, Stage 2 `2026-06-15-stage2-test-execution-design.md`.

## 1. Mục tiêu

Stage 2 đã ghi `result.{chrome,safari}` (status OK/NG/N·A, tester, date, note, bug_id,
`evidence: [paths]`) vào `testcases/<screen>.yaml`. Stage 3 đọc các `result` đó để:

1. Sinh **báo cáo team** (sheet "3. Test Report" của template) — tổng hợp pass/NG/N·A theo
   browser, số bug, áp **cổng exit-criteria** (≥95% pass-rate **và** 0 bug Critical/High).
2. **Đính kèm evidence**: nhúng ảnh screenshot per-step vào một **sheet "Evidence" riêng**,
   kèm caption + hyperlink mở full-size.

Nguồn dữ liệu **chỉ là YAML** (không dùng JUnit XML cho Stage 3).

## 2. Quyết định thiết kế đã chốt (brainstorm)

| Câu hỏi | Quyết định |
|---|---|
| Nguồn dữ liệu | **Chỉ YAML** (`testcases/<screen>.yaml`). |
| Vị trí evidence | **Sheet "Evidence" riêng** (không chèn vào sheet "4.x"). |
| Nhúng vs link ảnh | **Nhúng ảnh thật + caption + hyperlink** mở full-size. |
| Bug severity | **Map từ `priority` testcase** (High→High, Medium→Medium, Low→Low). |
| Mẫu số pass-rate | **Chỉ các lượt đã chạy** (status≠null). Lượt chưa chạy không tính. |

## 3. Kiến trúc

Cách chọn: **tách aggregation thuần khỏi tầng xlsx** (hợp TDD, file nhỏ tập trung).

```
testcases/<screen>.yaml ─► schema.load_screen (đã có)
   │
   ▼
tcformat/report_data.py   ── aggregate(screens) → ReportData
   │   (đếm OK/NG/N·A lượt-đã-chạy, map priority→severity,
   │    dựng toolkit.report.Summary, áp evaluate_exit_criteria)
   ▼
tcformat/report_xlsx.py   ── write_report(report_data, screens, template, out)
   │   • sheet "3. Test Report": 1 dòng/màn hình + Total + khối exit-criteria
   │   • sheet "Evidence": 1 dòng/ảnh-step, nhúng ảnh + caption + hyperlink
   ▼
reports/test_report.xlsx

scripts/gen_report.py  ── thêm đường --yaml (Stage 3); giữ nguyên --chrome/--safari (JUnit)
```

Sheet testcase chi tiết "4.x" **vẫn do Stage 1/2 (`render_xlsx`) sinh** ở
`testcases/<screen>.xlsx`; Stage 3 **không lặp lại** sheet đó.

## 4. Thành phần

### 4.1 `tcformat/report_data.py` (aggregation thuần — không openpyxl)

Đơn vị thống kê = **lượt (run)** = mỗi cặp (testcase × browser). Một run "đã chạy" ⇔
`status ≠ None`.

Cấu trúc trả về (dataclass):

```python
@dataclass
class ScreenReport:
    screen: str
    chrome: dict   # {"ok": int, "ng": int, "na": int}
    safari: dict
    bugs: int      # số run NG của màn hình này
    planned: int   # 2 * số testcase (chrome+safari)
    executed: int  # số run status≠None

@dataclass
class ReportData:
    screens: list[ScreenReport]
    summary: Summary           # toolkit.report.Summary (total=executed, passed=OK, failed=NG)
    planned: int               # tổng planned mọi màn hình
    executed: int              # tổng executed
    exit_ok: bool
    exit_reasons: list[str]
```

Quy tắc:
- `executed = ok + ng + na` (chỉ lượt đã chạy). `pass_rate = ok / executed` (0 nếu executed=0).
- `Summary(total=executed, passed=ok, failed=ng)`; N·A = total − passed − failed.
- **Bug & severity:** mỗi run `status == "NG"` → 1 bug, severity = `priority` của testcase
  (`High`→`"High"`, `Medium`→`"Medium"`, `Low`→`"Low"`). `summary.bugs_by_severity` đếm theo đó.
- Cổng: `evaluate_exit_criteria(summary, criteria)` từ `toolkit.report` (criteria mặc định
  `min_pass_rate=0.95`, `block_severities=["Critical","High"]`). Không có priority "Critical"
  nên Critical luôn 0 — chấp nhận được; bug priority High đủ để chặn cổng.
- Hàm nhận `criteria` qua tham số (mặc định lấy `toolkit.config` default) để test biên dễ.

### 4.2 `tcformat/report_xlsx.py` (render)

`write_report(report_data, screens, template_path, out_path)`:

**Sheet "3. Test Report"** — tái dùng layout `gen_report.py`:
`No | Function/Screen | total | Chrome OK/NG/N·A | Safari OK/NG/N·A | bugs`, + dòng `Total`.
Logic tìm header + clear-region (unmerge → blank) **gom vào helper dùng chung** với
`gen_report.py` để tránh phân kỳ (xem §6). Ngay **dưới dòng Total** ghi khối exit-criteria:
verdict `PASS`/`FAIL`, `pass_rate`, `executed N / planned M`, và từng lý do fail (nếu có).

**Sheet "Evidence"** (tạo mới, append vào workbook):
- Header: `TestcaseID | Browser | Step | Ảnh | Mở full-size | Note`.
- 1 dòng/ảnh-step, sắp xếp theo **testcase → browser → step**. Chỉ liệt kê testcase có evidence.
- Cột "Ảnh": nhúng bằng `openpyxl.drawing.image.Image`, **resize giữ tỉ lệ, cap rộng ~480px**;
  chỉnh `row_dimensions[r].height` cho vừa ảnh.
- Cột "Step": caption `step_N` (chi tiết `<screen>/<id>/<browser>` ở các cột TestcaseID/Browser).
- Cột "Mở full-size": `cell.hyperlink = <đường dẫn tương đối tới png gốc>`.
- Cột "Note": `result.<browser>.note` (ghi 1 lần ở dòng step đầu của mỗi (testcase,browser)).
- **Ảnh thiếu file trên đĩa → ghi "(file missing)" ở cột Ảnh, vẫn giữ hyperlink, không crash.**

### 4.3 `scripts/gen_report.py` (CLI — mở rộng)

Thêm đường vào Stage 3, **không phá đường JUnit cũ**:

```
# Stage 3 (YAML → report + evidence)
python scripts/gen_report.py --yaml testcases/basic-information-input.yaml \
    --out reports/test_report.xlsx
# (lặp --yaml cho nhiều màn hình)

# Cũ (JUnit → report), giữ nguyên
python scripts/gen_report.py --chrome reports/integration-junit.xml --out ...
```

- `--yaml` (repeatable) và `--chrome/--safari` loại trừ nhau; thiếu cả hai → lỗi argparse.
- Đường `--yaml`: `load_screen` từng file → `aggregate` → `write_report`. In tóm tắt
  (pass-rate, executed/planned, bugs, verdict) và **exit non-zero nếu `exit_ok` False**.
- Tránh ký tự non-ASCII trong docstring module (cp932 console — bẫy đã gặp ở HANDOFF §8).

## 5. Xử lý lỗi

- YAML thiếu `screen` / sai schema → `SchemaError` (fail fast, đã có).
- `status` ngoài `VALID_STATUSES` khi load → lỗi rõ ràng (schema validate khi cần).
- **0 lượt chạy** → vẫn sinh báo cáo (executed=0, pass_rate=0, gate FAIL), không nổ exception.
- Ảnh evidence thiếu file → "(file missing)", không crash (xem §4.2).
- `reports/` tự tạo (`mkdir parents=True`).

## 6. Tái dùng & dọn dẹp đi kèm

`gen_report.py` (JUnit) và `report_xlsx.py` (YAML) cùng ghi sheet "3. Test Report". Để
tránh phân kỳ layout, **trích helper dùng chung** cho: tìm header row, clear-region
(unmerge→blank), và ghi một dòng số liệu màn hình. Đặt helper ở `report_xlsx.py`
(hoặc `tcformat/_report_sheet.py`); `gen_report.py` import lại. Đây là cải thiện có chủ đích
trong vùng đang sửa, không refactor lan man.

## 7. Định nghĩa hoàn thành (DoD)

- `report_data.aggregate` có unit test: mẫu số chỉ-lượt-đã-chạy, map priority→severity,
  gate pass/fail biên 95%, trường hợp 0 lượt, đếm bug.
- `report_xlsx.write_report` có test: mở lại workbook → sheet "3. Test Report" + "Evidence"
  tồn tại, ô Total đúng, có ảnh nhúng (`ws._images` không rỗng), hyperlink set, khối
  exit-criteria có verdict; ảnh thiếu file không crash.
- `scripts/gen_report.py --yaml ...` chạy thật trên `testcases/basic-information-input.yaml`
  (6 ảnh chrome) → `reports/test_report.xlsx` mở được, 2 sheet đúng, exit code phản ánh gate.
- Toàn bộ `pytest -q` xanh (không phá 63 test hiện có).

## 8. Ngoài phạm vi (YAGNI)

- Không sinh PDF/HTML báo cáo (chỉ xlsx).
- Không chạy thêm testcase (đó là Stage 2, dùng skill `run-testcases` khi cần).
- Không nhúng video / không nén ảnh nâng cao (chỉ resize giữ tỉ lệ đơn giản).

## 9. Cập nhật sau review (2026-06-15)

Theo phản hồi: report và testcase ra 2 file rời rạc, khó kiểm tra và không đồng bộ. **Đã đổi:**
`write_report` nay gọi `render_xlsx.render_into(wb, screens)` để chèn luôn sheet "4.x" testcase detail
vào **cùng** workbook báo cáo → một file `reports/test_report.xlsx` chứa đủ "4.x" + "3. Test Report" +
"Evidence", tất cả sinh từ cùng YAML nên luôn đồng bộ. `render()` cũ (Stage 1, ra `testcases/<screen>.xlsx`)
vẫn giữ làm artifact soạn testcase, nhưng để kiểm tra kết quả cuối chỉ cần một file Stage 3.
