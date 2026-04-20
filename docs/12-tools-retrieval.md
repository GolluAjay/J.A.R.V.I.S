# 12 — Structured tools & retrieval extras

## JSON tools (`jarvis.tools`)

### Wire format

A **single line** of JSON:

```json
{"tool": "<name>", "args": { ... }}
```

If the line is not valid JSON or lacks a string **`tool`** key, **`execute_tool_json`** returns **`None`** and the agent continues normal routing.

### Built-in tools (`tools/registry.py`)

| Tool | Args | Behavior |
|------|------|----------|
| `now` | (ignored) | Local timestamp string |
| `calculator` | `expr` or `expression` | Delegates to **`jarvis.agent.math_quick.calculator_tool_expr`** |
| `list_tools` | (ignored) | Text list of registered tools |

Registration is lazy (`register_builtin_tools` idempotent).

---

## Query expansion (`jarvis.retrieval`)

**Function:** `maybe_expand_query_for_retrieval(question, enabled)`.

- When **`enabled`** is false or the question is short, returns the original string.
- When true, performs a **stateless** `POST /api/generate` to Ollama (see `retrieval/expand.py`) with a tight prompt: rewrite into a short keyword search query.
- On failure or suspicious output, returns the original question.

Controlled by **`JarvisRuntimeSettings.retrieval_query_expand`** ← `features.retrieval.expand_queries` in `jarvis.json`.

---

## Grounding helpers (`jarvis.agent.grounding`)

### `answer_covers_evidence_ids(answer, evidence)`

True if any **`evidence_id`** substring appears in the answer text (or if evidence list empty).

### `append_citation_retry_instruction(base_prompt)`

Appends a reminder block requiring bracket tags like **`[E1]`** tied to evidence blocks.

Used in **`GeneralPurposeAgent.process_grounded`** when **`reflect_retry`** is on and the first answer lacks citations.

---

## Timings

`process_grounded` **`timings_ms`** may include:

- From expansion: `query_expand_ms`, optionally `retrieval_query` when rewritten.
- From `hybrid_retrieve`: `embed_ms`, `graph_ms`, `vector_ms`, `lexical_ms`, `merge_ms`, …
- From reflect pass: `reflect_retry_ms`
