# 04 — General purpose agent

Class: **`jarvis.agent.GeneralPurposeAgent`** (`agent/gp_agent.py`).

## Constructor dependencies

| Dependency | Default | Role |
|------------|---------|------|
| `brain` | `JARVISBrain()` | LLM + memory |
| `orchestrator` | `Orchestrator()` | Shell execution |
| `skills` | `SkillsManager()` | Named quick commands |
| `work_partner` | `WorkPartner()` | Neo4j hybrid retrieval (may be offline) |

## `process(user_input, cwd=None)` — chat-style path

High-level order:

1. Empty input → polite refusal string.
2. **Skill match** → execute skill, append to brain history, return.
3. **User memory fact** (`extract_user_memory_fact`) → persist to `knowledge/user_preferences.txt`, re-index via `KnowledgeBase.add_document`, remember, return.
4. **`execute_tool_json`** — if the line is a JSON tool object, run registry handler, remember, return.
5. **`try_answer_arithmetic`** — deterministic math for phrasing like “what is 2+2”, remember, return.
6. **`detect_intent`**: for `command` / `action`, **`orchestrator.process_command`**; if non-`None`, remember and return.
7. Else **`_process_tool_loop`**: brain may emit `execute_command: …` lines; orchestrator runs them; loop up to `max_iterations` (default 2).
8. Remember user + assistant; return final string.

## `process_grounded(user_input, cwd=None, stream=False, force_retrieval=False)` — RAG path

Returns a **dict** (not a plain string) with keys including:

- `answer`, `citations`, `confidence`, `conflicts`, `suggested_actions`, `evidence`, `timings_ms`

Order (simplified):

1. Same early exits as `process` for **skills**, **memory facts**, **JSON tools**, **arithmetic** (each returns a dict-shaped payload).
2. **Intent** + **`force_retrieval`**: retrieval used when `force_retrieval` or intent in `("query", "chat")`.
3. **`command` / `action`** → orchestrator attempt; if result, return dict with that answer.
4. If Neo4j unavailable **or** retrieval not selected → `_process_tool_loop` + dict with empty citations/evidence.
5. Else **`_ensure_kg`** (best-effort schema), optional **query expansion** (`maybe_expand_query_for_retrieval` + `get_settings().retrieval_query_expand`), then **`work_partner.hybrid_retrieve(retrieve_query)`**.
6. **Confidence gate**: if `confidence_from_evidence` &lt; `0.35`, return abstention message with conflicts if any.
7. **`build_grounded_prompt(user_input, evidence)`** — user’s original question text is preserved for the prompt even when retrieval used an expanded query.
8. **`brain.think`** or **`think_stream`** with `enable_tools=False` for grounded prompts.
9. Non-streaming: optional **citation reflect** — if `reflect_retry` and answer lacks evidence ids, second `think` with `append_citation_retry_instruction`.
10. Strip accidental `execute_command:` lines from model output; build citation list from evidence; remember; return dict.

## Constants worth knowing

- **`USER_PREFERENCES_FILENAME`**: `"user_preferences.txt"` under `knowledge_dir`.
- Memory regexes: phrases like “remember that …”, “note to self: …”, etc. (see `_MEMORY_PATTERNS` in source).

## `chat(prompt, cwd=None)`

Alias for `process(prompt, cwd=cwd)`.

## Module-level `test()`

Prints a few canned `process` calls; runnable via `python -m jarvis.agent.gp_agent` if you add `if __name__` or invoke from REPL.
