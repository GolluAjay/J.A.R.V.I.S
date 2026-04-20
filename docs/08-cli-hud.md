# 08 — Terminal HUD

**Entry:** `jarvis-hud`, `./jarvis hud`, or `python -m jarvis` → `jarvis.cli.hud:main`.

## Startup (`HUD.init_modules`)

Lazy-loads (with try/except per module):

- **Brain** — `JARVISBrain` (Ollama)
- **Orchestrator** — cwd set to HUD `self.cwd`
- **Skills** — `SkillsManager`
- **Agent** — `GeneralPurposeAgent(brain=…, orchestrator=…, skills=…)` sharing those instances
- **SmartHome** — `SmartHome` from integrations

Best-effort **`work_partner.bootstrap_schema()`** when Neo4j is up.

## Screen layout (`render`)

- ASCII header and boxes: **system status**, **module health**, **quick commands**, **session** (history length, cwd, hint).

## Command dispatch (`handle_command`)

Processed in order (first match wins). Summary below mirrors in-HUD **`help`**.

### Session / HUD

| Input | Action |
|-------|--------|
| `exit`, `quit`, `q` | Quit |
| `clear` | Redraw full HUD |
| `help`, `h`, `?` | Long help text |
| `history` | Show prior commands |

### System

| Input | Action |
|-------|--------|
| `status`, `stats`, `sys` | System status box |
| `ps`, `top`, `processes` | Top processes |
| `kill <pid>` | Send kill |
| `battery`, `batt` | `pmset -g batt` |
| `wifi`, `network`, `net` | WiFi / fallback command |
| `docker`, `containers` | `docker ps` style |
| `docker …` | Passthrough with optional `\| check …` brain verification branch |
| `ip`, `myip` | Public IP via curl |

### Shell

| Input | Action |
|-------|--------|
| `shell <cmd>`, `$ <cmd>`, `! <cmd>` | Run via orchestrator path with consent checks; optional `\| check …` suffix for AI verification of output |

### Privileged confirmation

| Input | Action |
|-------|--------|
| `yes`, `y`, `confirm`, `run` | If a shell command is **pending confirmation**, execute once with `force_allow=True` |
| `no`, `n`, `cancel`, `abort` | Clear pending |

### Skills & smart home

| Input | Action |
|-------|--------|
| `skills`, `skill` | List registered skills |
| Skill names (`time`, `weather London`, …) | Routed via `SkillsManager` |
| `volume <0-100>` | SmartHome volume |

### Brain memory

| Input | Action |
|-------|--------|
| `memory`, `mem` | Show deque summary |
| `forget`, `clear memory`, `reset` | `brain.clear_memory()` |

### Knowledge partner

| Input | Action |
|-------|--------|
| `ask …`, `partner …` | Grounded question path (`_handle_ask` → `process_grounded`) |
| `ingest <path>` | File ingest into KB/graph |
| `kg …` | Subcommands such as `kg status`, `kg bootstrap` |

### Fallback routing

1. **`detect_intent`** + orchestrator for command/action-shaped lines (and a second orchestrator pass for other intents when `process_command` returns non-`None`).
2. Else **`GeneralPurposeAgent.process_grounded`** with pretty-print of confidence, timings, conflicts, citations, suggested actions.
3. If no agent but brain exists: **`think_stream`** plus optional handling of embedded `execute_command:` lines.

## Grounded payload display (`_print_grounded_payload`)

Prints answer, confidence, timing key/values (ms), conflicts list, citations, suggested actions (may set **`pending_shell`** for user-confirmed follow-up).

## Colors / terminal

Uses ANSI constants at module top; width adapts to `shutil.get_terminal_size`.
