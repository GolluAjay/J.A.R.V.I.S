# 02 — Configuration

## Filesystem root: `JARVIS_HOME`

Resolved by `jarvis.core.paths.get_jarvis_home()`:

1. Environment variable **`JARVIS_HOME`** if it points to an existing directory.
2. Else **`~/JARVIS`** if that directory exists.
3. Else the repository root (directory containing `pyproject.toml` and `src/jarvis`).
4. Fallback: `~/JARVIS` even if missing (callers may create children).

Important directories (all under that root unless overridden in code):

| Path | Purpose |
|------|---------|
| `knowledge/` | User documents, `.index.json`, `user_preferences.txt` for “remember …” |
| `config/` | `jarvis.json`, `system-prompt.txt`, `automation.json`, `smart-home.json` |
| `skills/` | Optional skill assets |
| `ui/` | `index.html` for the web UI |
| `logs/` | Log file location referenced by config (create as needed) |

## `config/jarvis.json`

Merged at startup by `jarvis.core.settings.load_settings()`; values are applied with **`os.environ.setdefault`** so **existing environment variables win**.

### `server`

| Key | Effect |
|-----|--------|
| `host` | Hostname for Ollama URL construction |
| `apiPort` | Port for Ollama → `OLLAMA_HOST` defaults to `http://{host}:{apiPort}` |
| `port` | Intended web port (see Web UI doc); server also scans for a free port |

### `features.llm`

| Key | Effect |
|-----|--------|
| `model` | Default chat model → `JARVIS_CHAT_MODEL` |
| `embedModel` / `embed_model` | Default embed model name → `JARVIS_EMBED_MODEL` |

### `features.retrieval`

| Key | Effect |
|-----|--------|
| `expand_queries` | If true, optional LLM rewrite of the user query before `hybrid_retrieve` |
| `reflect_retry` | If true (non-streaming grounded path), second LLM pass when citations missing |

### Other `features.*` blocks

Present for product metadata (voice, smartHome, automation, etc.). Not every flag is consumed by every code path; the HUD and agent primarily use LLM + retrieval + paths as above.

## Environment variables (common)

| Variable | Purpose |
|----------|---------|
| `JARVIS_HOME` | Override data/config root |
| `OLLAMA_HOST` | Ollama base URL (no trailing slash required; code strips) |
| `JARVIS_CHAT_MODEL` | Model id for `/api/generate` |
| `JARVIS_EMBED_MODEL` | Model id for embeddings in `WorkPartner` |
| `NEO4J_URI` | Bolt URI, default `bolt://localhost:7687` |
| `NEO4J_USER` | Default `neo4j` |
| `NEO4J_PASSWORD` | Default `password` in code; **change in production** |

## System prompt

`JARVISBrain` loads personality text from **`config/system-prompt.txt`** under `JARVIS_HOME` (`jarvis.core.paths.system_prompt_path()`). If missing, a short built-in J.A.R.V.I.S. string is used.

## Reloading settings

`load_settings()` is **`lru_cache(maxsize=1)`**. Restart the process to pick up `jarvis.json` edits, or call `jarvis.core.settings.clear_settings_cache()` if you extend the code to hot-reload.
