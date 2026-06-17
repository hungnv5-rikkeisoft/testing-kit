"""Stage 1 critic — semi-automated review checklist by category.

Reuses the depth analysis, regroups findings into review categories, flags
categories outside the mechanical matrix (UI/BusinessRule) for AI/human review,
and gates only on depends_on edges with no linking case. Advisory otherwise.
Installed as the `tk-critic` console script.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path


def _default_inventory(screen_path) -> str:
    return str(Path(screen_path).with_suffix(".inventory.yaml"))


def main(argv=None):
    # Console may use a non-UTF-8 code page (cp932 on Windows); the report uses
    # Unicode markers (✓/✗/⚠). Force UTF-8 so printing never crashes — including
    # during --help output which argparse emits inside parse_args().
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
    ap.add_argument("--out", default=None,
                    help="also write the markdown critic report to this file")
    args = ap.parse_args(argv)

    from tcformat.coverage_cli import run_depth_check
    from tcformat.critic import run_critic, render_critic_md

    inv_path = args.inventory or _default_inventory(args.screen)
    screen, inventory, checklists, depth = run_depth_check(
        args.screen, inv_path, config=args.config)
    report = run_critic(inventory, checklists, screen, depth)
    md = render_critic_md(report, screen.screen)

    print(md)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md + "\n", encoding="utf-8")
        print(f"\nCritic -> {args.out}")

    raise SystemExit(1 if report.gate_failures else 0)


if __name__ == "__main__":
    main()
