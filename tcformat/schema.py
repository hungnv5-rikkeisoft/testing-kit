from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import yaml

VALID_LEVELS = {"UT", "IT", "ST"}
VALID_PRIORITIES = {"Low", "Medium", "High"}
VALID_STATUSES = {"OK", "NG", "N/A"}
VALID_BROWSERS = {"chrome", "safari"}
VALID_CATEGORIES = {
    "UI", "Function", "Validation", "Boundary", "BusinessRule",
    "API", "ErrorHandling", "Security", "UserBehavior",
}

EXPECTED_KEYS = {
    "field", "value", "enabled", "required",
    "button_state", "request", "redirect",
}


class SchemaError(Exception):
    pass


@dataclass
class BrowserResult:
    status: str | None = None
    bug_id: str | None = None
    tester: str | None = None
    date: str | None = None
    note: str | None = None
    evidence: list = field(default_factory=list)


@dataclass
class Result:
    chrome: BrowserResult = field(default_factory=BrowserResult)
    safari: BrowserResult = field(default_factory=BrowserResult)


@dataclass
class Testcase:
    __test__ = False
    id: str
    section: str = ""
    main_item: str = ""
    middle_item: str = ""
    minor_item: str = ""
    type: str = "IT"
    priority: str = "Medium"
    strategy_ref: str = ""
    category: str = ""
    technique: str = ""
    target: str = ""
    precondition: str = ""
    steps: list = field(default_factory=list)
    expected: list = field(default_factory=list)
    result: Result = field(default_factory=Result)


@dataclass
class Screen:
    screen: str
    test_level: str = "IT"
    created_by: str = ""
    source_docs: list = field(default_factory=list)
    testcases: list = field(default_factory=list)


def _browser_result(d) -> BrowserResult:
    d = d or {}
    return BrowserResult(
        status=d.get("status"), bug_id=d.get("bug_id"),
        tester=d.get("tester"), date=d.get("date"),
        note=d.get("note"),
        evidence=list(d.get("evidence") or []))


def _result(d) -> Result:
    d = d or {}
    return Result(chrome=_browser_result(d.get("chrome")),
                  safari=_browser_result(d.get("safari")))


def _validate_expected(tc_id: str, items: list) -> list:
    out = []
    for item in items:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            unknown = sorted(set(item) - EXPECTED_KEYS)
            if unknown:
                raise SchemaError(
                    f"testcase {tc_id}: expected assertion has unknown key '{unknown[0]}'")
            if not any(k != "field" and item[k] is not None for k in item):
                raise SchemaError(
                    f"testcase {tc_id}: expected assertion has no assertion keys")
            out.append(item)
        else:
            raise SchemaError(
                f"testcase {tc_id}: expected item must be str or dict, "
                f"got {type(item).__name__}")
    return out


def flatten_expected(item) -> str:
    """Flatten one `expected` item (str or assertion dict) into display text.

    One dict describes one subject (`field`); attribute clauses are joined by
    '; ' in a fixed key order. Absent or None keys are skipped.
    """
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)
    prefix = f"{item['field']} " if item.get("field") else ""
    clauses = []
    if item.get("value") is not None:
        clauses.append(f"{prefix}= {item['value']}".strip())
    if item.get("enabled") is not None:
        clauses.append(f"{prefix}{'enabled' if item['enabled'] else 'disabled'}".strip())
    if item.get("required") is not None:
        clauses.append(f"{prefix}{'required' if item['required'] else 'optional'}".strip())
    if item.get("button_state") is not None:
        clauses.append(f"{prefix}button {item['button_state']}".strip())
    if item.get("request") is not None:
        clauses.append(str(item["request"]))
    if item.get("redirect") is not None:
        clauses.append(f"redirect {item['redirect']}")
    return "; ".join(clauses)


def _testcase(d: dict) -> Testcase:
    if not d.get("id"):
        raise SchemaError("testcase missing required 'id'")
    tc_id = str(d["id"])
    tc = Testcase(
        id=tc_id,
        section=d.get("section", ""),
        main_item=d.get("main_item", ""),
        middle_item=d.get("middle_item", ""),
        minor_item=d.get("minor_item", ""),
        type=d.get("type", "IT"),
        priority=d.get("priority", "Medium"),
        strategy_ref=d.get("strategy_ref", ""),
        category=d.get("category", ""),
        technique=d.get("technique", ""),
        target=d.get("target", ""),
        precondition=d.get("precondition", ""),
        steps=list(d.get("steps") or []),
        expected=_validate_expected(tc_id, list(d.get("expected") or [])),
        result=_result(d.get("result")),
    )
    if tc.type not in VALID_LEVELS:
        raise SchemaError(f"testcase {tc.id}: invalid type '{tc.type}'")
    if tc.priority not in VALID_PRIORITIES:
        raise SchemaError(f"testcase {tc.id}: invalid priority '{tc.priority}'")
    if tc.category and tc.category not in VALID_CATEGORIES:
        raise SchemaError(f"testcase {tc.id}: invalid category '{tc.category}'")
    return tc


def load_screen(path) -> Screen:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not data.get("screen"):
        raise SchemaError("missing required 'screen'")
    level = data.get("test_level", "IT")
    if level not in VALID_LEVELS:
        raise SchemaError(f"invalid test_level '{level}'")
    tcs = [_testcase(t) for t in (data.get("testcases") or [])]
    ids = [t.id for t in tcs]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    if dups:
        raise SchemaError(f"duplicate testcase id(s): {dups}")
    return Screen(
        screen=data["screen"], test_level=level,
        created_by=data.get("created_by", ""),
        source_docs=list(data.get("source_docs") or []),
        testcases=tcs)


def dump_screen(screen: Screen, path) -> None:
    Path(path).write_text(
        yaml.safe_dump(asdict(screen), allow_unicode=True, sort_keys=False),
        encoding="utf-8")
