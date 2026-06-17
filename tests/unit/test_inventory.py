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
