"""Generate tester checklists from the strategy workbook.

Reads the testing objects of a strategy sheet (via tcformat.strategy) and emits
a Markdown checklist.

Usage:
    python scripts/gen_checklist.py --sheet 1_APITesting --title "API Testing"
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tcformat.strategy import list_objects


def extract_objects(xlsx_path, sheet_name: str) -> list[dict]:
    """Back-compat shim: {object, how} pairs for a sheet."""
    return [{"object": o["object"], "how": o["how"]}
            for o in list_objects(xlsx_path, sheet_name)]


def render_markdown(title: str, objects: list[dict]) -> str:
    lines = [f"# Checklist — {title}", ""]
    for o in objects:
        lines.append(f"- [ ] **{o['object']}**")
        if o["how"]:
            lines.append(f"  - {o['how'].replace(chr(10), ' ')}")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xlsx", default="strategy/strategy.xlsx")
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--out", default="checklists/")
    args = ap.parse_args()

    objects = extract_objects(args.xlsx, args.sheet)
    md = render_markdown(args.title, objects)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.sheet}.md"
    out_file.write_text(md, encoding="utf-8")
    print(f"Wrote {len(objects)} objects -> {out_file}")


if __name__ == "__main__":
    main()
