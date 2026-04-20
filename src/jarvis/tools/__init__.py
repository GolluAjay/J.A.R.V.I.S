"""Pluggable structured tools (JSON) for the general-purpose agent."""

from jarvis.tools.registry import (
    execute_tool_json,
    list_registered_tools,
    register_builtin_tools,
)

__all__ = ("execute_tool_json", "list_registered_tools", "register_builtin_tools")
