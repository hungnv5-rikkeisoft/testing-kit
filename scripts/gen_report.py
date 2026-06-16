"""Build the team's Test Report workbook from test-case YAML (Stage 3).

Aggregates the `result` fields that Stage 2 wrote into `testcases/<screen>.yaml`
and renders ONE workbook from the company template
"Format test case + Test report.xlsx" (testcase sheets + "3. Test Report" +
"Evidence"), all in sync from the same YAML.

Usage:
    python scripts/gen_report.py --yaml testcases/basic-information-input.yaml \
        --out reports/test_report.xlsx
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_TEMPLATE = "template/Format test case + Test report.xlsx"


def build_report_from_yaml(yaml_paths, template_path, out_path, base_dir=".",
                           project_name="Project Name"):
    """Stage 3 path: aggregate testcase YAML(s) and write the report workbook.

    Returns the ReportData (caller uses .exit_ok for the process exit code)."""
    from tcformat.schema import load_screen
    from tcformat.report_data import aggregate
    from tcformat.report_xlsx import write_report
    screens = [load_screen(p) for p in yaml_paths]
    data = aggregate(screens)
    write_report(data, screens, template_path, out_path, base_dir=base_dir,
                 project_name=project_name)
    return data


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yaml", action="append", default=None, required=True,
                    help="Stage 3: testcase YAML with results (repeatable)")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--out", default="reports/test_report.xlsx")
    ap.add_argument("--project-name", dest="project_name", default="Project Name",
                    help="project-name banner on the Record-of-Change sheet")
    args = ap.parse_args()

    data = build_report_from_yaml(args.yaml, args.template, args.out,
                                  project_name=args.project_name)
    s = data.summary
    print(f"Wrote report -> {args.out} (executed {data.executed}/{data.planned}, "
          f"OK {s.passed} NG {s.failed}, pass {s.pass_rate:.0%}, "
          f"exit {'PASS' if data.exit_ok else 'FAIL'})")
    raise SystemExit(0 if data.exit_ok else 1)


if __name__ == "__main__":
    main()
