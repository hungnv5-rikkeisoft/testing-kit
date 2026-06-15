from __future__ import annotations


class PerfCheckError(AssertionError):
    pass


def assert_under(measured_ms: float, budget_ms: float, label: str = ""):
    """Generic threshold gate used by web & API perf checks."""
    if measured_ms > budget_ms:
        raise PerfCheckError(
            f"{label or 'duration'} {measured_ms:.0f}ms exceeds budget {budget_ms}ms")
    return measured_ms
