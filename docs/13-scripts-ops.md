# 13 — Scripts & operations

## Root `./jarvis` bash launcher

Sets **`PYTHONPATH=$REPO_ROOT/src`**, prefers **`.venv/bin/python3`**.

| Subcommand | Purpose |
|------------|---------|
| *(default)* / `test` / `t` | Smoke-import brain, voice, skills, smarthome, `KnowledgeBase` |
| `start` / `run` / `r` | Minimal “systems online” voice line |
| `chat` / `c` | Simple REPL: skills or `brain.think` |
| `voice` / `v` | Delegates to `chat` |
| `skills` / `s` | Lists skills |
| `home` | SmartHome demo calls |
| `auto` / `a` | Automation trigger listing |
| `hud` | `python -m jarvis.cli.hud` |
| `web` / `ui` | Opens browser (macOS `open`) + `python -m jarvis.cli.server` |
| `help` / `h` | Prints launcher help |

## Other shell scripts

| File | Role |
|------|------|
| `start.sh` | Dependency echo + service-oriented startup (project-specific) |
| `launcher.sh`, `jarvis.sh` | Thin wrappers (see comments inside files) |

## Docker Compose

**File:** `docker-compose.yml`.

Services:

- **ollama** — port `11434`, volume `ollama_data`
- **neo4j** — browser `7474`, Bolt `7687`, `NEO4J_AUTH=neo4j/password`

After `docker compose up -d`, export `NEO4J_*` and pull models with `ollama` on the host (or exec into the Ollama container).

## Knowledge graph eval

```bash
PYTHONPATH=src python -m jarvis.kg_eval
```

Runs canned questions through **`WorkPartner.hybrid_retrieve`**, prints per-query stats and simple aggregates. Exit non-zero if Neo4j unavailable.

## Logs

`start.sh` may `mkdir -p logs` under repo root. `config/jarvis.json` `logging.file` points at a path under `~/JARVIS/logs` in the sample config—adjust for your `JARVIS_HOME`.

## egg-info / packaging

After structural changes, run:

```bash
pip install -e .
```

to refresh `*.egg-info` / `dist-info` for installers and IDEs.
