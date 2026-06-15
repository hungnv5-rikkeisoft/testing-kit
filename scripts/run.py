"""CLI to run a test layer and emit reports.

Examples:
    python scripts/run.py --layer integration
    python scripts/run.py --layer api --tablet
    python scripts/run.py --layer system --dry-run
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

LAYER_PATHS = {
    "api": "tests/api",
    "integration": "tests/integration",
    "system": "tests/system",
    "unit": "tests/unit",
}


def build_args(layer: str, tablet: bool, reports_dir: str) -> list[str]:
    Path(reports_dir).mkdir(parents=True, exist_ok=True)
    # Compose layer + tablet into ONE marker expression so both filters apply
    # (two separate -m flags would silently drop all but the last).
    terms = []
    if layer != "unit":
        terms.append(layer)
    if not tablet:
        # default desktop-only run excludes the iPad/Safari subset (marker: tablet)
        terms.append("not tablet")
    args = ["-m", "pytest", LAYER_PATHS[layer], "-v"]
    if terms:
        args += ["-m", " and ".join(terms)]
    args += ["--html", f"{reports_dir}/{layer}.html", "--self-contained-html",
             "--junitxml", f"{reports_dir}/{layer}-junit.xml",
             "--summary-out", f"{reports_dir}/{layer}-summary.json"]
    return args


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--layer", required=True, choices=list(LAYER_PATHS))
    ap.add_argument("--tablet", action="store_true",
                    help="Include the iPad/Safari selective subset")
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pytest_args = build_args(args.layer, args.tablet, args.reports)
    if args.dry_run:
        print(" ".join([sys.executable] + pytest_args))
        return 0
    return subprocess.call([sys.executable] + pytest_args)


if __name__ == "__main__":
    raise SystemExit(main())
