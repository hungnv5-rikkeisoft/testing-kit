from pathlib import Path
import pytest
from toolkit.checks.ui_checks import (
    assert_components_present, assert_console_clean, assert_responsive)
from toolkit.checks.security_checks import assert_no_xss

SAMPLE = Path("tests/fixtures/sample.html").resolve().as_uri()


@pytest.mark.integration
def test_ui_components_and_safety(page):
    capture = assert_console_clean(page)       # 2.3.3: no JS errors
    page.goto(SAMPLE)
    page.wait_for_load_state("networkidle")
    assert_components_present(page, ["#site-header", "#btn-primary", "#search"])
    assert_responsive(page, [{"width": 1920, "height": 1080},
                             {"width": 1536, "height": 2048}])
    assert_no_xss(page, "#search", echo_selector="#echo")  # 2.3.3: XSS
    capture.verify()
