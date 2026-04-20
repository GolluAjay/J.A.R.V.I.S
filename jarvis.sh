#!/bin/bash
# Deprecated: use ./jarvis from the repo root instead.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/jarvis" "$@"
