# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Iterable

LEGACY_DIVIDER = "━━━━━━━━━━━━━━━━━━"
TACTICAL_DIVIDER = "──────────────"

PLAIN_CARD_PREFIXES: tuple[tuple[str, str], ...] = (
    ("💎 BLACK CROWN PREMIUM", "PREMIUM"),
    ("🔗 ОДНОРАЗОВАЯ ПРИВЯЗКА", "ACCOUNT LINK"),
    ("🔐 Привязка доступна", "ACCOUNT SECURITY"),
    ("⚠️ Подтверди отвязку", "ACCOUNT SECURITY"),
)


def _strip_edges(lines: Iterable[str]) -> list[str]:
    result = list(lines)
    while result and not result[0].strip():
        result.pop(0)
    while result and not result[-1].strip():
        result.pop()
    return result


def _compact_blank_lines(lines: Iterable[str]) -> list[str]:
    result: list[str] = []
    previous_blank = False
    for raw in lines:
        line = raw.rstrip()
        blank = not line.strip()
        if blank and previous_blank:
            continue
        result.append(line)
        previous_blank = blank
    return _strip_edges(result)


def tactical_card(body: str, *, channel: str = "SYSTEM", state: str | None = None) -> str:
    """Render one restrained BLACK CROWN text card without Telegram parse modes."""
    clean_body = "\n".join(_compact_blank_lines(str(body or "").replace("\r\n", "\n").split("\n")))
    label = str(channel or "SYSTEM").strip().upper()[:24] or "SYSTEM"
    header = f"◼ BLACK CROWN OPS // {label}"
    if state:
        header = f"{header} · {str(state).strip().upper()[:18]}"
    return f"{header}\n{TACTICAL_DIVIDER}\n{clean_body}" if clean_body else header


def _start_body() -> str:
    return (
        "AI-оператор для Warzone · BO7 · BF6 · Zombies.\n\n"
        "Быстрый запрос:\n"
        "• «Почему я умер на ротации?»\n"
        "• «Собери тренировку на 20 минут»\n"
        "• «Разбери этот VOD»\n\n"
        "Выбери модуль на панели ниже или опиши ситуацию одной строкой."
    )


def _legacy_mode(header: str) -> str:
    return "COACH" if "КОУЧ" in header.upper() else "TEAMMATE"


def _unwrap_legacy(lines: list[str]) -> tuple[str, list[str]] | None:
    if len(lines) < 3:
        return None
    header = lines[0].strip()
    if not header.startswith(("🖤 BLACK CROWN OPS", "👑 BLACK CROWN OPS")):
        return None

    try:
        first_divider = lines.index(LEGACY_DIVIDER, 1)
    except ValueError:
        return None

    body_end = len(lines)
    if lines and lines[-1].strip().startswith(("— BCO", "— BLACK CROWN OPS")):
        body_end -= 1
    if body_end > first_divider and lines[body_end - 1].strip() == LEGACY_DIVIDER:
        body_end -= 1

    body = _compact_blank_lines(lines[first_divider + 1 : body_end])
    return _legacy_mode(header), body


def _unwrap_plain_card(lines: list[str]) -> tuple[str, list[str]] | None:
    if not lines:
        return None
    first = lines[0].strip()
    for prefix, channel in PLAIN_CARD_PREFIXES:
        if first.startswith(prefix):
            body = _compact_blank_lines(lines[1:])
            if not body and first != prefix:
                body = [first[len(prefix) :].lstrip(" :—-")]
            return channel, body
    return None


def polish_telegram_text(text: str) -> str:
    """
    Convert legacy BCO chrome and selected account panels into compact cards.

    Non-BCO messages, source text and code blocks are returned unchanged.
    """
    raw = str(text or "")
    if not raw:
        return raw

    normalized = raw.replace("\r\n", "\n")
    lines = normalized.split("\n")

    unwrapped = _unwrap_legacy(lines)
    if unwrapped:
        mode, body_lines = unwrapped
        body = "\n".join(body_lines)
        if body.startswith("BLACK CROWN OPS — это искусственный разум"):
            body = _start_body()
        return tactical_card(body, channel=mode)

    plain_card = _unwrap_plain_card(lines)
    if plain_card:
        channel, body_lines = plain_card
        return tactical_card("\n".join(body_lines), channel=channel)

    return raw
