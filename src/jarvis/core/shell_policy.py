#!/usr/bin/env python3
"""Detect shell strings that require explicit user consent before execution."""

import re
from typing import Pattern, Tuple

_PATTERNS: Tuple[Pattern[str], ...] = (
    re.compile(r"\bsudo\b", re.I),
    re.compile(r"\bdoas\b", re.I),
    re.compile(r"\bpkexec\b", re.I),
    re.compile(r"\bgksudo?\b", re.I),
    re.compile(r"(?:^|[;&|])\s*su(?:\s+|$|\s+-|\s+root\b)", re.I),
    re.compile(r"\bdiskutil\s+(erase|partitionDisk|reformat|randomDisk)\b", re.I),
    re.compile(r"\bdd\b.+\bof=/dev/", re.I),
    re.compile(r"\b(mkfs|fdisk)\b", re.I),
    re.compile(r"(?:^|[;&|])\s*(?:sudo\s+)?(?:shutdown|reboot|halt|poweroff)\b", re.I),
    re.compile(r"\bnetworksetup\s+-set\w", re.I),
    re.compile(r"\bcsrutil\b", re.I),
    re.compile(r"\bsoftwareupdate\b.+\b(-i\b|--install\b)", re.I),
    # Recursive delete (-r/-R) or combined -rf / -fr flags
    re.compile(r"\brm\s+-\S*[rR]\S*(\s+|$)", re.I),
    re.compile(r"\brm\s+-\S*f\S*r\S*\b", re.I),
    re.compile(r"\brm\s+-\S*r\S*f\S*\b", re.I),
    re.compile(r"\bchmod\s+\S+\s+.*/(etc|usr/sbin|System)\b", re.I),
    re.compile(r"\bchown\b.*\broot[:@]", re.I),
    re.compile(r">\s*/dev/[nr]?", re.I),
    re.compile(r"curl\b.+\|\s*(ba)?sh\b", re.I),
    re.compile(r"wget\b.+\|\s*(ba)?sh\b", re.I),
    # pmset writes (not read-only -g)
    re.compile(r"\bpmset\b.*\b-(a|b|c|d|u)\s", re.I),
)


def shell_requires_consent(command: str) -> bool:
    """True if the command should not run until the user explicitly approves."""
    if not command or not str(command).strip():
        return False
    text = str(command).strip()
    for pat in _PATTERNS:
        if pat.search(text):
            return True
    return False


REFUSAL_MESSAGE = (
    "Command refused, sir: elevated or destructive shell patterns detected. "
    "In the HUD, use `shell <command>` and type `yes` to approve that exact command once."
)
