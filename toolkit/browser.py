from __future__ import annotations
from dataclasses import dataclass


@dataclass
class DeviceProfile:
    name: str
    engine: str            # "chromium" or "webkit"
    viewport: dict
    marker: str | None = None
    primary: bool = False


def launch_page(playwright, profile: DeviceProfile, headless: bool = True):
    """Launch a browser for the given device profile and return (page, browser)."""
    engine = getattr(playwright, profile.engine)
    browser = engine.launch(headless=headless)
    context = browser.new_context(viewport=profile.viewport)
    page = context.new_page()
    return page, browser


def goto_and_wait(page, url: str):
    """Navigate then wait for JS to settle (strategy: inspect only after networkidle)."""
    page.goto(url)
    page.wait_for_load_state("networkidle")
    return page


def profiles_from_config(devices_cfg: dict) -> list[DeviceProfile]:
    """Build DeviceProfile list from devices.yaml structure."""
    out = []
    for d in devices_cfg.get("devices", []):
        out.append(DeviceProfile(
            name=d["name"], engine=d["engine"], viewport=d["viewport"],
            marker=d.get("marker"), primary=d.get("primary", False),
        ))
    return out
