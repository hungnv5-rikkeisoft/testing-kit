"""Advisory DOM audit — diff an authored inventory against a live DOM snapshot.

Second net for the inventory blind spot. The snapshot is produced EXTERNALLY by
Playwright MCP (no python-playwright dep here) and handed in as a dict:

    {"elements": [{"role": "textbox", "name": "userId"}, ...],
     "forms":    [{"action": "/", "method": "POST"}, ...]}

Matching identity: input/select elements by `name` ↔ inventory id/label; buttons
by visible text ↔ inventory label/id. All matching is normalized (lower/strip).
This is heuristic (hidden/conditional elements may mis-match) so the tool is
ADVISORY: it prints suspicions and ALWAYS exits 0.
"""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

_FIELD_ROLES = {"textbox", "combobox", "listbox", "spinbutton", "searchbox", "slider"}
_BUTTON_ROLES = {"button", "link"}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


@dataclass
class AuditReport:
    missing: list   # DOM identities with no inventory match
    stale: list     # inventory ids (input/select/button) with no DOM match
    form_without_api: bool


def audit_inventory(inventory, snapshot: dict) -> AuditReport:
    els = snapshot.get("elements") or []
    forms = snapshot.get("forms") or []

    inv_keys = set()          # normalized id + label for every element
    for el in inventory.elements:
        inv_keys.add(_norm(el.id))
        if el.label:
            inv_keys.add(_norm(el.label))

    missing = []
    for el in els:
        role = _norm(el.get("role"))
        name = el.get("name") or ""
        if role in _FIELD_ROLES or role in _BUTTON_ROLES:
            if _norm(name) not in inv_keys:
                missing.append(name)

    dom_keys = {_norm(el.get("name")) for el in els}
    stale = []
    for el in inventory.elements:
        if el.kind not in ("input", "select", "button"):
            continue
        keys = {_norm(el.id)} | ({_norm(el.label)} if el.label else set())
        if not (keys & dom_keys):
            stale.append(el.id)

    has_api = any(el.kind == "api" for el in inventory.elements)
    form_without_api = bool(forms) and not has_api

    return AuditReport(missing=missing, stale=stale,
                       form_without_api=form_without_api)


def format_report(inventory, report: AuditReport) -> str:
    lines = [f"# Inventory audit — {inventory.screen}", ""]
    lines.append(f"## SUSPECTED MISSING ({len(report.missing)}) "
                 "— có trên DOM, thiếu trong inventory")
    lines += [f"- {m}" for m in report.missing] or ["- (none)"]
    lines.append("")
    lines.append(f"## SUSPECTED STALE ({len(report.stale)}) "
                 "— có trong inventory, không thấy trên DOM")
    lines += [f"- {s}" for s in report.stale] or ["- (none)"]
    lines.append("")
    if report.form_without_api:
        lines.append("## ⚠ FORM WITHOUT API — DOM có <form> nhưng inventory "
                     "thiếu element kind 'api' (xem lint R1).")
    lines.append("")
    lines.append("_Advisory — đối chiếu thủ công, không tự sửa._")
    return "\n".join(lines)


def main(argv=None):
    for _stream in (sys.stdout, sys.stderr):
        rc = getattr(_stream, "reconfigure", None)
        if rc is not None:
            rc(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Advisory inventory vs DOM-snapshot audit.")
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--snapshot", required=True, help="JSON snapshot file")
    ap.add_argument("--out", default=None, help="also write the markdown report here")
    args = ap.parse_args(argv)

    from tcformat.inventory import load_inventory
    inventory = load_inventory(args.inventory)
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    report = audit_inventory(inventory, snapshot)
    text = format_report(inventory, report)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"\nAudit -> {args.out}")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
