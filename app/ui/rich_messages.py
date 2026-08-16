# -*- coding: utf-8 -*-
from __future__ import annotations

from html import escape
from typing import Iterable

TACTICAL_PREFIX = "◼ BLACK CROWN OPS //"
TACTICAL_DIVIDER = "──────────────"
_MAX_RICH_SOURCE_CHARS = 48_000


def _strip_edges(lines: Iterable[str]) -> list[str]:
    result = [str(line).rstrip() for line in lines]
    while result and not result[0].strip():
        result.pop(0)
    while result and not result[-1].strip():
        result.pop()
    return result


def _groups(lines: Iterable[str]) -> list[list[str]]:
    result: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if not str(line).strip():
            if current:
                result.append(current)
                current = []
            continue
        current.append(str(line).strip())
    if current:
        result.append(current)
    return result


def _bullet(line: str) -> str | None:
    stripped = str(line or "").strip()
    for prefix in ("• ", "- ", "— "):
        if stripped.startswith(prefix) and len(stripped) > len(prefix):
            return stripped[len(prefix) :].strip()
    return None


def _render_group(group: list[str]) -> str:
    if not group:
        return ""

    bullets = [_bullet(line) for line in group]
    if all(item is not None for item in bullets):
        items = "".join(f"<li>{escape(item or '')}</li>" for item in bullets)
        return f"<ul>{items}</ul>"

    if len(group) > 1 and group[0].endswith(":") and all(item is not None for item in bullets[1:]):
        heading = escape(group[0][:-1].strip())
        items = "".join(f"<li>{escape(item or '')}</li>" for item in bullets[1:])
        return f"<p><b>{heading}</b></p><ul>{items}</ul>"

    # Rich-message HTML is block-oriented. A short paragraph per source line
    # produces stable spacing across Telegram iOS, Android and Desktop.
    return "".join(f"<p>{escape(line)}</p>" for line in group)


def tactical_rich_message(text: str) -> dict | None:
    """Convert a polished BLACK CROWN card into safe InputRichMessage HTML."""
    raw = str(text or "").replace("\r\n", "\n")
    if not raw.startswith(TACTICAL_PREFIX):
        return None

    lines = _strip_edges(raw[:_MAX_RICH_SOURCE_CHARS].split("\n"))
    if not lines:
        return None

    title = lines.pop(0).removeprefix("◼ ").strip()
    if lines and lines[0].strip() == TACTICAL_DIVIDER:
        lines.pop(0)
    lines = _strip_edges(lines)

    html_parts = [f"<h3>{escape(title)}</h3>", "<hr/>"]
    for group in _groups(lines):
        rendered = _render_group(group)
        if rendered:
            html_parts.append(rendered)

    return {
        "html": "".join(html_parts),
        "skip_entity_detection": True,
    }
