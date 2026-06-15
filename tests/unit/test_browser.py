from pathlib import Path
from playwright.sync_api import sync_playwright
from toolkit.browser import launch_page, DeviceProfile

SAMPLE = Path("tests/fixtures/sample.html").resolve().as_uri()


def test_launch_page_navigates_chromium():
    profile = DeviceProfile(name="desktop", engine="chromium",
                            viewport={"width": 1920, "height": 1080})
    with sync_playwright() as p:
        page, browser = launch_page(p, profile)
        page.goto(SAMPLE)
        page.wait_for_load_state("networkidle")
        assert page.title() == "Testing-Kit Sample"
        assert page.viewport_size["width"] == 1920
        browser.close()


def test_launch_page_webkit_viewport():
    profile = DeviceProfile(name="ipad", engine="webkit",
                            viewport={"width": 1536, "height": 2048})
    with sync_playwright() as p:
        page, browser = launch_page(p, profile)
        assert page.viewport_size["height"] == 2048
        browser.close()
