"""Deterministic bookkeeping for Stage 2 test execution.

Creates evidence directories and writes per-testcase results back into the
testcase YAML. Does NOT drive a browser — the agent (via Playwright MCP) does
that and calls this helper to record what happened.
"""
from __future__ import annotations
import argparse
from pathlib import Path

from tcformat.schema import load_screen, dump_screen, VALID_STATUSES

VALID_BROWSERS = {"chrome", "safari"}


def evidence_dir(screen_slug: str, browser: str, tc_id: str,
                 root: str = "evidence") -> Path:
    """Create and return evidence/<screen_slug>/<browser>/<tc_id>/."""
    if browser not in VALID_BROWSERS:
        raise ValueError(f"invalid browser '{browser}' (use {VALID_BROWSERS})")
    d = Path(root) / screen_slug / browser / tc_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def record_result(yaml_path, tc_id: str, browser: str, status: str,
                  evidence=None, note=None, bug_id=None,
                  tester=None, date=None) -> None:
    """Set one browser's result on one testcase, then write the YAML back.

    `status` is required and validated. Optional fields are only written when
    provided (None = leave existing value untouched), except `status` which is
    always set.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status '{status}' (use {VALID_STATUSES})")
    if browser not in VALID_BROWSERS:
        raise ValueError(f"invalid browser '{browser}' (use {VALID_BROWSERS})")
    sc = load_screen(yaml_path)
    tc = next((t for t in sc.testcases if t.id == tc_id), None)
    if tc is None:
        raise ValueError(f"testcase '{tc_id}' not found in {yaml_path}")
    br = getattr(tc.result, browser)
    br.status = status
    if evidence is not None:
        br.evidence = list(evidence)
    if note is not None:
        br.note = note
    if bug_id is not None:
        br.bug_id = bug_id
    if tester is not None:
        br.tester = tester
    if date is not None:
        br.date = date
    dump_screen(sc, yaml_path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("evidence-dir", help="create+print an evidence directory")
    e.add_argument("--screen", required=True)
    e.add_argument("--browser", required=True)
    e.add_argument("--id", required=True)
    e.add_argument("--root", default="evidence")

    r = sub.add_parser("record", help="record a testcase result into YAML")
    r.add_argument("--yaml", required=True)
    r.add_argument("--id", required=True)
    r.add_argument("--browser", required=True)
    r.add_argument("--status", required=True)
    r.add_argument("--evidence", action="append", default=None)
    r.add_argument("--note", default=None)
    r.add_argument("--bug-id", dest="bug_id", default=None)
    r.add_argument("--tester", default=None)
    r.add_argument("--date", default=None)

    args = ap.parse_args(argv)
    if args.cmd == "evidence-dir":
        print(evidence_dir(args.screen, args.browser, args.id, root=args.root))
    else:
        record_result(args.yaml, args.id, args.browser, args.status,
                      evidence=args.evidence, note=args.note,
                      bug_id=args.bug_id, tester=args.tester, date=args.date)
        print(f"recorded {args.id} [{args.browser}] = {args.status}")


if __name__ == "__main__":
    main()
