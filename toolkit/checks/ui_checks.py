from __future__ import annotations


class UiCheckError(AssertionError):
    pass


def assert_components_present(page, selectors: list[str]):
    """Strategy 2.3.1: confirm all required components are present & visible."""
    missing = [s for s in selectors if page.query_selector(s) is None]
    if missing:
        raise UiCheckError(f"Missing components: {missing}")


class ConsoleErrorCapture:
    def __init__(self):
        self.errors: list[str] = []

    def verify(self):
        """Strategy 2.3.3: no JS errors in console log."""
        if self.errors:
            raise UiCheckError(f"Console errors detected: {self.errors}")


def assert_console_clean(page) -> ConsoleErrorCapture:
    """Attach a console listener. Call .verify() after interactions."""
    cap = ConsoleErrorCapture()
    page.on("console", lambda msg: cap.errors.append(msg.text)
            if msg.type == "error" else None)
    page.on("pageerror", lambda exc: cap.errors.append(str(exc)))
    return cap


def measure_load_time(page) -> float:
    """Return full page load time in ms via the Navigation Timing API."""
    return page.evaluate(
        "() => { const t = performance.getEntriesByType('navigation')[0];"
        " return t ? t.duration : performance.now(); }")


def assert_responsive(page, sizes: list[dict]):
    """Strategy 2.3.1: layout must not break across screen sizes.
    Checks the document has no horizontal overflow at each size."""
    for size in sizes:
        page.set_viewport_size(size)
        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth >"
            " document.documentElement.clientWidth")
        if overflow:
            raise UiCheckError(f"Horizontal overflow at {size}")
