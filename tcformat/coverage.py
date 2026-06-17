"""Compare a screen's testcase refs against an expected strategy ref set."""
from __future__ import annotations
from dataclasses import dataclass, field


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
    gaps: list  # list[tuple[element_id, technique]] — uncovered, not justified -> fails gate
    skipped: list = field(default_factory=list)              # (element_id, technique) justified via skip_techniques
    unknown_techniques: list = field(default_factory=list)   # (target, technique) tagged but not in that kind's checklist
    kinds_without_checklist: list = field(default_factory=list)  # (element_id, kind) kind has no checklist entry

    @property
    def depth_rate(self) -> float:
        return self.covered / self.expected if self.expected else 0.0


def check_depth(inventory, checklists, screen) -> DepthReport:
    """Expected matrix = each element's kind techniques + screen techniques (once).

    A cell (element_id, technique) is covered when a testcase has matching
    target and technique. `skip_techniques` on an element removes its cells from
    `expected` (recorded in `skipped`). Elements whose kind has no checklist
    entry are reported in `kinds_without_checklist` (0 expected cells, warning
    only). Testcase tags whose technique is not valid for the target's kind are
    reported in `unknown_techniques` (warning only).
    """
    have = {(tc.target, tc.technique)
            for tc in screen.testcases if tc.target and tc.technique}
    kind_by_id = {el.id: el.kind for el in inventory.elements}
    kind_by_id["screen"] = "screen"

    expected_cells: list = []
    skipped: list = []
    kinds_without_checklist: list = []
    for el in inventory.elements:
        if el.kind == "screen":
            continue
        if el.kind not in checklists:
            kinds_without_checklist.append((el.id, el.kind))
            continue
        for entry in checklists[el.kind]:
            tech = entry["technique"]
            if tech in el.skip_techniques:
                skipped.append((el.id, tech))
            else:
                expected_cells.append((el.id, tech))
    for entry in checklists.get("screen", []):
        expected_cells.append(("screen", entry["technique"]))

    gaps = [cell for cell in expected_cells if cell not in have]

    valid_by_kind = {kind: {e["technique"] for e in entries}
                     for kind, entries in checklists.items()}
    unknown_techniques: list = []
    for target, tech in have:
        kind = kind_by_id.get(target)
        if kind is None:
            continue  # target matches no element — out of scope for this metric
        if tech not in valid_by_kind.get(kind, set()):
            unknown_techniques.append((target, tech))

    return DepthReport(
        expected=len(expected_cells),
        covered=len(expected_cells) - len(gaps),
        gaps=gaps, skipped=skipped,
        unknown_techniques=unknown_techniques,
        kinds_without_checklist=kinds_without_checklist)
