"""Verify the report-summary hook writes summary.json after a run.

The temp test dir is rooted INSIDE the repo on purpose: pytest discovers the
root conftest.py by walking up from the test file to the rootdir, and on Windows
a temp dir on C: cannot reach a project on D:.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def test_summary_json_written():
    repo = Path.cwd()
    with tempfile.TemporaryDirectory(dir=str(repo)) as td:
        td = Path(td)
        test_file = td / "test_sample.py"
        test_file.write_text(
            "def test_pass():\n    assert True\n", encoding="utf-8")
        out = td / "reports"
        subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file),
             "-p", "no:cacheprovider", "--summary-out", str(out / "summary.json")],
            cwd=str(repo), check=False)
        data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        assert data["summary"]["total"] == 1
        assert data["summary"]["passed"] == 1
        assert data["exit_criteria_passed"] is True
