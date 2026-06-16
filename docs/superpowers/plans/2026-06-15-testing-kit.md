# Testing-Kit Implementation Plan

> ⚠️ **LỖI THỜI (point-in-time).** Plan này dựng lớp `pytest` theo layer (`toolkit/`
> browser/checks/api_client, `conftest.py`, `scripts/run.py`, `tests/{api,integration,system}`)
> — lớp đó **đã bị gỡ khỏi codebase**. Kiến trúc hiện hành là pipeline 3-stage skill-driven
> (Stage 2 chạy qua Playwright MCP). Giữ lại làm hồ sơ; xem `CLAUDE.md`/`HANDOFF.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable, config-driven Python + Playwright toolkit that automates the project's testing strategy (API, Integration/UI, System) and produces QA reports with an exit-criteria gate, plus auto-generated test checklists.

**Architecture:** A reusable helper library (`toolkit/`) consumed by `pytest` test suites. YAML config makes it project-agnostic. Helpers encode the strategy's concrete rules (status-code checks, perf thresholds, XSS payloads, permission checks). A `conftest.py` hook aggregates results into HTML/JUnit/JSON and enforces exit criteria. A standalone script generates checklists from `strategy/strategy.xlsx`.

**Tech Stack:** Python 3.11+, pytest, pytest-html, playwright (chromium + webkit), requests, pyyaml, openpyxl, pytest-httpserver.

> **Git note:** `d:\Testing-kit` is NOT a git repo yet. Before the first commit, initialize one (`git init`). **Per project policy, every `git add`/`git commit` step in this plan REQUIRES explicit user confirmation before running.** If the user prefers no git, skip all commit steps.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `requirements.txt` | Pin dependencies |
| `pytest.ini` | pytest config: markers, paths, html/junit output |
| `README.md` | How to configure for a new project + run each layer |
| `config/config.example.yaml` | Base config template (URL, thresholds, exit criteria) |
| `config/devices.yaml` | Device matrix (sheet 4) |
| `config/users.example.yaml` | Role accounts for permission tests |
| `toolkit/config.py` | Load + validate YAML, apply strategy defaults |
| `toolkit/browser.py` | Playwright launch + device profiles + nav helper |
| `toolkit/api_client.py` | API calls + status/schema/timing assertions |
| `toolkit/checks/ui_checks.py` | UI/Integration helpers |
| `toolkit/checks/security_checks.py` | XSS payloads + permission checks |
| `toolkit/checks/perf_checks.py` | Perf threshold helpers |
| `toolkit/report.py` | Result model + summary/exit-criteria computation |
| `conftest.py` | Shared fixtures + report aggregation hook |
| `scripts/gen_checklist.py` | strategy.xlsx → checklist markdown |
| `scripts/run.py` | CLI to run a layer/env and emit reports |
| `scripts/with_server.py` | Copied from webapp-testing plugin |
| `tests/fixtures/sample.html` | Static page to prove helpers without a real app |
| `tests/unit/` | Unit tests for toolkit helpers |
| `tests/{api,integration,system}/` | Example layer tests |

---

## Task 1: Project scaffold

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `toolkit/__init__.py`
- Create: `toolkit/checks/__init__.py`
- Create: `.gitignore`

- [ ] **Step 1: Create `requirements.txt`**

```
pytest==8.3.4
pytest-html==4.1.1
pytest-httpserver==1.1.0
playwright==1.49.1
requests==2.32.3
pyyaml==6.0.2
openpyxl==3.1.5
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    tablet: subset (~25%) run on iPad gen5 / Safari per strategy sheet 4
    api: API-layer tests
    integration: Integration/UI-layer tests
    system: System (user-flow) tests
addopts = -ra
```

- [ ] **Step 3: Create package markers**

`toolkit/__init__.py`:
```python
"""Reusable testing toolkit (Python + Playwright) driven by the project test strategy."""
```

`toolkit/checks/__init__.py`:
```python
"""Strategy-derived check helpers: UI, security, performance."""
```

- [ ] **Step 4: Create `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
reports/
checklists/
config/config.yaml
config/users.yaml
.venv/
```

- [ ] **Step 5: Install and verify**

Run: `pip install -r requirements.txt && python -m playwright install chromium webkit`
Expected: installs succeed; `pytest --version` prints a version.

- [ ] **Step 6: Commit** *(requires user confirmation; run `git init` first if needed)*

```bash
git add requirements.txt pytest.ini toolkit/__init__.py toolkit/checks/__init__.py .gitignore
git commit -m "chore: scaffold testing-kit project"
```

---

## Task 2: Config loader

**Files:**
- Create: `toolkit/config.py`
- Create: `config/config.example.yaml`
- Create: `config/devices.yaml`
- Create: `config/users.example.yaml`
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_config.py`:
```python
from pathlib import Path
import textwrap
import pytest
from toolkit.config import load_config, ConfigError


def write(tmp_path, text):
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return p


def test_defaults_applied_from_strategy(tmp_path):
    cfg = load_config(write(tmp_path, """
        base_url: http://localhost:5173
    """))
    assert cfg.base_url == "http://localhost:5173"
    assert cfg.thresholds.api_ms == 600
    assert cfg.thresholds.web_response_ms == 1500
    assert cfg.thresholds.page_load_ms == 2500
    assert cfg.exit_criteria.min_pass_rate == 0.95
    assert cfg.exit_criteria.block_severities == ["Critical", "High"]


def test_overrides_win(tmp_path):
    cfg = load_config(write(tmp_path, """
        base_url: http://x
        thresholds:
          api_ms: 800
    """))
    assert cfg.thresholds.api_ms == 800
    assert cfg.thresholds.page_load_ms == 2500  # untouched default


def test_missing_base_url_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, "thresholds: {api_ms: 600}\n"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'toolkit.config'`

- [ ] **Step 3: Write minimal implementation**

`toolkit/config.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml


class ConfigError(Exception):
    pass


@dataclass
class Thresholds:
    api_ms: int = 600           # strategy sheet 1: API < 600ms
    web_response_ms: int = 1500  # sheet 2: web server response < 1.5s
    page_load_ms: int = 2500     # sheet 2: full page load < 2.5s


@dataclass
class ExitCriteria:
    min_pass_rate: float = 0.95  # sheet 6: >= 95% pass
    block_severities: list = field(default_factory=lambda: ["Critical", "High"])


@dataclass
class Config:
    base_url: str
    thresholds: Thresholds
    exit_criteria: ExitCriteria
    raw: dict


def load_config(path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base_url = data.get("base_url")
    if not base_url:
        raise ConfigError("'base_url' is required in config")

    t = data.get("thresholds", {}) or {}
    thresholds = Thresholds(
        api_ms=t.get("api_ms", 600),
        web_response_ms=t.get("web_response_ms", 1500),
        page_load_ms=t.get("page_load_ms", 2500),
    )
    e = data.get("exit_criteria", {}) or {}
    exit_criteria = ExitCriteria(
        min_pass_rate=e.get("min_pass_rate", 0.95),
        block_severities=e.get("block_severities", ["Critical", "High"]),
    )
    return Config(base_url=base_url, thresholds=thresholds,
                  exit_criteria=exit_criteria, raw=data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Create the example YAML files**

`config/config.example.yaml`:
```yaml
# Copy to config/config.yaml and edit per project.
base_url: http://localhost:5173
thresholds:
  api_ms: 600          # API response budget (strategy: < 600ms)
  web_response_ms: 1500 # web server response budget (< 1.5s)
  page_load_ms: 2500    # full page load budget (< 2.5s)
exit_criteria:
  min_pass_rate: 0.95
  block_severities: [Critical, High]
```

`config/devices.yaml`:
```yaml
# Device matrix from strategy sheet 4 "Môi trường & Thiết bị".
devices:
  - name: desktop_1920_chrome   # primary: full GUI + Function
    engine: chromium
    viewport: { width: 1920, height: 1080 }
    primary: true
  - name: ipad_gen5_safari      # secondary: ~25% selective
    engine: webkit
    viewport: { width: 1536, height: 2048 }
    primary: false
    marker: tablet
```

`config/users.example.yaml`:
```yaml
# Copy to config/users.yaml. Accounts used for permission tests (strategy sheet 2.3.3 / 3.3.2).
users:
  admin:   { username: admin@example.com, password: CHANGE_ME, role: admin }
  user_a:  { username: a@example.com,     password: CHANGE_ME, role: user }
  user_b:  { username: b@example.com,     password: CHANGE_ME, role: user }
```

- [ ] **Step 6: Commit** *(requires user confirmation)*

```bash
git add toolkit/config.py config/ tests/unit/test_config.py
git commit -m "feat: config loader with strategy defaults"
```

---

## Task 3: Static sample page (test target)

**Files:**
- Create: `tests/fixtures/sample.html`

- [ ] **Step 1: Create the sample page**

`tests/fixtures/sample.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Testing-Kit Sample</title>
  <style>
    .card { border: 1px solid #ccc; padding: 8px; }
    #wide-only { display: none; }
    @media (min-width: 1000px) { #wide-only { display: block; } }
  </style>
</head>
<body>
  <header id="site-header"><h1>Sample App</h1></header>
  <nav><a id="link-home" href="#home">Home</a></nav>
  <main>
    <button id="btn-primary" class="card">Primary</button>
    <button id="btn-secondary" class="card">Secondary</button>
    <input id="search" type="text" aria-label="search" />
    <div id="echo"></div>
    <div id="wide-only">wide</div>
  </main>
  <script>
    // Echo input safely as text (so XSS payloads do NOT execute).
    const input = document.getElementById('search');
    const echo = document.getElementById('echo');
    input.addEventListener('input', () => { echo.textContent = input.value; });
  </script>
</body>
</html>
```

- [ ] **Step 2: Verify it opens**

Run: `python -c "import pathlib; print(pathlib.Path('tests/fixtures/sample.html').exists())"`
Expected: `True`

- [ ] **Step 3: Commit** *(requires user confirmation)*

```bash
git add tests/fixtures/sample.html
git commit -m "test: add static sample page for helper tests"
```

---

## Task 4: Browser helper + device fixtures

**Files:**
- Create: `toolkit/browser.py`
- Test: `tests/unit/test_browser.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_browser.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_browser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'toolkit.browser'`

- [ ] **Step 3: Write minimal implementation**

`toolkit/browser.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_browser.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit** *(requires user confirmation)*

```bash
git add toolkit/browser.py tests/unit/test_browser.py
git commit -m "feat: playwright browser helper + device profiles"
```

---

## Task 5: API client with status/schema/timing assertions

**Files:**
- Create: `toolkit/api_client.py`
- Test: `tests/unit/test_api_client.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_api_client.py`:
```python
import pytest
from toolkit.api_client import ApiClient, ApiAssertionError


def test_status_and_schema_and_timing(httpserver):
    httpserver.expect_request("/ok").respond_with_json(
        {"id": 1, "name": "x"}, status=200)
    client = ApiClient(base_url=httpserver.url_for(""))
    resp = client.get("/ok")
    resp.assert_status(200).assert_schema({"id": int, "name": str}).assert_under_ms(5000)


def test_wrong_status_raises(httpserver):
    httpserver.expect_request("/bad").respond_with_json({}, status=400)
    client = ApiClient(base_url=httpserver.url_for(""))
    with pytest.raises(ApiAssertionError):
        client.get("/bad").assert_status(200)


def test_business_error_header(httpserver):
    # strategy 1.3.3: business error => HTTP 200 + a business code header
    httpserver.expect_request("/biz").respond_with_json(
        {}, status=200, headers={"x-business-code": "42"})
    client = ApiClient(base_url=httpserver.url_for(""))
    client.get("/biz").assert_status(200).assert_business_code("42")


def test_schema_mismatch_raises(httpserver):
    httpserver.expect_request("/s").respond_with_json({"id": "not-int"}, status=200)
    client = ApiClient(base_url=httpserver.url_for(""))
    with pytest.raises(ApiAssertionError):
        client.get("/s").assert_schema({"id": int})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_api_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'toolkit.api_client'`

- [ ] **Step 3: Write minimal implementation**

`toolkit/api_client.py`:
```python
from __future__ import annotations
import requests


class ApiAssertionError(AssertionError):
    pass


class ApiResponse:
    def __init__(self, resp: requests.Response, elapsed_ms: float):
        self.resp = resp
        self.elapsed_ms = elapsed_ms

    def assert_status(self, expected: int) -> "ApiResponse":
        if self.resp.status_code != expected:
            raise ApiAssertionError(
                f"Expected status {expected}, got {self.resp.status_code}")
        return self

    def assert_under_ms(self, budget_ms: int) -> "ApiResponse":
        if self.elapsed_ms > budget_ms:
            raise ApiAssertionError(
                f"Response took {self.elapsed_ms:.0f}ms > budget {budget_ms}ms")
        return self

    def assert_business_code(self, code: str) -> "ApiResponse":
        actual = self.resp.headers.get("x-business-code")
        if actual != code:
            raise ApiAssertionError(
                f"Expected business code header {code}, got {actual}")
        return self

    def assert_schema(self, schema: dict) -> "ApiResponse":
        body = self.resp.json()
        for key, typ in schema.items():
            if key not in body:
                raise ApiAssertionError(f"Missing required field '{key}'")
            if not isinstance(body[key], typ):
                raise ApiAssertionError(
                    f"Field '{key}' expected {typ.__name__}, "
                    f"got {type(body[key]).__name__}")
        return self


class ApiClient:
    def __init__(self, base_url: str, default_headers: dict | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if default_headers:
            self.session.headers.update(default_headers)

    def request(self, method: str, path: str, **kwargs) -> ApiResponse:
        url = self.base_url + path
        resp = self.session.request(method, url, **kwargs)
        return ApiResponse(resp, resp.elapsed.total_seconds() * 1000)

    def get(self, path: str, **kwargs) -> ApiResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> ApiResponse:
        return self.request("POST", path, **kwargs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_api_client.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit** *(requires user confirmation)*

```bash
git add toolkit/api_client.py tests/unit/test_api_client.py
git commit -m "feat: api client with status/schema/timing/business-code asserts"
```

---

## Task 6: UI checks

**Files:**
- Create: `toolkit/checks/ui_checks.py`
- Test: `tests/unit/test_ui_checks.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_ui_checks.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_ui_checks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'toolkit.checks.ui_checks'`

- [ ] **Step 3: Write minimal implementation**

`toolkit/checks/ui_checks.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_ui_checks.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit** *(requires user confirmation)*

```bash
git add toolkit/checks/ui_checks.py tests/unit/test_ui_checks.py
git commit -m "feat: ui checks (components, console, load time, responsive)"
```

---

## Task 7: Security checks (XSS + permission)

**Files:**
- Create: `toolkit/checks/security_checks.py`
- Test: `tests/unit/test_security_checks.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_security_checks.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_security_checks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'toolkit.checks.security_checks'`

- [ ] **Step 3: Write minimal implementation**

`toolkit/checks/security_checks.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_security_checks.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit** *(requires user confirmation)*

```bash
git add toolkit/checks/security_checks.py tests/unit/test_security_checks.py
git commit -m "feat: security checks (xss payloads + permission denied)"
```

---

## Task 8: Performance checks

**Files:**
- Create: `toolkit/checks/perf_checks.py`
- Test: `tests/unit/test_perf_checks.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_perf_checks.py`:
```python
import pytest
from toolkit.checks.perf_checks import assert_under, PerfCheckError


def test_under_budget_passes():
    assert_under(measured_ms=500, budget_ms=600, label="api")


def test_over_budget_raises():
    with pytest.raises(PerfCheckError):
        assert_under(measured_ms=700, budget_ms=600, label="api")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_perf_checks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'toolkit.checks.perf_checks'`

- [ ] **Step 3: Write minimal implementation**

`toolkit/checks/perf_checks.py`:
```python
from __future__ import annotations


class PerfCheckError(AssertionError):
    pass


def assert_under(measured_ms: float, budget_ms: float, label: str = ""):
    """Generic threshold gate used by web & API perf checks."""
    if measured_ms > budget_ms:
        raise PerfCheckError(
            f"{label or 'duration'} {measured_ms:.0f}ms exceeds budget {budget_ms}ms")
    return measured_ms
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_perf_checks.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit** *(requires user confirmation)*

```bash
git add toolkit/checks/perf_checks.py tests/unit/test_perf_checks.py
git commit -m "feat: perf threshold check"
```

---

## Task 9: Report model + exit-criteria computation

**Files:**
- Create: `toolkit/report.py`
- Test: `tests/unit/test_report.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_report.py`:
```python
from toolkit.report import Summary, evaluate_exit_criteria
from toolkit.config import ExitCriteria


def test_summary_pass_rate():
    s = Summary(total=10, passed=9, failed=1, bugs_by_severity={"High": 1})
    assert s.pass_rate == 0.9


def test_exit_criteria_blocks_on_low_pass_rate():
    s = Summary(total=100, passed=90, failed=10, bugs_by_severity={})
    ok, reasons = evaluate_exit_criteria(s, ExitCriteria())
    assert ok is False
    assert any("pass rate" in r.lower() for r in reasons)


def test_exit_criteria_blocks_on_blocking_bug():
    s = Summary(total=100, passed=100, failed=0,
                bugs_by_severity={"Critical": 1})
    ok, reasons = evaluate_exit_criteria(s, ExitCriteria())
    assert ok is False
    assert any("critical" in r.lower() for r in reasons)


def test_exit_criteria_pass():
    s = Summary(total=100, passed=96, failed=4, bugs_by_severity={"Low": 4})
    ok, reasons = evaluate_exit_criteria(s, ExitCriteria())
    assert ok is True
    assert reasons == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'toolkit.report'`

- [ ] **Step 3: Write minimal implementation**

`toolkit/report.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class Summary:
    total: int
    passed: int
    failed: int
    bugs_by_severity: dict = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def to_dict(self) -> dict:
        return {
            "total": self.total, "passed": self.passed, "failed": self.failed,
            "pass_rate": round(self.pass_rate, 4),
            "bugs_by_severity": self.bugs_by_severity,
        }


def evaluate_exit_criteria(summary: Summary, criteria) -> tuple[bool, list[str]]:
    """Return (ok, reasons). Strategy sheet 6 exit criteria."""
    reasons: list[str] = []
    if summary.pass_rate < criteria.min_pass_rate:
        reasons.append(
            f"Pass rate {summary.pass_rate:.0%} < required "
            f"{criteria.min_pass_rate:.0%}")
    for sev in criteria.block_severities:
        if summary.bugs_by_severity.get(sev, 0) > 0:
            reasons.append(
                f"{summary.bugs_by_severity[sev]} {sev}-severity bug(s) present")
    return (len(reasons) == 0, reasons)


def write_summary_json(summary: Summary, criteria, path) -> dict:
    ok, reasons = evaluate_exit_criteria(summary, criteria)
    payload = {"summary": summary.to_dict(),
               "exit_criteria_passed": ok, "reasons": reasons}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_report.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit** *(requires user confirmation)*

```bash
git add toolkit/report.py tests/unit/test_report.py
git commit -m "feat: report summary + exit-criteria evaluation"
```

---

## Task 10: conftest fixtures + report aggregation hook

**Files:**
- Create: `conftest.py`
- Test: `tests/unit/test_conftest_summary.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_conftest_summary.py`:
```python
"""Verify the report-summary hook writes reports/summary.json after a run."""
import json
import subprocess
import sys
from pathlib import Path


def test_summary_json_written(tmp_path):
    test_file = tmp_path / "test_sample.py"
    test_file.write_text(
        "def test_pass():\n    assert True\n", encoding="utf-8")
    out = tmp_path / "reports"
    subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file),
         "-p", "no:cacheprovider", "--summary-out", str(out / "summary.json")],
        cwd=Path.cwd(), check=False)
    data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert data["summary"]["total"] == 1
    assert data["summary"]["passed"] == 1
    assert data["exit_criteria_passed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_conftest_summary.py -v`
Expected: FAIL (no `--summary-out` option / no summary.json)

- [ ] **Step 3: Write minimal implementation**

`conftest.py`:
```python
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
def pytest_configure(config):
    config._tk_counts = {"passed": 0, "failed": 0, "total": 0}


def pytest_runtest_logreport(report):
    if report.when == "call":
        counts = report.session.config._tk_counts
        counts["total"] += 1
        if report.passed:
            counts["passed"] += 1
        elif report.failed:
            counts["failed"] += 1


def pytest_sessionfinish(session, exitstatus):
    counts = session.config._tk_counts
    if counts["total"] == 0:
        return
    summary = Summary(total=counts["total"], passed=counts["passed"],
                      failed=counts["failed"], bugs_by_severity={})
    criteria = ExitCriteria()
    out = session.config.getoption("--summary-out")
    payload = write_summary_json(summary, criteria, out)
    if not payload["exit_criteria_passed"]:
        print("\n[exit-criteria] FAILED:", "; ".join(payload["reasons"]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_conftest_summary.py -v`
Expected: PASS (1 passed) and `reports/summary.json` style file created in tmp

- [ ] **Step 5: Commit** *(requires user confirmation)*

```bash
git add conftest.py tests/unit/test_conftest_summary.py
git commit -m "feat: conftest fixtures + summary/exit-criteria hook"
```

---

## Task 11: Checklist generator from strategy.xlsx

**Files:**
- Create: `scripts/gen_checklist.py`
- Create: `scripts/__init__.py`
- Test: `tests/unit/test_gen_checklist.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_gen_checklist.py`:
```python
from pathlib import Path
from openpyxl import Workbook
from scripts.gen_checklist import extract_objects, render_markdown


def _make_xlsx(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "1_APITesting"
    ws["A72"] = "STT"; ws["C72"] = "Đối tượng testing"
    ws["J72"] = "Cách thức thực hiện và xác nhận"
    ws["A74"] = 1; ws["C74"] = "URL"; ws["J74"] = "Nhập URL và xác nhận domain"
    ws["A79"] = 2; ws["C79"] = "Header"; ws["J79"] = "Nhập header sai/đúng"
    p = tmp_path / "s.xlsx"
    wb.save(p)
    return p


def test_extract_objects_finds_rows(tmp_path):
    xlsx = _make_xlsx(tmp_path)
    objs = extract_objects(xlsx, "1_APITesting")
    names = [o["object"] for o in objs]
    assert "URL" in names and "Header" in names


def test_render_markdown_has_checkboxes(tmp_path):
    objs = [{"object": "URL", "how": "Nhập URL"}]
    md = render_markdown("API Testing", objs)
    assert "- [ ]" in md and "URL" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_gen_checklist.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.gen_checklist'`

- [ ] **Step 3: Write minimal implementation**

`scripts/__init__.py`:
```python
```

`scripts/gen_checklist.py`:
```python
"""Generate tester checklists from the strategy workbook.

Reads the "Đối tượng testing" (object) + "Cách thức thực hiện và xác nhận" (how)
columns of a strategy sheet and emits a Markdown checklist.

Usage:
    python scripts/gen_checklist.py --xlsx strategy/strategy.xlsx \
        --sheet 1_APITesting --title "API Testing" --out checklists/
"""
from __future__ import annotations
import argparse
from pathlib import Path
from openpyxl import load_workbook

# Column letters that hold the object name / the "how" description per strategy layout.
OBJECT_COL = "C"
HOW_COL = "J"
HEADER_TOKEN = "Đối tượng testing"


def extract_objects(xlsx_path, sheet_name: str) -> list[dict]:
    wb = load_workbook(xlsx_path, data_only=True)
    ws = wb[sheet_name]
    objects: list[dict] = []
    header_seen = False
    for row in range(1, ws.max_row + 1):
        cval = ws[f"{OBJECT_COL}{row}"].value
        if cval is None:
            continue
        text = str(cval).strip()
        if HEADER_TOKEN in text:
            header_seen = True
            continue
        if not header_seen:
            continue
        # A row is a testing object only if column A has an STT number.
        stt = ws[f"A{row}"].value
        if stt is None or not str(stt).strip().split(".")[0].isdigit():
            continue
        how = ws[f"{HOW_COL}{row}"].value
        objects.append({"object": text,
                        "how": str(how).strip() if how else ""})
    return objects


def render_markdown(title: str, objects: list[dict]) -> str:
    lines = [f"# Checklist — {title}", ""]
    for o in objects:
        lines.append(f"- [ ] **{o['object']}**")
        if o["how"]:
            how = o["how"].replace("\n", " ")
            lines.append(f"  - {how}")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xlsx", default="strategy/strategy.xlsx")
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--out", default="checklists/")
    args = ap.parse_args()

    objects = extract_objects(args.xlsx, args.sheet)
    md = render_markdown(args.title, objects)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.sheet}.md"
    out_file.write_text(md, encoding="utf-8")
    print(f"Wrote {len(objects)} objects -> {out_file}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_gen_checklist.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Generate real checklists and eyeball them**

Run:
```bash
python scripts/gen_checklist.py --sheet 1_APITesting --title "API Testing"
python scripts/gen_checklist.py --sheet 2_IntergrationTesting --title "Integration/UI Testing"
python scripts/gen_checklist.py --sheet 3_System_Testing --title "System Testing"
```
Expected: three files in `checklists/`, each listing the strategy's testing objects as `- [ ]` items.

- [ ] **Step 6: Commit** *(requires user confirmation)*

```bash
git add scripts/__init__.py scripts/gen_checklist.py tests/unit/test_gen_checklist.py
git commit -m "feat: checklist generator from strategy workbook"
```

---

## Task 12: CLI runner + server helper

**Files:**
- Create: `scripts/run.py`
- Create: `scripts/with_server.py` (copy from plugin)
- Test: `tests/unit/test_run_cli.py`

- [ ] **Step 1: Copy the server helper from the webapp-testing plugin**

Run (adjust the source hash dir if different):
```bash
cp "C:/Users/HungNV5/.claude/plugins/cache/anthropic-agent-skills/claude-api/575462609294/skills/webapp-testing/scripts/with_server.py" scripts/with_server.py
```
Expected: `scripts/with_server.py` exists. Verify usage: `python scripts/with_server.py --help`

- [ ] **Step 2: Write the failing test**

`tests/unit/test_run_cli.py`:
```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_run_cli.py -v`
Expected: FAIL (`scripts/run.py` does not exist)

- [ ] **Step 4: Write minimal implementation**

`scripts/run.py`:
```python
"""CLI to run a test layer and emit reports.

Examples:
    python scripts/run.py --layer integration
    python scripts/run.py --layer api --tablet
    python scripts/run.py --layer system --dry-run
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

LAYER_PATHS = {
    "api": "tests/api",
    "integration": "tests/integration",
    "system": "tests/system",
    "unit": "tests/unit",
}


def build_args(layer: str, tablet: bool, reports_dir: str) -> list[str]:
    Path(reports_dir).mkdir(parents=True, exist_ok=True)
    args = ["-m", "pytest", LAYER_PATHS[layer], "-v",
            "-m", layer if layer != "unit" else "not tablet",
            "--html", f"{reports_dir}/{layer}.html", "--self-contained-html",
            "--junitxml", f"{reports_dir}/{layer}-junit.xml",
            "--summary-out", f"{reports_dir}/{layer}-summary.json"]
    if not tablet:
        # default desktop-only run excludes the tablet-marked subset
        args += ["-k", "not tablet_only"]
    return args


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--layer", required=True, choices=list(LAYER_PATHS))
    ap.add_argument("--tablet", action="store_true",
                    help="Include the iPad/Safari selective subset")
    ap.add_argument("--reports", default="reports")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pytest_args = build_args(args.layer, args.tablet, args.reports)
    if args.dry_run:
        print(" ".join([sys.executable] + pytest_args))
        return 0
    return subprocess.call([sys.executable] + pytest_args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_run_cli.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit** *(requires user confirmation)*

```bash
git add scripts/run.py scripts/with_server.py tests/unit/test_run_cli.py
git commit -m "feat: cli runner + bundled server helper"
```

---

## Task 13: Example layer tests (API / Integration / System)

**Files:**
- Create: `tests/api/test_example_api.py`
- Create: `tests/integration/test_example_ui.py`
- Create: `tests/system/test_example_flow.py`
- Create: `tests/api/__init__.py`, `tests/integration/__init__.py`, `tests/system/__init__.py`

These are runnable references demonstrating each helper. The API example uses `httpserver`; the UI/System examples use the static sample page so they pass with no real app.

- [ ] **Step 1: Create the API example**

`tests/api/__init__.py`: (empty)

`tests/api/test_example_api.py`:
```python
import pytest
from toolkit.api_client import ApiClient


@pytest.mark.api
def test_endpoint_returns_200_and_schema_within_budget(httpserver):
    httpserver.expect_request("/users/1").respond_with_json(
        {"id": 1, "name": "Alice"}, status=200)
    client = ApiClient(base_url=httpserver.url_for(""))
    (client.get("/users/1")
        .assert_status(200)
        .assert_schema({"id": int, "name": str})
        .assert_under_ms(600))  # strategy: API < 600ms
```

- [ ] **Step 2: Create the Integration/UI example**

`tests/integration/__init__.py`: (empty)

`tests/integration/test_example_ui.py`:
```python
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
```

- [ ] **Step 3: Create the System example**

`tests/system/__init__.py`: (empty)

`tests/system/test_example_flow.py`:
```python
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
```

- [ ] **Step 4: Run all example layers**

Run: `pytest tests/api tests/integration tests/system -v`
Expected: PASS (3 passed) with no real app — uses sample page + httpserver.

- [ ] **Step 5: Commit** *(requires user confirmation)*

```bash
git add tests/api tests/integration tests/system
git commit -m "test: example api/integration/system layer tests"
```

---

## Task 14: README + full green run

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the README**

`README.md`:
````markdown
# Testing-Kit

Reusable Python + Playwright toolkit automating the project test strategy
(API, Integration/UI, System) with auto-generated checklists, HTML/JUnit
reports, and an exit-criteria gate (strategy sheet 6).

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium webkit
cp config/config.example.yaml config/config.yaml   # then edit base_url
cp config/users.example.yaml  config/users.yaml     # for permission tests
```

## Run

```bash
python scripts/run.py --layer integration   # desktop 1920 Chrome
python scripts/run.py --layer integration --tablet  # include iPad/Safari subset
python scripts/run.py --layer api
python scripts/run.py --layer system
```

Reports land in `reports/` (`*.html`, `*-junit.xml`, `*-summary.json`).
The run prints `[exit-criteria] FAILED` if pass rate < 95% or any
Critical/High bug is recorded.

## Generate checklists

```bash
python scripts/gen_checklist.py --sheet 1_APITesting        --title "API Testing"
python scripts/gen_checklist.py --sheet 2_IntergrationTesting --title "Integration/UI Testing"
python scripts/gen_checklist.py --sheet 3_System_Testing     --title "System Testing"
```

Output: `checklists/<sheet>.md`.

## Adapt to a new project

1. Edit `config/config.yaml` (`base_url`, thresholds if different).
2. Edit `config/devices.yaml` if the device matrix changes.
3. Replace the example tests in `tests/{api,integration,system}/` with your
   own, reusing helpers from `toolkit/`.

## Thresholds (from strategy)

| Metric | Budget |
|--------|--------|
| API response | < 600 ms |
| Web server response | < 1.5 s |
| Full page load | < 2.5 s |
| Exit: pass rate | ≥ 95% |
| Exit: blocking bugs | 0 Critical/High |
````

- [ ] **Step 2: Full green run**

Run: `pytest -v`
Expected: all unit + example tests PASS; `reports/summary.json` written.

- [ ] **Step 3: Commit** *(requires user confirmation)*

```bash
git add README.md
git commit -m "docs: usage readme"
```

---

## Self-Review Notes (coverage map)

- Spec §5.1 config → Task 2. §5.2 browser → Task 4. §5.3 api_client → Task 5.
  §5.4 ui_checks → Task 6. §5.5 security_checks → Task 7. §5.6 perf_checks →
  Task 8. §5.7 gen_checklist → Task 11. §5.8 conftest/report → Tasks 9–10.
- Spec §6 data flow: runner (Task 12) + report hook (Task 10) + checklist (Task 11).
- Spec §7 device matrix → `config/devices.yaml` (Task 2) + `--tablet` (Task 12) +
  tablet marker (`pytest.ini`, Task 1).
- Spec §8 error handling → config fail-fast (Task 2), missing-config skip (Task 10).
- Spec §9 toolkit self-tests → every helper task has unit tests on sample.html /
  httpserver.
- Spec §10 DoD → Task 14 full green run + README.
- Naming consistency verified: `Summary`, `evaluate_exit_criteria`,
  `ExitCriteria`, `DeviceProfile`, `launch_page`, `ApiClient`/`ApiResponse`,
  `assert_components_present`, `assert_console_clean`, `assert_no_xss`,
  `assert_under`, `extract_objects`/`render_markdown`, `build_args` are used
  consistently across tasks.
