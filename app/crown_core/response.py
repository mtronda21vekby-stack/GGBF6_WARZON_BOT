from __future__ import annotations

import re
import unicodedata


_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
_CODE_BLOCK = re.compile(r"```.*?(?:```|$)", re.DOTALL)
_MARKDOWN = re.compile(r"(?:```|`|\*\*|__|~~|^#{1,6}\s*)", re.MULTILINE)
_URL = re.compile(r"https?://\S+")
_SPACE = re.compile(r"\s+")
_SENTENCE = re.compile(r".+?(?:[.!?…]+(?:[\"'»)]*)|$)(?:\s+|$)", re.DOTALL)


def spoken_text(display_text: str) -> str:
    """Conservative, language-neutral projection for client speech synthesis."""

    value = _CODE_BLOCK.sub(" ", str(display_text or ""))
    value = _MARKDOWN_LINK.sub(r"\1", value)
    value = _URL.sub(" ", value)
    value = _MARKDOWN.sub("", value)
    value = value.replace("•", ". ").replace("—", " — ")
    safe_lines: list[str] = []
    for source_line in value.splitlines():
        line = source_line.strip()
        upper = line.upper()
        if upper in {"— BCO", "- BCO"}:
            continue
        line = re.sub(r"BLACK\s+CROWN\s+OPS", " ", line, flags=re.IGNORECASE)
        if line and set(line) <= {"━", "─", "-", "_", "=", " "}:
            continue
        line = "".join(
            character
            for character in line
            if unicodedata.category(character) not in {"So", "Cs", "Co"}
        )
        if any(character.isalnum() for character in line):
            safe_lines.append(line)
    return _SPACE.sub(" ", " ".join(safe_lines)).strip()


class SpokenSentenceAccumulator:
    """Turns cumulative model partials into ordered, non-duplicated speech units."""

    def __init__(self) -> None:
        self._cumulative = ""
        self._spoken_characters = 0

    def update(self, cumulative: str) -> tuple[str, list[str]]:
        current = str(cumulative or "")
        if current.startswith(self._cumulative):
            display_delta = current[len(self._cumulative):]
        else:
            display_delta = ""
            self._spoken_characters = 0
        self._cumulative = current

        prepared = spoken_text(current)
        complete_end = 0
        for match in _SENTENCE.finditer(prepared):
            segment = match.group(0).strip()
            if segment and segment[-1:] in ".!?…»\")'":
                complete_end = match.end()
        ready = prepared[:complete_end]
        if len(ready) <= self._spoken_characters:
            return display_delta, []
        new = ready[self._spoken_characters:].strip()
        self._spoken_characters = len(ready)
        return display_delta, [new] if new else []

    def finish(self, final_text: str) -> tuple[str, list[str], str]:
        current = str(final_text or "")
        display_delta = current[len(self._cumulative):] if current.startswith(self._cumulative) else ""
        prepared = spoken_text(current)
        tail = prepared[self._spoken_characters:].strip()
        self._cumulative = current
        self._spoken_characters = len(prepared)
        return display_delta, [tail] if tail else [], prepared
