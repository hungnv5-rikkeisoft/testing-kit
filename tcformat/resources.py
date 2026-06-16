"""Locate the bundled default template/strategy xlsx, with override hooks.

Resolution order for a path: explicit argument > config.yaml key > bundled
default shipped as package data. Bundled files live under tcformat/data/ and
are resolved via importlib.resources (works when pip-installed from a source
directory, which is how /tk:setup installs the plugin).
"""
from __future__ import annotations
from importlib.resources import files
from pathlib import Path

TEMPLATE_NAME = "Format test case + Test report.xlsx"
STRATEGY_NAME = "strategy.xlsx"


def default_template() -> str:
    return str(files("tcformat").joinpath("data", "template", TEMPLATE_NAME))


def default_strategy() -> str:
    return str(files("tcformat").joinpath("data", "strategy", STRATEGY_NAME))


def _from_config(config_path, key):
    if not config_path:
        return None
    p = Path(config_path)
    if not p.exists():
        return None
    import yaml
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data.get(key)


def template_path(explicit=None, config_path=None) -> str:
    return explicit or _from_config(config_path, "template_path") or default_template()


def strategy_path(explicit=None, config_path=None) -> str:
    return explicit or _from_config(config_path, "strategy_path") or default_strategy()
