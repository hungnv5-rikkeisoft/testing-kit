"""Compare a screen's testcase refs against an expected strategy ref set."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class CoverageReport:
    covered: set
    missing: set
    unknown: set
    total: int

    @property
    def coverage_rate(self) -> float:
        return len(self.covered) / self.total if self.total else 0.0


def check_coverage(screen, strategy_refs: set) -> CoverageReport:
    """strategy_refs = the refs this screen is expected to cover."""
    tagged = {tc.strategy_ref for tc in screen.testcases if tc.strategy_ref}
    covered = tagged & strategy_refs
    unknown = tagged - strategy_refs
    missing = strategy_refs - tagged
    return CoverageReport(covered=covered, missing=missing,
                          unknown=unknown, total=len(strategy_refs))
