"""Aggregate Stage 2 YAML results into report counts + exit-criteria verdict.

Pure data layer (no openpyxl). The unit of counting is a "run" = one
(testcase x browser) pair. A run is "planned" (in scope) when it has any
recorded status (OK/NG/N/A); a run with no status (None) was never in scope
- e.g. a testcase outside the ~25% Safari subset. A run is "executed" only
when it produced a verdict (OK or NG); N/A means planned-but-not-executed.
Pass-rate = OK / (OK + NG) over executed runs (strategy sheet 6 exit criteria).
"""
from __future__ import annotations
from dataclasses import dataclass, field

from toolkit.report import Summary, evaluate_exit_criteria
from toolkit.config import ExitCriteria

BROWSERS = ("chrome", "safari")
# testcase priority -> bug severity bucket
_SEVERITY = {"High": "High", "Medium": "Medium", "Low": "Low"}


@dataclass
class ScreenReport:
    screen: str
    chrome: dict           # {"ok": int, "ng": int, "na": int}
    safari: dict
    bugs: int              # number of NG runs on this screen
    planned: int           # in-scope runs (any recorded status: OK/NG/N/A)
    executed: int          # runs with a verdict (OK or NG); excludes N/A


@dataclass
class ReportData:
    screens: list
    summary: Summary
    planned: int
    executed: int
    exit_ok: bool
    exit_reasons: list = field(default_factory=list)


def _blank():
    return {"ok": 0, "ng": 0, "na": 0}


def _tally(counts, status):
    if status == "OK":
        counts["ok"] += 1
    elif status == "NG":
        counts["ng"] += 1
    elif status == "N/A":
        counts["na"] += 1


def aggregate(screens, criteria=None) -> ReportData:
    criteria = criteria or ExitCriteria()
    screen_reports = []
    bugs_by_severity: dict = {}
    tot_planned = 0

    for sc in screens:
        c, s = _blank(), _blank()
        bugs = 0
        for tc in sc.testcases:
            for br_name in BROWSERS:
                status = getattr(tc.result, br_name).status
                _tally(c if br_name == "chrome" else s, status)
                if status == "NG":
                    bugs += 1
                    sev = _SEVERITY.get(tc.priority, "Medium")
                    bugs_by_severity[sev] = bugs_by_severity.get(sev, 0) + 1
        # planned = in-scope runs (OK+NG+N/A); executed = verdicts (OK+NG)
        planned = sum(c.values()) + sum(s.values())
        executed = c["ok"] + c["ng"] + s["ok"] + s["ng"]
        screen_reports.append(ScreenReport(
            screen=sc.screen, chrome=c, safari=s, bugs=bugs,
            planned=planned, executed=executed))
        tot_planned += planned

    tot_ok = sum(r.chrome["ok"] + r.safari["ok"] for r in screen_reports)
    tot_ng = sum(r.chrome["ng"] + r.safari["ng"] for r in screen_reports)
    executed = tot_ok + tot_ng
    summary = Summary(total=executed, passed=tot_ok, failed=tot_ng,
                      bugs_by_severity=bugs_by_severity)
    ok, reasons = evaluate_exit_criteria(summary, criteria)
    return ReportData(
        screens=screen_reports, summary=summary,
        planned=tot_planned, executed=executed,
        exit_ok=ok, exit_reasons=reasons)
