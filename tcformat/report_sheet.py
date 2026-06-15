"""Shared helpers for the template's "3. Test Report" sheet.

Used by both scripts/gen_report.py (JUnit path) and tcformat/report_xlsx.py
(YAML path) so the sheet layout lives in one place.
"""
from __future__ import annotations

REPORT_SHEET = "3. Test Report"
HEADER_LABEL = "Function/Screen"


def find_header_row(ws, label=HEADER_LABEL) -> int:
    for r in range(1, 30):
        if ws.cell(r, 2).value == label:
            return r
    raise ValueError(f"'{label}' header not found in sheet '{ws.title}'")


def clear_region(ws, first_row, last_row, last_col=11):
    """Unmerge ranges inside the body, then blank cells, so leftover template
    sample rows / Total row don't bleed into the generated report."""
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row >= first_row and rng.max_row <= last_row:
            ws.unmerge_cells(str(rng))
    for r in range(first_row, last_row + 1):
        for c in range(1, last_col + 1):
            ws.cell(r, c).value = None


def write_screen_row(ws, row, no, name, total, chrome, safari, bugs):
    """Write one aggregate row. `no` None -> leave the No. column blank (Total).
    chrome/safari are {"ok","ng","na"} dicts."""
    if no is not None:
        ws.cell(row, 1).value = f"{no}.0"
    ws.cell(row, 2).value = name
    ws.cell(row, 3).value = total
    ws.cell(row, 4).value = chrome["ok"]
    ws.cell(row, 5).value = chrome["ng"]
    ws.cell(row, 6).value = chrome["na"]
    ws.cell(row, 7).value = safari["ok"]
    ws.cell(row, 8).value = safari["ng"]
    ws.cell(row, 9).value = safari["na"]
    ws.cell(row, 10).value = bugs
