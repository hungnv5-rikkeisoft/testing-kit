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


def test_R1_not_triggered_for_dict_without_request_or_redirect():
    inv = Inventory(screen="S", elements=[Element(id="b", kind="button")])
    sc = _screen([_tc("T1", target="b",
                       expected=[{"field": "email", "value": "x@y.com"}])])
    assert check_completeness(inv, sc).ok


def test_R1_not_triggered_for_dict_with_null_request():
    inv = Inventory(screen="S", elements=[Element(id="b", kind="button")])
    sc = _screen([_tc("T1", target="b", expected=[{"request": None, "value": "ok"}])])
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
