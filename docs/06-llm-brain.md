# 06 — LLM (brain)

Class: **`jarvis.llm.JARVISBrain`** (`llm/brain.py`).

## Construction

- **`host`**: defaults from `os.environ.get("OLLAMA_HOST", "http://localhost:11434")` (stripped trailing slash).
- **`model`**: defaults from `os.environ.get("JARVIS_CHAT_MODEL", "llama3.2:3b")`.

These align with `apply_runtime_settings()` from `config/jarvis.json` when env is unset.

## System prompt

Loaded once in `__init__` via `jarvis.core.paths.system_prompt_path()` → `config/system-prompt.txt`. Fallback string is a short J.A.R.V.I.S. persona if the file is missing.

## System context block

`_get_system_context(cwd)` builds a multi-line snapshot: time, cwd, hostname, CPU (via `top`), memory (`sysctl` + `vm_stat`), battery (`pmset`). Cached ~30 seconds to limit subprocess churn.

## Prompt assembly (`_build_prompt`)

Sections concatenated:

1. System prompt (+ optional **tool execution protocol** paragraph when `enable_tools=True`).
2. **Current system state**.
3. Optional **extra_context** (RAG or tool-loop results).
4. **Recent conversation** from `deque` history (assistant lines truncated to 200 chars).
5. Current user message with `JARVIS:` continuation marker.

## API calls

- **Non-streaming**: `POST {host}/api/generate` with `"stream": false`, parse JSON `response` field.
- **Streaming**: `stream: true`, read bytes, split on newlines, parse JSON chunks for `response` tokens until `done`.

Errors surface as short user-facing strings (Ollama down, timeout, generic connection error).

## Memory

- **`remember(role, message)`**: appends to `deque(maxlen=10)` (`MAX_HISTORY`).
- **`clear_memory`**, **`get_memory_summary`**.

`think` / `think_stream` remember using `memory_user_text` when provided (so the stored user line can differ from the long grounded prompt).

## Intent detection (`detect_intent`)

Returns one of: **`command`**, **`action`**, **`query`**, **`chat`**.

Heuristics include prefixes (`run `, `list `, …), CLI tokens (`ls`, `pwd`, …), action verbs (`open `, `launch `, …), question words / trailing `?`.

Used by **`GeneralPurposeAgent`** and the **HUD** router.

## Tool protocol (when tools enabled)

The system prompt instructs the model to output lines:

```text
execute_command: <shell command>
```

The **agent**’s `_process_tool_loop` parses these with a regex and runs commands through the orchestrator. The **HUD** has a related path when the agent is unavailable (legacy brain-only branch).

Grounded calls use **`enable_tools=False`** so this paragraph is omitted from the prompt.

## Interactive REPL

`JARVISBrain.chat()` runs a stdin loop with streaming, `exit`, `clear`, `memory` commands—useful for debugging Ollama without the HUD.
