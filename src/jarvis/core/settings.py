"""Runtime settings: merge config/jarvis.json with environment (env wins)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict

from jarvis.core.paths import config_dir


@dataclass
class JarvisRuntimeSettings:
    """Unified knobs for models, retrieval, and agent behavior."""

    chat_model: str = "llama3.2:3b"
    embed_model: str = "nomic-embed-text"
    ollama_host: str = "http://localhost:11434"
    retrieval_query_expand: bool = False
    grounded_reflect_retry: bool = True
    raw_json: Dict[str, Any] = field(default_factory=dict)


def _deep_get(data: Dict[str, Any], *keys: str, default=None):
    cur: Any = data
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


@lru_cache(maxsize=1)
def load_settings() -> JarvisRuntimeSettings:
    path = config_dir() / "jarvis.json"
    raw: Dict[str, Any] = {}
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            raw = {}

    llm = _deep_get(raw, "features", "llm", default={}) or {}
    server = _deep_get(raw, "server", default={}) or {}
    retr = _deep_get(raw, "features", "retrieval", default={}) or {}

    model = (llm.get("model") or "llama3.2:3b").strip()
    embed_from_file = (llm.get("embedModel") or llm.get("embed_model") or "").strip()
    embed_model = embed_from_file or os.environ.get("JARVIS_EMBED_MODEL") or "nomic-embed-text"
    host = server.get("host") or "localhost"
    api_port = server.get("apiPort") or 11434
    ollama_host = f"http://{host}:{api_port}" if str(api_port).isdigit() else "http://localhost:11434"

    return JarvisRuntimeSettings(
        chat_model=model,
        embed_model=embed_model,
        ollama_host=ollama_host,
        retrieval_query_expand=bool(retr.get("expand_queries", False)),
        grounded_reflect_retry=bool(retr.get("reflect_retry", True)),
        raw_json=raw,
    )


def apply_runtime_settings() -> JarvisRuntimeSettings:
    """Apply defaults from jarvis.json into os.environ (setdefault only). Call early on package import."""
    s = load_settings()
    os.environ.setdefault("OLLAMA_HOST", s.ollama_host)
    os.environ.setdefault("JARVIS_CHAT_MODEL", s.chat_model)
    os.environ.setdefault("JARVIS_EMBED_MODEL", s.embed_model)
    return s


def get_settings() -> JarvisRuntimeSettings:
    """Cached settings object (reload process to pick up file edits)."""
    return load_settings()


def clear_settings_cache() -> None:
    load_settings.cache_clear()
