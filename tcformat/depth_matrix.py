"""Render an element x technique depth matrix as a markdown table.

Output-only helper for the tk-coverage CLI; never touches the team xlsx format
(columns A-R). Each cell is covered (✓), a gap (✗), or skipped/justified (–).
"""
from __future__ import annotations

_HEADER = ("| element id | kind | technique | có case? | trạng thái |\n"
           "|------------|------|-----------|----------|------------|")


def render_depth_matrix(inventory, checklists, depth_report) -> str:
    gaps = set(depth_report.gaps)
    skipped = set(depth_report.skipped)

    def row(eid, kind, tech):
        cell = (eid, tech)
        if cell in skipped:
            mark, status = "–", "skipped"
        elif cell in gaps:
            mark, status = "✗", "GAP"
        else:
            mark, status = "✓", "covered"
        return f"| {eid} | {kind} | {tech} | {mark} | {status} |"

    rows: list = []
    for el in inventory.elements:
        if el.kind == "screen":
            continue
        for entry in checklists.get(el.kind, []):
            rows.append(row(el.id, el.kind, entry["technique"]))
    for entry in checklists.get("screen", []):
        rows.append(row("screen", "screen", entry["technique"]))

    return "\n".join([_HEADER, *rows])
