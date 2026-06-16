"""Backward-compatible shim. Real logic lives in tcformat.report_cli.

Kept so existing `python scripts/gen_report.py ...` invocations and imports
still work; new callers use the `tk-report` console script.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tcformat.report_cli import build_report_from_yaml, main  # noqa: E402,F401

if __name__ == "__main__":
    main()
