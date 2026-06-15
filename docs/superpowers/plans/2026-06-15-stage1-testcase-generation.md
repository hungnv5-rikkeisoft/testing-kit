# Stage 1 — Test Case Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic backbone for AI-hybrid test case generation: a YAML test-case schema, a strategy-object extractor with coverage checking, a renderer that produces team-format xlsx, and an orchestration skill for the AI drafting step.

**Architecture:** A new `tcformat/` package holds the shared YAML contract (schema), the strategy.xlsx object extractor (refs), coverage checking, and the YAML→xlsx renderer that clones the team template's testcase sheet. A `.claude/skills/generate-testcases` skill drives the AI drafting + coverage loop. `scripts/gen_checklist.py` is refactored to reuse the shared extractor (DRY).

**Tech Stack:** Python 3.13 (`.venv`), pytest, pyyaml, openpyxl.

> **Environment:** Use `d:/Testing-kit/.venv/Scripts/python.exe` for all python/pytest. **Per project policy, every `git add`/`git commit` step REQUIRES explicit user confirmation.**

---

## File Structure

| File | Responsibility |
|------|----------------|
| `tcformat/__init__.py` | Package marker |
| `tcformat/schema.py` | YAML contract dataclasses + load/dump/validate |
| `tcformat/strategy.py` | Extract testing objects + refs from strategy.xlsx |
| `tcformat/coverage.py` | Compare testcase refs vs strategy refs |
| `tcformat/render_xlsx.py` | Render screens → team-template xlsx |
| `scripts/gen_checklist.py` | (Modify) delegate extraction to `tcformat.strategy` |
| `.claude/skills/generate-testcases/SKILL.md` | AI orchestration process |
| `tests/fixtures/design-sample.md` | Sample design doc for the manual demo |
| `tests/unit/test_tc_schema.py` … | Unit tests per module |

---

## Task 1: tcformat package + YAML schema

**Files:**
- Create: `tcformat/__init__.py`
- Create: `tcformat/schema.py`
- Test: `tests/unit/test_tc_schema.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_tc_schema.py`:
```python
from dataclasses import asdict
import pytest
from tcformat.schema import load_screen, dump_screen, SchemaError, Screen, Testcase

SAMPLE = """
screen: "Basic Info"
test_level: IT
testcases:
  - id: UI_01
    section: UI
    main_item: "Move screen"
    type: IT
    priority: High
    strategy_ref: "2.3.1#1"
    precondition: "Logged in"
    steps: ["Open screen", "Click menu"]
    expected: ["Screen shows"]
"""


def _write(tmp_path, text):
    p = tmp_path / "s.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_screen_parses(tmp_path):
    sc = load_screen(_write(tmp_path, SAMPLE))
    assert sc.screen == "Basic Info"
    assert sc.test_level == "IT"
    assert len(sc.testcases) == 1
    tc = sc.testcases[0]
    assert tc.id == "UI_01"
    assert tc.steps == ["Open screen", "Click menu"]
    assert tc.result.chrome.status is None
    assert tc.result.safari.evidence == []


def test_invalid_priority_raises(tmp_path):
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, SAMPLE.replace("priority: High", "priority: Urgent")))


def test_missing_id_raises(tmp_path):
    y = "screen: S\ntestcases:\n  - type: IT\n    priority: Low\n"
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, y))


def test_duplicate_id_raises(tmp_path):
    y = ("screen: S\ntestcases:\n"
         "  - id: A\n    type: IT\n    priority: Low\n"
         "  - id: A\n    type: IT\n    priority: Low\n")
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, y))


def test_roundtrip(tmp_path):
    sc = load_screen(_write(tmp_path, SAMPLE))
    out = tmp_path / "o.yaml"
    dump_screen(sc, out)
    sc2 = load_screen(out)
    assert asdict(sc) == asdict(sc2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_tc_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tcformat.schema'`

- [ ] **Step 3: Write minimal implementation**

`tcformat/__init__.py`:
```python
"""Shared test-case format: YAML schema, strategy refs, coverage, xlsx render."""
```

`tcformat/schema.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import yaml

VALID_LEVELS = {"UT", "IT", "ST"}
VALID_PRIORITIES = {"Low", "Medium", "High"}


class SchemaError(Exception):
    pass


@dataclass
class BrowserResult:
    status: str | None = None
    bug_id: str | None = None
    tester: str | None = None
    date: str | None = None
    evidence: list = field(default_factory=list)


@dataclass
class Result:
    chrome: BrowserResult = field(default_factory=BrowserResult)
    safari: BrowserResult = field(default_factory=BrowserResult)


@dataclass
class Testcase:
    id: str
    section: str = ""
    main_item: str = ""
    middle_item: str = ""
    minor_item: str = ""
    type: str = "IT"
    priority: str = "Medium"
    strategy_ref: str = ""
    precondition: str = ""
    steps: list = field(default_factory=list)
    expected: list = field(default_factory=list)
    result: Result = field(default_factory=Result)


@dataclass
class Screen:
    screen: str
    test_level: str = "IT"
    created_by: str = ""
    source_docs: list = field(default_factory=list)
    testcases: list = field(default_factory=list)


def _browser_result(d) -> BrowserResult:
    d = d or {}
    return BrowserResult(
        status=d.get("status"), bug_id=d.get("bug_id"),
        tester=d.get("tester"), date=d.get("date"),
        evidence=list(d.get("evidence") or []))


def _result(d) -> Result:
    d = d or {}
    return Result(chrome=_browser_result(d.get("chrome")),
                  safari=_browser_result(d.get("safari")))


def _testcase(d: dict) -> Testcase:
    if not d.get("id"):
        raise SchemaError("testcase missing required 'id'")
    tc = Testcase(
        id=str(d["id"]),
        section=d.get("section", ""),
        main_item=d.get("main_item", ""),
        middle_item=d.get("middle_item", ""),
        minor_item=d.get("minor_item", ""),
        type=d.get("type", "IT"),
        priority=d.get("priority", "Medium"),
        strategy_ref=d.get("strategy_ref", ""),
        precondition=d.get("precondition", ""),
        steps=list(d.get("steps") or []),
        expected=list(d.get("expected") or []),
        result=_result(d.get("result")),
    )
    if tc.type not in VALID_LEVELS:
        raise SchemaError(f"testcase {tc.id}: invalid type '{tc.type}'")
    if tc.priority not in VALID_PRIORITIES:
        raise SchemaError(f"testcase {tc.id}: invalid priority '{tc.priority}'")
    return tc


def load_screen(path) -> Screen:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not data.get("screen"):
        raise SchemaError("missing required 'screen'")
    level = data.get("test_level", "IT")
    if level not in VALID_LEVELS:
        raise SchemaError(f"invalid test_level '{level}'")
    tcs = [_testcase(t) for t in (data.get("testcases") or [])]
    ids = [t.id for t in tcs]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    if dups:
        raise SchemaError(f"duplicate testcase id(s): {dups}")
    return Screen(
        screen=data["screen"], test_level=level,
        created_by=data.get("created_by", ""),
        source_docs=list(data.get("source_docs") or []),
        testcases=tcs)


def dump_screen(screen: Screen, path) -> None:
    Path(path).write_text(
        yaml.safe_dump(asdict(screen), allow_unicode=True, sort_keys=False),
        encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_tc_schema.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit** *(requires user confirmation)*

```bash
git add tcformat/__init__.py tcformat/schema.py tests/unit/test_tc_schema.py
git commit -m "feat: tcformat YAML test-case schema"
```

---

## Task 2: Strategy object extractor + refactor gen_checklist

**Files:**
- Create: `tcformat/strategy.py`
- Modify: `scripts/gen_checklist.py`
- Test: `tests/unit/test_tc_strategy.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_tc_strategy.py`:
```python
from openpyxl import Workbook
from tcformat.strategy import list_objects, all_refs


def _xlsx(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "2_IntergrationTesting"
    ws["A76"] = "STT"; ws["C76"] = "Đối tượng testing"; ws["J76"] = "Cách thức"
    ws["A77"] = "2.3.1 UI testing"
    ws["A78"] = 1; ws["C78"] = "Giao diện"; ws["J78"] = "Mở màn hình"
    ws["A79"] = 2; ws["C79"] = "Component"; ws["J79"] = "Đếm"
    ws["A88"] = "2.3.2 Functional testing"
    ws["A89"] = 1; ws["C89"] = "Validate"; ws["J89"] = "Nhập"
    p = tmp_path / "s.xlsx"
    wb.save(p)
    return p


def test_list_objects_builds_refs(tmp_path):
    objs = list_objects(_xlsx(tmp_path), "2_IntergrationTesting")
    refs = [o["ref"] for o in objs]
    assert "2.3.1#1" in refs and "2.3.1#2" in refs and "2.3.2#1" in refs
    first = next(o for o in objs if o["ref"] == "2.3.1#1")
    assert first["object"] == "Giao diện"
    assert first["section"] == "2.3.1"


def test_all_refs_on_real_strategy():
    refs = all_refs("strategy/strategy.xlsx")
    assert refs and "2.3.1#1" in refs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_tc_strategy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tcformat.strategy'`

- [ ] **Step 3: Write minimal implementation**

`tcformat/strategy.py`:
```python
"""Extract testing objects from the strategy workbook with stable refs.

A ref is "<section>#<stt>", e.g. "2.3.1#1" = sheet section 2.3.1, object STT 1.
Section dividers live in column A as text like "2.3.1 UI testing"; object rows
have an STT number in column A, the object name in column C, the how-to in J.
"""
from __future__ import annotations
import re
from openpyxl import load_workbook

OBJECT_COL = "C"
HOW_COL = "J"
HEADER_TOKEN = "Đối tượng testing"
SECTION_RE = re.compile(r"^(\d+\.\d+\.\d+)")
STRATEGY_SHEETS = ["1_APITesting", "2_IntergrationTesting", "3_System_Testing"]


def list_objects(xlsx_path, sheet_name: str) -> list[dict]:
    wb = load_workbook(xlsx_path, data_only=True)
    ws = wb[sheet_name]
    objects: list[dict] = []
    header_seen = False
    current = None
    for row in range(1, ws.max_row + 1):
        a = ws[f"A{row}"].value
        c = ws[f"{OBJECT_COL}{row}"].value
        if c is not None and HEADER_TOKEN in str(c):
            header_seen = True
            continue
        if a is None:
            continue
        a_text = str(a).strip()
        m = SECTION_RE.match(a_text)
        if m and not a_text.replace(".", "").strip().isdigit():
            current = m.group(1)  # section divider like "2.3.1 UI testing"
            continue
        if not header_seen:
            continue
        stt = a_text.split(".")[0]
        if stt.isdigit() and c is not None and str(c).strip():
            how = ws[f"{HOW_COL}{row}"].value
            objects.append({
                "ref": f"{current}#{stt}" if current else None,
                "section": current,
                "stt": stt,
                "object": str(c).strip(),
                "how": str(how).strip() if how else "",
            })
    return objects


def all_refs(xlsx_path) -> set[str]:
    refs: set[str] = set()
    for sheet in STRATEGY_SHEETS:
        for o in list_objects(xlsx_path, sheet):
            if o["ref"]:
                refs.add(o["ref"])
    return refs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_tc_strategy.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Refactor `scripts/gen_checklist.py` to reuse the extractor**

Replace the ENTIRE contents of `scripts/gen_checklist.py` with:
```python
"""Generate tester checklists from the strategy workbook.

Reads the testing objects of a strategy sheet (via tcformat.strategy) and emits
a Markdown checklist.

Usage:
    python scripts/gen_checklist.py --sheet 1_APITesting --title "API Testing"
"""
from __future__ import annotations
import argparse
from pathlib import Path

from tcformat.strategy import list_objects


def extract_objects(xlsx_path, sheet_name: str) -> list[dict]:
    """Back-compat shim: {object, how} pairs for a sheet."""
    return [{"object": o["object"], "how": o["how"]}
            for o in list_objects(xlsx_path, sheet_name)]


def render_markdown(title: str, objects: list[dict]) -> str:
    lines = [f"# Checklist — {title}", ""]
    for o in objects:
        lines.append(f"- [ ] **{o['object']}**")
        if o["how"]:
            lines.append(f"  - {o['how'].replace(chr(10), ' ')}")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xlsx", default="strategy/strategy.xlsx")
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--out", default="checklists/")
    args = ap.parse_args()

    objects = extract_objects(args.xlsx, args.sheet)
    md = render_markdown(args.title, objects)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.sheet}.md"
    out_file.write_text(md, encoding="utf-8")
    print(f"Wrote {len(objects)} objects -> {out_file}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Verify the refactor kept gen_checklist working**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_gen_checklist.py tests/unit/test_tc_strategy.py -v`
Expected: PASS (all). Then regenerate real checklists to confirm counts unchanged:
`./.venv/Scripts/python.exe scripts/gen_checklist.py --sheet 2_IntergrationTesting --title "Integration/UI Testing"`
Expected: prints `Wrote 24 objects -> checklists/2_IntergrationTesting.md`

- [ ] **Step 7: Commit** *(requires user confirmation)*

```bash
git add tcformat/strategy.py scripts/gen_checklist.py tests/unit/test_tc_strategy.py
git commit -m "feat: strategy ref extractor; gen_checklist reuses it"
```

---

## Task 3: Coverage checking

**Files:**
- Create: `tcformat/coverage.py`
- Test: `tests/unit/test_tc_coverage.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_tc_coverage.py`:
```python
from tcformat.coverage import check_coverage
from tcformat.schema import Screen, Testcase


def test_coverage_covered_missing_unknown():
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", strategy_ref="2.3.1#1"),
        Testcase(id="B", strategy_ref="9.9.9#9"),  # not a real ref
        Testcase(id="C", strategy_ref=""),          # untagged -> ignored
    ])
    rep = check_coverage(sc, {"2.3.1#1", "2.3.1#2"})
    assert rep.covered == {"2.3.1#1"}
    assert rep.missing == {"2.3.1#2"}
    assert rep.unknown == {"9.9.9#9"}
    assert rep.total == 2
    assert abs(rep.coverage_rate - 0.5) < 1e-9


def test_full_coverage():
    sc = Screen(screen="S", testcases=[Testcase(id="A", strategy_ref="x#1")])
    rep = check_coverage(sc, {"x#1"})
    assert rep.missing == set()
    assert rep.coverage_rate == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_tc_coverage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tcformat.coverage'`

- [ ] **Step 3: Write minimal implementation**

`tcformat/coverage.py`:
```python
"""Compare a screen's testcase refs against an expected strategy ref set."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class CoverageReport:
    covered: set
    missing: set
    unknown: set
    total: int

    @property
    def coverage_rate(self) -> float:
        return len(self.covered) / self.total if self.total else 0.0


def check_coverage(screen, strategy_refs: set) -> CoverageReport:
    """strategy_refs = the refs this screen is expected to cover."""
    tagged = {tc.strategy_ref for tc in screen.testcases if tc.strategy_ref}
    covered = tagged & strategy_refs
    unknown = tagged - strategy_refs
    missing = strategy_refs - tagged
    return CoverageReport(covered=covered, missing=missing,
                          unknown=unknown, total=len(strategy_refs))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_tc_coverage.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit** *(requires user confirmation)*

```bash
git add tcformat/coverage.py tests/unit/test_tc_coverage.py
git commit -m "feat: coverage checking of testcase refs vs strategy"
```

---

## Task 4: Render YAML screens → team-template xlsx

**Files:**
- Create: `tcformat/render_xlsx.py`
- Test: `tests/unit/test_tc_render.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_tc_render.py`:
```python
from openpyxl import load_workbook
from tcformat.schema import Screen, Testcase
from tcformat.render_xlsx import render

TEMPLATE = "template/Format test case + Test report.xlsx"


def _sheet_by_c1(wb, name):
    for ws in wb.worksheets:
        if ws["C1"].value == name:
            return ws
    return None


def test_render_fills_testcase_sheet(tmp_path):
    sc = Screen(screen="Login Screen", test_level="IT", testcases=[
        Testcase(id="UI_01", section="UI", main_item="Show",
                 type="IT", priority="High", precondition="none",
                 steps=["Open page", "Click login"], expected=["Form shows"]),
        Testcase(id="FN_01", section="FUNCTION", main_item="Submit",
                 type="IT", priority="Medium",
                 steps=["Fill form"], expected=["Saved"]),
    ])
    out = tmp_path / "login.xlsx"
    render([sc], TEMPLATE, str(out))

    wb = load_workbook(out)
    ws = _sheet_by_c1(wb, "Login Screen")
    assert ws is not None
    assert ws["C2"].value == "IT"
    assert ws["B7"].value == "TestcaseID"  # template header preserved

    rows = {}
    for r in range(10, 40):
        b = ws.cell(r, 2).value
        if b:
            rows[b] = r
    assert "UI_01" in rows and "FN_01" in rows
    r = rows["UI_01"]
    assert "Open page" in (ws.cell(r, 7).value or "")
    assert "Form shows" in (ws.cell(r, 8).value or "")
    assert ws.cell(r, 9).value == "IT"
    assert ws.cell(r, 10).value == "High"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_tc_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tcformat.render_xlsx'`

- [ ] **Step 3: Write minimal implementation**

`tcformat/render_xlsx.py`:
```python
"""Render Screen objects into the team's testcase-sheet xlsx format.

Clones the template's '4.1.*' sample sheet (preserving styles + summary block),
renames it per screen, and fills the data region from row 10.
"""
from __future__ import annotations
import re
from pathlib import Path
from openpyxl import load_workbook

DATA_START = 10
LAST_COL = 18  # through column R (result columns left blank for Stage 2)
INVALID_TITLE = re.compile(r"[\[\]:\*\?/\\]")


def _find_sample(wb):
    for ws in wb.worksheets:
        if ws.title.strip().startswith("4.1"):
            return ws
    raise ValueError("template missing a '4.1.*' sample testcase sheet")


def _sheet_title(idx: int, name: str) -> str:
    return f"4.{idx} {INVALID_TITLE.sub('', name)}".strip()[:31]


def _clear(ws, first: int, last: int):
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row >= first and rng.max_row <= last:
            ws.unmerge_cells(str(rng))
    for r in range(first, last + 1):
        for c in range(1, LAST_COL + 1):
            ws.cell(r, c).value = None


def _write(ws, testcases, start: int):
    row = start
    no = 0
    last_section = None
    for tc in testcases:
        if tc.section and tc.section != last_section:
            ws.cell(row, 1).value = tc.section
            last_section = tc.section
            row += 1
        no += 1
        ws.cell(row, 1).value = no
        ws.cell(row, 2).value = tc.id
        ws.cell(row, 3).value = tc.main_item
        ws.cell(row, 4).value = tc.middle_item
        ws.cell(row, 5).value = tc.minor_item
        ws.cell(row, 6).value = tc.precondition
        ws.cell(row, 7).value = "\n".join(
            f"{i + 1}. {s}" for i, s in enumerate(tc.steps))
        ws.cell(row, 8).value = "\n".join(
            f"{i + 1}. {e}" for i, e in enumerate(tc.expected))
        ws.cell(row, 9).value = tc.type
        ws.cell(row, 10).value = tc.priority
        row += 1
    return row


def render(screens, template_path, out_path) -> None:
    wb = load_workbook(template_path)
    sample = _find_sample(wb)
    for idx, screen in enumerate(screens, start=1):
        ws = wb.copy_worksheet(sample)
        ws.title = _sheet_title(idx, screen.screen)
        ws["C1"] = screen.screen
        ws["C2"] = screen.test_level
        _clear(ws, DATA_START, DATA_START + max(len(screen.testcases) * 2, 10) + 5)
        _write(ws, screen.testcases, DATA_START)
    wb.remove(sample)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_tc_render.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit** *(requires user confirmation)*

```bash
git add tcformat/render_xlsx.py tests/unit/test_tc_render.py
git commit -m "feat: render screens to team-template xlsx"
```

---

## Task 5: generate-testcases skill + demo fixture

**Files:**
- Create: `.claude/skills/generate-testcases/SKILL.md`
- Create: `tests/fixtures/design-sample.md`

- [ ] **Step 1: Create the demo design doc**

`tests/fixtures/design-sample.md`:
```markdown
# Screen: Basic Information Input

Test level: IT

## Components
- Usage: two buttons "Residential" / "Industrial" (single-select).
- Property Region: two dropdowns "Prefecture" (47 items) and "Municipality"
  (depends on Prefecture).
- Submit button.

## Business rules
- Selecting a Prefecture loads its Municipalities and clears prior Municipality.
- Submitting with required fields empty shows a validation error.
- Input must be safe against HTML/script injection.
```

- [ ] **Step 2: Create the skill**

`.claude/skills/generate-testcases/SKILL.md`:
```markdown
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
   run `./.venv/Scripts/python.exe -c "from tcformat.strategy import list_objects; import json; print(json.dumps(list_objects('strategy/strategy.xlsx','2_IntergrationTesting'), ensure_ascii=False))"`
   (swap the sheet for 1_APITesting / 3_System_Testing as needed).

## Process
1. For EACH strategy testing object relevant to the screen, write at least one
   testcase whose `strategy_ref` equals that object's `ref` (e.g. "2.3.1#1").
   Add screen-specific cases beyond the checklist where the design warrants.
2. Each testcase follows the schema in `tcformat/schema.py`: id, section
   (UI/FUNCTION/...), main_item, type (UT|IT|ST), priority (Low|Medium|High),
   strategy_ref, precondition, steps (NL, ordered), expected (NL, ordered).
   Write steps/expected concretely enough that a browser agent can execute them.
3. Save `testcases/<screen-slug>.yaml`. Validate + render + check coverage:
   ```
   ./.venv/Scripts/python.exe -c "
   from tcformat.schema import load_screen
   from tcformat.render_xlsx import render
   from tcformat.coverage import check_coverage
   from tcformat.strategy import all_refs
   sc = load_screen('testcases/<screen-slug>.yaml')
   render([sc], 'template/Format test case + Test report.xlsx', 'testcases/<screen-slug>.xlsx')
   # scope refs to the levels you targeted; here: integration objects
   from tcformat.strategy import list_objects
   refs = {o['ref'] for o in list_objects('strategy/strategy.xlsx','2_IntergrationTesting') if o['ref']}
   rep = check_coverage(sc, refs)
   print('missing:', sorted(rep.missing)); print('unknown:', sorted(rep.unknown))
   "
   ```
4. If `missing` is non-empty, add testcases for those refs and repeat. If
   `unknown` is non-empty, fix the wrong `strategy_ref` values. Stop when both
   are empty.

## Output
- `testcases/<screen-slug>.yaml` (the contract, reviewable/diffable)
- `testcases/<screen-slug>.xlsx` (team format, sheet "4.x <screen>")
- A short coverage summary (objects covered, any screen-specific extras)
```

- [ ] **Step 3: Smoke-check the skill's commands run**

Run (verifies the documented one-liner works end to end on a tiny inline screen):
```
./.venv/Scripts/python.exe -c "
from tcformat.schema import Screen, Testcase, dump_screen, load_screen
from tcformat.render_xlsx import render
sc = Screen(screen='Demo', test_level='IT', testcases=[Testcase(id='UI_01', section='UI', type='IT', priority='High', strategy_ref='2.3.1#1', steps=['Open'], expected=['Shown'])])
dump_screen(sc, 'testcases/demo.yaml')
render([load_screen('testcases/demo.yaml')], 'template/Format test case + Test report.xlsx', 'testcases/demo.xlsx')
print('demo render ok')
"
```
Expected: prints `demo render ok` and creates `testcases/demo.yaml` + `testcases/demo.xlsx`.

- [ ] **Step 4: Add `testcases/` to .gitignore generated outputs (keep the dir intent documented)**

Confirm `.gitignore` ignores generated artifacts. Run `git check-ignore testcases/demo.xlsx`. If it is NOT ignored, append a line `testcases/` to `.gitignore` (generated per-project, like `checklists/`). The `.yaml` contracts MAY be committed per project; for this toolkit repo they are demo artifacts, so ignoring `testcases/` is correct.

- [ ] **Step 5: Commit** *(requires user confirmation)*

```bash
git add .claude/skills/generate-testcases/SKILL.md tests/fixtures/design-sample.md .gitignore
git commit -m "feat: generate-testcases skill + demo design fixture"
```

---

## Task 6: Full suite green + README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Full suite run**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass (existing 31 + new schema/strategy/coverage/render tests). Report the count.

- [ ] **Step 2: Add a Stage 1 section to README**

Insert after the "Generate checklists" section in `README.md`:
```markdown
## Generate project test cases (Stage 1)

Draft test cases from design docs into the team xlsx format with strategy
coverage. Driven by the `generate-testcases` skill (AI reads the design docs);
the deterministic backbone lives in `tcformat/`:

- `tcformat/schema.py`  — YAML test-case contract (`testcases/<screen>.yaml`)
- `tcformat/strategy.py`— testing-object refs from `strategy.xlsx`
- `tcformat/coverage.py`— checks every strategy object has a testcase
- `tcformat/render_xlsx.py` — renders YAML → `testcases/<screen>.xlsx`
  (template sheet "4.x")

Invoke in Claude Code: run the `generate-testcases` skill and point it at the
screen's design docs. Output: a reviewable YAML contract + the team-format xlsx,
with a coverage summary.
```

- [ ] **Step 3: Commit** *(requires user confirmation)*

```bash
git add README.md
git commit -m "docs: Stage 1 test-case generation usage"
```

---

## Self-Review Notes (coverage map)

- Spec §3 YAML contract → Task 1 (`schema.py`, all fields incl. `result`).
- Spec §4.1 schema → Task 1. §4.2 strategy → Task 2 (+ gen_checklist DRY refactor,
  spec §8 DoD). §4.3 coverage → Task 3. §4.4 render_xlsx → Task 4. §4.5 skill → Task 5.
- Spec §5 data flow: skill (Task 5) chains strategy→schema→render→coverage.
- Spec §6 error handling: `SchemaError` (Task 1), `unknown` refs (Task 3),
  missing `4.1.*` sheet raises (Task 4 `_find_sample`).
- Spec §7 testing: each module has unit tests; real-strategy smoke test (Task 2);
  render reopen-and-assert (Task 4); demo fixture + skill smoke (Task 5).
- Spec §8 DoD → Task 6 full run + README; gen_checklist refactor verified Task 2 Step 6.
- Naming consistency: `load_screen`/`dump_screen`/`Screen`/`Testcase`/`Result`/
  `BrowserResult`/`SchemaError`, `list_objects`/`all_refs`, `check_coverage`/
  `CoverageReport`/`coverage_rate`, `render` used consistently across tasks.
