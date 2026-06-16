"""Stage 3 - build the team's Test Report workbook from test-case YAML.

Aggregates the `result` fields Stage 2 wrote into testcases/<screen>.yaml and
renders ONE workbook from the team template (testcase sheets + "3. Test Report"
+ "Evidence"). Installed as the `tk-report` console script.
"""
from __future__ import annotations
import argparse

from tcformat.resources import template_path


def build_report_from_yaml(yaml_paths, template, out_path, base_dir=".",
                           project_name="Project Name"):
    """Aggregate testcase YAML(s) and write the report workbook.

    Returns the ReportData (caller uses .exit_ok for the process exit code)."""
    from tcformat.schema import load_screen
    from tcformat.report_data import aggregate
    from tcformat.report_xlsx import write_report
    screens = [load_screen(p) for p in yaml_paths]
    data = aggregate(screens)
    write_report(data, screens, template, out_path, base_dir=base_dir,
                 project_name=project_name)
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yaml", action="append", required=True,
                    help="testcase YAML with results (repeatable)")
    ap.add_argument("--template", default=None,
                    help="override template xlsx (default: bundled / config)")
    ap.add_argument("--config", default=None,
                    help="config.yaml to read template_path override from")
    ap.add_argument("--out", default="reports/test_report.xlsx")
    ap.add_argument("--project-name", dest="project_name", default="Project Name")
    args = ap.parse_args(argv)

    tmpl = template_path(args.template, args.config)
    data = build_report_from_yaml(args.yaml, tmpl, args.out,
                                  project_name=args.project_name)
    s = data.summary
    print(f"Wrote report -> {args.out} (executed {data.executed}/{data.planned}, "
          f"OK {s.passed} NG {s.failed}, pass {s.pass_rate:.0%}, "
          f"exit {'PASS' if data.exit_ok else 'FAIL'})")
    raise SystemExit(0 if data.exit_ok else 1)


if __name__ == "__main__":
    main()
