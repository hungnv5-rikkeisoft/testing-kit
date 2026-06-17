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
