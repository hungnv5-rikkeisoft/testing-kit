# Stage 2 — Test Execution + Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho phép một AI agent chạy các testcase ngôn ngữ tự nhiên trong `testcases/<screen>.yaml` qua Playwright MCP, chụp screenshot mỗi bước làm evidence, chấm OK/NG/N·A, và ghi kết quả ngược vào YAML một cách tất định — chứng minh end-to-end bằng một demo app (Flask).

**Architecture:** Một helper Python tất định (`tcformat/runlog.py`) lo việc tạo thư mục evidence và ghi `result` vào YAML qua `dump_screen`. Một skill (`run-testcases`) hướng dẫn agent điều khiển Playwright MCP và gọi helper qua Bash. Một demo Flask app (`demo/app.py`) đóng vai app dưới test. `render_xlsx` được mở rộng để điền cột result.

**Tech Stack:** Python 3.13 (`.venv`), pytest, Flask, openpyxl, PyYAML, Playwright MCP.

**LƯU Ý MÔI TRƯỜNG:** Mọi lệnh python/pytest dùng `./.venv/Scripts/python.exe` (KHÔNG dùng `python` bare = 3.14, thiếu wheel). Git: chỉ commit khi user xác nhận; message thuần, KHÔNG trailer `Co-Authored-By`.

---

## File Structure

| File | Trách nhiệm | Create/Modify |
|---|---|---|
| `tcformat/schema.py` | Thêm `note` vào `BrowserResult` + hằng `VALID_STATUSES` | Modify |
| `tcformat/runlog.py` | `evidence_dir()`, `record_result()`, CLI ghi sổ tất định | Create |
| `tcformat/render_xlsx.py` | Điền cột result (11–18) từ `tc.result` | Modify |
| `demo/app.py` | Flask demo "Basic Information Input" (login/role/cascading/validate/XSS) | Create |
| `requirements.txt` | Thêm `flask` | Modify |
| `.gitignore` | Thêm `evidence/` | Modify |
| `.claude/skills/run-testcases/SKILL.md` | Quy trình agent chạy testcase + evidence | Create |
| `tests/unit/test_schema_note.py` | Round-trip field `note` | Create |
| `tests/unit/test_runlog.py` | evidence_dir + record_result | Create |
| `tests/unit/test_render_result_cols.py` | render điền cột result | Create |
| `tests/demo/test_demo_app.py` | Flask test client: login/cascade/validate/XSS/permission | Create |
| `HANDOFF.md` | Đánh dấu Stage 2 ✅, hướng Stage 3 | Modify |

Cột result trong sheet "4.x" (row 9 của template, xác minh bằng openpyxl):
`K(11)=Chrome Status, L(12)=Chrome Bug ID, M(13)=Chrome Tester, N(14)=Chrome Date, O(15)=Safari Status, P(16)=Safari Bug ID, Q(17)=Safari Tester, R(18)=Safari Date`. **Không có cột note** → `note` chỉ lưu trong YAML (dùng cho Stage 3).

---

## Task 1: Schema — thêm `note` + `VALID_STATUSES`

**Files:**
- Modify: `tcformat/schema.py`
- Test: `tests/unit/test_schema_note.py`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/unit/test_schema_note.py
from tcformat.schema import load_screen, dump_screen, VALID_STATUSES, BrowserResult


def test_browser_result_has_note_default():
    assert BrowserResult().note is None


def test_valid_statuses_set():
    assert VALID_STATUSES == {"OK", "NG", "N/A"}


def test_note_roundtrip(tmp_path):
    y = (
        "screen: S\n"
        "testcases:\n"
        "  - id: UI_01\n"
        "    type: IT\n"
        "    priority: Low\n"
        "    result:\n"
        "      chrome:\n"
        "        status: NG\n"
        "        note: 'validate sai'\n"
    )
    p = tmp_path / "s.yaml"
    p.write_text(y, encoding="utf-8")
    sc = load_screen(p)
    assert sc.testcases[0].result.chrome.note == "validate sai"
    out = tmp_path / "o.yaml"
    dump_screen(sc, out)
    sc2 = load_screen(out)
    assert sc2.testcases[0].result.chrome.note == "validate sai"
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_schema_note.py -v`
Expected: FAIL — `ImportError: cannot import name 'VALID_STATUSES'`.

- [ ] **Step 3: Sửa schema**

Trong `tcformat/schema.py`, thêm hằng cạnh `VALID_PRIORITIES`:

```python
VALID_STATUSES = {"OK", "NG", "N/A"}
```

Thêm `note` vào `BrowserResult`:

```python
@dataclass
class BrowserResult:
    status: str | None = None
    bug_id: str | None = None
    tester: str | None = None
    date: str | None = None
    note: str | None = None
    evidence: list = field(default_factory=list)
```

Cập nhật `_browser_result` để đọc `note`:

```python
def _browser_result(d) -> BrowserResult:
    d = d or {}
    return BrowserResult(
        status=d.get("status"), bug_id=d.get("bug_id"),
        tester=d.get("tester"), date=d.get("date"),
        note=d.get("note"),
        evidence=list(d.get("evidence") or []))
```

- [ ] **Step 4: Chạy test để xác nhận PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_schema_note.py tests/unit/test_tc_schema.py -v`
Expected: PASS (cả test cũ Stage 1 vẫn xanh).

- [ ] **Step 5: Commit** (chỉ khi user xác nhận)

```bash
git add tcformat/schema.py tests/unit/test_schema_note.py
git commit -m "feat(schema): add note field and VALID_STATUSES for stage 2 results"
```

---

## Task 2: `tcformat/runlog.py` — helper ghi sổ tất định

**Files:**
- Create: `tcformat/runlog.py`
- Test: `tests/unit/test_runlog.py`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/unit/test_runlog.py
import pytest
from pathlib import Path
from tcformat.schema import load_screen
from tcformat import runlog

YAML = (
    "screen: Basic Info\n"
    "testcases:\n"
    "  - id: UI_01\n    type: IT\n    priority: High\n"
    "  - id: FN_01\n    type: IT\n    priority: High\n"
)


def _write(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text(YAML, encoding="utf-8")
    return p


def test_evidence_dir_created(tmp_path):
    d = runlog.evidence_dir("basic-info", "chrome", "UI_01", root=str(tmp_path / "ev"))
    assert d.exists() and d.is_dir()
    assert d.parts[-3:] == ("basic-info", "chrome", "UI_01")


def test_evidence_dir_bad_browser(tmp_path):
    with pytest.raises(ValueError):
        runlog.evidence_dir("s", "edge", "UI_01", root=str(tmp_path))


def test_record_result_roundtrip(tmp_path):
    p = _write(tmp_path)
    runlog.record_result(p, "UI_01", "chrome", "OK",
                         evidence=["a.png", "b.png"], tester="bot", date="2026-06-15")
    sc = load_screen(p)
    tc = next(t for t in sc.testcases if t.id == "UI_01")
    assert tc.result.chrome.status == "OK"
    assert tc.result.chrome.evidence == ["a.png", "b.png"]
    assert tc.result.chrome.tester == "bot"
    # other testcase untouched
    fn = next(t for t in sc.testcases if t.id == "FN_01")
    assert fn.result.chrome.status is None


def test_record_result_ng_with_note(tmp_path):
    p = _write(tmp_path)
    runlog.record_result(p, "FN_01", "chrome", "NG", note="validate không hiện")
    sc = load_screen(p)
    fn = next(t for t in sc.testcases if t.id == "FN_01")
    assert fn.result.chrome.status == "NG"
    assert fn.result.chrome.note == "validate không hiện"


def test_record_result_bad_status(tmp_path):
    p = _write(tmp_path)
    with pytest.raises(ValueError):
        runlog.record_result(p, "UI_01", "chrome", "PASS")


def test_record_result_bad_browser(tmp_path):
    p = _write(tmp_path)
    with pytest.raises(ValueError):
        runlog.record_result(p, "UI_01", "edge", "OK")


def test_record_result_unknown_id(tmp_path):
    p = _write(tmp_path)
    with pytest.raises(ValueError):
        runlog.record_result(p, "ZZ_99", "chrome", "OK")
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_runlog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tcformat.runlog'`.

- [ ] **Step 3: Viết implementation**

```python
# tcformat/runlog.py
"""Deterministic bookkeeping for Stage 2 test execution.

Creates evidence directories and writes per-testcase results back into the
testcase YAML. Does NOT drive a browser — the agent (via Playwright MCP) does
that and calls this helper to record what happened.
"""
from __future__ import annotations
import argparse
from pathlib import Path

from tcformat.schema import load_screen, dump_screen, VALID_STATUSES

VALID_BROWSERS = {"chrome", "safari"}


def evidence_dir(screen_slug: str, browser: str, tc_id: str,
                 root: str = "evidence") -> Path:
    """Create and return evidence/<screen_slug>/<browser>/<tc_id>/."""
    if browser not in VALID_BROWSERS:
        raise ValueError(f"invalid browser '{browser}' (use {VALID_BROWSERS})")
    d = Path(root) / screen_slug / browser / tc_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def record_result(yaml_path, tc_id: str, browser: str, status: str,
                  evidence=None, note=None, bug_id=None,
                  tester=None, date=None) -> None:
    """Set one browser's result on one testcase, then write the YAML back.

    `status` is required and validated. Optional fields are only written when
    provided (None = leave existing value untouched), except `status` which is
    always set.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status '{status}' (use {VALID_STATUSES})")
    if browser not in VALID_BROWSERS:
        raise ValueError(f"invalid browser '{browser}' (use {VALID_BROWSERS})")
    sc = load_screen(yaml_path)
    tc = next((t for t in sc.testcases if t.id == tc_id), None)
    if tc is None:
        raise ValueError(f"testcase '{tc_id}' not found in {yaml_path}")
    br = getattr(tc.result, browser)
    br.status = status
    if evidence is not None:
        br.evidence = list(evidence)
    if note is not None:
        br.note = note
    if bug_id is not None:
        br.bug_id = bug_id
    if tester is not None:
        br.tester = tester
    if date is not None:
        br.date = date
    dump_screen(sc, yaml_path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("evidence-dir", help="create+print an evidence directory")
    e.add_argument("--screen", required=True)
    e.add_argument("--browser", required=True)
    e.add_argument("--id", required=True)
    e.add_argument("--root", default="evidence")

    r = sub.add_parser("record", help="record a testcase result into YAML")
    r.add_argument("--yaml", required=True)
    r.add_argument("--id", required=True)
    r.add_argument("--browser", required=True)
    r.add_argument("--status", required=True)
    r.add_argument("--evidence", action="append", default=None)
    r.add_argument("--note", default=None)
    r.add_argument("--bug-id", dest="bug_id", default=None)
    r.add_argument("--tester", default=None)
    r.add_argument("--date", default=None)

    args = ap.parse_args(argv)
    if args.cmd == "evidence-dir":
        print(evidence_dir(args.screen, args.browser, args.id, root=args.root))
    else:
        record_result(args.yaml, args.id, args.browser, args.status,
                      evidence=args.evidence, note=args.note,
                      bug_id=args.bug_id, tester=args.tester, date=args.date)
        print(f"recorded {args.id} [{args.browser}] = {args.status}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Chạy test để xác nhận PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_runlog.py -v`
Expected: PASS (7 test).

- [ ] **Step 5: Smoke-test CLI**

Run:
```bash
./.venv/Scripts/python.exe -m tcformat.runlog evidence-dir --screen demo --browser chrome --id UI_01 --root reports/_tmp_ev
```
Expected: in ra đường dẫn `reports/_tmp_ev/demo/chrome/UI_01` (rồi xoá thư mục tạm).

- [ ] **Step 6: Commit** (chỉ khi user xác nhận)

```bash
git add tcformat/runlog.py tests/unit/test_runlog.py
git commit -m "feat(runlog): deterministic evidence dirs and result write-back"
```

---

## Task 3: `render_xlsx` — điền cột result

**Files:**
- Modify: `tcformat/render_xlsx.py`
- Test: `tests/unit/test_render_result_cols.py`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/unit/test_render_result_cols.py
from openpyxl import load_workbook
from tcformat.schema import Screen, Testcase, Result, BrowserResult
from tcformat.render_xlsx import render

TEMPLATE = "template/Format test case + Test report.xlsx"


def _row_of(ws, tc_id):
    for r in range(10, ws.max_row + 1):
        if ws.cell(r, 2).value == tc_id:
            return r
    raise AssertionError(f"{tc_id} not found")


def test_render_writes_result_columns(tmp_path):
    sc = Screen(screen="Result Screen", test_level="IT", testcases=[
        Testcase(id="UI_01", section="UI", main_item="x", type="IT",
                 priority="High", steps=["s"], expected=["e"],
                 result=Result(
                     chrome=BrowserResult(status="OK", tester="bot", date="2026-06-15"),
                     safari=BrowserResult(status="NG", bug_id="BUG-1"))),
        Testcase(id="FN_01", section="FUNCTION", main_item="y", type="IT",
                 priority="Low", steps=["s"], expected=["e"]),  # no result
    ])
    out = tmp_path / "r.xlsx"
    render([sc], TEMPLATE, str(out))
    wb = load_workbook(out)
    ws = next(w for w in wb.worksheets if w["C1"].value == "Result Screen")

    r = _row_of(ws, "UI_01")
    assert ws.cell(r, 11).value == "OK"      # Chrome status
    assert ws.cell(r, 13).value == "bot"     # Chrome tester
    assert ws.cell(r, 14).value == "2026-06-15"  # Chrome date
    assert ws.cell(r, 15).value == "NG"      # Safari status
    assert ws.cell(r, 16).value == "BUG-1"   # Safari bug id

    r2 = _row_of(ws, "FN_01")
    assert ws.cell(r2, 11).value is None     # untested → blank
    assert ws.cell(r2, 15).value is None
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_render_result_cols.py -v`
Expected: FAIL — `assert None == "OK"` (cột result đang để trống).

- [ ] **Step 3: Sửa `_write` để điền cột result**

Trong `tcformat/render_xlsx.py`, thêm một helper và gọi trong vòng lặp `_write`, ngay sau dòng `ws.cell(row, 10).value = tc.priority`:

```python
def _write_result(ws, row, result):
    """Fill result columns K..R from a Result (blank when status is None)."""
    cols = [
        (11, result.chrome.status), (12, result.chrome.bug_id),
        (13, result.chrome.tester), (14, result.chrome.date),
        (15, result.safari.status), (16, result.safari.bug_id),
        (17, result.safari.tester), (18, result.safari.date),
    ]
    for c, v in cols:
        if v is not None:
            ws.cell(row, c).value = v
```

Trong `_write`, sau `ws.cell(row, 10).value = tc.priority` thêm:

```python
        _write_result(ws, row, tc.result)
```

Lưu ý: `LAST_COL = 18` đã có sẵn nên `_clear` đã quét tới cột R — không cần đổi.

- [ ] **Step 4: Chạy test để xác nhận PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_render_result_cols.py tests/unit/test_tc_render.py -v`
Expected: PASS (cả test render Stage 1 vẫn xanh).

- [ ] **Step 5: Commit** (chỉ khi user xác nhận)

```bash
git add tcformat/render_xlsx.py tests/unit/test_render_result_cols.py
git commit -m "feat(render): fill testcase-sheet result columns from YAML result"
```

---

## Task 4: Dependencies & gitignore

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Thêm Flask vào requirements**

Thêm dòng vào `requirements.txt`:

```
flask==3.0.3
```

- [ ] **Step 2: Cài vào venv**

Run: `./.venv/Scripts/python.exe -m pip install flask==3.0.3`
Expected: "Successfully installed flask-3.0.3 ..." (cùng các dep Werkzeug/Jinja2 đã có sẵn từ template? nếu thiếu sẽ tự cài).

- [ ] **Step 3: Thêm `evidence/` vào `.gitignore`**

Trong `.gitignore`, dưới mục "Generated outputs" (cạnh `reports/`):

```
evidence/
```

- [ ] **Step 4: Verify import Flask**

Run: `./.venv/Scripts/python.exe -c "import flask; print(flask.__version__)"`
Expected: `3.0.3`.

- [ ] **Step 5: Commit** (chỉ khi user xác nhận)

```bash
git add requirements.txt .gitignore
git commit -m "chore: add flask dependency and ignore evidence/"
```

---

## Task 5: Demo Flask app — "Basic Information Input"

**Files:**
- Create: `demo/app.py`
- Create: `demo/__init__.py` (rỗng, để import trong test)
- Test: `tests/demo/test_demo_app.py`
- Create: `tests/demo/__init__.py` (rỗng) nếu cần cho discovery (theo pattern repo — kiểm tra `tests/unit` có `__init__.py` không; nếu không có thì BỎ QUA file này)

- [ ] **Step 1: Viết test thất bại**

```python
# tests/demo/test_demo_app.py
import pytest
from demo.app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _login(client, email, password):
    return client.post("/login", data={"email": email, "password": password},
                       follow_redirects=False)


def test_screen_requires_login(client):
    resp = client.get("/")
    assert resp.status_code in (302, 401)


def test_login_success_then_screen(client):
    assert _login(client, "a@example.com", "a").status_code in (302, 200)
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Usage" in resp.data
    assert b"Prefecture" in resp.data


def test_login_failure(client):
    resp = _login(client, "a@example.com", "wrong")
    assert resp.status_code == 401


def test_guest_no_permission(client):
    _login(client, "noperm@example.com", "n")
    resp = client.get("/")
    assert resp.status_code == 403


def test_municipalities_cascade(client):
    _login(client, "a@example.com", "a")
    resp = client.get("/api/municipalities?prefecture=13")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data["municipalities"], list) and data["municipalities"]


def test_basic_info_validation_empty(client):
    _login(client, "a@example.com", "a")
    resp = client.post("/api/basic-info", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_basic_info_valid(client):
    _login(client, "a@example.com", "a")
    resp = client.post("/api/basic-info", json={
        "usage": "Residential", "prefecture": "13", "municipality": "Chiyoda"})
    assert resp.status_code == 200
    assert resp.get_json().get("ok") is True


def test_xss_echo_is_escaped(client):
    _login(client, "a@example.com", "a")
    payload = "<script>alert('x')</script>"
    resp = client.post("/api/basic-info", json={
        "usage": "Residential", "prefecture": "13",
        "municipality": payload})
    # whatever the server echoes must NOT contain a raw executable script tag
    assert b"<script>" not in resp.data


def test_user_b_cannot_read_user_a(client):
    _login(client, "a@example.com", "a")
    client.post("/api/basic-info", json={
        "usage": "Residential", "prefecture": "13", "municipality": "Chiyoda"})
    # switch to user b
    client.get("/logout")
    _login(client, "b@example.com", "b")
    resp = client.get("/api/basic-info?owner=a@example.com")
    assert resp.status_code == 403
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

Run: `./.venv/Scripts/python.exe -m pytest tests/demo/test_demo_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'demo'`.

- [ ] **Step 3: Viết `demo/__init__.py` (rỗng) và `demo/app.py`**

`demo/__init__.py`: file rỗng.

```python
# demo/app.py
"""Minimal Flask demo app standing in for the app-under-test (Stage 2).

Implements the "Basic Information Input" screen used by
testcases/basic-information-input.yaml: Usage buttons, cascading
Prefecture->Municipality dropdowns, validation, XSS-safe echo, login + roles.

Run:  ./.venv/Scripts/python.exe demo/app.py   (serves on 127.0.0.1:5005)
"""
from __future__ import annotations
from markupsafe import escape
from flask import (Flask, request, session, redirect, jsonify,
                   render_template_string, abort)

USERS = {
    "admin@example.com": {"password": "admin", "role": "admin"},
    "a@example.com": {"password": "a", "role": "user"},
    "b@example.com": {"password": "b", "role": "user"},
    "noperm@example.com": {"password": "n", "role": "guest"},
}

PREFECTURES = {"13": "Tokyo", "27": "Osaka"}
MUNICIPALITIES = {
    "13": ["Chiyoda", "Shibuya"],
    "27": ["Kita", "Chuo"],
}

# in-memory submitted records keyed by owner email
RECORDS: dict[str, dict] = {}

SCREEN_HTML = """
<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Basic Information Input</title></head><body>
<h1>Basic Information Input</h1>
<form id="biForm">
  <fieldset><legend>Usage</legend>
    <button type="button" id="usageResidential" data-usage="Residential">Residential</button>
    <button type="button" id="usageIndustrial" data-usage="Industrial">Industrial</button>
  </fieldset>
  <label>Prefecture
    <select id="prefecture"><option value="">--</option>
      {% for k, v in prefectures.items() %}<option value="{{ k }}">{{ v }}</option>{% endfor %}
    </select>
  </label>
  <label>Municipality
    <select id="municipality" disabled><option value="">--</option></select>
  </label>
  <button type="submit" id="submitBtn">Submit</button>
</form>
<p id="error" role="alert"></p>
<p id="result"></p>
<script>
let usage = "";
document.querySelectorAll('[data-usage]').forEach(b =>
  b.addEventListener('click', () => { usage = b.dataset.usage;
    document.querySelectorAll('[data-usage]').forEach(x=>x.removeAttribute('aria-pressed'));
    b.setAttribute('aria-pressed','true'); }));
const pref = document.getElementById('prefecture');
const muni = document.getElementById('municipality');
pref.addEventListener('change', async () => {
  muni.innerHTML = '<option value="">--</option>'; muni.value = '';   // clear on change (FN_03)
  if (!pref.value) { muni.disabled = true; return; }
  const r = await fetch('/api/municipalities?prefecture=' + pref.value);
  const d = await r.json();
  d.municipalities.forEach(m => { const o = document.createElement('option');
    o.value = m; o.textContent = m; muni.appendChild(o); });
  muni.disabled = false;
});
let submitting = false;
document.getElementById('biForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (submitting) return; submitting = true;          // anti double-submit (NF_09)
  document.getElementById('error').textContent = '';
  const body = { usage, prefecture: pref.value, municipality: muni.value };
  const r = await fetch('/api/basic-info',
    { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
  const d = await r.json();
  if (!r.ok) { document.getElementById('error').textContent = d.error || 'Error'; }
  else { document.getElementById('result').textContent = 'Saved: ' + d.echo; }  // textContent => XSS-safe
  submitting = false;
});
</script>
</body></html>
"""

LOGIN_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>Login</title></head><body>
<h1>Login</h1>
{% if err %}<p role="alert">{{ err }}</p>{% endif %}
<form method="post" action="/login">
  <input name="email" placeholder="email">
  <input name="password" type="password" placeholder="password">
  <button type="submit">Login</button>
</form></body></html>
"""


def create_app():
    app = Flask(__name__)
    app.secret_key = "demo-secret-key"

    @app.get("/login")
    def login_form():
        return render_template_string(LOGIN_HTML, err=None)

    @app.post("/login")
    def login():
        email = request.form.get("email", "")
        pw = request.form.get("password", "")
        u = USERS.get(email)
        if not u or u["password"] != pw:
            return render_template_string(LOGIN_HTML, err="Invalid credentials"), 401
        session["user"] = email
        session["role"] = u["role"]
        return redirect("/")

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect("/login")

    @app.get("/")
    def screen():
        if "user" not in session:
            return redirect("/login")
        if session.get("role") == "guest":          # NF_07
            return "Bạn không có quyền truy cập màn hình này", 403
        return render_template_string(SCREEN_HTML, prefectures=PREFECTURES)

    @app.get("/api/municipalities")
    def municipalities():
        if "user" not in session:
            abort(401)
        pref = request.args.get("prefecture", "")
        return jsonify({"municipalities": MUNICIPALITIES.get(pref, [])})

    @app.post("/api/basic-info")
    def basic_info():
        if "user" not in session:
            abort(401)
        data = request.get_json(silent=True) or {}
        missing = [k for k in ("usage", "prefecture", "municipality") if not data.get(k)]
        if missing:
            return jsonify({"error": f"Thiếu trường bắt buộc: {', '.join(missing)}"}), 400
        RECORDS[session["user"]] = data
        # echo escaped so a raw <script> can never round-trip executable (NF_04)
        return jsonify({"ok": True, "echo": str(escape(data["municipality"]))})

    @app.get("/api/basic-info")
    def read_basic_info():
        if "user" not in session:
            abort(401)
        owner = request.args.get("owner", session["user"])
        if owner != session["user"]:                # NF_08
            abort(403)
        return jsonify({"record": RECORDS.get(owner)})

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5005)
```

- [ ] **Step 4: Chạy test để xác nhận PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/demo/test_demo_app.py -v`
Expected: PASS (9 test). Nếu `tests/demo` không được discover, thêm `tests/demo/__init__.py` rỗng hoặc kiểm tra `pytest.ini`/`pyproject` rootdir.

- [ ] **Step 5: Smoke-test server thật**

Run (nền): `./.venv/Scripts/python.exe demo/app.py` rồi mở `http://127.0.0.1:5005/login` — đăng nhập `a@example.com`/`a`, thấy màn hình Basic Information Input. Dừng server sau khi xem.

- [ ] **Step 6: Commit** (chỉ khi user xác nhận)

```bash
git add demo/ tests/demo/
git commit -m "feat(demo): Flask Basic Information Input app for stage 2 e2e"
```

---

## Task 6: Skill `run-testcases`

**Files:**
- Create: `.claude/skills/run-testcases/SKILL.md`

- [ ] **Step 1: Viết SKILL.md**

```markdown
---
name: run-testcases
description: Use when executing generated test cases against a web app via Playwright MCP, capturing per-step screenshots and recording OK/NG/N·A results. Triggers - "chạy test case", "run testcases", "execute test cases".
---

# Run Test Cases (Stage 2 — agent + Playwright MCP)

Drive the NL `steps` in `testcases/<screen>.yaml` against a running web app via
Playwright MCP, screenshot every step as evidence, judge each testcase against
its `expected`, and record results back into the YAML with `tcformat.runlog`.

## Inputs you gather first
1. Testcase file: `testcases/<screen-slug>.yaml` (+ which testcase IDs to run; default all).
2. Target: `config/config.yaml` (base_url/port) and `config/users.yaml` (role accounts).
   For the bundled demo, start it first:
   `./.venv/Scripts/python.exe demo/app.py` (127.0.0.1:5005) — run in background.
3. Browser: `chrome` (chromium) primary; `safari` (webkit) optional subset.

## Process — for EACH testcase
1. Make the evidence dir:
   `./.venv/Scripts/python.exe -m tcformat.runlog evidence-dir --screen <slug> --browser chrome --id <ID>`
2. Reset state: `browser_navigate` to base_url. If `precondition` mentions a role,
   log in the matching user from `config/users.yaml` via the app's login form.
3. Execute each `step` in order via Playwright MCP tools
   (`browser_navigate/click/type/select_option/press_key/...`), reading
   `browser_snapshot` to pick selectors.
4. After EACH step: `browser_take_screenshot` saving to
   `evidence/<slug>/chrome/<ID>/step_<N>.png`.
5. Judge `expected`:
   - All expected met -> `OK`.
   - An expected fails -> `NG`; write a `--note` describing the bug.
   - Step not automatable (Figma compare, DevTools Styles, memory) -> `N/A` with a
     `--note` giving the reason; still screenshot what is visible.
6. Optional deterministic aux checks via `toolkit/checks` (console-clean for NF_01,
   perf timing NF_02/NF_03, XSS-safe for NF_04).
7. Record the result:
   `./.venv/Scripts/python.exe -m tcformat.runlog record --yaml testcases/<slug>.yaml \
       --id <ID> --browser chrome --status OK|NG|N/A --note "..." \
       --evidence evidence/<slug>/chrome/<ID>/step_1.png --evidence ...`

## Stop rule
A failing step does NOT abort the session: mark that testcase `NG`, note it, move
to the next testcase.

## Output
- `testcases/<slug>.yaml` with `result` filled for the run IDs.
- `evidence/<slug>/chrome/<ID>/step_N.png` trees.
- Optionally re-render the xlsx (see HANDOFF Stage 1 snippet) to show result columns.
```

- [ ] **Step 2: Verify skill phát hiện được**

Run: `ls .claude/skills/run-testcases/SKILL.md` — tồn tại. (Skill được nạp ở session sau.)

- [ ] **Step 3: Commit** (chỉ khi user xác nhận)

```bash
git add .claude/skills/run-testcases/SKILL.md
git commit -m "feat(skill): run-testcases procedure for stage 2 execution"
```

---

## Task 7: Chạy end-to-end lát cắt 3–5 testcase (bằng chứng)

> Đây là bước **agent-interactive** (không phải pytest). Thực hiện ngay trong phiên
> bằng skill `run-testcases` đã tạo. Mục tiêu: sinh evidence thật + điền result.

**Lát cắt chọn (4 testcase, browser chrome):** `UI_02` (đếm thành phần UI),
`FN_02` (validate rỗng), `FN_03` (cascading Prefecture→Municipality), `NF_04` (XSS).
`UI_03`/`UI_04`/`NF_05` minh hoạ N·A nếu muốn.

- [ ] **Step 1: Start demo app nền**

Run (background): `./.venv/Scripts/python.exe demo/app.py`
Expected: server lắng nghe 127.0.0.1:5005.

- [ ] **Step 2: Chạy skill cho lát cắt**

Dùng skill `run-testcases` với `testcases/basic-information-input.yaml`, browser
chrome, các ID: UI_02, FN_02, FN_03, NF_04. Mỗi step → screenshot vào
`evidence/basic-information-input/chrome/<ID>/step_N.png`; gọi `runlog record` ghi kết quả.

- [ ] **Step 3: Verify evidence + YAML**

Run:
```bash
./.venv/Scripts/python.exe -c "from tcformat.schema import load_screen; sc=load_screen('testcases/basic-information-input.yaml'); [print(t.id, t.result.chrome.status, t.result.chrome.evidence) for t in sc.testcases if t.id in {'UI_02','FN_02','FN_03','NF_04'}]"
```
Expected: mỗi ID có status (OK/NG/N·A) và list evidence path tồn tại trên đĩa.

- [ ] **Step 4: (Tuỳ chọn) Re-render xlsx có result**

Run:
```bash
./.venv/Scripts/python.exe -c "from tcformat.schema import load_screen; from tcformat.render_xlsx import render; sc=load_screen('testcases/basic-information-input.yaml'); render([sc],'template/Format test case + Test report.xlsx','testcases/basic-information-input.xlsx'); print('rendered')"
```
Expected: sheet "4.x" có cột Status điền cho 4 ID đã chạy.

- [ ] **Step 5: Dừng demo app nền.**

> Không commit `evidence/` và `testcases/` (đã gitignore). Đây là bằng chứng chạy, không phải artifact source.

---

## Task 8: Cập nhật suite + HANDOFF

**Files:**
- Modify: `HANDOFF.md`

- [ ] **Step 1: Chạy TOÀN BỘ test**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: tất cả PASS (41 cũ + ~18 mới = ~59). Nếu đỏ → systematic-debugging trước khi tiếp.

- [ ] **Step 2: Cập nhật HANDOFF.md**

- Đổi sơ đồ pipeline: Stage 2 từ "⬜ CHƯA LÀM" → "✅ XONG (helper runlog + skill run-testcases + demo app)".
- Mục "Đã hoàn thành": thêm Stage 2 (runlog.py, render result cols, demo Flask, skill).
- Mục "Chưa làm": chỉ còn Stage 3.
- Cập nhật số test (≈59 passed).
- Mục 6 → thay bằng mô tả Stage 3 là việc tiếp theo (đọc result YAML → gen_report nhúng/đính kèm evidence).

- [ ] **Step 3: Commit** (chỉ khi user xác nhận)

```bash
git add HANDOFF.md
git commit -m "docs: mark stage 2 complete, point handoff at stage 3"
```

---

## Self-Review notes

- **Spec coverage:** demo app (§3.1)→T5; runlog (§3.2)→T2; schema note (§3.3)→T1;
  render result cols (§3.4)→T3; skill (§3.5)→T6; tests (§4)→T1-3,T5 + e2e→T7;
  evidence/gitignore (§5)→T4; DoD (§7)→T8.
- **Type consistency:** `record_result(yaml, tc_id, browser, status, evidence, note, bug_id, tester, date)` dùng nhất quán giữa T2 (định nghĩa) và T6/T7 (gọi qua CLI). `evidence_dir(screen_slug, browser, tc_id, root)` nhất quán. Cột result K..R nhất quán giữa T3 và mapping template.
- **Placeholder scan:** không có TBD/TODO; mọi step có code/command cụ thể.
- **Ẩn số đã chốt:** mapping cột result lấy từ template (row 9); `note` không có cột → chỉ ở YAML.
