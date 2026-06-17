"""Load a per-screen element inventory: the fan-out axis for test generation.

One inventory file (testcases/<screen>.inventory.yaml) lists every interactive
element (button/input/select/link), plus api endpoints, with metadata that
drives which checklist techniques apply. Reviewed by a human before cases are
written, so a missing element is caught before it becomes missing coverage.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml

VALID_KINDS = {"button", "input", "select", "link", "api", "screen"}


class InventoryError(Exception):
    pass


@dataclass
class Element:
    id: str
    kind: str
    label: str = ""
    options_source: str = ""
    default: str = ""
    depends_on: list = field(default_factory=list)
    method: str = ""
    path: str = ""
    params: list = field(default_factory=list)


@dataclass
class Inventory:
    screen: str
    elements: list = field(default_factory=list)


def _element(d: dict) -> Element:
    if not d.get("id"):
        raise InventoryError("element missing required 'id'")
    kind = d.get("kind")
    if not kind:
        raise InventoryError(f"element {d['id']}: missing required 'kind'")
    if kind not in VALID_KINDS:
        raise InventoryError(f"element {d['id']}: invalid kind '{kind}'")
    return Element(
        id=str(d["id"]),
        kind=kind,
        label=d.get("label", ""),
        options_source=d.get("options_source", ""),
        default=d.get("default", ""),
        depends_on=list(d.get("depends_on") or []),
        method=d.get("method", ""),
        path=d.get("path", ""),
        params=list(d.get("params") or []),
    )


def load_inventory(path) -> Inventory:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not data.get("screen"):
        raise InventoryError("missing required 'screen'")
    elements = [_element(e) for e in (data.get("elements") or [])]
    return Inventory(screen=data["screen"], elements=elements)
