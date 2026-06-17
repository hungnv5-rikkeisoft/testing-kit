from dataclasses import asdict
import pytest
from tcformat.schema import load_screen, dump_screen, SchemaError

BASE = (
    "screen: S\n"
    "testcases:\n"
    "  - id: V_01\n"
    "    type: IT\n"
    "    priority: High\n"
    "    category: Validation\n"
    "    technique: empty\n"
    "    target: name_field\n"
)


def _write(tmp_path, text):
    p = tmp_path / "s.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_tags_parse(tmp_path):
    sc = load_screen(_write(tmp_path, BASE))
    tc = sc.testcases[0]
    assert tc.category == "Validation"
    assert tc.technique == "empty"
    assert tc.target == "name_field"


def test_tags_default_empty_when_absent(tmp_path):
    y = "screen: S\ntestcases:\n  - id: A\n    type: IT\n    priority: Low\n"
    sc = load_screen(_write(tmp_path, y))
    tc = sc.testcases[0]
    assert tc.category == "" and tc.technique == "" and tc.target == ""


def test_invalid_category_raises(tmp_path):
    with pytest.raises(SchemaError):
        load_screen(_write(tmp_path, BASE.replace("category: Validation",
                                                  "category: Nonsense")))


def test_tags_roundtrip(tmp_path):
    sc = load_screen(_write(tmp_path, BASE))
    out = tmp_path / "o.yaml"
    dump_screen(sc, out)
    sc2 = load_screen(out)
    assert asdict(sc) == asdict(sc2)
