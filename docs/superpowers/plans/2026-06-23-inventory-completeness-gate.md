# Inventory Completeness Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a forgotten element-dimension (e.g. the form-submit `api` element) a hard `tk-coverage` failure, with an app-grounded DOM audit as an advisory second net.

**Architecture:** Add a deterministic, YAML-only completeness lint (`tcformat/inventory_lint.py`, rules R1/R2/R3) surfaced through the existing `tk-coverage` gate (one CLI, one exit code). Add a pure-Python advisory differ (`tcformat/inventory_audit.py` + `tk-inventory-audit`) that diffs an inventory against a Playwright-MCP DOM snapshot. No new runtime deps.

**Tech Stack:** Python 3.13, dataclasses, PyYAML, pytest. Console scripts via `[project.scripts]` in `pyproject.toml`.

## Global Constraints

- No Python-Playwright dependency — DOM snapshot is produced externally by Playwright MCP; the audit consumes a snapshot file. (DoD: "Stage 2 uses the Playwright MCP server, no Python Playwright dep".)
- Lint is a **hard gate** (non-zero exit); DOM audit is **advisory** (always exit 0).
- App-agnostic: lint rules derive only from the screen YAML + inventory YAML. No per-framework source parsing.
- Spec/strategy artifacts are Vietnamese; keep new user-facing strings consistent.
- Git: do NOT run `git add`/`commit`/`push` without explicit user confirmation (user global policy). Each "Commit" step below is a **proposed** commit — pause for confirmation.
- Run tests with the repo venv: `./.venv/Scripts/python.exe -m pytest`.

---

### Task 1: `Inventory.absent` field + loader

**Files:**
- Modify: `tcformat/inventory.py:34-37` (Inventory dataclass), `tcformat/inventory.py:62-67` (load_inventory)
- Test: `tests/unit/test_inventory.py`

**Interfaces:**
- Produces: `Inventory.absent: dict[str, str]` (kind → reason), default `{}`. `load_inventory(path) -> Inventory` parses top-level `absent:` mapping; raises `InventoryError` if `absent` is not a mapping.

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_inventory.py`:

```python
def test_load_inventory_parses_absent(tmp_path):
    from tcformat.inventory import load_inventory
    p = tmp_path / "s.inventory.yaml"
    p.write_text(
        "screen: S\n"
        "absent:\n"
        "  api: 'Màn chỉ hiển thị, không gọi backend.'\n"
        "elements:\n"
        "  - {id: btn, kind: button, label: B}\n",
        encoding="utf-8")
    inv = load_inventory(p)
    assert inv.absent == {"api": "Màn chỉ hiển thị, không gọi backend."}


def test_load_inventory_absent_defaults_empty(tmp_path):
    from tcformat.inventory import load_inventory
    p = tmp_path / "s.inventory.yaml"
    p.write_text("screen: S\nelements: []\n", encoding="utf-8")
    assert load_inventory(p).absent == {}


def test_load_inventory_absent_must_be_mapping(tmp_path):
    import pytest
    from tcformat.inventory import load_inventory, InventoryError
    p = tmp_path / "s.inventory.yaml"
    p.write_text("screen: S\nabsent: [api]\nelements: []\n", encoding="utf-8")
    with pytest.raises(InventoryError):
        load_inventory(p)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_inventory.py -k absent -v`
Expected: FAIL (`Inventory` has no attribute `absent` / TypeError on unexpected kwarg).

- [ ] **Step 3: Implement**

In `tcformat/inventory.py`, extend the dataclass:

```python
@dataclass
class Inventory:
    screen: str
    elements: list = field(default_factory=list)
    absent: dict = field(default_factory=dict)
```

Replace `load_inventory`:

```python
def load_inventory(path) -> Inventory:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not data.get("screen"):
        raise InventoryError("missing required 'screen'")
    elements = [_element(e) for e in (data.get("elements") or [])]
    absent = data.get("absent") or {}
    if not isinstance(absent, dict):
        raise InventoryError("'absent' must be a mapping of kind -> reason")
    absent = {str(k): str(v) for k, v in absent.items()}
    return Inventory(screen=data["screen"], elements=elements, absent=absent)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_inventory.py -v`
Expected: PASS (all, including pre-existing inventory tests).

- [ ] **Step 5: Commit (pause for user confirmation)**

```bash
git add tcformat/inventory.py tests/unit/test_inventory.py
git commit -m "feat(inventory): add declared-absence registry (Inventory.absent)"
```

---

### Task 2: `inventory_lint.py` — completeness rules R1/R2/R3

**Files:**
- Create: `tcformat/inventory_lint.py`
- Test: `tests/unit/test_inventory_lint.py` (new)

**Interfaces:**
- Consumes: `Inventory` (with `.elements`, `.absent`), `Screen` (with `.testcases`; each testcase has `.id`, `.target`, `.expected` list of str|dict).
- Produces:
  - `LintViolation(rule: str, message: str, target: str = "")`
  - `LintReport(violations: list)` with property `ok -> bool` (True when no violations)
  - `check_completeness(inventory, screen) -> LintReport`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_inventory_lint.py`:

```python
from tcformat.inventory import Inventory, Element
from tcformat.schema import Screen, Testcase
from tcformat.inventory_lint import check_completeness


def _screen(testcases):
    return Screen(screen="S", test_level="IT", testcases=testcases)


def _tc(id, target=None, expected=None):
    return Testcase(id=id, main_item=id, target=target, expected=expected or [])


def test_R1_request_expected_without_api_fails():
    inv = Inventory(screen="S", elements=[Element(id="b", kind="button")])
    sc = _screen([_tc("T1", target="b",
                       expected=[{"request": "POST /"}])])
    rep = check_completeness(inv, sc)
    assert not rep.ok
    assert any(v.rule == "R1" for v in rep.violations)


def test_R1_satisfied_by_api_element():
    inv = Inventory(screen="S", elements=[Element(id="submit", kind="api")])
    sc = _screen([_tc("T1", target="submit",
                       expected=[{"redirect": "/home"}])])
    assert check_completeness(inv, sc).ok


def test_R1_satisfied_by_declared_absent():
    inv = Inventory(screen="S", elements=[Element(id="b", kind="button")],
                    absent={"api": "Không gọi backend."})
    sc = _screen([_tc("T1", target="b", expected=[{"request": "POST /"}])])
    assert check_completeness(inv, sc).ok


def test_R1_absent_with_empty_reason_does_not_satisfy():
    inv = Inventory(screen="S", elements=[Element(id="b", kind="button")],
                    absent={"api": "   "})
    sc = _screen([_tc("T1", target="b", expected=[{"request": "POST /"}])])
    assert not check_completeness(inv, sc).ok


def test_R1_not_triggered_without_request_or_redirect():
    inv = Inventory(screen="S", elements=[Element(id="b", kind="button")])
    sc = _screen([_tc("T1", target="b", expected=["nút phản hồi đúng"])])
    assert check_completeness(inv, sc).ok


def test_R3_target_must_exist():
    inv = Inventory(screen="S", elements=[Element(id="b", kind="button")])
    sc = _screen([_tc("T1", target="ghost", expected=["x"])])
    rep = check_completeness(inv, sc)
    assert any(v.rule == "R3" and v.target == "ghost" for v in rep.violations)


def test_R3_screen_target_is_valid():
    inv = Inventory(screen="S", elements=[Element(id="b", kind="button")])
    sc = _screen([_tc("T1", target="screen", expected=["x"])])
    assert all(v.rule != "R3" for v in check_completeness(inv, sc).violations)
```

> Note: confirm the real `Testcase`/`Screen` constructor kwargs while implementing (see `tcformat/schema.py`). If positional/required fields differ, adapt the `_tc`/`_screen` helpers — keep the assertions identical.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_inventory_lint.py -v`
Expected: FAIL (`No module named 'tcformat.inventory_lint'`).

- [ ] **Step 3: Implement**

Create `tcformat/inventory_lint.py`:

```python
"""Stage 1 completeness lint — catches a forgotten element DIMENSION.

`tk-coverage`'s depth check only validates technique cells for elements that
EXIST in the inventory; it cannot flag a whole element kind that was never
listed. These deterministic, YAML-only rules close that blind spot:

- R1  request/redirect expected ⇒ inventory must have an `api` element
      (or declare `absent.api: "<reason>"`).
- R2  declared-absence registry: a kind in `inventory.absent` with a non-empty
      reason satisfies the "must have ≥1 of this kind" rules (escape hatch).
- R3  every testcase `target` must be `screen` or an existing element id.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class LintViolation:
    rule: str
    message: str
    target: str = ""


@dataclass
class LintReport:
    violations: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def _declared_absent(inventory, kind: str) -> bool:
    return bool((inventory.absent.get(kind) or "").strip())


def check_completeness(inventory, screen) -> LintReport:
    violations: list = []
    element_ids = {el.id for el in inventory.elements}
    kinds = {el.kind for el in inventory.elements}

    # R1 (+ R2 escape hatch): a backend call is asserted via structured
    # request/redirect expected keys, so an `api` element must be inventoried.
    needs_api = any(
        isinstance(item, dict)
        and (item.get("request") is not None or item.get("redirect") is not None)
        for tc in screen.testcases
        for item in tc.expected
    )
    if needs_api and "api" not in kinds and not _declared_absent(inventory, "api"):
        violations.append(LintViolation(
            rule="R1",
            message=("Có testcase với assertion request/redirect nhưng inventory "
                     "thiếu element kind 'api'. Thêm 1 element api, hoặc khai báo "
                     "absent.api: \"<lý do>\" trong inventory."),
            target="api"))

    # R3: referential integrity of testcase target -> inventory element.
    for tc in screen.testcases:
        if tc.target and tc.target != "screen" and tc.target not in element_ids:
            violations.append(LintViolation(
                rule="R3",
                message=(f"testcase {tc.id}: target '{tc.target}' không tồn tại "
                         "trong inventory (thêm element hoặc sửa target)."),
                target=tc.target))

    return LintReport(violations=violations)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_inventory_lint.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit (pause for user confirmation)**

```bash
git add tcformat/inventory_lint.py tests/unit/test_inventory_lint.py
git commit -m "feat(inventory): completeness lint rules R1/R2/R3"
```

---

### Task 3: Wire lint into `tk-coverage` (hard gate)

**Files:**
- Modify: `tcformat/coverage_cli.py:51-86`
- Test: `tests/unit/test_coverage_cli.py`

**Interfaces:**
- Consumes: `check_completeness(inventory, screen)` from Task 2; `run_depth_check(...)` already returns `(screen, inventory, checklists, report)`.
- Produces: `tk-coverage` prints an "INVENTORY COMPLETENESS" section and exits non-zero when there are lint violations OR depth gaps.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_coverage_cli.py` (follow the file's existing fixture style for writing a screen + inventory to `tmp_path`; the screen must contain a testcase whose `expected` has a `request:` key and whose inventory has NO `api` element):

```python
def test_main_exits_nonzero_on_completeness_violation(tmp_path, capsys):
    import pytest
    from tcformat.coverage_cli import main
    screen = tmp_path / "s.yaml"
    screen.write_text(
        "screen: S\ntest_level: IT\ntestcases:\n"
        "  - id: T1\n    main_item: m\n    target: btn\n    technique: single-action\n"
        "    expected:\n      - {request: 'POST /'}\n",
        encoding="utf-8")
    inv = tmp_path / "s.inventory.yaml"
    inv.write_text(
        "screen: S\nelements:\n  - {id: btn, kind: button, label: B}\n",
        encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        main(["--screen", str(screen), "--inventory", str(inv)])
    assert e.value.code == 1
    out = capsys.readouterr().out
    assert "COMPLETENESS" in out and "R1" in out


def test_main_completeness_passes_with_declared_absent(tmp_path):
    import pytest
    from tcformat.coverage_cli import main
    screen = tmp_path / "s.yaml"
    screen.write_text(
        "screen: S\ntest_level: IT\ntestcases:\n"
        "  - id: T1\n    main_item: m\n    target: btn\n    technique: single-action\n"
        "    expected:\n      - {request: 'POST /'}\n",
        encoding="utf-8")
    inv = tmp_path / "s.inventory.yaml"
    inv.write_text(
        "screen: S\nabsent:\n  api: 'mock POST, không kiểm response'\n"
        "elements:\n  - {id: btn, kind: button, label: B}\n",
        encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        main(["--screen", str(screen), "--inventory", str(inv)])
    # No depth gaps for a single covered button technique, no lint violation:
    assert e.value.code == 0
```

> While implementing, verify the depth check does not itself produce gaps for this minimal screen (the button kind has techniques beyond `single-action`). If it does, the second test should assert the exit reflects only depth — instead give the button `skip_techniques` for the other techniques in the inventory YAML so depth is clean and the test isolates the completeness behavior. Keep the first test as the canonical R1 gate.

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_coverage_cli.py -k completeness -v`
Expected: FAIL (exit code 0 instead of 1 / "COMPLETENESS" not in output).

- [ ] **Step 3: Implement**

In `tcformat/coverage_cli.py`, capture the screen from `run_depth_check` (currently discarded as `_`) and run the lint. Change lines 52-53 from:

```python
    _, inventory, checklists, report = run_depth_check(
        args.screen, inv_path, config=args.config)
```

to:

```python
    screen, inventory, checklists, report = run_depth_check(
        args.screen, inv_path, config=args.config)
    from tcformat.inventory_lint import check_completeness
    lint = check_completeness(inventory, screen)
```

Immediately before the matrix print (`print("\n" + matrix)`), add the completeness section:

```python
    if lint.violations or inventory.absent:
        print(f"\nINVENTORY COMPLETENESS ({len(lint.violations)} violation(s)):")
        for v in lint.violations:
            print(f"  ✗ [{v.rule}] {v.message}")
        for kind, reason in inventory.absent.items():
            print(f"  – absent.{kind}: {reason}")
```

Change the final exit line from:

```python
    raise SystemExit(1 if report.gaps else 0)
```

to:

```python
    raise SystemExit(1 if (report.gaps or lint.violations) else 0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_coverage_cli.py -v`
Expected: PASS (new + existing).

- [ ] **Step 5: Regression — real screen still passes**

Run:
```bash
cd /d/Aptech-souce/web-planner-kitchen && \
  ./.venv/Scripts/tk-coverage.exe --screen testcases/hows-renkei.yaml --config config/config.yaml; echo "exit=$?"
```
Expected: `exit=0`; output shows `INVENTORY COMPLETENESS` with no violations (the `submit-api` element satisfies R1). If the web-planner venv lacks the new code, reinstall the package there (`./.venv/Scripts/pip.exe install -e <path-to-Testing-kit>`), or run via the Testing-kit venv module path.

- [ ] **Step 6: Commit (pause for user confirmation)**

```bash
git add tcformat/coverage_cli.py tests/unit/test_coverage_cli.py
git commit -m "feat(tk-coverage): run completeness lint as hard gate before depth"
```

---

### Task 4: `inventory_audit.py` + `tk-inventory-audit` CLI (advisory)

**Files:**
- Create: `tcformat/inventory_audit.py`
- Modify: `pyproject.toml:15-19` (`[project.scripts]`)
- Test: `tests/unit/test_inventory_audit.py` (new)

**Interfaces:**
- Consumes: `Inventory` (Task 1); a snapshot `dict` of shape
  `{"elements": [{"role": str, "name": str}, ...], "forms": [{"action": str, "method": str}, ...]}`.
- Produces:
  - `AuditReport(missing: list[str], stale: list[str], form_without_api: bool)`
  - `audit_inventory(inventory, snapshot: dict) -> AuditReport`
  - `format_report(inventory, report) -> str` (markdown)
  - `main(argv=None)` for the `tk-inventory-audit` console script; **always exits 0**.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_inventory_audit.py`:

```python
from tcformat.inventory import Inventory, Element
from tcformat.inventory_audit import audit_inventory


SNAP = {
    "elements": [
        {"role": "textbox", "name": "userId"},
        {"role": "combobox", "name": "mode"},
        {"role": "button", "name": "Lクラス"},
    ],
    "forms": [{"action": "/", "method": "POST"}],
}


def test_missing_dom_element_not_in_inventory():
    inv = Inventory(screen="S", elements=[
        Element(id="userId", kind="input", label="ユーザーID"),
        Element(id="submit", kind="api"),
        # 'mode' and the Lクラス button are present in the DOM but NOT inventoried
    ])
    rep = audit_inventory(inv, SNAP)
    assert "mode" in rep.missing
    assert any("クラス" in m for m in rep.missing)


def test_stale_inventory_element_not_in_dom():
    inv = Inventory(screen="S", elements=[
        Element(id="userId", kind="input"),
        Element(id="mode", kind="select"),
        Element(id="ghostField", kind="input", label="ghost"),
        Element(id="submit", kind="api"),
        Element(id="preset-l", kind="button", label="Lクラス"),
    ])
    rep = audit_inventory(inv, SNAP)
    assert "ghostField" in rep.stale
    assert "userId" not in rep.stale


def test_form_without_api_flag():
    inv = Inventory(screen="S", elements=[Element(id="userId", kind="input")])
    rep = audit_inventory(inv, SNAP)
    assert rep.form_without_api is True


def test_form_with_api_not_flagged():
    inv = Inventory(screen="S", elements=[Element(id="submit", kind="api")])
    rep = audit_inventory(inv, SNAP)
    assert rep.form_without_api is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_inventory_audit.py -v`
Expected: FAIL (`No module named 'tcformat.inventory_audit'`).

- [ ] **Step 3: Implement**

Create `tcformat/inventory_audit.py`:

```python
"""Advisory DOM audit — diff an authored inventory against a live DOM snapshot.

Second net for the inventory blind spot. The snapshot is produced EXTERNALLY by
Playwright MCP (no python-playwright dep here) and handed in as a dict:

    {"elements": [{"role": "textbox", "name": "userId"}, ...],
     "forms":    [{"action": "/", "method": "POST"}, ...]}

Matching identity: input/select elements by `name` ↔ inventory id/label; buttons
by visible text ↔ inventory label/id. All matching is normalized (lower/strip).
This is heuristic (hidden/conditional elements may mis-match) so the tool is
ADVISORY: it prints suspicions and ALWAYS exits 0.
"""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

_FIELD_ROLES = {"textbox", "combobox", "listbox", "spinbutton", "searchbox", "slider"}
_BUTTON_ROLES = {"button", "link"}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


@dataclass
class AuditReport:
    missing: list   # DOM identities with no inventory match
    stale: list     # inventory ids (input/select/button) with no DOM match
    form_without_api: bool


def audit_inventory(inventory, snapshot: dict) -> AuditReport:
    els = snapshot.get("elements") or []
    forms = snapshot.get("forms") or []

    inv_keys = set()          # normalized id + label for every element
    for el in inventory.elements:
        inv_keys.add(_norm(el.id))
        if el.label:
            inv_keys.add(_norm(el.label))

    missing = []
    for el in els:
        role = _norm(el.get("role"))
        name = el.get("name") or ""
        if role in _FIELD_ROLES or role in _BUTTON_ROLES:
            if _norm(name) not in inv_keys:
                missing.append(name)

    dom_keys = {_norm(el.get("name")) for el in els}
    stale = []
    for el in inventory.elements:
        if el.kind not in ("input", "select", "button"):
            continue
        keys = {_norm(el.id)} | ({_norm(el.label)} if el.label else set())
        if not (keys & dom_keys):
            stale.append(el.id)

    has_api = any(el.kind == "api" for el in inventory.elements)
    form_without_api = bool(forms) and not has_api

    return AuditReport(missing=missing, stale=stale,
                       form_without_api=form_without_api)


def format_report(inventory, report: AuditReport) -> str:
    lines = [f"# Inventory audit — {inventory.screen}", ""]
    lines.append(f"## SUSPECTED MISSING ({len(report.missing)}) "
                 "— có trên DOM, thiếu trong inventory")
    lines += [f"- {m}" for m in report.missing] or ["- (none)"]
    lines.append("")
    lines.append(f"## SUSPECTED STALE ({len(report.stale)}) "
                 "— có trong inventory, không thấy trên DOM")
    lines += [f"- {s}" for s in report.stale] or ["- (none)"]
    lines.append("")
    if report.form_without_api:
        lines.append("## ⚠ FORM WITHOUT API — DOM có <form> nhưng inventory "
                     "thiếu element kind 'api' (xem lint R1).")
    lines.append("")
    lines.append("_Advisory — đối chiếu thủ công, không tự sửa._")
    return "\n".join(lines)


def main(argv=None):
    for _stream in (sys.stdout, sys.stderr):
        rc = getattr(_stream, "reconfigure", None)
        if rc is not None:
            rc(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Advisory inventory vs DOM-snapshot audit.")
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--snapshot", required=True, help="JSON snapshot file")
    ap.add_argument("--out", default=None, help="also write the markdown report here")
    args = ap.parse_args(argv)

    from tcformat.inventory import load_inventory
    inventory = load_inventory(args.inventory)
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    report = audit_inventory(inventory, snapshot)
    text = format_report(inventory, report)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"\nAudit -> {args.out}")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_inventory_audit.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Register the console script**

In `pyproject.toml` under `[project.scripts]`, add:

```toml
tk-inventory-audit = "tcformat.inventory_audit:main"
```

Then reinstall so the script appears: `./.venv/Scripts/pip.exe install -e .`
Verify: `./.venv/Scripts/tk-inventory-audit.exe --help` prints usage.

- [ ] **Step 6: Commit (pause for user confirmation)**

```bash
git add tcformat/inventory_audit.py tests/unit/test_inventory_audit.py pyproject.toml
git commit -m "feat: tk-inventory-audit advisory DOM-snapshot vs inventory differ"
```

---

### Task 5: Update `generate-testcases` skill doc

**Files:**
- Modify: `skills/generate-testcases/SKILL.md`

**Interfaces:** Documentation only — no code interface.

- [ ] **Step 1: Update the depth-gate step (step 4)**

In `skills/generate-testcases/SKILL.md`, in the "Kiểm tra độ phủ chiều sâu" section, add after the description of `tk-coverage`:

```markdown
   `tk-coverage` nay chạy **completeness lint (hard gate)** TRƯỚC depth:
   - R1: nếu có testcase với assertion `request`/`redirect` thì inventory phải có
     element `kind: api` (hoặc khai báo `absent.api: "<lý do>"`).
   - R3: mọi `target` của testcase phải là `screen` hoặc id element có thật.
   Vi phạm → exit non-zero, section "INVENTORY COMPLETENESS" liệt kê cách sửa
   (thêm element, hoặc thêm `absent.<kind>: "<lý do>"` vào inventory).
```

- [ ] **Step 2: Add the advisory audit step (under step 1, inventory building)**

After the "Pause and have a human confirm the inventory is complete" paragraph, add:

```markdown
   **(Advisory) Đối chiếu với app thật:** nếu app đang chạy, dùng Playwright MCP
   `browser_snapshot` chụp cây element của màn, lưu thành JSON
   `{elements:[{role,name}], forms:[{action,method}]}`, rồi chạy:
   ```bash
   ./.venv/Scripts/tk-inventory-audit --inventory testcases/<screen>.inventory.yaml \
       --snapshot <snapshot.json> --out reports/<screen>_inventory-audit.md
   ```
   Đối chiếu các cảnh báo SUSPECTED MISSING / STALE / FORM-WITHOUT-API trước khi
   chốt inventory. Đây là advisory (luôn exit 0) — không tự sửa, người/AI quyết định.
```

- [ ] **Step 3: Commit (pause for user confirmation)**

```bash
git add skills/generate-testcases/SKILL.md
git commit -m "docs(skill): document completeness gate + advisory inventory audit"
```

---

## Final verification

- [ ] Run the whole unit suite: `./.venv/Scripts/python.exe -m pytest tests/unit -q` → all green.
- [ ] Regression on a real screen: `tk-coverage` on `hows-renkei` exits 0 with a clean completeness section; temporarily removing the `submit-api` element makes it exit 1 with an R1 violation (revert after checking).

## Self-review notes (author)

- **Spec coverage:** R1 (Task 2/3), R2 `absent` (Task 1/2), R3 (Task 2/3), DOM audit advisory (Task 4), skill updates (Task 5), no-python-playwright honored (snapshot consumed as file). `expected_kinds` generalization intentionally omitted (spec §4.1 marks it out of v1 scope).
- **Type consistency:** `check_completeness(inventory, screen)`, `LintReport.violations`, `LintViolation.rule/message/target`, `audit_inventory(inventory, snapshot)`, `AuditReport.missing/stale/form_without_api` used identically across tasks and the CLI wiring.
- **Open implementation check (flagged in-task):** the exact `Testcase`/`Screen` constructor signature (Task 2 helpers) and whether the minimal coverage_cli test screen yields incidental depth gaps (Task 3 note) must be confirmed against `tcformat/schema.py` at implementation time.
```
