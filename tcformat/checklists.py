"""Load the technique checklist (element kind -> techniques), config-overridable.

Default ships bundled at tcformat/data/checklists.yaml and is resolved via
tcformat.resources, mirroring strategy/template resolution.
"""
from __future__ import annotations
from pathlib import Path
import yaml

from tcformat.resources import checklists_path


def load_checklists(explicit: str | None = None,
                    config_path: str | None = None) -> dict:
    """Return {kind: [{technique, category, title}, ...]} including key 'screen'."""
    path = checklists_path(explicit, config_path)
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return data
