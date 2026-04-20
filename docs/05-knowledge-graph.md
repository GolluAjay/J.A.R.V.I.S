# 05 — Knowledge graph & RAG

Two related layers:

1. **`jarvis.rag.KnowledgeBase`** — file-based `.index.json`, paragraph chunking, optional push into Neo4j.
2. **`jarvis.graph.work_partner.WorkPartner`** — Neo4j schema, embeddings, **hybrid retrieval**, grounded prompt helpers.

## Neo4j connection

`WorkPartner.__init__` reads (with defaults from module-level constants loaded from env at import time):

| Env | Default |
|-----|---------|
| `NEO4J_URI` | `bolt://localhost:7687` |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | `password` |
| `OLLAMA_HOST` | `http://localhost:11434` |
| `JARVIS_EMBED_MODEL` | `nomic-embed-text` |

If the Python **neo4j** driver is missing or connect fails, `is_available()` is false and `status()` explains why.

## Hybrid retrieval (conceptual)

`WorkPartner.hybrid_retrieve(question, top_k=8, …)` roughly:

1. **Embed** the question via Ollama embedding API.
2. **Graph neighborhood** search from lexical/graph cues.
3. **Vector** search against the Neo4j vector index when ready.
4. **Lexical** search.
5. **Merge** and assign evidence ids (`EvidenceItem` list).

Timing breakdown is returned in milliseconds per stage (keys like `embed_ms`, `graph_ms`, …).

## Evidence model

**`EvidenceItem`** fields include: `evidence_id`, `source_id`, `source_type`, `chunk_index`, `text`, `score`, optional entity/relation ids, timestamp.

Used by:

- Grounded prompt construction.
- Citation list in `process_grounded` response.
- **`jarvis.agent.grounding.answer_covers_evidence_ids`** for reflect/retry.

## Ingestion (HUD)

- Command **`ingest <path>`** (`cli/hud.py` → `_handle_ingest`): reads a text file, indexes into the knowledge base / graph as implemented there.
- **`KnowledgeBase.add_document`**: updates local index; if `work_partner.is_available()`, calls `bootstrap_schema` and `index_document_from_text`.

## Schema bootstrap

- **`WorkPartner.bootstrap_schema`**: constraints/indexes for first-run.
- HUD command **`kg bootstrap`** and **`kg status`** route through `_handle_kg_command` for operator visibility.

## Evaluation helper

**`python -m jarvis.kg_eval`** (`jarvis/kg_eval.py`): offline-ish latency/confidence smoke over fixed question strings against a live `WorkPartner`. Requires Neo4j up and populated for meaningful scores.

## Docker

`docker-compose.yml` at repo root defines **ollama** and **neo4j** services; see [Scripts & ops](13-scripts-ops.md).
