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
