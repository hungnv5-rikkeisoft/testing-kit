# Phase 1 Coverage-Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Stage 1 generate test cases with *depth* — fanning each screen element across a technique matrix — and make that depth measurable, without changing the xlsx deliverable.

**Architecture:** Add three optional, YAML-only tags to the `Testcase` schema (`category`/`technique`/`target`). Introduce a reviewable per-screen element inventory (`tcformat/inventory.py`), a bundled config-overridable technique checklist (`tcformat/data/checklists.yaml` + `tcformat/checklists.py`), and an advisory depth report (`coverage.check_depth`). Rewrite the `generate-testcases` skill to go inventory-first → fan-out → dual report (refs + depth).

**Tech Stack:** Python 3.11+, dataclasses, PyYAML, openpyxl, pytest. No new dependencies.

## Global Constraints

- Python `>=3.11`; new deps NOT allowed (use stdlib + existing `pyyaml`/`openpyxl`/`Pillow`).
- New schema fields are **optional, default `""`/empty**, and **backward compatible** — existing YAMLs must still load and render.
- New tags are **YAML-only metadata**: do NOT modify `tcformat/render_xlsx.py`; the team xlsx format (columns A–R) is untouched.
- Config override pattern is fixed: `explicit arg > config.yaml key > bundled default` (mirror `resources.template_path`).
- Tests live in `tests/unit/`, named `test_*.py`, run with `pytest` (config in `pyproject.toml`/`pytest.ini`). No running app required.
- **Git policy (repo + user CLAUDE.md):** every `git add`/`commit` step requires **explicit user confirmation** before running. Use plain commit messages — NO `Co-Authored-By` / Claude attribution trailer.
- Run python via the project venv: `./.venv/Scripts/python.exe` and `./.venv/Scripts/pytest` (Windows).

---

### Task 1: Schema tags (`category` / `technique` / `target`)

**Files:**
- Modify: `tcformat/schema.py` (the `Testcase` dataclass + `_testcase()` + add `VALID_CATEGORIES`)
- Test: `tests/unit/test_tc_schema_tags.py` (create)

**Interfaces:**
- Consumes: nothing (foundation task).
- Produces: `Testcase.category: str`, `Testcase.technique: str`, `Testcase.target: str` (all default `""`); `schema.VALID_CATEGORIES: set[str]`; `_testcase()` raises `SchemaError` on an unknown non-empty `category`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_tc_schema_tags.py`:

```python
from dataclasses import asdict
import pytest
from tcformat.schema import load_screen, dump_screen, SchemaError

BASE = (
    "screen: S\n"
    "testcases:\n"
    "  - id: V_01\n"
    "    type: IT\n"
    "    priority: High\n"
    "    category: Validation\n"
    "    technique: empty\n"
    "    target: name_field\n"
)


def _write(tmp_path, text):
    p = tmp_path / "s.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_tags_parse(tmp_path):
    sc = load_screen(_write(tmp_path, BASE))
    tc = sc.testcases[0]
    assert tc.category == "Validation"
    assert tc.technique == "empty"
    assert tc.target == "name_field"


def test_tags_default_empty_when_absent(tmp_path):
    y = "screen: S\ntestcases:\n  - id: A\n    type: IT\n    priority: Low\n"
    sc = load_screen(_write(tmp_path, y))
    tc = sc.testcases[0]
    assert tc.category == "" and tc.technique == "" and tc.target == ""


def test_invalid_category_raises(tmp_path):
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, BASE.replace("category: Validation",
                                                  "category: Nonsense")))


def test_tags_roundtrip(tmp_path):
    sc = load_screen(_write(tmp_path, BASE))
    out = tmp_path / "o.yaml"
    dump_screen(sc, out)
    sc2 = load_screen(out)
    assert asdict(sc) == asdict(sc2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/pytest tests/unit/test_tc_schema_tags.py -v`
Expected: FAIL — `TypeError`/`SchemaError` mismatch (fields not yet on `Testcase`; bad category not rejected).

- [ ] **Step 3: Add the fields and validation**

In `tcformat/schema.py`, add the category set near the other constants (after line 9):

```python
VALID_CATEGORIES = {
    "UI", "Function", "Validation", "Boundary", "BusinessRule",
    "API", "ErrorHandling", "Security", "UserBehavior",
}
```

Add three fields to the `Testcase` dataclass (after `strategy_ref`, before `precondition`):

```python
    category: str = ""
    technique: str = ""
    target: str = ""
```

In `_testcase()`, set them from the dict (alongside the existing assignments):

```python
        category=d.get("category", ""),
        technique=d.get("technique", ""),
        target=d.get("target", ""),
```

And add validation before `return tc` (after the priority check):

```python
    if tc.category and tc.category not in VALID_CATEGORIES:
        raise SchemaError(f"testcase {tc.id}: invalid category '{tc.category}'")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/pytest tests/unit/test_tc_schema_tags.py tests/unit/test_tc_schema.py -v`
Expected: PASS (new tags work; existing schema tests still green — back-compat).

- [ ] **Step 5: Commit** *(ask user before running)*

```bash
git add tcformat/schema.py tests/unit/test_tc_schema_tags.py
git commit -m "feat(schema): add optional category/technique/target tags to Testcase"
```

---

### Task 2: Bundled checklist data + resources wiring + loader

**Files:**
- Create: `tcformat/data/checklists.yaml`
- Create: `tcformat/checklists.py`
- Modify: `tcformat/resources.py` (add `CHECKLISTS_NAME`, `default_checklists`, `checklists_path`)
- Modify: `pyproject.toml` (package-data: include `data/*.yaml`)
- Test: `tests/unit/test_checklists.py` (create); extend `tests/unit/test_resources.py`

**Interfaces:**
- Consumes: `resources._from_config` (existing).
- Produces:
  - `resources.default_checklists() -> str`
  - `resources.checklists_path(explicit=None, config_path=None) -> str`
  - `checklists.load_checklists(explicit=None, config_path=None) -> dict[str, list[dict]]` — maps element kind → list of `{technique, category, title}` entries; includes a `"screen"` key for cross-cutting techniques.

- [ ] **Step 1: Create the bundled checklist data file**

Create `tcformat/data/checklists.yaml`:

```yaml
input:
  - {technique: empty,             category: Validation,    title: "Bỏ trống field bắt buộc"}
  - {technique: null-value,        category: Validation,    title: "Giá trị null"}
  - {technique: only-space,        category: Validation,    title: "Chỉ chứa khoảng trắng"}
  - {technique: min-length,        category: Boundary,      title: "Độ dài tối thiểu"}
  - {technique: max-length,        category: Boundary,      title: "Độ dài tối đa"}
  - {technique: over-max,          category: Boundary,      title: "Vượt độ dài tối đa"}
  - {technique: boundary,          category: Boundary,      title: "Giá trị biên (n-1/n/n+1)"}
  - {technique: special-char,      category: Validation,    title: "Ký tự đặc biệt"}
  - {technique: jp-chars,          category: Validation,    title: "Ký tự tiếng Nhật"}
  - {technique: vn-chars,          category: Validation,    title: "Ký tự tiếng Việt có dấu"}
  - {technique: wrong-format,      category: Validation,    title: "Sai định dạng"}
  - {technique: nonexistent-value, category: Validation,    title: "Giá trị không tồn tại trong hệ thống"}
select:
  - {technique: option-source,     category: Function,      title: "Nguồn dữ liệu option (DB/hard-code)"}
  - {technique: option-list,       category: Function,      title: "Đủ danh sách option expected"}
  - {technique: option-order,      category: Function,      title: "Thứ tự hiển thị option"}
  - {technique: default-value,     category: Function,      title: "Giá trị mặc định khi load"}
button:
  - {technique: single-action,     category: Function,      title: "Thao tác chính của button (1 case/button)"}
  - {technique: state-after-click, category: Function,      title: "Trạng thái field/button sau khi click"}
  - {technique: double-click,      category: UserBehavior,  title: "Double click"}
  - {technique: multi-click-pending, category: UserBehavior, title: "Multi-click khi request đang xử lý"}
api:
  - {technique: http-200,          category: API,           title: "HTTP 200 + body hợp lệ"}
  - {technique: http-400,          category: API,           title: "HTTP 400"}
  - {technique: http-401,          category: API,           title: "HTTP 401"}
  - {technique: http-403,          category: API,           title: "HTTP 403"}
  - {technique: http-404,          category: API,           title: "HTTP 404"}
  - {technique: http-500,          category: API,           title: "HTTP 500"}
  - {technique: missing-param,     category: API,           title: "Thiếu parameter"}
  - {technique: invalid-data,      category: API,           title: "Dữ liệu không hợp lệ"}
  - {technique: empty-response,    category: API,           title: "Response rỗng"}
screen:
  - {technique: url-tamper,             category: Security,      title: "Thay đổi URL trên browser"}
  - {technique: query-tamper,           category: Security,      title: "Thay đổi query parameter"}
  - {technique: direct-access-no-login, category: Security,      title: "Truy cập URL khi chưa login"}
  - {technique: lower-priv-user,        category: Security,      title: "Truy cập bằng user không đủ quyền"}
  - {technique: session-expired,        category: ErrorHandling, title: "Session hết hạn"}
  - {technique: network-down,           category: ErrorHandling, title: "Mất kết nối mạng"}
  - {technique: server-timeout,         category: ErrorHandling, title: "Server timeout"}
  - {technique: back-forward,           category: UserBehavior,  title: "Back/Forward browser"}
  - {technique: refresh-during-submit,  category: UserBehavior,  title: "Refresh khi đang submit"}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_checklists.py`:

```python
import os
from tcformat.checklists import load_checklists
from tcformat.resources import default_checklists, checklists_path


def test_default_file_exists():
    assert os.path.isfile(default_checklists())
    assert default_checklists().endswith("checklists.yaml")


def test_loads_default_kinds():
    data = load_checklists()
    for kind in ("input", "select", "button", "api", "screen"):
        assert kind in data and len(data[kind]) > 0
    # entries are well-formed
    entry = data["input"][0]
    assert {"technique", "category", "title"} <= set(entry)


def test_override_path(tmp_path):
    custom = tmp_path / "c.yaml"
    custom.write_text("button:\n  - {technique: t1, category: Function, title: x}\n",
                      encoding="utf-8")
    data = load_checklists(str(custom))
    assert list(data) == ["button"]
    assert data["button"][0]["technique"] == "t1"
```

Add to `tests/unit/test_resources.py` (extend the existing file):

```python
def test_checklists_default_and_override(tmp_path):
    from tcformat.resources import default_checklists, checklists_path
    assert checklists_path() == default_checklists()
    assert checklists_path("/x/c.yaml") == "/x/c.yaml"
    cfg = tmp_path / "config.yaml"
    cfg.write_text("checklists_path: /from/cfg.yaml\n", encoding="utf-8")
    assert checklists_path(None, str(cfg)) == "/from/cfg.yaml"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `./.venv/Scripts/pytest tests/unit/test_checklists.py tests/unit/test_resources.py -v`
Expected: FAIL — `ModuleNotFoundError: tcformat.checklists` / `ImportError` for `default_checklists`.

- [ ] **Step 4: Wire resources**

In `tcformat/resources.py`, add after `STRATEGY_NAME` (line 15):

```python
CHECKLISTS_NAME = "checklists.yaml"
```

Add after `default_strategy()`:

```python
def default_checklists() -> str:
    return str(files("tcformat").joinpath("data", CHECKLISTS_NAME))
```

Add after `strategy_path()`:

```python
def checklists_path(explicit: str | None = None, config_path: str | None = None) -> str:
    return explicit or _from_config(config_path, "checklists_path") or default_checklists()
```

- [ ] **Step 5: Create the loader**

Create `tcformat/checklists.py`:

```python
"""Load the technique checklist (element kind -> techniques), config-overridable.

Default ships bundled at tcformat/data/checklists.yaml and is resolved via
tcformat.resources, mirroring strategy/template resolution.
"""
from __future__ import annotations
from pathlib import Path
import yaml

from tcformat.resources import checklists_path


def load_checklists(explicit: str | None = None,
                    config_path: str | None = None) -> dict:
    """Return {kind: [{technique, category, title}, ...]} including key 'screen'."""
    path = checklists_path(explicit, config_path)
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return data
```

- [ ] **Step 6: Include the data file in the package**

In `pyproject.toml`, change the package-data line:

```toml
[tool.setuptools.package-data]
tcformat = ["data/template/*.xlsx", "data/strategy/*.xlsx", "data/*.yaml"]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `./.venv/Scripts/pytest tests/unit/test_checklists.py tests/unit/test_resources.py -v`
Expected: PASS.

- [ ] **Step 8: Commit** *(ask user before running)*

```bash
git add tcformat/checklists.py tcformat/data/checklists.yaml tcformat/resources.py pyproject.toml tests/unit/test_checklists.py tests/unit/test_resources.py
git commit -m "feat(checklists): add bundled config-overridable technique checklist"
```

---

### Task 3: Element inventory module

**Files:**
- Create: `tcformat/inventory.py`
- Test: `tests/unit/test_inventory.py` (create)

**Interfaces:**
- Consumes: nothing (PyYAML only).
- Produces:
  - `inventory.Element` dataclass: `id: str`, `kind: str`, `label=""`, `options_source=""`, `default=""`, `depends_on: list`, `method=""`, `path=""`, `params: list`.
  - `inventory.Inventory` dataclass: `screen: str`, `elements: list[Element]`.
  - `inventory.VALID_KINDS = {"button","input","select","link","api","screen"}`.
  - `inventory.InventoryError(Exception)`.
  - `inventory.load_inventory(path) -> Inventory` — raises `InventoryError` on missing `screen`, missing element `id`/`kind`, or unknown `kind`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_inventory.py`:

```python
import pytest
from tcformat.inventory import load_inventory, InventoryError

SAMPLE = """
screen: Basic Information Input
elements:
  - id: usage_residential
    kind: button
    label: "Usage: Residential"
  - id: prefecture
    kind: select
    options_source: "db:prefectures.name"
    depends_on: []
  - id: municipality
    kind: select
    options_source: "db:municipalities.name"
    depends_on: [prefecture]
  - id: api_submit
    kind: api
    method: POST
    path: /api/basic-info
    params: [usage, prefecture, municipality]
"""


def _write(tmp_path, text):
    p = tmp_path / "inv.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_loads_elements(tmp_path):
    inv = load_inventory(_write(tmp_path, SAMPLE))
    assert inv.screen == "Basic Information Input"
    assert len(inv.elements) == 4
    muni = next(e for e in inv.elements if e.id == "municipality")
    assert muni.kind == "select"
    assert muni.depends_on == ["prefecture"]
    api = next(e for e in inv.elements if e.id == "api_submit")
    assert api.method == "POST" and api.params == ["usage", "prefecture", "municipality"]


def test_missing_screen_raises(tmp_path):
    with pytest.raises(InventoryError):
        load_inventory(_write(tmp_path, "elements: []\n"))


def test_element_missing_id_raises(tmp_path):
    y = "screen: S\nelements:\n  - kind: button\n"
    with pytest.raises(InventoryError):
        load_inventory(_write(tmp_path, y))


def test_unknown_kind_raises(tmp_path):
    y = "screen: S\nelements:\n  - id: x\n    kind: widget\n"
    with pytest.raises(InventoryError):
        load_inventory(_write(tmp_path, y))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/pytest tests/unit/test_inventory.py -v`
Expected: FAIL — `ModuleNotFoundError: tcformat.inventory`.

- [ ] **Step 3: Implement the module**

Create `tcformat/inventory.py`:

```python
"""Load a per-screen element inventory: the fan-out axis for test generation.

One inventory file (testcases/<screen>.inventory.yaml) lists every interactive
element (button/input/select/link), plus api endpoints, with metadata that
drives which checklist techniques apply. Reviewed by a human before cases are
written, so a missing element is caught before it becomes missing coverage.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml

VALID_KINDS = {"button", "input", "select", "link", "api", "screen"}


class InventoryError(Exception):
    pass


@dataclass
class Element:
    id: str
    kind: str
    label: str = ""
    options_source: str = ""
    default: str = ""
    depends_on: list = field(default_factory=list)
    method: str = ""
    path: str = ""
    params: list = field(default_factory=list)


@dataclass
class Inventory:
    screen: str
    elements: list = field(default_factory=list)


def _element(d: dict) -> Element:
    if not d.get("id"):
        raise InventoryError("element missing required 'id'")
    kind = d.get("kind")
    if not kind:
        raise InventoryError(f"element {d['id']}: missing required 'kind'")
    if kind not in VALID_KINDS:
        raise InventoryError(f"element {d['id']}: invalid kind '{kind}'")
    return Element(
        id=str(d["id"]),
        kind=kind,
        label=d.get("label", ""),
        options_source=d.get("options_source", ""),
        default=d.get("default", ""),
        depends_on=list(d.get("depends_on") or []),
        method=d.get("method", ""),
        path=d.get("path", ""),
        params=list(d.get("params") or []),
    )


def load_inventory(path) -> Inventory:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not data.get("screen"):
        raise InventoryError("missing required 'screen'")
    elements = [_element(e) for e in (data.get("elements") or [])]
    return Inventory(screen=data["screen"], elements=elements)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/pytest tests/unit/test_inventory.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** *(ask user before running)*

```bash
git add tcformat/inventory.py tests/unit/test_inventory.py
git commit -m "feat(inventory): add per-screen element inventory loader"
```

---

### Task 4: Advisory depth report (`coverage.check_depth`)

**Files:**
- Modify: `tcformat/coverage.py` (add `DepthReport` + `check_depth`)
- Test: `tests/unit/test_tc_depth.py` (create)

**Interfaces:**
- Consumes: `inventory.Inventory`/`Element` (Task 3); `checklists.load_checklists` output shape (Task 2); `Testcase.target`/`technique` (Task 1).
- Produces:
  - `coverage.DepthReport` dataclass: `expected: int`, `covered: int`, `gaps: list[tuple[str, str]]`; property `depth_rate -> float` (`covered/expected`, or `0.0` when `expected == 0`).
  - `coverage.check_depth(inventory, checklists, screen) -> DepthReport`.

Matrix rule: for each inventory element whose `kind` is **not** `"screen"`, expect one cell per technique in `checklists[kind]`; additionally expect each `checklists["screen"]` technique exactly once under the synthetic target id `"screen"`. A cell `(element_id, technique)` is covered when some testcase has `target == element_id` **and** `technique == technique`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tc_depth.py`:

```python
from tcformat.coverage import check_depth
from tcformat.inventory import Inventory, Element
from tcformat.schema import Screen, Testcase

CHECKLISTS = {
    "button": [{"technique": "single-action", "category": "Function", "title": "x"},
               {"technique": "double-click", "category": "UserBehavior", "title": "y"}],
    "select": [{"technique": "default-value", "category": "Function", "title": "z"}],
    "screen": [{"technique": "url-tamper", "category": "Security", "title": "s"}],
}


def _inv():
    return Inventory(screen="S", elements=[
        Element(id="btn", kind="button"),
        Element(id="sel", kind="select"),
    ])


def test_gaps_listed_for_uncovered_cells():
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", target="btn", technique="single-action"),
    ])
    rep = check_depth(_inv(), CHECKLISTS, sc)
    # expected cells: btn x2, sel x1, screen x1 = 4
    assert rep.expected == 4
    assert rep.covered == 1
    assert ("btn", "double-click") in rep.gaps
    assert ("sel", "default-value") in rep.gaps
    assert ("screen", "url-tamper") in rep.gaps
    assert ("btn", "single-action") not in rep.gaps


def test_full_depth_no_gaps():
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", target="btn", technique="single-action"),
        Testcase(id="B", target="btn", technique="double-click"),
        Testcase(id="C", target="sel", technique="default-value"),
        Testcase(id="D", target="screen", technique="url-tamper"),
    ])
    rep = check_depth(_inv(), CHECKLISTS, sc)
    assert rep.gaps == []
    assert rep.expected == 4 and rep.covered == 4
    assert rep.depth_rate == 1.0


def test_screen_techniques_counted_once():
    inv = Inventory(screen="S", elements=[Element(id="btn", kind="button")])
    sc = Screen(screen="S", testcases=[])
    rep = check_depth(inv, CHECKLISTS, sc)
    # btn x2 + screen x1 = 3 ; screen technique not multiplied per element
    assert rep.expected == 3
    assert rep.depth_rate == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/pytest tests/unit/test_tc_depth.py -v`
Expected: FAIL — `ImportError: cannot import name 'check_depth'`.

- [ ] **Step 3: Implement `check_depth`**

Append to `tcformat/coverage.py`:

```python
@dataclass
class DepthReport:
    expected: int
    covered: int
    gaps: list  # list[tuple[element_id, technique]]

    @property
    def depth_rate(self) -> float:
        return self.covered / self.expected if self.expected else 0.0


def check_depth(inventory, checklists, screen) -> DepthReport:
    """Expected matrix = each element's kind techniques + screen techniques (once).

    A cell (element_id, technique) is covered when a testcase has matching
    target and technique. Elements of kind 'screen' are skipped here because
    screen-level techniques are added once under the synthetic target 'screen'.
    """
    have = {(tc.target, tc.technique)
            for tc in screen.testcases if tc.target and tc.technique}
    expected_cells: list = []
    for el in inventory.elements:
        if el.kind == "screen":
            continue
        for entry in checklists.get(el.kind, []):
            expected_cells.append((el.id, entry["technique"]))
    for entry in checklists.get("screen", []):
        expected_cells.append(("screen", entry["technique"]))
    gaps = [cell for cell in expected_cells if cell not in have]
    return DepthReport(expected=len(expected_cells),
                       covered=len(expected_cells) - len(gaps), gaps=gaps)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/pytest tests/unit/test_tc_depth.py tests/unit/test_tc_coverage.py -v`
Expected: PASS (new depth report works; existing ref-coverage tests still green).

- [ ] **Step 5: Commit** *(ask user before running)*

```bash
git add tcformat/coverage.py tests/unit/test_tc_depth.py
git commit -m "feat(coverage): add advisory element x technique depth report"
```

---

### Task 5: Rewrite the `generate-testcases` skill (inventory-first fan-out)

**Files:**
- Modify: `skills/generate-testcases/SKILL.md` (replace the Inputs/Process/Output sections)
- Test: manual — run the embedded verification snippet against the existing screen.

**Interfaces:**
- Consumes: everything above — `load_inventory`, `load_checklists`, `check_coverage`, `check_depth`, the new tags.
- Produces: documented flow only (no code symbols).

- [ ] **Step 1: Replace the "Inputs you gather first" section**

In `skills/generate-testcases/SKILL.md`, replace the `## Inputs you gather first` block with:

```markdown
## Inputs you gather first

1. Design docs for the screen: text/markdown spec, business rules, DB/API design.
2. Figma or screenshot images (read them multimodally if provided).
3. Strategy testing objects for the relevant level(s):
   run `./.venv/Scripts/tk-strategy --sheet 2_IntergrationTesting`
   (swap for 1_APITesting / 3_System_Testing as needed). Output is JSON.
   For any screen that calls an API, ALSO pull `1_APITesting` so HTTP-code
   techniques get generated.
4. The technique checklist (element kind -> techniques): bundled at
   `tcformat/data/checklists.yaml`, overridable via the `checklists_path`
   config key. This is the fan-out matrix — do not hand-wave it.
```

- [ ] **Step 2: Replace the "Process" section**

Replace the `## Process` block with:

````markdown
## Process

1. **Build the element inventory FIRST.** From the design docs / Figma, write
   `testcases/<screen-slug>.inventory.yaml` listing EVERY interactive element
   and api endpoint (schema: `tcformat/inventory.py`):
   - `kind`: button | input | select | link | api | screen
   - selects: `options_source` (`db:<table>.<col>` or `hardcode:[...]`),
     `default`, `depends_on`
   - apis: `method`, `path`, `params`
   Pause and have a human confirm the inventory is complete (e.g. all preset
   buttons present) before writing cases — a missing element here becomes
   missing coverage downstream.

2. **Fan out into cases.** For EACH strategy testing object relevant to the
   screen, AND for EACH (element x technique) implied by the checklist
   (element kinds + the once-per-screen `screen` techniques), write a testcase.
   Rules:
   - ONE element / ONE scenario per testcase (never group multiple buttons or
     multiple validation techniques into one case).
   - Tag every case with `category`, `technique`, and `target` (the element id,
     or `screen` for cross-cutting cases). Keep `strategy_ref` where the case
     maps to a strategy object.
   - Write steps/expected concretely enough for a browser agent to execute.

3. **Validate + render + report (refs AND depth):**
   ```
   ./.venv/Scripts/python.exe -c "
   from tcformat.schema import load_screen
   from tcformat.render_xlsx import render
   from tcformat.coverage import check_coverage, check_depth
   from tcformat.inventory import load_inventory
   from tcformat.checklists import load_checklists
   from tcformat.strategy import list_objects
   from tcformat.resources import default_template, default_strategy
   sc = load_screen('testcases/<screen-slug>.yaml')
   inv = load_inventory('testcases/<screen-slug>.inventory.yaml')
   render([sc], default_template(), 'testcases/<screen-slug>.xlsx')
   refs = {o['ref'] for o in list_objects(default_strategy(),'2_IntergrationTesting') if o['ref']}
   cov = check_coverage(sc, refs)
   dep = check_depth(inv, load_checklists(), sc)
   print('missing refs:', sorted(cov.missing)); print('unknown refs:', sorted(cov.unknown))
   print('depth gaps:', dep.gaps); print('depth_rate:', round(dep.depth_rate, 2))
   "
   ```

4. **Loop** until `missing`/`unknown` are empty AND `depth gaps` is empty or
   every remaining gap is explicitly justified in the coverage summary
   (e.g. element genuinely has no such technique). The depth report is advisory
   in this phase — do not ignore it.
````

- [ ] **Step 3: Replace the "Output" section**

Replace the `## Output` block with:

```markdown
## Output

- `testcases/<screen-slug>.inventory.yaml` (element inventory, reviewable)
- `testcases/<screen-slug>.yaml` (the contract, reviewable/diffable; cases
  tagged with category/technique/target)
- `testcases/<screen-slug>.xlsx` (team format, sheet "4.x <screen>")
- A short coverage summary: objects covered, depth_rate, and any justified
  depth gaps.
```

- [ ] **Step 4: Manual verification of the reporting snippet**

Create a throwaway minimal inventory for the existing screen and confirm the
snippet runs and reports depth gaps (proves the wiring end-to-end):

```bash
./.venv/Scripts/python.exe -c "
from tcformat.schema import load_screen
from tcformat.coverage import check_depth
from tcformat.inventory import Inventory, Element
from tcformat.checklists import load_checklists
sc = load_screen('testcases/basic-information-input.yaml')
inv = Inventory(screen=sc.screen, elements=[
    Element(id='usage_residential', kind='button'),
    Element(id='prefecture', kind='select'),
    Element(id='api_submit', kind='api'),
])
dep = check_depth(inv, load_checklists(), sc)
print('expected cells:', dep.expected)
print('gaps:', len(dep.gaps), 'depth_rate:', round(dep.depth_rate, 2))
"
```
Expected: prints a non-zero `expected cells` count and a `gaps` count > 0
(today's YAML has no `target`/`technique` tags, so every cell is a gap —
demonstrating the metric now exposes the depth hole the human review found).

- [ ] **Step 5: Run the full suite (regression gate)**

Run: `./.venv/Scripts/pytest -q`
Expected: PASS — all unit tests green, including the new schema/checklists/inventory/depth tests.

- [ ] **Step 6: Commit** *(ask user before running)*

```bash
git add skills/generate-testcases/SKILL.md
git commit -m "docs(skill): rewrite generate-testcases for inventory-first depth fan-out"
```

---

## Self-Review

**Spec coverage:**
- Schema tags (spec §1) → Task 1. ✓
- Inventory artifact + `inventory.py` (spec §2) → Task 3. ✓
- Checklist data + `checklists.py` + override (spec §3) → Task 2. ✓
- Depth report `check_depth` (spec §4) → Task 4. ✓
- Resources wiring `checklists_path` (spec §5) → Task 2. ✓
- SKILL.md rewrite (spec §6) → Task 5. ✓
- Constraint "YAML-only, render untouched" → enforced in Global Constraints + no render task. ✓
- Constraint "backward compatible" → Task 1 Step 4 reruns existing schema tests; Task 4 reruns existing coverage tests. ✓
- Testing plan (spec "Testing") → Tasks 1–4 each add unit tests; Task 5 Step 5 runs full suite. ✓
- Success criteria (depth report exposes gaps) → Task 5 Step 4 manual verification. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code; no "similar to Task N". ✓

**Type consistency:** `check_depth(inventory, checklists, screen)` and `DepthReport(expected, covered, gaps)` used identically in Task 4 impl and tests. `load_checklists()` return shape (`dict[kind] -> list[{technique,category,title}]`) consistent across Tasks 2/4/5. `Element`/`Inventory` field names match between Task 3 and Task 4 usage. `category`/`technique`/`target` field names consistent across Tasks 1/4/5. ✓

**Package-data note:** `data/*.yaml` glob (Task 2 Step 6) also covers any future bundled yaml — intentional and harmless. ✓
