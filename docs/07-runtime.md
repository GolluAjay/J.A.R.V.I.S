# 07 — Runtime (orchestrator & skills)

## Orchestrator (`jarvis.runtime.Orchestrator`)

**File:** `runtime/orchestrator.py`.

### Working directory

- **`cwd`**: set in constructor (`os.getcwd()` by default) or **`set_cwd(path)`** for subsequent commands.

### Command execution

- **`run_cmd(cmd)`**: refuses strings matching **`shell_requires_consent`** → returns `REFUSAL_MESSAGE` from `jarvis.core.shell_policy`.
- **`_run_raw(cmd)`**: internal `subprocess.run(..., shell=True, cwd=self.cwd, timeout=10)` without consent gate (used for read-only stats helpers).

### `process_command(user_input)`

Lowercases input. If the line equals or starts with a small set of utilities (`ls`, `pwd`, `date`, …), runs **`run_cmd`** with the raw line. Otherwise returns **`None`** so callers can fall through to the LLM/agent.

### Other methods

Rich set of macOS-oriented helpers: `get_system_stats`, `get_top_processes`, Docker listings, `open_app`, `volume_control`, `empty_trash`, etc. Many use **`_run_raw`** for read-only introspection.

---

## Skills (`jarvis.runtime.SkillsManager`)

**File:** `runtime/skills.py`.

### Skill directory

Defaults to **`jarvis.core.paths.skills_dir()`** unless overridden in constructor.

### Built-in registrations (`load_builtin_skills`)

| Name | Behavior |
|------|----------|
| `system` | Run shell command with consent check; 30s timeout; truncates stdout/stderr |
| `open` | `open -a <app>` (macOS) |
| `weather` | `curl` to `wttr.in` |
| `time` | `date` |
| `search` | DuckDuckGo instant answer API via `curl` |
| `knowledge` | Instantiates `KnowledgeBase`, `query` or status |

### API

- **`register(name, description, function)`**
- **`execute(skill_name, *args)`**
- **`list_skills()`** → dict name → description
- **`match_skill(query)`**: exact name or `name + " "` prefix match on lowercased input

Skills are invoked from **`GeneralPurposeAgent.process`** / **`process_grounded`** before broader routing, and from the **HUD** when the line matches a skill prefix.
