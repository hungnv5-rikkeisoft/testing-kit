import os
from tcformat.checklists import load_checklists
from tcformat.resources import default_checklists, checklists_path


def test_default_file_exists():
    assert os.path.isfile(default_checklists())
    assert default_checklists().endswith("checklists.yaml")


def test_loads_default_kinds():
    data = load_checklists()
    for kind in ("input", "select", "button", "api", "screen"):
        assert kind in data and len(data[kind]) > 0
    # entries are well-formed
    entry = data["input"][0]
    assert {"technique", "category", "title"} <= set(entry)


def test_override_path(tmp_path):
    custom = tmp_path / "c.yaml"
    custom.write_text("button:\n  - {technique: t1, category: Function, title: x}\n",
                      encoding="utf-8")
    data = load_checklists(str(custom))
    assert list(data) == ["button"]
    assert data["button"][0]["technique"] == "t1"
