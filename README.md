# JARVIS

Local AI assistant: terminal HUD, Neo4j-backed RAG, Ollama.

**Full handbook:** [docs/README.md](docs/README.md) (install, config, architecture, HUD commands, security, ops).

## Setup

```bash
cd /path/to/JARVIS
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Optional: set `JARVIS_HOME` if your repo is not at `~/JARVIS` and you want data (`knowledge/`, `config/`) elsewhere.

## Source layout (`src/jarvis`)

| Package | Role |
|--------|------|
| `core/` | Paths (`JARVIS_HOME`), `jarvis.json` settings merge, shell consent policy |
| `llm/` | Ollama client and conversation memory (`JARVISBrain`) |
| `agent/` | `GeneralPurposeAgent`, arithmetic shortcuts, grounded citation helpers |
| `runtime/` | Shell orchestrator and HUD skills |
| `rag/` | File-backed knowledge index + Neo4j ingestion hooks |
| `graph/` | Neo4j work partner, hybrid retrieval, grounded prompts |
| `retrieval/` | Optional query expansion before retrieval |
| `tools/` | JSON structured tool registry |
| `voice/` | Microphone capture, TTS, optional macOS recorder helper (`MacSpeechRecorder`) |
| `integrations/` | Smart home stubs, automation triggers |
| `cli/` | HUD and web server entrypoints |
| `legacy/` | Older monolithic app entrypoint |

## Run

- **HUD:** `./jarvis hud` or `jarvis-hud` or `python -m jarvis`
- **Web UI:** `./jarvis web` or `jarvis-web`
- **Tests:** `./jarvis test`

Requires Ollama and (for grounded mode) Neo4j as configured in `jarvis/graph/work_partner.py` / env vars.

## Local stack (Docker)

From the repo root:

```bash
docker compose up -d
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=password
ollama pull llama3:8b
ollama pull nomic-embed-text
```

Defaults for the chat model and Ollama URL can be set in `config/jarvis.json` (`features.llm.model`, `server.host`, `server.apiPort`). Environment variables override those defaults. Optional retrieval flags live under `features.retrieval` (`expand_queries`, `reflect_retry`).

## Structured tools (JSON)

The agent accepts a single-line JSON object: `{"tool": "now", "args": {}}`, `{"tool": "calculator", "args": {"expr": "2+2"}}`, or `{"tool": "list_tools", "args": {}}`.
