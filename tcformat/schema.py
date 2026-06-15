from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import yaml

VALID_LEVELS = {"UT", "IT", "ST"}
VALID_PRIORITIES = {"Low", "Medium", "High"}
VALID_STATUSES = {"OK", "NG", "N/A"}


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


def _testcase(d: dict) -> Testcase:
    if not d.get("id"):
        raise SchemaError("testcase missing required 'id'")
    tc = Testcase(
        id=str(d["id"]),
        section=d.get("section", ""),
        main_item=d.get("main_item", ""),
        middle_item=d.get("middle_item", ""),
        minor_item=d.get("minor_item", ""),
        type=d.get("type", "IT"),
        priority=d.get("priority", "Medium"),
        strategy_ref=d.get("strategy_ref", ""),
        precondition=d.get("precondition", ""),
        steps=list(d.get("steps") or []),
        expected=list(d.get("expected") or []),
        result=_result(d.get("result")),
    )
    if tc.type not in VALID_LEVELS:
        raise SchemaError(f"testcase {tc.id}: invalid type '{tc.type}'")
    if tc.priority not in VALID_PRIORITIES:
        raise SchemaError(f"testcase {tc.id}: invalid priority '{tc.priority}'")
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
