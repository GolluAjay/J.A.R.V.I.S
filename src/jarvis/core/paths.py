"""Single source of truth for JARVIS filesystem layout (no scattered ~/JARVIS literals)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_jarvis_home() -> Path:
    """Resolve project root: JARVIS_HOME env, then ~/JARVIS, then repo root via pyproject.toml."""
    env = os.environ.get("JARVIS_HOME")
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return p

    home_default = (Path.home() / "JARVIS").resolve()
    if home_default.is_dir():
        return home_default

    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "jarvis").is_dir():
            return parent

    return home_default


def knowledge_dir() -> Path:
    return get_jarvis_home() / "knowledge"


def config_dir() -> Path:
    return get_jarvis_home() / "config"


def system_prompt_path() -> Path:
    return config_dir() / "system-prompt.txt"


def skills_dir() -> Path:
    return get_jarvis_home() / "skills"


def ui_dir() -> Path:
    return get_jarvis_home() / "ui"


def html_index_path() -> Path:
    return ui_dir() / "index.html"


def logs_dir() -> Path:
    return get_jarvis_home() / "logs"


def automation_config_path() -> Path:
    return config_dir() / "automation.json"


def smarthome_config_path() -> Path:
    return config_dir() / "smart-home.json"
