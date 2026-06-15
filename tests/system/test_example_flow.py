from pathlib import Path
import pytest
from toolkit.checks.ui_checks import assert_components_present

SAMPLE = Path("tests/fixtures/sample.html").resolve().as_uri()


@pytest.mark.system
def test_user_flow_navigates_and_renders(page):
    # Multi-step user flow (strategy sheet 3): land -> interact -> verify state.
    page.goto(SAMPLE)
    page.wait_for_load_state("networkidle")
    assert_components_present(page, ["#link-home"])
    page.click("#btn-primary")
    page.fill("#search", "hello")
    page.dispatch_event("#search", "input")
    assert page.inner_text("#echo") == "hello"
