# Phase 3a: Structured `expected` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow each `expected` list item in a testcase YAML to be either a plain string (unchanged) or a structured assertion dict, flattened to display text when rendered to the team xlsx.

**Architecture:** One source of truth for the flatten rule — a pure `flatten_expected(item)` in `tcformat/schema.py` — reused by both the xlsx renderer and the critic. Validation lives in the schema loader (fail fast on unknown/empty assertion dicts). No xlsx format change: dict assertions collapse to a single numbered line in column 8.

**Tech Stack:** Python 3, `dataclasses`, `PyYAML`, `openpyxl`, `pytest`. venv at `./.venv/`.

## Global Constraints

- YAML-only feature: do NOT change the team xlsx layout (columns A–R, numbering `1.`/`2.`/`3.` in column 8).
- Optional everywhere: NO category enforcement — string items must keep working byte-for-byte.
- Assertion key set is EXACTLY 7: `field, value, enabled, required, button_state, request, redirect`. All optional; unknown keys rejected.
- A dict must carry at least one non-`field` key with a non-`None` value, else `SchemaError` (`field` alone produces no clause). Note: `enabled: false` / `required: false` are valid (False ≠ None).
- Use venv: `./.venv/Scripts/python.exe` and `./.venv/Scripts/pytest`.
- Spec terminology is Vietnamese; keep it consistent.
- Git: commit only when the user confirms; plain messages, no `Co-Authored-By` trailer.

**Spec:** `docs/superpowers/specs/2026-06-18-phase3a-structured-expected-design.md`

---

### Task 1: Schema — validate mixed `expected` + `flatten_expected`

**Files:**
- Modify: `tcformat/schema.py` (add `EXPECTED_KEYS`, `_validate_expected`, `flatten_expected`; wire into `_testcase`)
- Test: `tests/unit/test_tc_schema.py`

**Interfaces:**
- Consumes: existing `SchemaError`, `_testcase`, `load_screen`.
- Produces:
  - `EXPECTED_KEYS: set[str]` = `{"field","value","enabled","required","button_state","request","redirect"}`
  - `flatten_expected(item) -> str` — module-level pure function; `str` in → same `str` out; `dict` in → clauses joined by `"; "`.
  - `_testcase` now stores `expected` as a validated `list[str | dict]` (raises `SchemaError` on bad items).

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tc_schema.py`:

```python
from tcformat.schema import flatten_expected

DICT_SAMPLE = """
screen: "S"
test_level: IT
testcases:
  - id: VAL_01
    type: IT
    priority: High
    steps: ["Submit empty form"]
    expected:
      - "Plain string still works"
      - {field: "Field A", value: "XXX"}
      - {field: "Field B", enabled: false}
      - {request: "POST /api/x"}
      - {redirect: "/home"}
"""


def test_mixed_expected_loads(tmp_path):
    sc = load_screen(_write(tmp_path, DICT_SAMPLE))
    exp = sc.testcases[0].expected
    assert exp[0] == "Plain string still works"
    assert exp[1] == {"field": "Field A", "value": "XXX"}
    assert exp[2] == {"field": "Field B", "enabled": False}


def test_expected_unknown_key_raises(tmp_path):
    y = DICT_SAMPLE.replace('{field: "Field A", value: "XXX"}', '{field: "A", foo: 1}')
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, y))


def test_expected_no_assertion_keys_raises(tmp_path):
    # field-only dict has no clause-producing key
    y = DICT_SAMPLE.replace('{field: "Field A", value: "XXX"}', '{field: "A"}')
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, y))


def test_expected_empty_dict_raises(tmp_path):
    y = DICT_SAMPLE.replace('{field: "Field A", value: "XXX"}', '{}')
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, y))


def test_expected_wrong_type_raises(tmp_path):
    y = DICT_SAMPLE.replace('{field: "Field A", value: "XXX"}', '[1, 2]')
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, y))


def test_flatten_string_passthrough():
    assert flatten_expected("just text") == "just text"


def test_flatten_value_with_field():
    assert flatten_expected({"field": "Field A", "value": "XXX"}) == "Field A = XXX"


def test_flatten_value_without_field():
    assert flatten_expected({"value": "XXX"}) == "= XXX"


def test_flatten_enabled_false_is_disabled():
    assert flatten_expected({"field": "Field B", "enabled": False}) == "Field B disabled"


def test_flatten_required_true():
    assert flatten_expected({"field": "Email", "required": True}) == "Email required"


def test_flatten_required_false_is_optional():
    assert flatten_expected({"field": "Phone", "required": False}) == "Phone optional"


def test_flatten_button_state():
    assert flatten_expected({"field": "Submit", "button_state": "enabled"}) == "Submit button enabled"


def test_flatten_request_and_redirect():
    assert flatten_expected({"request": "POST /api/x"}) == "POST /api/x"
    assert flatten_expected({"redirect": "/home"}) == "redirect /home"


def test_flatten_multiple_keys_joined_in_order():
    item = {"field": "Field A", "value": "1", "required": True}
    assert flatten_expected(item) == "Field A = 1; Field A required"


def test_roundtrip_dict_expected(tmp_path):
    sc = load_screen(_write(tmp_path, DICT_SAMPLE))
    out = tmp_path / "o.yaml"
    dump_screen(sc, out)
    sc2 = load_screen(out)
    assert asdict(sc) == asdict(sc2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/pytest tests/unit/test_tc_schema.py -q`
Expected: FAIL — `ImportError: cannot import name 'flatten_expected'` (and `EXPECTED_KEYS`).

- [ ] **Step 3: Implement in `tcformat/schema.py`**

Add the constant right after `VALID_CATEGORIES` (near line 13):

```python
EXPECTED_KEYS = {
    "field", "value", "enabled", "required",
    "button_state", "request", "redirect",
}
```

Add these two module-level functions (place them above `_testcase`):

```python
def _validate_expected(tc_id: str, items: list) -> list:
    out = []
    for item in items:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            unknown = sorted(set(item) - EXPECTED_KEYS)
            if unknown:
                raise SchemaError(
                    f"testcase {tc_id}: expected assertion has unknown key '{unknown[0]}'")
            if not any(k != "field" and item[k] is not None for k in item):
                raise SchemaError(
                    f"testcase {tc_id}: expected assertion has no assertion keys")
            out.append(item)
        else:
            raise SchemaError(
                f"testcase {tc_id}: expected item must be str or dict, "
                f"got {type(item).__name__}")
    return out


def flatten_expected(item) -> str:
    """Flatten one `expected` item (str or assertion dict) into display text.

    One dict describes one subject (`field`); attribute clauses are joined by
    '; ' in a fixed key order. Absent or None keys are skipped.
    """
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)
    prefix = f"{item['field']} " if item.get("field") else ""
    clauses = []
    if item.get("value") is not None:
        clauses.append(f"{prefix}= {item['value']}".strip())
    if item.get("enabled") is not None:
        clauses.append(f"{prefix}{'enabled' if item['enabled'] else 'disabled'}".strip())
    if item.get("required") is not None:
        clauses.append(f"{prefix}{'required' if item['required'] else 'optional'}".strip())
    if item.get("button_state") is not None:
        clauses.append(f"{prefix}button {item['button_state']}".strip())
    if item.get("request") is not None:
        clauses.append(str(item["request"]))
    if item.get("redirect") is not None:
        clauses.append(f"redirect {item['redirect']}")
    return "; ".join(clauses)
```

Wire validation into `_testcase`. Add `tc_id` right after the missing-id check, and use it for `expected`:

```python
def _testcase(d: dict) -> Testcase:
    if not d.get("id"):
        raise SchemaError("testcase missing required 'id'")
    tc_id = str(d["id"])
    tc = Testcase(
        id=tc_id,
        section=d.get("section", ""),
        main_item=d.get("main_item", ""),
        middle_item=d.get("middle_item", ""),
        minor_item=d.get("minor_item", ""),
        type=d.get("type", "IT"),
        priority=d.get("priority", "Medium"),
        strategy_ref=d.get("strategy_ref", ""),
        category=d.get("category", ""),
        technique=d.get("technique", ""),
        target=d.get("target", ""),
        precondition=d.get("precondition", ""),
        steps=list(d.get("steps") or []),
        expected=_validate_expected(tc_id, list(d.get("expected") or [])),
        result=_result(d.get("result")),
    )
```

(The rest of `_testcase` — the type/priority/category checks and `return tc` — stays unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/pytest tests/unit/test_tc_schema.py -q`
Expected: PASS (all new + existing schema tests).

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `./.venv/Scripts/pytest -q`
Expected: PASS — previous count (83+) plus the new schema tests, all green.

- [ ] **Step 6: Commit (after user confirms)**

```bash
git add tcformat/schema.py tests/unit/test_tc_schema.py
git commit -m "feat(expected): structured expected assertions + flatten_expected in schema"
```

---

### Task 2: Renderer — flatten dict assertions into column 8

**Files:**
- Modify: `tcformat/render_xlsx.py` (import `flatten_expected`; use it on line ~79-80)
- Test: `tests/unit/test_tc_render.py`

**Interfaces:**
- Consumes: `flatten_expected` from `tcformat.schema` (Task 1).
- Produces: column 8 text where each item is `"{n}. {flattened}"`, numbering preserved.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_tc_render.py`:

```python
def test_render_flattens_dict_expected(tmp_path):
    sc = Screen(screen="Assert Screen", test_level="IT", testcases=[
        Testcase(id="VAL_01", section="VALIDATION", main_item="Submit",
                 type="IT", priority="High",
                 steps=["Submit empty"],
                 expected=[
                     {"field": "Field A", "value": "XXX"},
                     {"field": "Field B", "enabled": False},
                     {"request": "POST /api/x"},
                 ]),
    ])
    out = tmp_path / "assert.xlsx"
    render([sc], TEMPLATE, str(out))

    wb = load_workbook(out)
    ws = _sheet_by_c1(wb, "Assert Screen")
    cell = ws.cell([r for r in range(10, ws.max_row + 1)
                    if ws.cell(r, 2).value == "VAL_01"][0], 8).value
    assert "1. Field A = XXX" in cell
    assert "2. Field B disabled" in cell
    assert "3. POST /api/x" in cell
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/pytest tests/unit/test_tc_render.py::test_render_flattens_dict_expected -v`
Expected: FAIL — column 8 contains a raw dict repr like `{'field': 'Field A', ...}`, so `"1. Field A = XXX"` is not present.

- [ ] **Step 3: Implement the flatten wiring**

In `tcformat/render_xlsx.py`, add the import near the top (after the `openpyxl` import on line 9):

```python
from tcformat.schema import flatten_expected
```

Change the column-8 write in `_write` (lines 79-80) from:

```python
        ws.cell(row, 8).value = "\n".join(
            f"{i + 1}. {e}" for i, e in enumerate(tc.expected))
```

to:

```python
        ws.cell(row, 8).value = "\n".join(
            f"{i + 1}. {flatten_expected(e)}" for i, e in enumerate(tc.expected))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/pytest tests/unit/test_tc_render.py -q`
Expected: PASS (new test + the existing `test_render_fills_testcase_sheet`, which uses string expected and is unaffected).

- [ ] **Step 5: Commit (after user confirms)**

```bash
git add tcformat/render_xlsx.py tests/unit/test_tc_render.py
git commit -m "feat(expected): flatten structured expected when rendering xlsx column 8"
```

---

### Task 3: Critic — flatten before keyword matching

**Files:**
- Modify: `tcformat/critic.py` (import `flatten_expected`; flatten in the depends_on text blob, line ~87-88)
- Test: `tests/unit/test_critic.py`

**Interfaces:**
- Consumes: `flatten_expected` from `tcformat.schema` (Task 1).
- Produces: no signature change; `run_critic` no longer crashes on dict `expected`, and depends_on keyword matching reads flattened text.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_critic.py`. This mirrors the existing `test_depends_linked_via_parent_label` (line ~95) but the link evidence lives inside a **structured (dict) expected assertion**. It reuses the file's existing `_inv`, `_depth`, and `CHECKLISTS` — no new helpers. `flatten_expected({"field": "Quận", "value": "lọc theo Tỉnh/Thành"})` → `"Quận = lọc theo Tỉnh/Thành"`, whose lowercased form contains the parent label `tỉnh/thành`, so the depends_on link is detected:

```python
def test_depends_linked_via_dict_expected():
    inv = _inv([
        Element(id="field_a", kind="input", label="Tỉnh/Thành"),
        Element(id="field_b", kind="input", depends_on=["field_a"]),
    ])
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", target="field_b",
                 expected=[{"field": "Quận", "value": "lọc theo Tỉnh/Thành"}]),
    ])
    rep = run_critic(inv, CHECKLISTS, sc, _depth(inv, sc))
    d = next(x for x in rep.depends if x.element_id == "field_b")
    assert d.linked is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/pytest tests/unit/test_critic.py::test_depends_linked_via_dict_expected -v`
Expected: FAIL — `TypeError: sequence item ...: expected str instance, dict found` from the `" ".join(...)` at `tcformat/critic.py:87-88`.

- [ ] **Step 3: Implement the flatten wiring**

In `tcformat/critic.py`, extend the existing schema import on line 12:

```python
from tcformat.schema import VALID_CATEGORIES, flatten_expected
```

Change the text-blob build (lines 87-88) from:

```python
                text = " ".join(
                    list(tc.steps) + list(tc.expected) + [tc.precondition or ""]).lower()
```

to:

```python
                text = " ".join(
                    list(tc.steps)
                    + [flatten_expected(e) for e in tc.expected]
                    + [tc.precondition or ""]).lower()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/pytest tests/unit/test_critic.py -q`
Expected: PASS (new test + existing critic tests).

- [ ] **Step 5: Run the full suite (final regression gate)**

Run: `./.venv/Scripts/pytest -q`
Expected: PASS — all tests green (83+ baseline plus the new Phase 3a tests across schema/render/critic).

- [ ] **Step 6: Commit (after user confirms)**

```bash
git add tcformat/critic.py tests/unit/test_critic.py
git commit -m "feat(expected): flatten structured expected in critic keyword matching"
```

---

## Notes for the implementer

- Tasks are ordered: Task 1 (schema) must land first — Tasks 2 and 3 import `flatten_expected` from it.
- No circular import risk: `schema.py` imports neither `render_xlsx` nor `critic`.
- Do NOT add category enforcement or new config — out of scope (see spec §6).
- `flatten_expected` is the single source of truth for the str/dict rendering rule; never inline the flatten logic in render or critic.
