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
