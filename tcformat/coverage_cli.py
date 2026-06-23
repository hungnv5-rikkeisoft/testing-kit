"""Stage 1 gate - depth coverage check (element x technique matrix).

Loads a screen's testcases + its element inventory + the technique checklist,
prints gaps / skipped / warnings + a markdown matrix, and exits non-zero when
any expected cell has no test case and is not justified via `skip_techniques`.
Installed as the `tk-coverage` console script.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path


def run_depth_check(screen_path, inventory_path, config=None):
    """Load inputs and compute the DepthReport. Returns
    (screen, inventory, checklists, report)."""
    from tcformat.schema import load_screen
    from tcformat.inventory import load_inventory
    from tcformat.checklists import load_checklists
    from tcformat.coverage import check_depth
    screen = load_screen(screen_path)
    inventory = load_inventory(inventory_path)
    checklists = load_checklists(config_path=config)
    report = check_depth(inventory, checklists, screen)
    return screen, inventory, checklists, report


def _default_inventory(screen_path) -> str:
    return str(Path(screen_path).with_suffix(".inventory.yaml"))


def main(argv=None):
    # Console may use a non-UTF-8 code page (e.g. cp932 on Windows); gap markers
    # and the matrix use Unicode (✓/✗/–). Force UTF-8 so printing never crashes.
    for _stream in (sys.stdout, sys.stderr):
        _reconfigure = getattr(_stream, "reconfigure", None)
        if _reconfigure is not None:
            _reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--screen", required=True, help="testcase YAML for the screen")
    ap.add_argument("--inventory", default=None,
                    help="inventory YAML (default: <screen>.inventory.yaml)")
    ap.add_argument("--config", default=None,
                    help="config.yaml to read checklists_path override from")
    ap.add_argument("--matrix-out", dest="matrix_out", default=None,
                    help="also write the markdown matrix to this file")
    args = ap.parse_args(argv)

    inv_path = args.inventory or _default_inventory(args.screen)
    screen, inventory, checklists, report = run_depth_check(
        args.screen, inv_path, config=args.config)
    from tcformat.inventory_lint import check_completeness
    lint = check_completeness(inventory, screen)

    from tcformat.depth_matrix import render_depth_matrix
    matrix = render_depth_matrix(inventory, checklists, report)

    print(f"Depth: expected {report.expected}, covered {report.covered}, "
          f"rate {report.depth_rate:.0%}")
    if report.gaps:
        print(f"\nGAPS ({len(report.gaps)}) - need a case or skip_techniques justify:")
        for eid, tech in report.gaps:
            print(f"  ✗ {eid} / {tech}")
    if report.skipped:
        print(f"\nSKIPPED ({len(report.skipped)}) - justified, not tested:")
        for eid, tech in report.skipped:
            print(f"  – {eid} / {tech}")
    if report.unknown_techniques:
        print(f"\nWARNING unknown techniques ({len(report.unknown_techniques)}) "
              "- tag not in checklist for that kind:")
        for eid, tech in report.unknown_techniques:
            print(f"  ! {eid} / {tech}")
    if report.kinds_without_checklist:
        print(f"\nWARNING kinds without checklist "
              f"({len(report.kinds_without_checklist)}) - 0 gaps != tested:")
        for eid, kind in report.kinds_without_checklist:
            print(f"  ! {eid} (kind {kind})")

    if lint.violations or inventory.absent:
        print(f"\nINVENTORY COMPLETENESS ({len(lint.violations)} violation(s)):")
        for v in lint.violations:
            print(f"  ✗ [{v.rule}] {v.message}")
        for kind, reason in inventory.absent.items():
            print(f"  – absent.{kind}: {reason}")

    print("\n" + matrix)
    if args.matrix_out:
        out = Path(args.matrix_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(matrix + "\n", encoding="utf-8")
        print(f"\nMatrix -> {args.matrix_out}")

    raise SystemExit(1 if (report.gaps or lint.violations) else 0)


if __name__ == "__main__":
    main()
