from tcformat.schema import Screen, Testcase, Result, BrowserResult
from tcformat.report_data import aggregate


def _tc(tc_id, priority="High", chrome=None, safari=None):
    return Testcase(id=tc_id, section="UI", main_item="x", type="IT",
                    priority=priority,
                    result=Result(chrome=chrome or BrowserResult(),
                                  safari=safari or BrowserResult()))


def test_counts_only_executed_runs():
    # 2 testcases, only some browser runs executed (status != None)
    sc = Screen(screen="S", test_level="IT", testcases=[
        _tc("UI_01", chrome=BrowserResult(status="OK")),          # chrome ran, safari null
        _tc("UI_02", chrome=BrowserResult(status="NG"),
            safari=BrowserResult(status="N/A")),
    ])
    data = aggregate([sc])
    # planned = 2 testcases * 2 browsers = 4 ; executed = OK+NG+N/A = 3
    assert data.planned == 4
    assert data.executed == 3
    assert data.summary.passed == 1   # one OK
    assert data.summary.failed == 1   # one NG
    # pass-rate = OK / executed = 1/3
    assert round(data.summary.pass_rate, 4) == round(1 / 3, 4)


def test_ng_maps_priority_to_severity():
    sc = Screen(screen="S", test_level="IT", testcases=[
        _tc("HI", priority="High", chrome=BrowserResult(status="NG")),
        _tc("LO", priority="Low", chrome=BrowserResult(status="NG")),
    ])
    data = aggregate([sc])
    assert data.summary.bugs_by_severity == {"High": 1, "Low": 1}
    # High-severity bug present -> exit gate fails
    assert data.exit_ok is False
    assert any("High" in r for r in data.exit_reasons)


def test_all_ok_above_threshold_passes_gate():
    tcs = [_tc(f"T{i}", chrome=BrowserResult(status="OK")) for i in range(20)]
    sc = Screen(screen="S", test_level="IT", testcases=tcs)
    data = aggregate([sc])
    assert data.summary.pass_rate == 1.0
    assert data.exit_ok is True
    assert data.exit_reasons == []


def test_zero_executed_does_not_crash_and_fails_gate():
    sc = Screen(screen="S", test_level="IT", testcases=[_tc("UI_01")])
    data = aggregate([sc])
    assert data.executed == 0
    assert data.summary.pass_rate == 0.0
    assert data.exit_ok is False


def test_multi_screen_and_safari_aggregation():
    s1 = Screen(screen="S1", test_level="IT", testcases=[
        _tc("A", chrome=BrowserResult(status="OK"),
            safari=BrowserResult(status="NG")),  # safari NG, priority High
    ])
    s2 = Screen(screen="S2", test_level="IT", testcases=[
        _tc("B", priority="Low", safari=BrowserResult(status="OK")),
    ])
    data = aggregate([s1, s2])
    assert len(data.screens) == 2
    assert data.planned == 4          # 2 testcases * 2 browsers
    assert data.executed == 3         # OK + NG + OK
    assert data.summary.passed == 2
    assert data.summary.failed == 1
    assert data.summary.bugs_by_severity == {"High": 1}  # safari NG on High tc
    assert data.screens[0].safari == {"ok": 0, "ng": 1, "na": 0}
    assert data.screens[1].safari == {"ok": 1, "ng": 0, "na": 0}


def test_all_na_has_executed_but_zero_pass_rate():
    sc = Screen(screen="S", test_level="IT", testcases=[
        _tc("A", chrome=BrowserResult(status="N/A")),
    ])
    data = aggregate([sc])
    assert data.executed == 1
    assert data.summary.passed == 0
    assert data.summary.pass_rate == 0.0
    assert data.exit_ok is False
