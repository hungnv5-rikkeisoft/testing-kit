from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml


class ConfigError(Exception):
    pass


@dataclass
class Thresholds:
    api_ms: int = 600           # strategy sheet 1: API < 600ms
    web_response_ms: int = 1500  # sheet 2: web server response < 1.5s
    page_load_ms: int = 2500     # sheet 2: full page load < 2.5s


@dataclass
class ExitCriteria:
    min_pass_rate: float = 0.95  # sheet 6: >= 95% pass
    block_severities: list = field(default_factory=lambda: ["Critical", "High"])


@dataclass
class Config:
    base_url: str
    thresholds: Thresholds
    exit_criteria: ExitCriteria
    raw: dict


def load_config(path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base_url = data.get("base_url")
    if not base_url:
        raise ConfigError("'base_url' is required in config")

    t = data.get("thresholds", {}) or {}
    thresholds = Thresholds(
        api_ms=t.get("api_ms", 600),
        web_response_ms=t.get("web_response_ms", 1500),
        page_load_ms=t.get("page_load_ms", 2500),
    )
    e = data.get("exit_criteria", {}) or {}
    exit_criteria = ExitCriteria(
        min_pass_rate=e.get("min_pass_rate", 0.95),
        block_severities=e.get("block_severities", ["Critical", "High"]),
    )
    return Config(base_url=base_url, thresholds=thresholds,
                  exit_criteria=exit_criteria, raw=data)
