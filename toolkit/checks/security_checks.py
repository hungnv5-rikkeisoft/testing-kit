from __future__ import annotations


class SecurityCheckError(AssertionError):
    pass


# Strategy 2.3.3 #4 sample payloads.
XSS_PAYLOADS = [
    "<script>window.__xss=true;alert('Hello')</script>",
    "<html>abc</html>",
    "<img src=x onerror=window.__xss=true>",
]


def assert_no_xss(page, input_selector: str, echo_selector: str | None = None):
    """Type each XSS payload; confirm no script executes and value renders as text."""
    for payload in XSS_PAYLOADS:
        page.evaluate("() => { window.__xss = false; }")
        page.fill(input_selector, "")
        page.fill(input_selector, payload)
        page.dispatch_event(input_selector, "input")
        executed = page.evaluate("() => window.__xss === true")
        if executed:
            raise SecurityCheckError(f"XSS executed for payload: {payload}")
        if echo_selector is not None:
            # Payload must appear as literal text, not parsed HTML.
            text = page.inner_text(echo_selector)
            if payload not in text and text != "":
                raise SecurityCheckError(
                    f"Payload not rendered as text in {echo_selector}: {text!r}")


def assert_permission_denied(page, url: str, expected_markers: list[str]):
    """Strategy 2.3.3 #7/#8: an unauthorized user opening a protected URL must
    see an access-denied / not-found signal (one of expected_markers)."""
    page.goto(url)
    page.wait_for_load_state("networkidle")
    body = page.inner_text("body").lower()
    if not any(m.lower() in body for m in expected_markers):
        raise SecurityCheckError(
            f"No permission-denied marker {expected_markers} found at {url}")
