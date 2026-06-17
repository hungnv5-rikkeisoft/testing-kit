# Phase 2: Depth GATE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the advisory `DepthReport` into a hard Stage-1 gate via a new `tk-coverage` CLI that exits non-zero when any expected element×technique cell has no test case and is not justified.

**Architecture:** Extend `check_depth` to track `skipped`/`unknown_techniques`/`kinds_without_checklist`, add a `skip_techniques` justify mechanism on inventory elements, render an element×technique markdown matrix in a new module, and wire a `tk-coverage` console script that gates on `len(gaps) > 0`. Warnings never affect exit code.

**Tech Stack:** Python 3.11+, dataclasses, PyYAML, argparse, pytest. No new dependencies.

## Global Constraints

- venv only: run via `./.venv/Scripts/python.exe` and `./.venv/Scripts/pytest`.
- New inventory keys are **YAML-only**; never change the team xlsx format (columns A–R).
- All resource paths stay config-overridable (`checklists_path` via `tcformat.resources`); switching projects must not require code changes.
- Spec/strategy artifacts are Vietnamese; keep terminology consistent.
- Gate semantics: PASS iff `len(gaps) == 0`. `unknown_techniques` and `kinds_without_checklist` are **warnings only** — they never change the exit code.
- Fail fast on missing/unreadable screen/inventory files.
- Git: commit only after the user confirms; plain messages, NO `Co-Authored-By` trailer.
- Follow existing `tcformat/` style: `from __future__ import annotations`, dataclasses with `field(default_factory=...)`, plain `list`/`set` annotations (no generics).

---

### Task 1: Add `skip_techniques` to inventory `Element`

**Files:**
- Modify: `tcformat/inventory.py` (the `Element` dataclass + `_element()` loader)
- Test: `tests/unit/test_inventory.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Element.skip_techniques: list` (default `[]`), populated from YAML key `skip_techniques`. Consumed by `check_depth` in Task 2.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_inventory.py` (create the file if it does not exist; if it exists, append the test and reuse its imports):

```python
from tcformat.inventory import load_inventory


def test_skip_techniques_loaded(tmp_path):
    p = tmp_path / "s.inventory.yaml"
    p.write_text(
        "screen: S\n"
        "elements:\n"
        "  - id: name\n"
        "    kind: input\n"
        "    skip_techniques: [boundary, max-length]\n"
        "  - id: btn\n"
        "    kind: button\n",
        encoding="utf-8")
    inv = load_inventory(str(p))
    by_id = {e.id: e for e in inv.elements}
    assert by_id["name"].skip_techniques == ["boundary", "max-length"]
    assert by_id["btn"].skip_techniques == []   # default empty
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/pytest tests/unit/test_inventory.py::test_skip_techniques_loaded -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'skip_techniques'` (or `AttributeError` on `.skip_techniques`).

- [ ] **Step 3: Add the field + loader line**

In `tcformat/inventory.py`, add to the `Element` dataclass (after `params`):

```python
    skip_techniques: list = field(default_factory=list)
```

In `_element()`, add to the `Element(...)` constructor call (after `params=...`):

```python
        skip_techniques=list(d.get("skip_techniques") or []),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/pytest tests/unit/test_inventory.py::test_skip_techniques_loaded -v`
Expected: PASS

- [ ] **Step 5: Commit** (after user confirmation)

```bash
git add tcformat/inventory.py tests/unit/test_inventory.py
git commit -m "feat(inventory): add element skip_techniques justify field"
```

---

### Task 2: Extend `DepthReport` + `check_depth`

**Files:**
- Modify: `tcformat/coverage.py` (`DepthReport` dataclass + `check_depth`)
- Test: `tests/unit/test_tc_depth.py`

**Interfaces:**
- Consumes: `Element.skip_techniques` (Task 1); `checklists` dict `{kind: [{"technique", "category", "title"}, ...]}`; `screen.testcases` with `.target`/`.technique`.
- Produces: `DepthReport` with new fields `skipped: list`, `unknown_techniques: list`, `kinds_without_checklist: list` (all `list[tuple]`, default `[]`). `check_depth(inventory, checklists, screen) -> DepthReport` signature unchanged. Consumed by Task 3 (matrix) and Task 4 (CLI).

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tc_depth.py`:

```python
def test_depth_rate_partial_is_quarter():
    # btn x2 + sel x1 + screen x1 = 4 expected, 1 covered -> 0.25
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", target="btn", technique="single-action"),
    ])
    rep = check_depth(_inv(), CHECKLISTS, sc)
    assert rep.depth_rate == 0.25


def test_skip_techniques_excluded_from_expected():
    inv = Inventory(screen="S", elements=[
        Element(id="btn", kind="button", skip_techniques=["double-click"]),
    ])
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", target="btn", technique="single-action"),
    ])
    rep = check_depth(inv, CHECKLISTS, sc)
    # btn: single-action expected (covered), double-click skipped; + screen x1 (gap)
    assert ("btn", "double-click") in rep.skipped
    assert ("btn", "double-click") not in rep.gaps
    assert rep.expected == 2          # btn single-action + screen url-tamper
    assert rep.covered == 1


def test_unknown_technique_flagged():
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", target="btn", technique="typo-technique"),
    ])
    rep = check_depth(_inv(), CHECKLISTS, sc)
    assert ("btn", "typo-technique") in rep.unknown_techniques


def test_kind_without_checklist_flagged():
    inv = Inventory(screen="S", elements=[Element(id="lnk", kind="link")])
    sc = Screen(screen="S", testcases=[])
    rep = check_depth(inv, CHECKLISTS, sc)
    assert ("lnk", "link") in rep.kinds_without_checklist
    # link contributes 0 expected cells (only screen x1 remains)
    assert rep.expected == 1
```

Note: `CHECKLISTS` and `_inv()` already exist at the top of this file (button has `single-action` + `double-click`, select has `default-value`, screen has `url-tamper`). `link` is intentionally absent from `CHECKLISTS`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/pytest tests/unit/test_tc_depth.py -v`
Expected: the 4 new tests FAIL (`AttributeError: 'DepthReport' object has no attribute 'skipped'` etc.); the 3 existing tests still PASS.

- [ ] **Step 3: Extend `DepthReport`**

In `tcformat/coverage.py`, add `field` to the import and replace the `DepthReport` dataclass:

```python
from dataclasses import dataclass, field
```

```python
@dataclass
class DepthReport:
    expected: int
    covered: int
    gaps: list  # list[tuple[element_id, technique]] — uncovered, not justified -> fails gate
    skipped: list = field(default_factory=list)              # (element_id, technique) justified via skip_techniques
    unknown_techniques: list = field(default_factory=list)   # (target, technique) tagged but not in that kind's checklist
    kinds_without_checklist: list = field(default_factory=list)  # (element_id, kind) kind has no checklist entry

    @property
    def depth_rate(self) -> float:
        return self.covered / self.expected if self.expected else 0.0
```

- [ ] **Step 4: Rewrite `check_depth`**

Replace the body of `check_depth` in `tcformat/coverage.py`:

```python
def check_depth(inventory, checklists, screen) -> DepthReport:
    """Expected matrix = each element's kind techniques + screen techniques (once).

    A cell (element_id, technique) is covered when a testcase has matching
    target and technique. `skip_techniques` on an element removes its cells from
    `expected` (recorded in `skipped`). Elements whose kind has no checklist
    entry are reported in `kinds_without_checklist` (0 expected cells, warning
    only). Testcase tags whose technique is not valid for the target's kind are
    reported in `unknown_techniques` (warning only).
    """
    have = {(tc.target, tc.technique)
            for tc in screen.testcases if tc.target and tc.technique}
    kind_by_id = {el.id: el.kind for el in inventory.elements}
    kind_by_id["screen"] = "screen"

    expected_cells: list = []
    skipped: list = []
    kinds_without_checklist: list = []
    for el in inventory.elements:
        if el.kind == "screen":
            continue
        if el.kind not in checklists:
            kinds_without_checklist.append((el.id, el.kind))
            continue
        for entry in checklists[el.kind]:
            tech = entry["technique"]
            if tech in el.skip_techniques:
                skipped.append((el.id, tech))
            else:
                expected_cells.append((el.id, tech))
    for entry in checklists.get("screen", []):
        expected_cells.append(("screen", entry["technique"]))

    gaps = [cell for cell in expected_cells if cell not in have]

    valid_by_kind = {kind: {e["technique"] for e in entries}
                     for kind, entries in checklists.items()}
    unknown_techniques: list = []
    for target, tech in have:
        kind = kind_by_id.get(target)
        if kind is None:
            continue  # target matches no element — out of scope for this metric
        if tech not in valid_by_kind.get(kind, set()):
            unknown_techniques.append((target, tech))

    return DepthReport(
        expected=len(expected_cells),
        covered=len(expected_cells) - len(gaps),
        gaps=gaps, skipped=skipped,
        unknown_techniques=unknown_techniques,
        kinds_without_checklist=kinds_without_checklist)
```

- [ ] **Step 5: Run the full depth test file to verify all pass**

Run: `./.venv/Scripts/pytest tests/unit/test_tc_depth.py -v`
Expected: all tests PASS (3 existing + 4 new).

- [ ] **Step 6: Commit** (after user confirmation)

```bash
git add tcformat/coverage.py tests/unit/test_tc_depth.py
git commit -m "feat(coverage): depth report tracks skipped/unknown/kind-gaps"
```

---

### Task 3: Render element × technique matrix

**Files:**
- Create: `tcformat/depth_matrix.py`
- Test: `tests/unit/test_depth_matrix.py`

**Interfaces:**
- Consumes: `inventory` (`Inventory` with `.elements`), `checklists` dict, `depth_report` (`DepthReport` with `.gaps`/`.skipped`) from Task 2.
- Produces: `render_depth_matrix(inventory, checklists, depth_report) -> str` — a markdown table string (no trailing newline). Consumed by Task 4 (CLI).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_depth_matrix.py`:

```python
from tcformat.coverage import check_depth
from tcformat.depth_matrix import render_depth_matrix
from tcformat.inventory import Inventory, Element
from tcformat.schema import Screen, Testcase

CHECKLISTS = {
    "button": [{"technique": "single-action", "category": "Function", "title": "x"},
               {"technique": "double-click", "category": "UserBehavior", "title": "y"}],
    "screen": [{"technique": "url-tamper", "category": "Security", "title": "s"}],
}


def test_matrix_marks_each_status():
    inv = Inventory(screen="S", elements=[
        Element(id="btn", kind="button", skip_techniques=["double-click"]),
    ])
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", target="btn", technique="single-action"),
    ])
    rep = check_depth(inv, CHECKLISTS, sc)
    out = render_depth_matrix(inv, CHECKLISTS, rep)

    assert "| element id | kind | technique | có case? | trạng thái |" in out
    # covered cell
    assert "| btn | button | single-action | ✓ | covered |" in out
    # skipped (justified) cell
    assert "| btn | button | double-click | – | skipped |" in out
    # screen-level gap
    assert "| screen | screen | url-tamper | ✗ | GAP |" in out


def test_matrix_row_order_elements_then_screen():
    inv = Inventory(screen="S", elements=[Element(id="btn", kind="button")])
    sc = Screen(screen="S", testcases=[])
    out = render_depth_matrix(inv, CHECKLISTS, check_depth(inv, CHECKLISTS, sc))
    lines = out.splitlines()
    # header + separator first, then btn rows, then screen row last
    assert lines[-1].startswith("| screen | screen | url-tamper |")
    assert any(l.startswith("| btn | button | single-action |") for l in lines[2:-1])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/pytest tests/unit/test_depth_matrix.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tcformat.depth_matrix'`.

- [ ] **Step 3: Write the module**

Create `tcformat/depth_matrix.py`:

```python
"""Render an element x technique depth matrix as a markdown table.

Output-only helper for the tk-coverage CLI; never touches the team xlsx format
(columns A-R). Each cell is covered (✓), a gap (✗), or skipped/justified (–).
"""
from __future__ import annotations

_HEADER = ("| element id | kind | technique | có case? | trạng thái |\n"
           "|------------|------|-----------|----------|------------|")


def render_depth_matrix(inventory, checklists, depth_report) -> str:
    gaps = set(depth_report.gaps)
    skipped = set(depth_report.skipped)

    def row(eid, kind, tech):
        cell = (eid, tech)
        if cell in skipped:
            mark, status = "–", "skipped"
        elif cell in gaps:
            mark, status = "✗", "GAP"
        else:
            mark, status = "✓", "covered"
        return f"| {eid} | {kind} | {tech} | {mark} | {status} |"

    rows: list = []
    for el in inventory.elements:
        if el.kind == "screen":
            continue
        for entry in checklists.get(el.kind, []):
            rows.append(row(el.id, el.kind, entry["technique"]))
    for entry in checklists.get("screen", []):
        rows.append(row("screen", "screen", entry["technique"]))

    return "\n".join([_HEADER, *rows])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/pytest tests/unit/test_depth_matrix.py -v`
Expected: PASS

- [ ] **Step 5: Commit** (after user confirmation)

```bash
git add tcformat/depth_matrix.py tests/unit/test_depth_matrix.py
git commit -m "feat(coverage): render element x technique depth matrix"
```

---

### Task 4: `tk-coverage` CLI gate

**Files:**
- Create: `tcformat/coverage_cli.py`
- Modify: `pyproject.toml` (`[project.scripts]`)
- Test: `tests/unit/test_coverage_cli.py`

**Interfaces:**
- Consumes: `load_screen` (schema), `load_inventory` (inventory), `load_checklists` (checklists, resolves `checklists_path` from `--config`), `check_depth` (Task 2), `render_depth_matrix` (Task 3).
- Produces: `main(argv=None)` — raises `SystemExit(1)` when `report.gaps` is non-empty, else `SystemExit(0)`. Console script `tk-coverage`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_coverage_cli.py`:

```python
import yaml
import pytest

from tcformat.coverage_cli import main

CHECKLISTS = {
    "button": [{"technique": "single-action", "category": "Function", "title": "x"}],
    "screen": [],
}


def _setup(tmp_path, testcases, *, skip=None):
    (tmp_path / "checklists.yaml").write_text(
        yaml.safe_dump(CHECKLISTS), encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"checklists_path": str(tmp_path / "checklists.yaml")}),
        encoding="utf-8")
    el = {"id": "btn", "kind": "button"}
    if skip:
        el["skip_techniques"] = skip
    (tmp_path / "s.inventory.yaml").write_text(
        yaml.safe_dump({"screen": "S", "elements": [el]}), encoding="utf-8")
    (tmp_path / "s.yaml").write_text(
        yaml.safe_dump({"screen": "S", "testcases": testcases}), encoding="utf-8")
    return [
        "--screen", str(tmp_path / "s.yaml"),
        "--config", str(tmp_path / "config.yaml"),
    ]


def test_exit_1_on_gap(tmp_path):
    argv = _setup(tmp_path, testcases=[])   # btn/single-action uncovered
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == 1


def test_exit_0_when_covered(tmp_path):
    argv = _setup(tmp_path, testcases=[
        {"id": "A", "target": "btn", "technique": "single-action"}])
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == 0


def test_skip_techniques_makes_gate_pass(tmp_path):
    argv = _setup(tmp_path, testcases=[], skip=["single-action"])
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == 0


def test_unknown_technique_warns_but_passes(tmp_path):
    # covered + an extra testcase with a bogus technique -> warning, still exit 0
    argv = _setup(tmp_path, testcases=[
        {"id": "A", "target": "btn", "technique": "single-action"},
        {"id": "B", "target": "btn", "technique": "bogus"}])
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == 0


def test_matrix_out_written(tmp_path):
    out = tmp_path / "sub" / "matrix.md"
    argv = _setup(tmp_path, testcases=[
        {"id": "A", "target": "btn", "technique": "single-action"}])
    argv += ["--matrix-out", str(out)]
    with pytest.raises(SystemExit):
        main(argv)
    assert out.exists()
    assert "technique" in out.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/pytest tests/unit/test_coverage_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tcformat.coverage_cli'`.

- [ ] **Step 3: Write the CLI module**

Create `tcformat/coverage_cli.py`:

```python
"""Stage 1 gate - depth coverage check (element x technique matrix).

Loads a screen's testcases + its element inventory + the technique checklist,
prints gaps / skipped / warnings + a markdown matrix, and exits non-zero when
any expected cell has no test case and is not justified via `skip_techniques`.
Installed as the `tk-coverage` console script.
"""
from __future__ import annotations
import argparse
from pathlib import Path


def run_depth_check(screen_path, inventory_path, config=None):
    """Load inputs and compute the DepthReport. Returns
    (screen, inventory, checklists, report)."""
    from tcformat.schema import load_screen
    from tcformat.inventory import load_inventory
    from tcformat.checklists import load_checklists
    from tcformat.coverage import check_depth
    screen = load_screen(screen_path)
    inventory = load_inventory(inventory_path)
    checklists = load_checklists(config_path=config)
    report = check_depth(inventory, checklists, screen)
    return screen, inventory, checklists, report


def _default_inventory(screen_path) -> str:
    return str(Path(screen_path).with_suffix(".inventory.yaml"))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--screen", required=True, help="testcase YAML for the screen")
    ap.add_argument("--inventory", default=None,
                    help="inventory YAML (default: <screen>.inventory.yaml)")
    ap.add_argument("--config", default=None,
                    help="config.yaml to read checklists_path override from")
    ap.add_argument("--matrix-out", dest="matrix_out", default=None,
                    help="also write the markdown matrix to this file")
    args = ap.parse_args(argv)

    inv_path = args.inventory or _default_inventory(args.screen)
    _, inventory, checklists, report = run_depth_check(
        args.screen, inv_path, config=args.config)

    from tcformat.depth_matrix import render_depth_matrix
    matrix = render_depth_matrix(inventory, checklists, report)

    print(f"Depth: expected {report.expected}, covered {report.covered}, "
          f"rate {report.depth_rate:.0%}")
    if report.gaps:
        print(f"\nGAPS ({len(report.gaps)}) - need a case or skip_techniques justify:")
        for eid, tech in report.gaps:
            print(f"  ✗ {eid} / {tech}")
    if report.skipped:
        print(f"\nSKIPPED ({len(report.skipped)}) - justified, not tested:")
        for eid, tech in report.skipped:
            print(f"  – {eid} / {tech}")
    if report.unknown_techniques:
        print(f"\nWARNING unknown techniques ({len(report.unknown_techniques)}) "
              "- tag not in checklist for that kind:")
        for eid, tech in report.unknown_techniques:
            print(f"  ! {eid} / {tech}")
    if report.kinds_without_checklist:
        print(f"\nWARNING kinds without checklist "
              f"({len(report.kinds_without_checklist)}) - 0 gaps != tested:")
        for eid, kind in report.kinds_without_checklist:
            print(f"  ! {eid} (kind {kind})")

    print("\n" + matrix)
    if args.matrix_out:
        out = Path(args.matrix_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(matrix + "\n", encoding="utf-8")
        print(f"\nMatrix -> {args.matrix_out}")

    raise SystemExit(1 if report.gaps else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Register the console script**

In `pyproject.toml`, under `[project.scripts]`, add the line (keep existing lines):

```toml
tk-coverage = "tcformat.coverage_cli:main"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/Scripts/pytest tests/unit/test_coverage_cli.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 6: Commit** (after user confirmation)

```bash
git add tcformat/coverage_cli.py pyproject.toml tests/unit/test_coverage_cli.py
git commit -m "feat(coverage): add tk-coverage Stage-1 depth gate CLI"
```

---

### Task 5: Make SKILL.md step 4 a hard gate

**Files:**
- Modify: `skills/generate-testcases/SKILL.md` (the depth-report / step-4 section)

**Interfaces:**
- Consumes: the `tk-coverage` CLI from Task 4. No code; documentation only.
- Produces: nothing consumed downstream.

- [ ] **Step 1: Locate the current step-4 wording**

Run: `./.venv/Scripts/python.exe -c "import pathlib; print(pathlib.Path('skills/generate-testcases/SKILL.md').read_text(encoding='utf-8'))"`
(Or read the file.) Find the section describing the advisory dual report (`check_coverage` + `check_depth`).

- [ ] **Step 2: Rewrite it as a mandatory gate**

Replace the advisory wording with text equivalent to:

> **Bước 4 (bắt buộc — cổng Stage 1):** Sau khi sinh case, chạy:
> ```bash
> ./.venv/Scripts/tk-coverage --screen testcases/<screen>.yaml --config config.yaml
> ```
> CLI exit **non-zero** khi còn ô element×technique chưa có case và chưa justify.
> Nếu fail: bổ sung test case cho ô thiếu, HOẶC thêm `skip_techniques: [<technique>, ...]`
> (kèm lý do rõ ràng) cho element trong `testcases/<screen>.inventory.yaml`, rồi chạy lại.
> **Chỉ chuyển sang Stage 2 khi `tk-coverage` exit 0.**
> Cảnh báo (`unknown techniques`, `kinds without checklist`) cần xem và xử lý — sửa tag sai
> hoặc bổ sung kind vào `checklists.yaml` — nhưng KHÔNG chặn gate.

Keep `check_coverage` (breadth) guidance intact; only the depth part becomes a hard gate.

- [ ] **Step 3: Verify the file reads coherently**

Read `skills/generate-testcases/SKILL.md` and confirm the gate step references the correct CLI name (`tk-coverage`), the justify key (`skip_techniques`), and the "exit 0 before Stage 2" rule.

- [ ] **Step 4: Commit** (after user confirmation)

```bash
git add skills/generate-testcases/SKILL.md
git commit -m "docs(skill): make depth check a hard Stage-1 gate"
```

---

### Task 6: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the entire unit suite**

Run: `./.venv/Scripts/pytest -q`
Expected: all tests PASS — the Phase 1 baseline (70 passed) plus the new tests from Tasks 1–4 (no regressions). Report the exact passed count.

- [ ] **Step 2: Smoke-test the real screen gate**

Run: `./.venv/Scripts/python.exe -m tcformat.coverage_cli --screen testcases/basic-information-input.yaml --config config.yaml`
Expected: prints the depth summary + matrix; exit code reflects real gaps (non-zero if the real screen still has unjustified gaps — this is informational, confirms the gate runs end to end). Note the result; do not "fix" the screen here.

---

## Notes for the implementer

- Existing `test_tc_depth.py` fixtures (`CHECKLISTS`, `_inv()`) are reused by Task 2 tests — do not redefine them.
- `load_checklists(config_path=config)` resolves the checklist file via `tcformat.resources.checklists_path`; passing `--config` pointing at a YAML with a `checklists_path` key (no `base_url` needed) is the hermetic way to inject a test checklist.
- `Path(screen_path).with_suffix(".inventory.yaml")` turns `testcases/foo.yaml` into `testcases/foo.inventory.yaml`.
- The matrix is output-only markdown — never write into the team xlsx (columns A–R).
