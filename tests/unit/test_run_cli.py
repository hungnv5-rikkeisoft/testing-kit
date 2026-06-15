import subprocess
import sys


def test_run_builds_pytest_args_dry_run():
    # --dry-run prints the pytest argv it WOULD execute, then exits 0.
    out = subprocess.run(
        [sys.executable, "scripts/run.py", "--layer", "integration", "--dry-run"],
        capture_output=True, text=True)
    assert out.returncode == 0
    assert "-m" in out.stdout and "integration" in out.stdout
    assert "--html" in out.stdout
