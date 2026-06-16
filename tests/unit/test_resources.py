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
