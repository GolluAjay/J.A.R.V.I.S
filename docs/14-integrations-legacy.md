# 14 — Integrations & legacy

## Smart home (`jarvis.integrations.smarthome`)

**Class:** `SmartHome`.

- On init, reads **`jarvis.core.paths.smarthome_config_path()`** → `config/smart-home.json` if present for Hue bridge + API key fields.
- Methods: **`hue_lights`**, **`hue_set_light`**, **`volume`** (osascript), **`mute`**, **`wifi_status`**, **`screen_brightness`**, **`dim_display`** (best-effort; some require extra CLI tools).

Used by the HUD for **`volume`** shortcuts and WiFi display.

## Automation (`jarvis.integrations.automation`)

**Class:** `Automation`.

- Config path: **`automation_config_path()`** → `config/automation.json` (or constructor override).
- JSON schema: list of **`triggers`** with `name`, `schedule` (e.g. `HH:MM`), `action`, `enabled`, `last_run`.
- **`execute_action`**: supports prefixes `say:`, `notify:`, `command:` (command branch uses shell consent policy).
- **`start`**: background thread loop checking triggers every 30 seconds (very simple scheduler).

## Legacy app (`jarvis.legacy.app_legacy`)

**Class:** `JARVIS` wires:

- `GeneralPurposeAgent`
- `VoiceOutput`
- `VoiceInput`

and provides a text menu (`voice`, `chat`, `test`, `exit`). Prefer **`cli/hud`** for new workflows; keep this module for reference or minimal demos.

Import example:

```python
from jarvis.legacy.app_legacy import JARVIS
```
