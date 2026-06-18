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


from tcformat.schema import flatten_expected

DICT_SAMPLE = """
screen: "S"
test_level: IT
testcases:
  - id: VAL_01
    type: IT
    priority: High
    steps: ["Submit empty form"]
    expected:
      - "Plain string still works"
      - {field: "Field A", value: "XXX"}
      - {field: "Field B", enabled: false}
      - {request: "POST /api/x"}
      - {redirect: "/home"}
"""


def test_mixed_expected_loads(tmp_path):
    sc = load_screen(_write(tmp_path, DICT_SAMPLE))
    exp = sc.testcases[0].expected
    assert exp[0] == "Plain string still works"
    assert exp[1] == {"field": "Field A", "value": "XXX"}
    assert exp[2] == {"field": "Field B", "enabled": False}


def test_expected_unknown_key_raises(tmp_path):
    y = DICT_SAMPLE.replace('{field: "Field A", value: "XXX"}', '{field: "A", foo: 1}')
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, y))


def test_expected_no_assertion_keys_raises(tmp_path):
    # field-only dict has no clause-producing key
    y = DICT_SAMPLE.replace('{field: "Field A", value: "XXX"}', '{field: "A"}')
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, y))


def test_expected_empty_dict_raises(tmp_path):
    y = DICT_SAMPLE.replace('{field: "Field A", value: "XXX"}', '{}')
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, y))


def test_expected_wrong_type_raises(tmp_path):
    y = DICT_SAMPLE.replace('{field: "Field A", value: "XXX"}', '[1, 2]')
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, y))


def test_flatten_string_passthrough():
    assert flatten_expected("just text") == "just text"


def test_flatten_value_with_field():
    assert flatten_expected({"field": "Field A", "value": "XXX"}) == "Field A = XXX"


def test_flatten_value_without_field():
    assert flatten_expected({"value": "XXX"}) == "= XXX"


def test_flatten_enabled_false_is_disabled():
    assert flatten_expected({"field": "Field B", "enabled": False}) == "Field B disabled"


def test_flatten_required_true():
    assert flatten_expected({"field": "Email", "required": True}) == "Email required"


def test_flatten_required_false_is_optional():
    assert flatten_expected({"field": "Phone", "required": False}) == "Phone optional"


def test_flatten_button_state():
    assert flatten_expected({"field": "Submit", "button_state": "enabled"}) == "Submit button enabled"


def test_flatten_request_and_redirect():
    assert flatten_expected({"request": "POST /api/x"}) == "POST /api/x"
    assert flatten_expected({"redirect": "/home"}) == "redirect /home"


def test_flatten_multiple_keys_joined_in_order():
    item = {"field": "Field A", "value": "1", "required": True}
    assert flatten_expected(item) == "Field A = 1; Field A required"


def test_roundtrip_dict_expected(tmp_path):
    sc = load_screen(_write(tmp_path, DICT_SAMPLE))
    out = tmp_path / "o.yaml"
    dump_screen(sc, out)
    sc2 = load_screen(out)
    assert asdict(sc) == asdict(sc2)
