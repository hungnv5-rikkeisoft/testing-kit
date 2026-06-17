# Phase 3b — Critic Linter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a semi-automated "critic" step (`tk-critic`) that reframes depth findings as a per-category review checklist, flags categories outside the mechanical matrix (UI/BusinessRule) for AI/human review, and gates only on `depends_on` edges with no linking case.

**Architecture:** A pure-logic module `tcformat/critic.py` (reuses the existing `DepthReport` from `check_depth`) plus a thin CLI `tcformat/critic_cli.py` exposed as the `tk-critic` console script. Advisory by design; the only hard gate is unlinked `depends_on`. The AI-judgment half lives as a new step in `skills/generate-testcases/SKILL.md`, not in code.

**Tech Stack:** Python 3.11+, dataclasses, pyyaml (already deps). pytest for tests. No new dependencies.

## Global Constraints

- Python `>=3.11`; no new runtime dependencies (`pyyaml`, `openpyxl`, `Pillow` only).
- New tags / outputs are YAML/markdown only — NEVER touch the team xlsx format (columns A–R).
- Everything overridable via config (`checklists_path`); switching projects must need no code change.
- `list` fields use no generics — match existing `schema.py` / `coverage.py` convention.
- Use the venv: `./.venv/Scripts/python.exe` and `./.venv/Scripts/pytest`.
- Spec/terms are Vietnamese; keep terminology consistent in output strings.
- Git: commit only when the user confirms; plain messages, NO `Co-Authored-By` trailer.
- `run_critic` is pure (no I/O, no print, no exit) — all gate logic is the `gate_failures` property.

---

### Task 1: `critic.py` — data model + `run_critic` logic

**Files:**
- Create: `tcformat/critic.py`
- Test: `tests/unit/test_critic.py`

**Interfaces:**
- Consumes: `tcformat.coverage.DepthReport` (`.gaps: list[(eid, tech)]`, `.unknown_techniques`, `.kinds_without_checklist`); `tcformat.inventory.Inventory`/`Element` (`.id`, `.label`, `.depends_on`); `tcformat.schema.Screen`/`Testcase` (`.category`, `.target`, `.steps`, `.expected`, `.precondition`), `tcformat.schema.VALID_CATEGORIES`; `checklists` dict `{kind: [{technique, category, title}]}`.
- Produces:
  - `CATEGORY_ORDER: tuple` (9 categories, stable order)
  - `CategoryFinding(category, in_matrix, case_count, gaps, needs_judgment)`
  - `DependsFinding(element_id, depends_on, linked)`
  - `CriticReport(categories, depends, unknown_techniques, kinds_without_checklist)` with property `gate_failures -> list[DependsFinding]`
  - `run_critic(inventory, checklists, screen, depth_report) -> CriticReport`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_critic.py`:

```python
from tcformat.coverage import check_depth
from tcformat.critic import (
    CATEGORY_ORDER, run_critic, CriticReport, CategoryFinding, DependsFinding,
)
from tcformat.inventory import Inventory, Element
from tcformat.schema import Screen, Testcase, VALID_CATEGORIES

CHECKLISTS = {
    "input": [{"technique": "max-length", "category": "Boundary", "title": "x"},
              {"technique": "empty", "category": "Validation", "title": "y"}],
    "button": [{"technique": "single-action", "category": "Function", "title": "z"}],
    "screen": [{"technique": "url-tamper", "category": "Security", "title": "s"}],
}


def _inv(elements):
    return Inventory(screen="S", elements=elements)


def _depth(inv, sc):
    return check_depth(inv, CHECKLISTS, sc)


def _finding(report, category):
    return next(c for c in report.categories if c.category == category)


def test_category_order_matches_schema():
    assert set(CATEGORY_ORDER) == VALID_CATEGORIES
    assert len(CATEGORY_ORDER) == len(VALID_CATEGORIES)


def test_categories_outside_matrix_need_judgment():
    inv = _inv([Element(id="f", kind="input")])
    sc = Screen(screen="S", testcases=[])
    rep = run_critic(inv, CHECKLISTS, sc, _depth(inv, sc))
    # checklist has no UI / BusinessRule technique
    assert _finding(rep, "UI").in_matrix is False
    assert _finding(rep, "UI").needs_judgment is True
    assert _finding(rep, "BusinessRule").needs_judgment is True
    # Validation IS in the matrix
    assert _finding(rep, "Validation").in_matrix is True
    assert _finding(rep, "Validation").needs_judgment is False


def test_gaps_grouped_by_category():
    inv = _inv([Element(id="f", kind="input")])
    sc = Screen(screen="S", testcases=[])  # no cases -> all cells are gaps
    rep = run_critic(inv, CHECKLISTS, sc, _depth(inv, sc))
    assert ("f", "max-length") in _finding(rep, "Boundary").gaps
    assert ("f", "empty") in _finding(rep, "Validation").gaps
    assert _finding(rep, "Function").gaps == []


def test_case_count_per_category():
    inv = _inv([Element(id="f", kind="input")])
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", target="f", technique="empty", category="Validation"),
        Testcase(id="B", target="f", technique="max-length", category="Boundary"),
    ])
    rep = run_critic(inv, CHECKLISTS, sc, _depth(inv, sc))
    assert _finding(rep, "Validation").case_count == 1
    assert _finding(rep, "Boundary").case_count == 1
    assert _finding(rep, "Security").case_count == 0


def test_depends_linked_when_case_mentions_parent_id():
    inv = _inv([
        Element(id="field_a", kind="input", label="Tỉnh"),
        Element(id="field_b", kind="input", depends_on=["field_a"]),
    ])
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", target="field_b",
                 steps=["Chọn field_a rồi nhập field_b"], category="BusinessRule"),
    ])
    rep = run_critic(inv, CHECKLISTS, sc, _depth(inv, sc))
    d = next(x for x in rep.depends if x.element_id == "field_b")
    assert d.linked is True
    assert rep.gate_failures == []


def test_depends_unlinked_fails_gate():
    inv = _inv([
        Element(id="field_a", kind="input"),
        Element(id="field_b", kind="input", depends_on=["field_a"]),
    ])
    sc = Screen(screen="S", testcases=[])
    rep = run_critic(inv, CHECKLISTS, sc, _depth(inv, sc))
    d = next(x for x in rep.depends if x.element_id == "field_b")
    assert d.linked is False
    assert d in rep.gate_failures


def test_depends_linked_via_parent_label():
    inv = _inv([
        Element(id="field_a", kind="input", label="Tỉnh/Thành"),
        Element(id="field_b", kind="input", depends_on=["field_a"]),
    ])
    sc = Screen(screen="S", testcases=[
        # mentions the label, not the id
        Testcase(id="A", target="field_b", expected=["Quận lọc theo Tỉnh/Thành"]),
    ])
    rep = run_critic(inv, CHECKLISTS, sc, _depth(inv, sc))
    d = next(x for x in rep.depends if x.element_id == "field_b")
    assert d.linked is True


def test_depends_unknown_parent_still_surfaced():
    inv = _inv([Element(id="field_b", kind="input", depends_on=["ghost"])])
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", target="field_b", steps=["mention ghost"]),
    ])
    rep = run_critic(inv, CHECKLISTS, sc, _depth(inv, sc))
    # parent not in inventory -> still surfaced; linked only if text matches the id
    d = next(x for x in rep.depends if x.depends_on == "ghost")
    assert d.linked is True   # 'ghost' appears in steps text


def test_warnings_forwarded():
    inv = _inv([Element(id="lnk", kind="link")])  # link has no checklist
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", target="lnk", technique="typo"),  # unknown technique
    ])
    rep = run_critic(inv, CHECKLISTS, sc, _depth(inv, sc))
    assert ("lnk", "link") in rep.kinds_without_checklist
    assert ("lnk", "typo") in rep.unknown_techniques
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/pytest tests/unit/test_critic.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tcformat.critic'`.

- [ ] **Step 3: Write minimal implementation**

Create `tcformat/critic.py`:

```python
"""Semi-automated critic over generated testcases — the review checklist as code.

Reuses the depth analysis (`check_depth`) and regroups it by category so the
output reads like the manual review. Flags categories with no checklist
technique (UI, BusinessRule) as needing AI/human judgment, and reports
`depends_on` edges with no linking case (the only hard-gate signal here).
Pure logic: no I/O, no printing, no exit.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from tcformat.schema import VALID_CATEGORIES

# VALID_CATEGORIES is an unordered set; pin a stable order for output.
CATEGORY_ORDER = (
    "UI", "Function", "Validation", "Boundary", "BusinessRule",
    "API", "ErrorHandling", "Security", "UserBehavior",
)
assert set(CATEGORY_ORDER) == VALID_CATEGORIES, "CATEGORY_ORDER out of sync with schema"


@dataclass
class CategoryFinding:
    category: str
    in_matrix: bool
    case_count: int
    gaps: list = field(default_factory=list)        # [(element_id, technique)]
    needs_judgment: bool = False                     # True when outside the matrix


@dataclass
class DependsFinding:
    element_id: str          # the dependent (child) element
    depends_on: str          # the parent element id
    linked: bool             # a case ties child -> parent


@dataclass
class CriticReport:
    categories: list = field(default_factory=list)          # list[CategoryFinding]
    depends: list = field(default_factory=list)             # list[DependsFinding]
    unknown_techniques: list = field(default_factory=list)
    kinds_without_checklist: list = field(default_factory=list)

    @property
    def gate_failures(self) -> list:
        return [d for d in self.depends if not d.linked]


def run_critic(inventory, checklists, screen, depth_report) -> CriticReport:
    cat_of = {}
    for entries in checklists.values():
        for e in entries:
            cat_of[e["technique"]] = e["category"]
    matrix_categories = set(cat_of.values())

    gaps_by_cat: dict = {}
    for eid, tech in depth_report.gaps:
        cat = cat_of.get(tech)
        if cat is not None:
            gaps_by_cat.setdefault(cat, []).append((eid, tech))

    categories = []
    for cat in CATEGORY_ORDER:
        in_matrix = cat in matrix_categories
        case_count = sum(1 for tc in screen.testcases if tc.category == cat)
        categories.append(CategoryFinding(
            category=cat,
            in_matrix=in_matrix,
            case_count=case_count,
            gaps=gaps_by_cat.get(cat, []),
            needs_judgment=not in_matrix,
        ))

    label_by_id = {el.id: el.label for el in inventory.elements}
    depends = []
    for el in inventory.elements:
        for parent_id in el.depends_on:
            needles = [parent_id.lower()]
            plabel = label_by_id.get(parent_id, "")
            if plabel:
                needles.append(plabel.lower())
            linked = False
            for tc in screen.testcases:
                if tc.target != el.id:
                    continue
                text = " ".join(
                    list(tc.steps) + list(tc.expected) + [tc.precondition]).lower()
                if any(n in text for n in needles):
                    linked = True
                    break
            depends.append(DependsFinding(
                element_id=el.id, depends_on=parent_id, linked=linked))

    return CriticReport(
        categories=categories,
        depends=depends,
        unknown_techniques=list(depth_report.unknown_techniques),
        kinds_without_checklist=list(depth_report.kinds_without_checklist),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/pytest tests/unit/test_critic.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add tcformat/critic.py tests/unit/test_critic.py
git commit -m "feat(critic): run_critic groups depth findings by category + depends_on gate"
```

---

### Task 2: `render_critic_md` — markdown review checklist

**Files:**
- Modify: `tcformat/critic.py` (append `render_critic_md`)
- Test: `tests/unit/test_critic.py` (append render tests)

**Interfaces:**
- Consumes: `CriticReport`, `screen_name: str`.
- Produces: `render_critic_md(report, screen_name) -> str` (markdown; output-only, never touches xlsx).

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_critic.py`:

```python
from tcformat.critic import render_critic_md


def test_render_marks_outside_matrix_and_gate():
    inv = _inv([
        Element(id="field_a", kind="input"),
        Element(id="field_b", kind="input", depends_on=["field_a"]),
    ])
    sc = Screen(screen="S", testcases=[])
    rep = run_critic(inv, CHECKLISTS, sc, _depth(inv, sc))
    md = render_critic_md(rep, "S")
    assert "## Critic review — S" in md
    assert "**BusinessRule**" in md and "NGOÀI MA TRẬN" in md
    assert "field_b depends_on field_a" in md
    assert "(fail gate)" in md            # unlinked depends rendered as gate fail


def test_render_clean_depends_no_gate_marker():
    inv = _inv([
        Element(id="field_a", kind="input", label="Tỉnh"),
        Element(id="field_b", kind="input", depends_on=["field_a"]),
    ])
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", target="field_b", steps=["liên kết field_a"]),
    ])
    rep = run_critic(inv, CHECKLISTS, sc, _depth(inv, sc))
    md = render_critic_md(rep, "S")
    assert "field_b depends_on field_a — đã có case" in md
    assert "(fail gate)" not in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/pytest tests/unit/test_critic.py -k render -q`
Expected: FAIL — `ImportError: cannot import name 'render_critic_md'`.

- [ ] **Step 3: Write minimal implementation**

Append to `tcformat/critic.py`:

```python
def render_critic_md(report, screen_name) -> str:
    """Render a CriticReport as a grouped markdown review checklist.

    Markers: ✓ covered / ✗ gap / ⚠ outside the mechanical matrix (needs review).
    Output-only — does not touch the team xlsx (columns A–R).
    """
    lines = [f"## Critic review — {screen_name}", "", "### Theo nhóm (category)"]
    for cf in report.categories:
        if not cf.in_matrix:
            lines.append(
                f"- **{cf.category}** — ⚠ NGOÀI MA TRẬN — cần AI/người review "
                f"({cf.case_count} case hiện có)")
        elif cf.gaps:
            lines.append(f"- **{cf.category}** — {cf.case_count} case, {len(cf.gaps)} gap")
            for eid, tech in cf.gaps:
                lines.append(f"    ✗ {eid} / {tech}")
        else:
            lines.append(f"- **{cf.category}** — {cf.case_count} case, 0 gap ✓")

    lines += ["", "### Phụ thuộc field (depends_on)"]
    if report.depends:
        for d in report.depends:
            if d.linked:
                lines.append(f"    ✓ {d.element_id} depends_on {d.depends_on} — đã có case")
            else:
                lines.append(
                    f"    ✗ {d.element_id} depends_on {d.depends_on} "
                    f"— KHÔNG có case liên kết   (fail gate)")
    else:
        lines.append("    (không có phần tử depends_on)")

    if report.unknown_techniques or report.kinds_without_checklist:
        lines += ["", "### Cảnh báo (không chặn gate)"]
        if report.unknown_techniques:
            ut = ", ".join(f"{e}/{t}" for e, t in report.unknown_techniques)
            lines.append(f"- unknown techniques: {ut}")
        if report.kinds_without_checklist:
            kw = ", ".join(f"{e}({k})" for e, k in report.kinds_without_checklist)
            lines.append(f"- kinds without checklist: {kw}")

    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/pytest tests/unit/test_critic.py -q`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add tcformat/critic.py tests/unit/test_critic.py
git commit -m "feat(critic): render grouped markdown review checklist"
```

---

### Task 3: `tk-critic` CLI + console script

**Files:**
- Create: `tcformat/critic_cli.py`
- Modify: `pyproject.toml:15-18` (`[project.scripts]`)
- Test: `tests/unit/test_critic.py` (append CLI tests)

**Interfaces:**
- Consumes: `tcformat.coverage_cli.run_depth_check(screen_path, inventory_path, config=None) -> (screen, inventory, checklists, report)`; `tcformat.critic.run_critic`, `render_critic_md`.
- Produces: `main(argv=None)` — prints the report, writes `--out` if given, `raise SystemExit(1 if report.gate_failures else 0)`. Console script `tk-critic`.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_critic.py`:

```python
import pytest


def _write(tmp_path, inv_body, sc_body):
    inv = tmp_path / "s.inventory.yaml"
    inv.write_text("screen: S\n" + inv_body, encoding="utf-8")
    sc = tmp_path / "s.yaml"
    sc.write_text("screen: S\n" + sc_body, encoding="utf-8")
    return sc, inv


def test_cli_exits_1_on_unlinked_depends(tmp_path, capsys):
    from tcformat.critic_cli import main
    sc, inv = _write(
        tmp_path,
        "elements:\n  - {id: field_a, kind: input}\n"
        "  - {id: field_b, kind: input, depends_on: [field_a]}\n",
        "testcases: []\n")
    with pytest.raises(SystemExit) as e:
        main(["--screen", str(sc), "--inventory", str(inv)])
    assert e.value.code == 1
    out = capsys.readouterr().out
    assert "Critic review — S" in out          # Unicode printed, no crash


def test_cli_exits_0_when_depends_linked(tmp_path):
    from tcformat.critic_cli import main
    sc, inv = _write(
        tmp_path,
        "elements:\n  - {id: field_a, kind: input}\n"
        "  - {id: field_b, kind: input, depends_on: [field_a]}\n",
        "testcases:\n"
        "  - {id: A, target: field_b, steps: ['chọn field_a']}\n")
    with pytest.raises(SystemExit) as e:
        main(["--screen", str(sc), "--inventory", str(inv)])
    assert e.value.code == 0


def test_cli_writes_out_file(tmp_path):
    from tcformat.critic_cli import main
    sc, inv = _write(
        tmp_path,
        "elements:\n  - {id: field_a, kind: input}\n",
        "testcases: []\n")
    out = tmp_path / "rep.md"
    with pytest.raises(SystemExit):
        main(["--screen", str(sc), "--inventory", str(inv), "--out", str(out)])
    assert out.exists()
    assert "Critic review — S" in out.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/pytest tests/unit/test_critic.py -k cli -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tcformat.critic_cli'`.

- [ ] **Step 3: Write minimal implementation**

Create `tcformat/critic_cli.py`:

```python
"""Stage 1 critic — semi-automated review checklist by category.

Reuses the depth analysis, regroups findings into review categories, flags
categories outside the mechanical matrix (UI/BusinessRule) for AI/human review,
and gates only on depends_on edges with no linking case. Advisory otherwise.
Installed as the `tk-critic` console script.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path


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
    ap.add_argument("--out", default=None,
                    help="also write the markdown critic report to this file")
    args = ap.parse_args(argv)

    # Console may use a non-UTF-8 code page (cp932 on Windows); the report uses
    # Unicode markers (✓/✗/⚠). Force UTF-8 so printing never crashes.
    for _stream in (sys.stdout, sys.stderr):
        _reconfigure = getattr(_stream, "reconfigure", None)
        if _reconfigure is not None:
            _reconfigure(encoding="utf-8")

    from tcformat.coverage_cli import run_depth_check
    from tcformat.critic import run_critic, render_critic_md

    inv_path = args.inventory or _default_inventory(args.screen)
    screen, inventory, checklists, depth = run_depth_check(
        args.screen, inv_path, config=args.config)
    report = run_critic(inventory, checklists, screen, depth)
    md = render_critic_md(report, screen.screen)

    print(md)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md + "\n", encoding="utf-8")
        print(f"\nCritic -> {args.out}")

    raise SystemExit(1 if report.gate_failures else 0)


if __name__ == "__main__":
    main()
```

Modify `pyproject.toml` `[project.scripts]` (currently lines 15–18) to add the `tk-critic` line:

```toml
[project.scripts]
tk-report = "tcformat.report_cli:main"
tk-strategy = "tcformat.strategy:main"
tk-coverage = "tcformat.coverage_cli:main"
tk-critic = "tcformat.critic_cli:main"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/pytest tests/unit/test_critic.py -q`
Expected: PASS (14 tests).

- [ ] **Step 5: Re-install the console script and full suite**

Run: `./.venv/Scripts/python.exe -m pip install -e . -q && ./.venv/Scripts/pytest -q`
Expected: editable re-install succeeds; whole suite green (83 prior + 14 new = 97 passed). `./.venv/Scripts/tk-critic --help` works.

- [ ] **Step 6: Commit**

```bash
git add tcformat/critic_cli.py pyproject.toml tests/unit/test_critic.py
git commit -m "feat(critic): tk-critic CLI gating only on unlinked depends_on"
```

---

### Task 4: Wire critic into SKILL.md + update handoff

**Files:**
- Modify: `skills/generate-testcases/SKILL.md` (add step 5 after the `tk-coverage` step; update Output)
- Modify: `docs/superpowers/2026-06-17-phase2-3-handoff.md` (mark 3b done, point to remaining 3a)

**Interfaces:** Documentation only — no code, no test. Reviewer-gateable on its own (skill wording correctness).

- [ ] **Step 1: Add the critic step to SKILL.md**

In `skills/generate-testcases/SKILL.md`, after the current step 4 block (the `tk-coverage` gate, ends before `## Output`), insert:

```markdown
5. **Critic review (bán-tự-động — bước cuối Stage 1):** Chạy:
   ```bash
   ./.venv/Scripts/tk-critic --screen testcases/<screen>.yaml --config config.yaml \
       [--out reports/<screen>_critic.md]
   ```
   - **Cổng nhẹ:** nếu có `depends_on` chưa-liên-kết (exit 1), bổ sung case kiểm tương
     tác field con↔cha (case target field con, có nhắc tới field cha) rồi chạy lại.
   - **Phần phán đoán (AI):** với mỗi nhóm gắn `⚠ NGOÀI MA TRẬN` (đặc biệt `BusinessRule`,
     `UI`) và các ràng buộc required-theo-mode / liên field, **tự đối chiếu design doc** và
     bổ sung case còn thiếu — ma trận cơ học (`tk-coverage`) KHÔNG bắt được các nhóm này.
   - Chỉ kết thúc Stage 1 khi `tk-coverage` exit 0 **và** đã review xong các nhóm `⚠` của critic.
```

Then update the `## Output` list — append:

```markdown
- `reports/<screen>_critic.md` (tuỳ chọn, từ `--out`): checklist review theo nhóm
  + nhóm cần AI/người phán đoán + depends_on chưa liên kết.
```

- [ ] **Step 2: Update the handoff doc**

In `docs/superpowers/2026-06-17-phase2-3-handoff.md`:

- Change the status line near the top (line ~7) from
  `**Trạng thái: Phase 2 ĐÃ XONG (merged main). Còn lại Phase 3.**`
  to:
  `**Trạng thái: Phase 2 & 3b ĐÃ XONG. Còn lại Phase 3a (structured expected).**`
- At the start of the `## 3. Phase 3` section, add a sub-note:
  `> **3b (critic linter) ĐÃ XONG** — spec `specs/2026-06-17-phase3b-critic-linter-design.md`,`
  `> plan `plans/2026-06-17-phase3b-critic-linter.md`. CLI `tk-critic` (advisory + cổng nhẹ`
  `> depends_on). Còn lại **3a structured expected** dưới đây.`

- [ ] **Step 3: Verify the skill text references real flags**

Run: `./.venv/Scripts/tk-critic --help`
Expected: usage shows `--screen`, `--inventory`, `--config`, `--out` — matches the SKILL.md snippet.

- [ ] **Step 4: Commit**

```bash
git add skills/generate-testcases/SKILL.md docs/superpowers/2026-06-17-phase2-3-handoff.md
git commit -m "docs(critic): add tk-critic step to generate-testcases skill + handoff"
```

---

## Self-Review

**Spec coverage:**
- §3 data model → Task 1 (all dataclasses + `gate_failures`). ✓
- §4 run_critic logic (cat map, grouping, depends_on heuristic, forward warnings) → Task 1 tests + impl. ✓
- §5 render → Task 2. ✓
- §6 CLI (args, UTF-8, exit code) → Task 3. ✓
- §7 SKILL.md step 5 → Task 4. ✓
- §8 testing (10 cases) → covered across Tasks 1–3 (category-outside-matrix, gaps-by-cat, case_count, depends linked/unlinked/label/unknown-parent, forwarded warnings, render markers, CLI exit codes + no UnicodeEncodeError via capsys). ✓
- §9 files touched → Tasks 1–4 match exactly. ✓
- §10 DoD (97 passed, tk-critic runs, SKILL step 5, overridable) → Task 3 Step 5 + Task 4. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**Type consistency:** `run_critic(inventory, checklists, screen, depth_report)` signature identical in spec, Task 1 interface, impl, and CLI call. `run_depth_check` returns `(screen, inventory, checklists, report)` — CLI unpacks in that exact order. `gate_failures` property name consistent across Tasks 1–3. `render_critic_md(report, screen_name)` consistent in Tasks 2–3. ✓

**Note on test count:** "97 passed" assumes the current suite is 83. If the baseline differs, the delta is +14 (this plan's tests); adjust the absolute number when running.
