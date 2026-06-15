from toolkit.report import Summary, evaluate_exit_criteria
from toolkit.config import ExitCriteria


def test_summary_pass_rate():
    s = Summary(total=10, passed=9, failed=1, bugs_by_severity={"High": 1})
    assert s.pass_rate == 0.9


def test_exit_criteria_blocks_on_low_pass_rate():
    s = Summary(total=100, passed=90, failed=10, bugs_by_severity={})
    ok, reasons = evaluate_exit_criteria(s, ExitCriteria())
    assert ok is False
    assert any("pass rate" in r.lower() for r in reasons)


def test_exit_criteria_blocks_on_blocking_bug():
    s = Summary(total=100, passed=100, failed=0,
                bugs_by_severity={"Critical": 1})
    ok, reasons = evaluate_exit_criteria(s, ExitCriteria())
    assert ok is False
    assert any("critical" in r.lower() for r in reasons)


def test_exit_criteria_pass():
    s = Summary(total=100, passed=96, failed=4, bugs_by_severity={"Low": 4})
    ok, reasons = evaluate_exit_criteria(s, ExitCriteria())
    assert ok is True
    assert reasons == []
