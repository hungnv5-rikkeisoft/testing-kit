import os
from tcformat.resources import (
    default_template, default_strategy, template_path, strategy_path)


def test_defaults_point_at_existing_bundled_files():
    assert os.path.isfile(default_template())
    assert os.path.isfile(default_strategy())
    assert default_template().endswith("Format test case + Test report.xlsx")


def test_explicit_overrides_default():
    assert template_path("/x/custom.xlsx") == "/x/custom.xlsx"
    assert strategy_path("/x/s.xlsx") == "/x/s.xlsx"


def test_config_override(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("base_url: http://x\ntemplate_path: /from/cfg.xlsx\n",
                   encoding="utf-8")
    assert template_path(None, str(cfg)) == "/from/cfg.xlsx"
    assert template_path("/explicit.xlsx", str(cfg)) == "/explicit.xlsx"
    assert strategy_path(None, str(cfg)) == default_strategy()


def test_config_path_missing_file_falls_back():
    assert template_path(None, "does/not/exist.yaml") == default_template()


def test_checklists_default_and_override(tmp_path):
    from tcformat.resources import default_checklists, checklists_path
    assert checklists_path() == default_checklists()
    assert checklists_path("/x/c.yaml") == "/x/c.yaml"
    cfg = tmp_path / "config.yaml"
    cfg.write_text("checklists_path: /from/cfg.yaml\n", encoding="utf-8")
    assert checklists_path(None, str(cfg)) == "/from/cfg.yaml"
