# Copyright (c) 2026 Tejus Gupta
"""Strip Agentverse @mention prefixes from inbound chat text."""

from __future__ import annotations

import re

_AGENT_MENTION_RE = re.compile(
    r"^@(agent1q\S+|agent-[^\s]+)(?:\s+(.*))?$",
    re.DOTALL,
)


def strip_leading_agent_mention(
    text: str,
    *,
    agent_address: str | None = None,
    agent_handle: str | None = None,
) -> str:
    """Remove a leading ``@<agent address|handle>`` prefix when present.

    Agentverse clients may send ``@agent1q... Hello`` or ``@agent-handle Hello``.
    When no leading mention is detected, ``text`` is returned unchanged.
    """
    if not text:
        return text

    stripped = text.strip()
    if not stripped.startswith("@"):
        return text

    for target in (agent_address, agent_handle):
        if not target:
            continue
        prefix = f"@{target}"
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].lstrip()

    match = _AGENT_MENTION_RE.match(stripped)
    if match:
        return (match.group(2) or "").strip()

    return text
