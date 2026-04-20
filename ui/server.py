#!/usr/bin/env python3
"""Backward-compatible entry: prefer `jarvis-web` or `python -m jarvis.cli.server`."""

from pathlib import Path
import sys

_root = Path(__file__).resolve().parents[1]
_src = _root / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from jarvis.cli.server import main

if __name__ == "__main__":
    main()
