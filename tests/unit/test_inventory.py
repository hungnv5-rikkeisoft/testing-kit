import pytest
from tcformat.inventory import load_inventory, InventoryError

SAMPLE = """
screen: Basic Information Input
elements:
  - id: usage_residential
    kind: button
    label: "Usage: Residential"
  - id: prefecture
    kind: select
    options_source: "db:prefectures.name"
    depends_on: []
  - id: municipality
    kind: select
    options_source: "db:municipalities.name"
    depends_on: [prefecture]
  - id: api_submit
    kind: api
    method: POST
    path: /api/basic-info
    params: [usage, prefecture, municipality]
"""


def _write(tmp_path, text):
    p = tmp_path / "inv.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_loads_elements(tmp_path):
    inv = load_inventory(_write(tmp_path, SAMPLE))
    assert inv.screen == "Basic Information Input"
    assert len(inv.elements) == 4
    muni = next(e for e in inv.elements if e.id == "municipality")
    assert muni.kind == "select"
    assert muni.depends_on == ["prefecture"]
    api = next(e for e in inv.elements if e.id == "api_submit")
    assert api.method == "POST" and api.params == ["usage", "prefecture", "municipality"]


def test_missing_screen_raises(tmp_path):
    with pytest.raises(InventoryError):
        load_inventory(_write(tmp_path, "elements: []\n"))


def test_element_missing_id_raises(tmp_path):
    y = "screen: S\nelements:\n  - kind: button\n"
    with pytest.raises(InventoryError):
        load_inventory(_write(tmp_path, y))


def test_unknown_kind_raises(tmp_path):
    y = "screen: S\nelements:\n  - id: x\n    kind: widget\n"
    with pytest.raises(InventoryError):
        load_inventory(_write(tmp_path, y))


def test_skip_techniques_loaded(tmp_path):
    p = tmp_path / "s.inventory.yaml"
    p.write_text(
        "screen: S\n"
        "elements:\n"
        "  - id: name\n"
        "    kind: input\n"
        "    skip_techniques: [boundary, max-length]\n"
        "  - id: btn\n"
        "    kind: button\n",
        encoding="utf-8")
    inv = load_inventory(str(p))
    by_id = {e.id: e for e in inv.elements}
    assert by_id["name"].skip_techniques == ["boundary", "max-length"]
    assert by_id["btn"].skip_techniques == []   # default empty


def test_load_inventory_parses_absent(tmp_path):
    p = tmp_path / "s.inventory.yaml"
    p.write_text(
        "screen: S\n"
        "absent:\n"
        "  api: 'Màn chỉ hiển thị, không gọi backend.'\n"
        "elements:\n"
        "  - {id: btn, kind: button, label: B}\n",
        encoding="utf-8")
    inv = load_inventory(p)
    assert inv.absent == {"api": "Màn chỉ hiển thị, không gọi backend."}


def test_load_inventory_absent_defaults_empty(tmp_path):
    p = tmp_path / "s.inventory.yaml"
    p.write_text("screen: S\nelements: []\n", encoding="utf-8")
    assert load_inventory(p).absent == {}


def test_load_inventory_absent_must_be_mapping(tmp_path):
    p = tmp_path / "s.inventory.yaml"
    p.write_text("screen: S\nabsent: [api]\nelements: []\n", encoding="utf-8")
    with pytest.raises(InventoryError):
        load_inventory(p)
