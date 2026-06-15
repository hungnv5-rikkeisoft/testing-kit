from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
from toolkit.browser import launch_page, DeviceProfile
from toolkit.checks.ui_checks import (
    assert_components_present, assert_console_clean, measure_load_time,
    UiCheckError,
)

SAMPLE = Path("tests/fixtures/sample.html").resolve().as_uri()
DESKTOP = DeviceProfile(name="d", engine="chromium",
                        viewport={"width": 1920, "height": 1080})


def _page(p):
    page, browser = launch_page(p, DESKTOP)
    page.goto(SAMPLE)
    page.wait_for_load_state("networkidle")
    return page, browser


def test_components_present_passes():
    with sync_playwright() as p:
        page, browser = _page(p)
        assert_components_present(page, ["#site-header", "#btn-primary", "#search"])
        browser.close()


def test_components_present_missing_raises():
    with sync_playwright() as p:
        page, browser = _page(p)
        with pytest.raises(UiCheckError):
            assert_components_present(page, ["#does-not-exist"])
        browser.close()


def test_console_clean_passes():
    with sync_playwright() as p:
        page, browser = launch_page(p, DESKTOP)
        errors = assert_console_clean(page)  # start capture before navigation
        page.goto(SAMPLE)
        page.wait_for_load_state("networkidle")
        errors.verify()
        browser.close()


def test_measure_load_time_returns_ms():
    with sync_playwright() as p:
        page, browser = _page(p)
        ms = measure_load_time(page)
        assert ms >= 0
        browser.close()
