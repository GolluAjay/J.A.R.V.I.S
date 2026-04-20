# 01 — Installation

## Requirements

- **Python ≥ 3.10** (see `pyproject.toml`).
- **pip** and a virtual environment recommended.
- **neo4j** Python driver is declared as a dependency; Neo4j server itself is separate (Docker or local install).
- **Ollama** installed and running for LLM features.

## Editable install (recommended)

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

This installs console scripts:

- **`jarvis-hud`** → `jarvis.cli.hud:main`
- **`jarvis-web`** → `jarvis.cli.server:main`

## Run without installing (developers)

The root **`./jarvis`** bash launcher sets:

```bash
export PYTHONPATH="$JARVIS_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
```

and prefers `.venv/bin/python3` when present. Any equivalent:

```bash
PYTHONPATH=src python3 -m jarvis
```

runs the HUD via `jarvis/__main__.py`.

## Pull models (Ollama)

Example (align names with `config/jarvis.json` → `features.llm.model` and `embedModel`):

```bash
ollama pull llama3:8b
ollama pull nomic-embed-text
```

## Verify

```bash
./jarvis test
# or
PYTHONPATH=src python3 -c "import jarvis; from jarvis.agent import GeneralPurposeAgent; print(GeneralPurposeAgent)"
```

See [Scripts & ops](13-scripts-ops.md) for all `./jarvis` subcommands.
