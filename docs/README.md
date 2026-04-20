# JARVIS documentation

Handbook for the **jarvis-assistant** project: local terminal HUD, Ollama LLM, optional Neo4j–backed retrieval, and a unified **GeneralPurposeAgent**.

Read in order the first time; use the index below for reference.

| # | Document | Contents |
|---|----------|----------|
| 00 | [Overview](00-overview.md) | Goals, stack, external services, terminology |
| 01 | [Installation](01-installation.md) | Python env, editable install, launchers |
| 02 | [Configuration](02-configuration.md) | `JARVIS_HOME`, `config/jarvis.json`, environment variables |
| 03 | [Architecture](03-architecture.md) | `src/jarvis` package map and request flows |
| 04 | [Agent](04-agent.md) | `GeneralPurposeAgent`: `process` vs `process_grounded` |
| 05 | [Knowledge graph & RAG](05-knowledge-graph.md) | Neo4j `WorkPartner`, ingest, hybrid retrieval |
| 06 | [LLM (brain)](06-llm-brain.md) | Ollama client, memory, intent, streaming |
| 07 | [Runtime](07-runtime.md) | Orchestrator and skills |
| 08 | [Terminal HUD](08-cli-hud.md) | Full HUD command reference |
| 09 | [Web UI](09-web-ui.md) | `jarvis-web` / `cli/server.py` |
| 10 | [Security](10-security.md) | Shell consent policy and HUD confirmation |
| 11 | [Voice](11-voice.md) | Input, output, macOS recorder helper |
| 12 | [Tools & retrieval extras](12-tools-retrieval.md) | JSON tools, query expansion, citation retry |
| 13 | [Scripts & ops](13-scripts-ops.md) | `./jarvis`, Docker, `kg_eval` |
| 14 | [Integrations & legacy](14-integrations-legacy.md) | Automation, smart home, `legacy/app_legacy` |

The canonical **quick start** for cloning and running remains in the repository [README.md](../README.md).
