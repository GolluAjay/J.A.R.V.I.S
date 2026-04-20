"""JARVIS assistant package (src layout)."""

from jarvis.core.settings import apply_runtime_settings

# Merge config/jarvis.json into env before submodules read OLLAMA_HOST / Neo4j defaults.
apply_runtime_settings()

__version__ = "1.0.0"
