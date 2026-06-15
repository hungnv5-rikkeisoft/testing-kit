import pytest
from toolkit.checks.perf_checks import assert_under, PerfCheckError


def test_under_budget_passes():
    assert_under(measured_ms=500, budget_ms=600, label="api")


def test_over_budget_raises():
    with pytest.raises(PerfCheckError):
        assert_under(measured_ms=700, budget_ms=600, label="api")
