"""Shared fixtures + report aggregation enforcing strategy exit criteria."""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright

from toolkit.config import load_config, ExitCriteria
from toolkit.report import Summary, write_summary_json

_DEFAULT_CONFIG = "config/config.yaml"


def pytest_addoption(parser):
    parser.addoption("--summary-out", default="reports/summary.json",
                     help="Path to write the JSON run summary")
    parser.addoption("--tk-config", default=_DEFAULT_CONFIG,
                     help="Path to the toolkit YAML config")


@pytest.fixture(scope="session")
def config(request):
    path = request.config.getoption("--tk-config")
    if not Path(path).exists():
        pytest.skip(f"Toolkit config not found at {path}; copy config.example.yaml")
    return load_config(path)


@pytest.fixture()
def page():
    """Default desktop chromium page (1920x1080) navigated lazily by the test.
    Intentionally independent of `config` so sample/example tests run without a
    project config.yaml; tests needing base_url should also request `config`."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
        pg = ctx.new_page()
        yield pg
        browser.close()


# --- report aggregation -------------------------------------------------
class _TkCountsPlugin:
    """Registered plugin that accumulates pass/fail counts per session."""

    def __init__(self):
        self.counts = {"passed": 0, "failed": 0, "total": 0}

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            self.counts["total"] += 1
            if report.passed:
                self.counts["passed"] += 1
            elif report.failed:
                self.counts["failed"] += 1


def pytest_configure(config):
    plugin = _TkCountsPlugin()
    config._tk_counts_plugin = plugin
    config.pluginmanager.register(plugin, "_tk_counts_plugin")


def pytest_sessionfinish(session, exitstatus):
    counts = session.config._tk_counts_plugin.counts
    if counts["total"] == 0:
        return
    summary = Summary(total=counts["total"], passed=counts["passed"],
                      failed=counts["failed"], bugs_by_severity={})
    criteria = ExitCriteria()
    out = session.config.getoption("--summary-out")
    payload = write_summary_json(summary, criteria, out)
    if not payload["exit_criteria_passed"]:
        print("\n[exit-criteria] FAILED:", "; ".join(payload["reasons"]))
        # Fail the run so CI blocks on unmet exit criteria, even when every
        # individual test passed but a blocking-severity bug was recorded.
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
