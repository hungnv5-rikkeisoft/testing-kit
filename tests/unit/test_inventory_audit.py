from tcformat.inventory import Inventory, Element
from tcformat.inventory_audit import audit_inventory


SNAP = {
    "elements": [
        {"role": "textbox", "name": "userId"},
        {"role": "combobox", "name": "mode"},
        {"role": "button", "name": "Lクラス"},
    ],
    "forms": [{"action": "/", "method": "POST"}],
}


def test_missing_dom_element_not_in_inventory():
    inv = Inventory(screen="S", elements=[
        Element(id="userId", kind="input", label="ユーザーID"),
        Element(id="submit", kind="api"),
        # 'mode' and the Lクラス button are present in the DOM but NOT inventoried
    ])
    rep = audit_inventory(inv, SNAP)
    assert "mode" in rep.missing
    assert any("クラス" in m for m in rep.missing)


def test_stale_inventory_element_not_in_dom():
    inv = Inventory(screen="S", elements=[
        Element(id="userId", kind="input"),
        Element(id="mode", kind="select"),
        Element(id="ghostField", kind="input", label="ghost"),
        Element(id="submit", kind="api"),
        Element(id="preset-l", kind="button", label="Lクラス"),
    ])
    rep = audit_inventory(inv, SNAP)
    assert "ghostField" in rep.stale
    assert "userId" not in rep.stale


def test_form_without_api_flag():
    inv = Inventory(screen="S", elements=[Element(id="userId", kind="input")])
    rep = audit_inventory(inv, SNAP)
    assert rep.form_without_api is True


def test_form_with_api_not_flagged():
    inv = Inventory(screen="S", elements=[Element(id="submit", kind="api")])
    rep = audit_inventory(inv, SNAP)
    assert rep.form_without_api is False
