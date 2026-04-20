# 00 — Overview

## What this project is

A **local-first** assistant that combines:

- A **terminal HUD** (`jarvis.cli.hud`) for system status, shell control, skills, and chat.
- An **Ollama**-backed LLM (`jarvis.llm.JARVISBrain`) with short conversation memory and optional tool lines (`execute_command: …`).
- A **general-purpose agent** (`jarvis.agent.GeneralPurposeAgent`) that routes skills, user “memory” facts, JSON tools, quick math, orchestrator commands, and—when Neo4j is available—**grounded** answers with citations and confidence.
- Optional **Neo4j** knowledge graph + embeddings (`jarvis.graph.work_partner.WorkPartner`) for hybrid retrieval over ingested text.
- File-backed knowledge indexing (`jarvis.rag.KnowledgeBase`) that can push content into the graph when available.

Python package name on PyPI-style metadata: **jarvis-assistant** (`pyproject.toml`). Import path: **`jarvis`**.

## What it is not

- Not a hosted SaaS product in this repo (you self-host Ollama and Neo4j).
- Not guaranteed cross-platform for every feature: much of the HUD and orchestrator assume **macOS**-style commands (`top`, `osascript`, `pmset`, etc.).

## External dependencies

| Service | Role | Default |
|--------|------|--------|
| **Ollama** | Chat and embedding HTTP API | `OLLAMA_HOST` (e.g. `http://localhost:11434`) |
| **Neo4j** | Graph + vector index for grounded retrieval | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` |

Optional: **sox** for audio capture in voice helpers; **curl** for skills and smart-home stubs.

## Terminology

| Term | Meaning |
|------|---------|
| **Brain** | `JARVISBrain`: Ollama `/api/generate`, sliding history, intent hints |
| **Work partner** | `WorkPartner`: Neo4j + hybrid search + grounded prompt pieces |
| **Grounded** | Answers driven by retrieved evidence with citation metadata |
| **HUD** | Full-screen terminal UI loop in `cli/hud.py` |
| **JARVIS_HOME** | Resolved root for `knowledge/`, `config/`, etc. (see Configuration) |

## Bootstrap order

Importing `jarvis` runs `apply_runtime_settings()` in `jarvis/__init__.py` so defaults from `config/jarvis.json` are merged into the environment **before** modules that read `os.environ` at import time (for example `graph/work_partner.py`).
