"""Optional LLM-based query expansion before hybrid retrieval (stateless Ollama call)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def _ollama_generate_once(prompt: str, max_tokens: int = 64) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = os.environ.get("JARVIS_CHAT_MODEL", "llama3.2:3b")
    url = f"{host}/api/generate"
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "top_p": 0.9, "num_predict": max_tokens},
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return (data.get("response") or "").strip()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return ""


def maybe_expand_query_for_retrieval(question: str, enabled: bool) -> str:
    """One short rewrite for lexical/vector search; returns original on skip/failure."""
    q = (question or "").strip()
    if not enabled or len(q) < 8:
        return q
    prompt = (
        "Rewrite the following user message into ONE short search query for a personal "
        "knowledge base (keywords only, no quotes, max 25 words). Output only the query line.\n\n"
        f"Message: {q}\n\nSearch query:"
    )
    out = _ollama_generate_once(prompt)
    line = out.split("\n")[0].strip().strip('"').strip("`")
    if 3 <= len(line) <= 400 and not line.lower().startswith("i cannot"):
        return line
    return q
