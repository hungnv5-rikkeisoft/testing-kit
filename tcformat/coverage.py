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


@dataclass
class DepthReport:
    expected: int
    covered: int
    gaps: list  # list[tuple[element_id, technique]]

    @property
    def depth_rate(self) -> float:
        return self.covered / self.expected if self.expected else 0.0


def check_depth(inventory, checklists, screen) -> DepthReport:
    """Expected matrix = each element's kind techniques + screen techniques (once).

    A cell (element_id, technique) is covered when a testcase has matching
    target and technique. Elements of kind 'screen' are skipped here because
    screen-level techniques are added once under the synthetic target 'screen'.
    """
    have = {(tc.target, tc.technique)
            for tc in screen.testcases if tc.target and tc.technique}
    expected_cells: list = []
    for el in inventory.elements:
        if el.kind == "screen":
            continue
        for entry in checklists.get(el.kind, []):
            expected_cells.append((el.id, entry["technique"]))
    for entry in checklists.get("screen", []):
        expected_cells.append(("screen", entry["technique"]))
    gaps = [cell for cell in expected_cells if cell not in have]
    return DepthReport(expected=len(expected_cells),
                       covered=len(expected_cells) - len(gaps), gaps=gaps)
