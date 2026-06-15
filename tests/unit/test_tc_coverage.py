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
