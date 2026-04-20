# 10 — Security

This project can **execute shell commands** and call **local network services** (Ollama, Neo4j, curl-based skills). Treat it as **high trust** software run only where you accept that risk.

## Shell consent policy

**Module:** `jarvis.core.shell_policy`.

### `shell_requires_consent(command) -> bool`

Returns true if the command string matches sensitive patterns, including (non-exhaustive):

- Privilege escalation: `sudo`, `doas`, `pkexec`, `su`, …
- Destructive disk ops: certain `diskutil`, `dd of=/dev/`, `mkfs`, …
- Power / lifecycle: `shutdown`, `reboot`, …
- Recursive / forced **`rm`**
- Dangerous redirects to `/dev/…`
- **`curl|sh`** / **`wget|sh`** style pipes
- Selected `pmset` write flags, `csrutil`, aggressive `networksetup` / `softwareupdate` patterns
- `chmod` / `chown` touching sensitive paths

### `REFUSAL_MESSAGE`

Human-readable refusal string returned instead of running the command. The HUD instructs users to use **`shell <command>`** and type **`yes`** once for a **pending** privileged command after review.

## Where consent is enforced

| Layer | Behavior |
|-------|----------|
| **`Orchestrator.run_cmd`** | Gate before `_run_raw` |
| **`SkillsManager`** `system` skill | Same gate + HUD-oriented hint |
| **`cli/server.py`** | Web UI checks before subprocess |
| **Automation** `command:` actions | Uses `shell_requires_consent` |

## HUD confirmation flow

When a suggested or gated command is staged:

- **`pending_shell`** holds the exact command string.
- **`pending_note`** may be `"pending_confirmation"` (see `_run_shell_capture` / grounded suggested actions).
- User must type **`yes`** (or aliases) to run once with **`force_allow=True`**.
- **`no` / `cancel`** clears without running.

## Secrets

- Default Neo4j password in code is **`password`**—change for any shared or networked deployment.
- Do not commit real API keys into `config/smart-home.json`; treat `JARVIS_HOME` config as sensitive.

## Model output

The LLM can still propose **`execute_command:`** lines. The agent strips those lines from **final grounded answers** (`_strip_execute_commands`) but tool-loop and HUD paths may execute them after orchestrator consent checks—keep models and prompts aligned with your threat model.
