from pathlib import Path
from playwright.sync_api import sync_playwright
from toolkit.browser import launch_page, DeviceProfile
from toolkit.checks.security_checks import assert_no_xss, XSS_PAYLOADS

SAMPLE = Path("tests/fixtures/sample.html").resolve().as_uri()
DESKTOP = DeviceProfile(name="d", engine="chromium",
                        viewport={"width": 1920, "height": 1080})


def test_xss_payloads_nonempty():
    assert any("<script>" in p for p in XSS_PAYLOADS)


def test_no_xss_on_safe_echo():
    # sample.html echoes input via textContent => payload must NOT execute.
    with sync_playwright() as p:
        page, browser = launch_page(p, DESKTOP)
        page.goto(SAMPLE)
        page.wait_for_load_state("networkidle")
        assert_no_xss(page, "#search", echo_selector="#echo")
        browser.close()
