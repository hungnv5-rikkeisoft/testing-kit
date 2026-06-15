# Stage 3 — Báo cáo + đính kèm evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đọc `result` từ `testcases/<screen>.yaml` (Stage 2) → sinh `reports/test_report.xlsx` gồm sheet "3. Test Report" (tổng hợp + cổng exit-criteria) và sheet "Evidence" (nhúng ảnh + caption + hyperlink).

**Architecture:** Tách 3 lớp: `tcformat/report_data.py` (aggregation thuần, không openpyxl) → `tcformat/report_xlsx.py` (render xlsx + nhúng ảnh) → `scripts/gen_report.py` (thêm đường `--yaml`). Helper ghi sheet "3. Test Report" gom vào `tcformat/report_sheet.py` dùng chung với đường JUnit cũ.

**Tech Stack:** Python 3.13 (venv `./.venv/Scripts/python.exe`), openpyxl 3.1.5, Pillow (mới — cần để nhúng ảnh), pytest, PyYAML. Tái dùng `toolkit.report.Summary`/`evaluate_exit_criteria` và `toolkit.config.ExitCriteria`.

**Spec:** `docs/superpowers/specs/2026-06-15-stage3-report-evidence-design.md`

**Lưu ý môi trường (HANDOFF §3/§8):** Mọi lệnh python/pytest dùng `./.venv/Scripts/python.exe`. Tránh ký tự non-ASCII trong docstring module có CLI (console cp932). Đường dẫn evidence trong YAML là tương đối repo-root.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `requirements.txt` (modify) | Thêm `Pillow` (openpyxl cần để nhúng ảnh). |
| `tcformat/report_data.py` (create) | Aggregation thuần: đếm OK/NG/N·A lượt-đã-chạy, map priority→severity, dựng `Summary` + áp cổng exit-criteria. |
| `tcformat/report_sheet.py` (create) | Helper dùng chung ghi sheet "3. Test Report": tìm header, clear-region, ghi 1 dòng màn hình. |
| `tcformat/report_xlsx.py` (create) | `write_report(...)`: ghi sheet "3. Test Report" + sheet "Evidence" (nhúng ảnh, caption, hyperlink). |
| `scripts/gen_report.py` (modify) | Refactor dùng `report_sheet`; thêm đường CLI `--yaml` (Stage 3) cạnh đường JUnit cũ. |
| `tests/unit/test_report_data.py` (create) | Unit cho `aggregate`. |
| `tests/unit/test_report_xlsx.py` (create) | Unit cho `write_report` (sheet, totals, ảnh nhúng, missing file). |
| `tests/unit/test_gen_report_yaml.py` (create) | Đường CLI `--yaml`. |

---

## Task 1: Thêm phụ thuộc Pillow

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Thêm dòng Pillow vào requirements.txt**

Thêm sau dòng `openpyxl==3.1.5`:

```
Pillow==11.0.0
```

- [ ] **Step 2: Cài Pillow vào venv**

Run: `./.venv/Scripts/python.exe -m pip install Pillow==11.0.0`
Expected: `Successfully installed pillow-11.0.0`

- [ ] **Step 3: Xác minh openpyxl nhúng được ảnh evidence**

Run:
```bash
./.venv/Scripts/python.exe -c "from openpyxl.drawing.image import Image as XL; i=XL('evidence/basic-information-input/chrome/UI_02/step_1.png'); print(i.width, i.height)"
```
Expected: in ra 2 số (vd `1280 720`), không còn `ImportError: You must install Pillow`.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "build: add Pillow dependency for evidence image embedding"
```

---

## Task 2: `tcformat/report_data.py` — aggregation thuần

**Files:**
- Create: `tcformat/report_data.py`
- Test: `tests/unit/test_report_data.py`

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/unit/test_report_data.py`:

```python
from tcformat.schema import Screen, Testcase, Result, BrowserResult
from tcformat.report_data import aggregate


def _tc(tc_id, priority="High", chrome=None, safari=None):
    return Testcase(id=tc_id, section="UI", main_item="x", type="IT",
                    priority=priority,
                    result=Result(chrome=chrome or BrowserResult(),
                                  safari=safari or BrowserResult()))


def test_counts_only_executed_runs():
    # 2 testcases, only some browser runs executed (status != None)
    sc = Screen(screen="S", test_level="IT", testcases=[
        _tc("UI_01", chrome=BrowserResult(status="OK")),          # chrome ran, safari null
        _tc("UI_02", chrome=BrowserResult(status="NG"),
            safari=BrowserResult(status="N/A")),
    ])
    data = aggregate([sc])
    # planned = 2 testcases * 2 browsers = 4 ; executed = OK+NG+N/A = 3
    assert data.planned == 4
    assert data.executed == 3
    assert data.summary.passed == 1   # one OK
    assert data.summary.failed == 1   # one NG
    # pass-rate = OK / executed = 1/3
    assert round(data.summary.pass_rate, 4) == round(1 / 3, 4)


def test_ng_maps_priority_to_severity():
    sc = Screen(screen="S", test_level="IT", testcases=[
        _tc("HI", priority="High", chrome=BrowserResult(status="NG")),
        _tc("LO", priority="Low", chrome=BrowserResult(status="NG")),
    ])
    data = aggregate([sc])
    assert data.summary.bugs_by_severity == {"High": 1, "Low": 1}
    # High-severity bug present -> exit gate fails
    assert data.exit_ok is False
    assert any("High" in r for r in data.exit_reasons)


def test_all_ok_above_threshold_passes_gate():
    tcs = [_tc(f"T{i}", chrome=BrowserResult(status="OK")) for i in range(20)]
    sc = Screen(screen="S", test_level="IT", testcases=tcs)
    data = aggregate([sc])
    assert data.summary.pass_rate == 1.0
    assert data.exit_ok is True
    assert data.exit_reasons == []


def test_zero_executed_does_not_crash_and_fails_gate():
    sc = Screen(screen="S", test_level="IT", testcases=[_tc("UI_01")])
    data = aggregate([sc])
    assert data.executed == 0
    assert data.summary.pass_rate == 0.0
    assert data.exit_ok is False
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_report_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tcformat.report_data'`.

- [ ] **Step 3: Viết `tcformat/report_data.py`**

```python
"""Aggregate Stage 2 YAML results into report counts + exit-criteria verdict.

Pure data layer (no openpyxl). The unit of counting is a "run" = one
(testcase x browser) pair; a run is "executed" when its status is not None.
Pass-rate counts only executed runs (strategy sheet 6 exit criteria).
"""
from __future__ import annotations
from dataclasses import dataclass, field

from toolkit.report import Summary, evaluate_exit_criteria
from toolkit.config import ExitCriteria

BROWSERS = ("chrome", "safari")
# testcase priority -> bug severity bucket
_SEVERITY = {"High": "High", "Medium": "Medium", "Low": "Low"}


@dataclass
class ScreenReport:
    screen: str
    chrome: dict           # {"ok": int, "ng": int, "na": int}
    safari: dict
    bugs: int              # number of NG runs on this screen
    planned: int           # 2 * number of testcases
    executed: int          # runs with status != None


@dataclass
class ReportData:
    screens: list
    summary: Summary
    planned: int
    executed: int
    exit_ok: bool
    exit_reasons: list = field(default_factory=list)


def _blank():
    return {"ok": 0, "ng": 0, "na": 0}


def _tally(counts, status):
    if status == "OK":
        counts["ok"] += 1
    elif status == "NG":
        counts["ng"] += 1
    elif status == "N/A":
        counts["na"] += 1


def aggregate(screens, criteria=None) -> ReportData:
    criteria = criteria or ExitCriteria()
    screen_reports = []
    bugs_by_severity: dict = {}
    tot_planned = 0

    for sc in screens:
        c, s = _blank(), _blank()
        bugs = 0
        planned = 0
        for tc in sc.testcases:
            for br_name in BROWSERS:
                planned += 1
                status = getattr(tc.result, br_name).status
                _tally(c if br_name == "chrome" else s, status)
                if status == "NG":
                    bugs += 1
                    sev = _SEVERITY.get(tc.priority, "Medium")
                    bugs_by_severity[sev] = bugs_by_severity.get(sev, 0) + 1
        executed = sum(c.values()) + sum(s.values())
        screen_reports.append(ScreenReport(
            screen=sc.screen, chrome=c, safari=s, bugs=bugs,
            planned=planned, executed=executed))
        tot_planned += planned

    tot_ok = sum(r.chrome["ok"] + r.safari["ok"] for r in screen_reports)
    tot_ng = sum(r.chrome["ng"] + r.safari["ng"] for r in screen_reports)
    tot_na = sum(r.chrome["na"] + r.safari["na"] for r in screen_reports)
    executed = tot_ok + tot_ng + tot_na
    summary = Summary(total=executed, passed=tot_ok, failed=tot_ng,
                      bugs_by_severity=bugs_by_severity)
    ok, reasons = evaluate_exit_criteria(summary, criteria)
    return ReportData(
        screens=screen_reports, summary=summary,
        planned=tot_planned, executed=executed,
        exit_ok=ok, exit_reasons=reasons)
```

- [ ] **Step 4: Chạy test để xác nhận PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_report_data.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tcformat/report_data.py tests/unit/test_report_data.py
git commit -m "feat(report): aggregate YAML results into counts + exit-criteria verdict"
```

---

## Task 3: `tcformat/report_sheet.py` — helper dùng chung + refactor gen_report

**Files:**
- Create: `tcformat/report_sheet.py`
- Modify: `scripts/gen_report.py`
- Test: `tests/unit/test_report_sheet.py` (mới) + `tests/unit/test_gen_report.py` (phải vẫn xanh)

- [ ] **Step 1: Viết test thất bại cho helper**

Tạo `tests/unit/test_report_sheet.py`:

```python
from openpyxl import load_workbook
from tcformat.report_sheet import (
    REPORT_SHEET, find_header_row, clear_region, write_screen_row)

TEMPLATE = "template/Format test case + Test report.xlsx"


def test_find_header_row_locates_function_screen():
    ws = load_workbook(TEMPLATE)[REPORT_SHEET]
    assert ws.cell(find_header_row(ws), 2).value == "Function/Screen"


def test_write_screen_row_fills_columns():
    ws = load_workbook(TEMPLATE)[REPORT_SHEET]
    row = find_header_row(ws) + 3
    clear_region(ws, row, row + 5)
    write_screen_row(ws, row, 1, "MyScreen", 3,
                     {"ok": 2, "ng": 1, "na": 0},
                     {"ok": 0, "ng": 0, "na": 0}, 1)
    assert ws.cell(row, 1).value == "1.0"
    assert ws.cell(row, 2).value == "MyScreen"
    assert ws.cell(row, 3).value == 3
    assert ws.cell(row, 4).value == 2   # chrome OK
    assert ws.cell(row, 5).value == 1   # chrome NG
    assert ws.cell(row, 10).value == 1  # bugs


def test_write_screen_row_total_has_no_number():
    ws = load_workbook(TEMPLATE)[REPORT_SHEET]
    row = find_header_row(ws) + 3
    clear_region(ws, row, row + 5)
    write_screen_row(ws, row, None, "Total", 0,
                     {"ok": 0, "ng": 0, "na": 0},
                     {"ok": 0, "ng": 0, "na": 0}, 0)
    assert ws.cell(row, 1).value is None
    assert ws.cell(row, 2).value == "Total"
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_report_sheet.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tcformat.report_sheet'`.

- [ ] **Step 3: Viết `tcformat/report_sheet.py`**

```python
"""Shared helpers for the template's "3. Test Report" sheet.

Used by both scripts/gen_report.py (JUnit path) and tcformat/report_xlsx.py
(YAML path) so the sheet layout lives in one place.
"""
from __future__ import annotations

REPORT_SHEET = "3. Test Report"
HEADER_LABEL = "Function/Screen"


def find_header_row(ws, label=HEADER_LABEL) -> int:
    for r in range(1, 30):
        if ws.cell(r, 2).value == label:
            return r
    raise ValueError(f"'{label}' header not found in sheet '{ws.title}'")


def clear_region(ws, first_row, last_row, last_col=11):
    """Unmerge ranges inside the body, then blank cells, so leftover template
    sample rows / Total row don't bleed into the generated report."""
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row >= first_row and rng.max_row <= last_row:
            ws.unmerge_cells(str(rng))
    for r in range(first_row, last_row + 1):
        for c in range(1, last_col + 1):
            ws.cell(r, c).value = None


def write_screen_row(ws, row, no, name, total, chrome, safari, bugs):
    """Write one aggregate row. `no` None -> leave the No. column blank (Total).
    chrome/safari are {"ok","ng","na"} dicts."""
    if no is not None:
        ws.cell(row, 1).value = f"{no}.0"
    ws.cell(row, 2).value = name
    ws.cell(row, 3).value = total
    ws.cell(row, 4).value = chrome["ok"]
    ws.cell(row, 5).value = chrome["ng"]
    ws.cell(row, 6).value = chrome["na"]
    ws.cell(row, 7).value = safari["ok"]
    ws.cell(row, 8).value = safari["ng"]
    ws.cell(row, 9).value = safari["na"]
    ws.cell(row, 10).value = bugs
```

- [ ] **Step 4: Chạy test helper để xác nhận PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_report_sheet.py -v`
Expected: 3 passed.

- [ ] **Step 5: Refactor `scripts/gen_report.py` dùng helper**

Trong `scripts/gen_report.py`:

(a) Thay phần import + hằng. Xoá các khối `DEFAULT_TEMPLATE`/`REPORT_SHEET`/`HEADER_LABEL` cũ và 2 hàm `_find_header_row`, `_clear_region`; thay bằng:

```python
from openpyxl import load_workbook

from tcformat.report_sheet import (
    REPORT_SHEET, find_header_row, clear_region, write_screen_row)

DEFAULT_TEMPLATE = "template/Format test case + Test report.xlsx"
```

(Giữ nguyên `parse_junit` và `_screen_name`.)

(b) Trong `build_report`, thay đoạn tìm header + clear + vòng ghi dòng. Đoạn cũ:

```python
    hdr = _find_header_row(ws)
    data_start = hdr + 3  # header row + 2 sub-header rows, then data

    _clear_region(ws, data_start, data_start + max(len(modules), 5) + 5)
```
đổi thành:
```python
    hdr = find_header_row(ws)
    data_start = hdr + 3  # header row + 2 sub-header rows, then data

    clear_region(ws, data_start, data_start + max(len(modules), 5) + 5)
```

(c) Trong vòng `for i, cls in enumerate(modules):`, thay 10 dòng `ws.cell(row, ...).value = ...` (từ `ws.cell(row, 1).value = f"{i + 1}.0"` tới `ws.cell(row, 10).value = bugs`) bằng:

```python
        row = data_start + i
        write_screen_row(ws, row, i + 1, _screen_name(cls), total, c, s, bugs)
```

(Giữ nguyên phần `rows.append(...)` và cập nhật `totals`, và giữ nguyên khối ghi dòng `Total` thủ công bên dưới.)

- [ ] **Step 6: Chạy lại test gen_report cũ để xác nhận KHÔNG vỡ**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_gen_report.py tests/unit/test_report_sheet.py -v`
Expected: tất cả passed (đường JUnit cũ giữ nguyên hành vi).

- [ ] **Step 7: Commit**

```bash
git add tcformat/report_sheet.py scripts/gen_report.py tests/unit/test_report_sheet.py
git commit -m "refactor(report): extract shared '3. Test Report' sheet helpers"
```

---

## Task 4: `tcformat/report_xlsx.py` — render report + evidence

**Files:**
- Create: `tcformat/report_xlsx.py`
- Test: `tests/unit/test_report_xlsx.py`

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/unit/test_report_xlsx.py`:

```python
from pathlib import Path
from openpyxl import load_workbook
from PIL import Image as PILImage

from tcformat.schema import Screen, Testcase, Result, BrowserResult
from tcformat.report_data import aggregate
from tcformat.report_xlsx import write_report, REPORT_SHEET, EVIDENCE_SHEET

TEMPLATE = "template/Format test case + Test report.xlsx"


def _png(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    PILImage.new("RGB", (600, 400), "white").save(path)


def _screen(evidence_rel):
    return Screen(screen="Basic Info", test_level="IT", testcases=[
        Testcase(id="UI_02", section="UI", main_item="x", type="IT",
                 priority="High",
                 result=Result(chrome=BrowserResult(
                     status="OK", tester="bot", date="2026-06-15",
                     note="looks good", evidence=[evidence_rel]))),
        Testcase(id="FN_02", section="FUNCTION", main_item="y", type="IT",
                 priority="High",
                 result=Result(chrome=BrowserResult(status="NG"))),
    ])


def test_report_sheet_totals_and_exit_block(tmp_path):
    rel = "evidence/basic-info/chrome/UI_02/step_1.png"
    _png(tmp_path / rel)
    sc = _screen(rel)
    out = tmp_path / "reports" / "test_report.xlsx"
    write_report(aggregate([sc]), [sc], TEMPLATE, str(out), base_dir=str(tmp_path))

    ws = load_workbook(out)[REPORT_SHEET]
    # find the screen row
    from tcformat.report_sheet import find_header_row
    ds = find_header_row(ws) + 3
    assert ws.cell(ds, 2).value == "Basic Info"
    assert ws.cell(ds, 4).value == 1   # chrome OK (UI_02)
    assert ws.cell(ds, 5).value == 1   # chrome NG (FN_02)
    # exit-criteria block exists below the table with a verdict
    txt = [ws.cell(r, 3).value for r in range(ds, ds + 12)]
    assert "FAIL" in txt          # High-severity NG -> gate fails


def test_evidence_sheet_embeds_image_and_link(tmp_path):
    rel = "evidence/basic-info/chrome/UI_02/step_1.png"
    _png(tmp_path / rel)
    sc = _screen(rel)
    out = tmp_path / "reports" / "test_report.xlsx"
    write_report(aggregate([sc]), [sc], TEMPLATE, str(out), base_dir=str(tmp_path))

    wb = load_workbook(out)
    assert EVIDENCE_SHEET in wb.sheetnames
    ws = wb[EVIDENCE_SHEET]
    assert ws.cell(1, 1).value == "TestcaseID"
    # row 2 = first evidence: UI_02 / chrome / step_1
    assert ws.cell(2, 1).value == "UI_02"
    assert ws.cell(2, 2).value == "chrome"
    assert ws.cell(2, 3).value == "step_1"
    assert ws.cell(2, 5).hyperlink is not None
    assert ws.cell(2, 6).value == "looks good"
    # the image was embedded
    assert len(ws._images) == 1


def test_missing_evidence_file_does_not_crash(tmp_path):
    rel = "evidence/basic-info/chrome/UI_02/step_1.png"  # NOT created on disk
    sc = _screen(rel)
    out = tmp_path / "reports" / "test_report.xlsx"
    write_report(aggregate([sc]), [sc], TEMPLATE, str(out), base_dir=str(tmp_path))

    ws = load_workbook(out)[EVIDENCE_SHEET]
    assert ws.cell(2, 4).value == "(file missing)"
    assert len(ws._images) == 0
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_report_xlsx.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tcformat.report_xlsx'`.

- [ ] **Step 3: Viết `tcformat/report_xlsx.py`**

```python
"""Render Stage 3 report from aggregated YAML results.

Writes the team template's "3. Test Report" sheet plus a new "Evidence" sheet
that embeds per-step screenshots with a caption and a hyperlink to the original.
"""
from __future__ import annotations
import os
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.utils import get_column_letter

from tcformat.report_sheet import (
    REPORT_SHEET, find_header_row, clear_region, write_screen_row)

EVIDENCE_SHEET = "Evidence"
EVIDENCE_HEADERS = ["TestcaseID", "Browser", "Step", "Image", "Open full-size", "Note"]
BROWSERS = ("chrome", "safari")
MAX_IMG_WIDTH = 480  # px


def _sum(reports, browser, key):
    return sum(getattr(r, browser)[key] for r in reports)


def _write_report_sheet(ws, report_data):
    hdr = find_header_row(ws)
    data_start = hdr + 3
    n = len(report_data.screens)
    clear_region(ws, data_start, data_start + max(n, 5) + 10)

    for i, sr in enumerate(report_data.screens):
        write_screen_row(ws, data_start + i, i + 1, sr.screen,
                         sr.executed, sr.chrome, sr.safari, sr.bugs)

    trow = data_start + n
    chrome_tot = {k: _sum(report_data.screens, "chrome", k) for k in ("ok", "ng", "na")}
    safari_tot = {k: _sum(report_data.screens, "safari", k) for k in ("ok", "ng", "na")}
    write_screen_row(ws, trow, None, "Total", report_data.executed,
                     chrome_tot, safari_tot,
                     sum(r.bugs for r in report_data.screens))

    v = trow + 2
    ws.cell(v, 2).value = "Exit criteria"
    ws.cell(v, 3).value = "PASS" if report_data.exit_ok else "FAIL"
    ws.cell(v + 1, 2).value = "Pass rate"
    ws.cell(v + 1, 3).value = f"{report_data.summary.pass_rate:.0%}"
    ws.cell(v + 2, 2).value = "Executed/Planned"
    ws.cell(v + 2, 3).value = f"{report_data.executed}/{report_data.planned}"
    for j, reason in enumerate(report_data.exit_reasons):
        ws.cell(v + 3 + j, 2).value = "Reason"
        ws.cell(v + 3 + j, 3).value = reason


def _embed(ws, row, col, img_abs):
    img = XLImage(str(img_abs))
    if img.width and img.width > MAX_IMG_WIDTH:
        scale = MAX_IMG_WIDTH / img.width
        img.width = int(img.width * scale)
        img.height = int(img.height * scale)
    ws.add_image(img, f"{get_column_letter(col)}{row}")
    ws.row_dimensions[row].height = (img.height or 100) * 0.75
    letter = get_column_letter(col)
    cur = ws.column_dimensions[letter].width or 0
    ws.column_dimensions[letter].width = max(cur, (img.width or MAX_IMG_WIDTH) / 7)


def _write_evidence_sheet(wb, screens, base_dir, out_path):
    ws = wb.create_sheet(EVIDENCE_SHEET)
    for col, h in enumerate(EVIDENCE_HEADERS, start=1):
        ws.cell(1, col).value = h
    out_dir = Path(out_path).resolve().parent

    row = 2
    for sc in screens:
        for tc in sc.testcases:
            for br_name in BROWSERS:
                br = getattr(tc.result, br_name)
                note_written = False
                for idx, rel in enumerate(br.evidence, start=1):
                    ws.cell(row, 1).value = tc.id
                    ws.cell(row, 2).value = br_name
                    ws.cell(row, 3).value = f"step_{idx}"
                    img_abs = (Path(base_dir) / rel).resolve()
                    link = os.path.relpath(img_abs, out_dir).replace("\\", "/")
                    if img_abs.exists():
                        _embed(ws, row, 4, img_abs)
                    else:
                        ws.cell(row, 4).value = "(file missing)"
                    cell = ws.cell(row, 5)
                    cell.value = "open"
                    cell.hyperlink = link
                    if not note_written and br.note:
                        ws.cell(row, 6).value = br.note
                        note_written = True
                    row += 1
    return ws


def write_report(report_data, screens, template_path, out_path, base_dir=".") -> None:
    wb = load_workbook(template_path)
    _write_report_sheet(wb[REPORT_SHEET], report_data)
    if EVIDENCE_SHEET in wb.sheetnames:
        del wb[EVIDENCE_SHEET]
    _write_evidence_sheet(wb, screens, base_dir, out_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
```

- [ ] **Step 4: Chạy test để xác nhận PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_report_xlsx.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tcformat/report_xlsx.py tests/unit/test_report_xlsx.py
git commit -m "feat(report): render '3. Test Report' + Evidence sheet from YAML"
```

---

## Task 5: `scripts/gen_report.py` — đường CLI `--yaml`

**Files:**
- Modify: `scripts/gen_report.py`
- Test: `tests/unit/test_gen_report_yaml.py`

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/unit/test_gen_report_yaml.py`:

```python
from pathlib import Path
from openpyxl import load_workbook
from PIL import Image as PILImage

from tcformat.schema import Screen, Testcase, Result, BrowserResult, dump_screen
from scripts.gen_report import build_report_from_yaml

TEMPLATE = "template/Format test case + Test report.xlsx"


def _png(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    PILImage.new("RGB", (600, 400), "white").save(path)


def test_build_report_from_yaml(tmp_path):
    rel = "evidence/s/chrome/UI_01/step_1.png"
    _png(tmp_path / rel)
    sc = Screen(screen="S", test_level="IT", testcases=[
        Testcase(id="UI_01", section="UI", main_item="x", type="IT",
                 priority="High",
                 result=Result(chrome=BrowserResult(
                     status="OK", evidence=[rel]))),
    ])
    yml = tmp_path / "s.yaml"
    dump_screen(sc, yml)
    out = tmp_path / "reports" / "test_report.xlsx"

    data = build_report_from_yaml([str(yml)], TEMPLATE, str(out),
                                  base_dir=str(tmp_path))
    assert data.executed == 1
    assert data.exit_ok is True   # 100% pass, no bugs
    wb = load_workbook(out)
    assert "3. Test Report" in wb.sheetnames
    assert "Evidence" in wb.sheetnames
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_gen_report_yaml.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_report_from_yaml'`.

- [ ] **Step 3: Thêm hàm + nhánh CLI vào `scripts/gen_report.py`**

(a) Thêm hàm mới (đặt ngay trên `def main():`):

```python
def build_report_from_yaml(yaml_paths, template_path, out_path, base_dir="."):
    """Stage 3 path: aggregate testcase YAML(s) and write the report workbook.

    Returns the ReportData (caller uses .exit_ok for the process exit code)."""
    from tcformat.schema import load_screen
    from tcformat.report_data import aggregate
    from tcformat.report_xlsx import write_report
    screens = [load_screen(p) for p in yaml_paths]
    data = aggregate(screens)
    write_report(data, screens, template_path, out_path, base_dir=base_dir)
    return data
```

(b) Sửa `main()`: `--chrome` không còn bắt buộc, thêm `--yaml`, và rẽ nhánh. Thay phần thân `main()` thành:

```python
def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yaml", action="append", default=None,
                    help="Stage 3: testcase YAML with results (repeatable)")
    ap.add_argument("--chrome", default=None,
                    help="JUnit XML from the desktop/Chrome run (JUnit path)")
    ap.add_argument("--safari", default=None,
                    help="JUnit XML from the iPad/Safari run (optional)")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--out", default="reports/test_report.xlsx")
    args = ap.parse_args()

    if args.yaml:
        data = build_report_from_yaml(args.yaml, args.template, args.out)
        s = data.summary
        print(f"Wrote report -> {args.out} (executed {data.executed}/{data.planned}, "
              f"OK {s.passed} NG {s.failed}, pass {s.pass_rate:.0%}, "
              f"exit {'PASS' if data.exit_ok else 'FAIL'})")
        raise SystemExit(0 if data.exit_ok else 1)

    if not args.chrome:
        ap.error("provide --yaml (Stage 3) or --chrome (JUnit path)")

    result = build_report(args.template, args.chrome, args.safari, args.out)
    t = result["totals"]
    print(f"Wrote {len(result['rows'])} screen row(s) -> {args.out} "
          f"(Chrome OK/NG/N-A {t['c_ok']}/{t['c_ng']}/{t['c_na']}, "
          f"Safari {t['s_ok']}/{t['s_ng']}/{t['s_na']}, bugs {t['bugs']})")
```

- [ ] **Step 4: Chạy test để xác nhận PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_gen_report_yaml.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/gen_report.py tests/unit/test_gen_report_yaml.py
git commit -m "feat(report): add --yaml Stage 3 CLI path with exit-criteria gate"
```

---

## Task 6: Chạy thật end-to-end + cập nhật HANDOFF

**Files:**
- Modify: `HANDOFF.md`

- [ ] **Step 1: Chạy toàn bộ test suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: tất cả passed (63 cũ + test mới của Stage 3), không lỗi.

- [ ] **Step 2: Sinh báo cáo thật từ YAML Stage 2**

Run:
```bash
./.venv/Scripts/python.exe scripts/gen_report.py --yaml testcases/basic-information-input.yaml --out reports/test_report.xlsx
```
Expected: in dòng `Wrote report -> reports/test_report.xlsx (executed 4/54, OK 4 NG 0 pass 100%, exit PASS)`
(4 lượt chrome đã chạy: UI_02, FN_02, FN_03, NF_04 — đều OK; 27 testcase × 2 browser = 54 planned). Exit code 0.

- [ ] **Step 3: Xác minh workbook xuất ra**

Run:
```bash
./.venv/Scripts/python.exe -c "from openpyxl import load_workbook; wb=load_workbook('reports/test_report.xlsx'); print('sheets', wb.sheetnames); ev=wb['Evidence']; print('evidence rows', ev.max_row, 'images', len(ev._images))"
```
Expected: `sheets [... '3. Test Report' ... 'Evidence']`; `images 6` (6 ảnh evidence chrome đã có).

- [ ] **Step 4: Cập nhật HANDOFF.md**

Trong `HANDOFF.md`: ở sơ đồ pipeline (mục 1), đổi dòng Stage 3 từ `⬜ CHƯA LÀM (đã có gen_report nền)` thành `✅ XONG`. Trong mục 2 "Đã hoàn thành", thêm gạch đầu dòng:

```
- **Stage 3** (báo cáo + evidence): `tcformat/report_data.py` (aggregate YAML -> Summary +
  exit-criteria, đếm chỉ lượt đã chạy, map priority->severity), `tcformat/report_sheet.py`
  (helper sheet "3. Test Report" dùng chung với gen_report), `tcformat/report_xlsx.py`
  (ghi sheet "3. Test Report" + sheet "Evidence" nhúng ảnh + caption + hyperlink).
  `scripts/gen_report.py --yaml` sinh `reports/test_report.xlsx` và exit non-zero nếu cổng fail.
  Đã chạy thật trên `basic-information-input.yaml`: executed 4/54, pass 100%, 6 ảnh nhúng, exit PASS.
```

Trong mục "Chưa làm", xoá dòng Stage 3 (đã xong) hoặc thay bằng các bước tuỳ chọn còn lại
(chạy nốt testcase Safari/iPad bằng skill `run-testcases` trước khi báo cáo cuối).

- [ ] **Step 5: Commit**

```bash
git add HANDOFF.md
git commit -m "docs: mark stage 3 complete, document report+evidence path"
```

---

## Notes cho người thực thi

- **Nhánh git:** Stage 2 ở branch `stage2-test-execution`. Hỏi user trước khi tạo branch mới cho Stage 3 hay tiếp tục trên branch hiện tại (HANDOFF §7). **Mọi commit chờ user xác nhận; message thuần, không trailer Co-Authored-By.**
- Nếu chạy `gen_report.py --yaml` mà `testcases/basic-information-input.yaml` chưa tồn tại (đang gitignore), regenerate bằng lệnh Stage 1 ở HANDOFF §5, hoặc chạy lại Stage 2 (skill `run-testcases`) để có result + evidence.
- `reports/` đang gitignore — file `test_report.xlsx` không vào git, chỉ là artifact xác minh.
