from dataclasses import asdict
import pytest
from tcformat.schema import load_screen, dump_screen, SchemaError, Screen, Testcase

SAMPLE = """
screen: "Basic Info"
test_level: IT
testcases:
  - id: UI_01
    section: UI
    main_item: "Move screen"
    type: IT
    priority: High
    strategy_ref: "2.3.1#1"
    precondition: "Logged in"
    steps: ["Open screen", "Click menu"]
    expected: ["Screen shows"]
"""


def _write(tmp_path, text):
    p = tmp_path / "s.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_screen_parses(tmp_path):
    sc = load_screen(_write(tmp_path, SAMPLE))
    assert sc.screen == "Basic Info"
    assert sc.test_level == "IT"
    assert len(sc.testcases) == 1
    tc = sc.testcases[0]
    assert tc.id == "UI_01"
    assert tc.steps == ["Open screen", "Click menu"]
    assert tc.result.chrome.status is None
    assert tc.result.safari.evidence == []


def test_invalid_priority_raises(tmp_path):
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, SAMPLE.replace("priority: High", "priority: Urgent")))


def test_missing_id_raises(tmp_path):
    y = "screen: S\ntestcases:\n  - type: IT\n    priority: Low\n"
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, y))


def test_duplicate_id_raises(tmp_path):
    y = ("screen: S\ntestcases:\n"
         "  - id: A\n    type: IT\n    priority: Low\n"
         "  - id: A\n    type: IT\n    priority: Low\n")
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, y))


def test_roundtrip(tmp_path):
    sc = load_screen(_write(tmp_path, SAMPLE))
    out = tmp_path / "o.yaml"
    dump_screen(sc, out)
    sc2 = load_screen(out)
    assert asdict(sc) == asdict(sc2)
