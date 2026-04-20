"""Structured tool calls: JSON object {"tool": "<name>", "args": {...}}."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

ToolFn = Callable[[Dict[str, Any]], str]


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: ToolFn


_REGISTRY: Dict[str, ToolSpec] = {}


def register_tool(spec: ToolSpec) -> None:
    _REGISTRY[spec.name] = spec


def list_registered_tools() -> List[Dict[str, str]]:
    return [{"name": s.name, "description": s.description} for s in _REGISTRY.values()]


def _tool_now(_args: Dict[str, Any]) -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z").strip() or datetime.now().isoformat()


def _tool_calculator(args: Dict[str, Any]) -> str:
    from jarvis.agent.math_quick import calculator_tool_expr

    expr = (args.get("expr") or args.get("expression") or "").strip()
    if not expr:
        return "Error: pass args.expr, e.g. {\"tool\":\"calculator\",\"args\":{\"expr\":\"2+2\"}}"
    return calculator_tool_expr(expr)


def _tool_list_tools(_args: Dict[str, Any]) -> str:
    lines = [f"- {t['name']}: {t['description']}" for t in list_registered_tools()]
    return "Registered tools:\n" + "\n".join(lines) if lines else "No tools registered."


def register_builtin_tools() -> None:
    if _REGISTRY:
        return
    register_tool(ToolSpec("now", "Current local date and time.", _tool_now))
    register_tool(ToolSpec("calculator", "Safe arithmetic on args.expr (+ - * / **).", _tool_calculator))
    register_tool(ToolSpec("list_tools", "List available tool names.", _tool_list_tools))


def execute_tool_json(user_text: str) -> Optional[str]:
    """
    If user_text is a single JSON object with key \"tool\", run it and return text result.
    Otherwise return None (caller continues normal routing).
    """
    register_builtin_tools()
    raw = (user_text or "").strip()
    if not raw.startswith("{") or '"tool"' not in raw and "'tool'" not in raw:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    name = obj.get("tool")
    if not isinstance(name, str) or not name.strip():
        return None
    args = obj.get("args")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return "Error: args must be a JSON object"
    name = name.strip()
    spec = _REGISTRY.get(name)
    if not spec:
        return f"Error: unknown tool '{name}'. Use list_tools."
    try:
        return spec.handler(args)
    except Exception as exc:
        return f"Error running tool '{name}': {exc}"
