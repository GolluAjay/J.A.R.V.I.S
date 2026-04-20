# 09 — Web UI

**Entry:** `jarvis-web` or `./jarvis web` → **`jarvis.cli.server`**.

## HTML location

Served from **`jarvis.core.paths.html_index_path()`**:

- `JARVIS_HOME / ui / index.html`

Ensure that file exists under your configured home (repo ships `ui/` at project root; if `JARVIS_HOME` points elsewhere, copy or symlink `ui/index.html` there).

## Port selection

`get_port(default=8080)` probes **8080 … 8089** for a bindable TCP port; first free wins.

The `./jarvis web` launcher may **`open http://localhost:8080`** before the server picks an alternate port—if the page fails to load, check console output for the actual bound port.

## Behavior (high level)

`server.py` implements an **`http.server`**-style handler with JSON endpoints and orchestrator-backed actions (system stats, processes, file ops, etc.). Many code paths mirror macOS shell utilities similar to the HUD.

## Shell consent

Imports **`shell_requires_consent`** and **`REFUSAL_MESSAGE`** from `jarvis.core.shell_policy` for dangerous command strings.

## Privileged action set

Module constant **`_PRIVILEGED_ACTIONS`** includes strings like `reboot`, `shutdown`, `empty_trash`, `clear_cache`—used to gate certain web-triggered behaviors (see source for exact HTTP contract).
