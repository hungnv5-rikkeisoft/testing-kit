from pathlib import Path
import textwrap
import pytest
from toolkit.config import load_config, ConfigError


def write(tmp_path, text):
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return p


def test_defaults_applied_from_strategy(tmp_path):
    cfg = load_config(write(tmp_path, """
        base_url: http://localhost:5173
    """))
    assert cfg.base_url == "http://localhost:5173"
    assert cfg.thresholds.api_ms == 600
    assert cfg.thresholds.web_response_ms == 1500
    assert cfg.thresholds.page_load_ms == 2500
    assert cfg.exit_criteria.min_pass_rate == 0.95
    assert cfg.exit_criteria.block_severities == ["Critical", "High"]


def test_overrides_win(tmp_path):
    cfg = load_config(write(tmp_path, """
        base_url: http://x
        thresholds:
          api_ms: 800
    """))
    assert cfg.thresholds.api_ms == 800
    assert cfg.thresholds.page_load_ms == 2500  # untouched default


def test_missing_base_url_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, "thresholds: {api_ms: 600}\n"))
