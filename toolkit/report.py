from __future__ import annotations
from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class Summary:
    total: int
    passed: int
    failed: int
    bugs_by_severity: dict = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def to_dict(self) -> dict:
        return {
            "total": self.total, "passed": self.passed, "failed": self.failed,
            "pass_rate": round(self.pass_rate, 4),
            "bugs_by_severity": self.bugs_by_severity,
        }


def evaluate_exit_criteria(summary: Summary, criteria) -> tuple[bool, list[str]]:
    """Return (ok, reasons). Strategy sheet 6 exit criteria."""
    reasons: list[str] = []
    if summary.pass_rate < criteria.min_pass_rate:
        reasons.append(
            f"Pass rate {summary.pass_rate:.0%} < required "
            f"{criteria.min_pass_rate:.0%}")
    for sev in criteria.block_severities:
        if summary.bugs_by_severity.get(sev, 0) > 0:
            reasons.append(
                f"{summary.bugs_by_severity[sev]} {sev}-severity bug(s) present")
    return (len(reasons) == 0, reasons)


def write_summary_json(summary: Summary, criteria, path) -> dict:
    ok, reasons = evaluate_exit_criteria(summary, criteria)
    payload = {"summary": summary.to_dict(),
               "exit_criteria_passed": ok, "reasons": reasons}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
