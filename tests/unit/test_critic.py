from tcformat.coverage import check_depth
from tcformat.critic import (
    CATEGORY_ORDER, run_critic, CriticReport, CategoryFinding, DependsFinding,
    render_critic_md,
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


def test_render_summary_line_when_no_blocking():
    """Fully clean report: no gaps, no unlinked depends, no warnings -> summary line."""
    inv = _inv([Element(id="btn", kind="button")])
    sc = Screen(screen="S", testcases=[
        Testcase(id="TC-1", target="btn", technique="single-action", category="Function"),
        Testcase(id="TC-2", target="screen", technique="url-tamper", category="Security"),
    ])
    rep = run_critic(inv, CHECKLISTS, sc, _depth(inv, sc))
    md = render_critic_md(rep, "S")
    assert "Không có phát hiện chặn — vẫn cần AI review nhóm ⚠" in md

    # Confirm the two pre-existing render tests would NOT get the summary line.
    # test_render_marks_outside_matrix_and_gate: has gaps (input element uncovered)
    inv2 = _inv([
        Element(id="field_a", kind="input"),
        Element(id="field_b", kind="input", depends_on=["field_a"]),
    ])
    sc2 = Screen(screen="S", testcases=[])
    rep2 = run_critic(inv2, CHECKLISTS, sc2, _depth(inv2, sc2))
    md2 = render_critic_md(rep2, "S")
    assert "Không có phát hiện chặn" not in md2

    # test_render_clean_depends_no_gate_marker: has gaps (input elements mostly uncovered)
    inv3 = _inv([
        Element(id="field_a", kind="input", label="Tỉnh"),
        Element(id="field_b", kind="input", depends_on=["field_a"]),
    ])
    sc3 = Screen(screen="S", testcases=[
        Testcase(id="A", target="field_b", steps=["liên kết field_a"]),
    ])
    rep3 = run_critic(inv3, CHECKLISTS, sc3, _depth(inv3, sc3))
    md3 = render_critic_md(rep3, "S")
    assert "Không có phát hiện chặn" not in md3


def test_render_warnings_section_present():
    """Report with unknown techniques + kinds without checklist -> Cảnh báo section."""
    inv = _inv([Element(id="lnk", kind="link")])  # link has no checklist
    sc = Screen(screen="S", testcases=[
        Testcase(id="A", target="lnk", technique="typo"),  # unknown technique
    ])
    rep = run_critic(inv, CHECKLISTS, sc, _depth(inv, sc))
    md = render_critic_md(rep, "S")
    assert "### Cảnh báo (không chặn gate)" in md
    assert "unknown techniques:" in md
    assert "kinds without checklist:" in md
