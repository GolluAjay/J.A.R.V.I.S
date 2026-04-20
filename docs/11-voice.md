# 11 — Voice

**Package:** `jarvis.voice`.

## `VoiceInput` (`voice/voice_input.py`)

- Uses **sox** to record from default device to a temp WAV (configurable sample rate, channels).
- **`listen_for_command(timeout)`** → temp path or `None` if silent.
- **`record_audio(duration)`** → temp path.
- **`audio_to_text`**: placeholder string (no real STT in-tree); production notes in source suggest Whisper or similar.

## `VoiceOutput` (`voice/voice_output.py`)

- macOS **`say`** with voice **`Daniel`**, rate **180** WPM.
- **`speak(text, async_mode=True)`** spawns a thread for async TTS.
- **`set_voice`**, **`get_voices`** helpers.

## `MacSpeechRecorder` (`voice/stt.py`)

Previously duplicated the name `VoiceInput`; renamed for clarity.

- Records via sox, returns path or `None`; **`test_microphone`** helper.
- Not wired as the default STT pipeline in the HUD; kept as a **helper / demo** module.

## Launcher usage

Root **`./jarvis`** `start` / `chat` snippets import **`VoiceOutput`** for spoken confirmations.

## Config note

`config/jarvis.json` → `features.voice` describes desired STT/TTS technologies for product direction; the Python modules above are simpler than that full vision.
