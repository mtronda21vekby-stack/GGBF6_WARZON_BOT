# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urljoin, urlparse

import httpx

from app.services.brain.intents import Intent
from app.services.brain.knowledge_context import (
    KnowledgeConfidence,
    KnowledgeContext,
    KnowledgeFact,
    KnowledgeRequest,
)


log = logging.getLogger("bco.live_knowledge")

_ALLOWED_HOSTS = {"callofduty.com", "www.callofduty.com", "ea.com", "www.ea.com"}
_COD_INDEX = "https://www.callofduty.com/patchnotes"
_BF6_INDEX = "https://www.ea.com/games/battlefield/battlefield-6/news"
_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(\d{1,2}),\s+(20\d{2})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OfficialDocument:
    game: str
    title: str
    url: str
    published: str
    blocks: tuple[str, ...]
    fetched_at: str


@dataclass
class _CacheEntry:
    document: OfficialDocument
    expires_at: float


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        values = dict(attrs)
        self._href = str(values.get("href") or "").strip() or None
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._href is None:
            return
        text = " ".join(" ".join(self._text).split())
        self.links.append((self._href, text))
        self._href = None
        self._text = []


class _VisibleTextParser(HTMLParser):
    _BLOCKS = {"h1", "h2", "h3", "h4", "p", "li", "article", "section", "div", "br"}
    _IGNORE = {"script", "style", "svg", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._buf: list[str] = []
        self._ignore_depth = 0

    def _flush(self) -> None:
        text = " ".join(" ".join(self._buf).split()).strip()
        if text and (not self.blocks or self.blocks[-1] != text):
            self.blocks.append(text)
        self._buf = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in self._IGNORE:
            self._ignore_depth += 1
            return
        if self._ignore_depth == 0 and tag in self._BLOCKS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._ignore_depth == 0:
            self._buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._IGNORE:
            if self._ignore_depth:
                self._ignore_depth -= 1
            return
        if self._ignore_depth == 0 and tag in self._BLOCKS:
            self._flush()

    def close(self) -> None:
        super().close()
        self._flush()


def _game_key(request: KnowledgeRequest) -> str | None:
    raw = str(request.profile.get("game") or "Warzone").lower().replace(" ", "")
    if raw in {"warzone", "wz", "warzone2"}:
        return "warzone"
    if raw in {"bo7", "blackops7"}:
        return "bo7"
    if raw in {"bf6", "battlefield", "battlefield6"}:
        return "bf6"
    return None


def _is_allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in _ALLOWED_HOSTS


def _candidate_matches(game: str, href: str, text: str) -> bool:
    value = f"{href} {text}".lower()
    if game == "warzone":
        return "/patchnotes/" in href.lower() and "warzone" in value
    if game == "bo7":
        return (
            "/patchnotes/" in href.lower()
            and ("black-ops-7" in value or "black ops 7" in value)
            and "warzone" not in value
        )
    if game == "bf6":
        return "battlefield-6-game-update-" in value
    return False


def _published_date(blocks: list[str], raw_html: str) -> str:
    haystack = "\n".join(blocks[:80]) + "\n" + raw_html[:120000]
    match = _DATE_RE.search(haystack)
    if not match:
        iso = re.search(r'"datePublished"\s*:\s*"(20\d{2}-\d{2}-\d{2})', raw_html)
        return iso.group(1) if iso else ""
    try:
        value = datetime.strptime(match.group(0), "%B %d, %Y")
        return value.date().isoformat()
    except ValueError:
        return ""


def _document_title(game: str, blocks: list[str], fallback: str) -> str:
    needles = {
        "warzone": ("warzone", "patch notes"),
        "bo7": ("black ops 7", "patch notes"),
        "bf6": ("battlefield 6", "game update"),
    }[game]
    for block in blocks[:50]:
        low = block.lower()
        if all(x in low for x in needles):
            return block[:240]
    return fallback[:240] or f"Official {game} update"


def _tokens(text: str) -> set[str]:
    stop = {
        "что", "какая", "какой", "какие", "сейчас", "последний", "последнего", "патч", "мета",
        "the", "and", "for", "with", "from", "this", "that", "current", "latest", "meta", "patch",
    }
    return {x for x in re.findall(r"[a-zа-я0-9-]{3,}", (text or "").lower()) if x not in stop}


def _select_blocks(document: OfficialDocument, request: KnowledgeRequest, limit: int = 16) -> list[str]:
    query = _tokens(request.text)
    if request.intent.intent == Intent.META_CURRENT:
        priority = {
            "weapon", "weapons", "damage", "range", "recoil", "attachment", "attachments", "increased",
            "decreased", "adjusted", "buff", "nerf", "rifle", "smg", "lmg", "shotgun", "pistol",
        }
    else:
        priority = {
            "update", "weapons", "weapon", "maps", "map", "modes", "mode", "player", "movement",
            "damage", "balance", "battle royale", "resurgence", "ranked", "zombies", "changelog",
        }

    junk = (
        "sign in", "buy now", "close view past patch notes", "please enter your date of birth",
        "terms of service", "privacy", "cookie", "image:",
    )
    scored: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for idx, raw in enumerate(document.blocks):
        block = " ".join(raw.split()).strip()
        low = block.lower()
        if not block or len(block) < 12 or len(block) > 700 or any(x in low for x in junk):
            continue
        key = low[:500]
        if key in seen:
            continue
        seen.add(key)
        score = 0
        score += sum(3 for token in query if token in low)
        score += sum(1 for token in priority if token in low)
        if low.startswith(("weapons", "weapon", "changelog", "major updates", "global", "multiplayer", "zombies")):
            score += 2
        if score:
            scored.append((score, idx, block[:600]))

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [item[2] for item in scored[:limit]]
    if not selected:
        selected = [x[:600] for x in document.blocks[:limit] if len(x.strip()) >= 12]
    return selected[:limit]


class OfficialPatchKnowledgeProvider:
    """Live official patch-note provider for Warzone, BO7 and Battlefield 6.

    It discovers the newest article from an allowlisted official index, fetches
    the official article, caches it briefly, and exposes only compact relevant
    evidence. A live official patch note verifies current patch facts; it does
    not turn an AI recommendation into an "official meta ranking".
    """

    def __init__(
        self,
        *,
        ttl_s: int = 900,
        timeout_s: float = 6.0,
        fetcher: Callable[[str], tuple[str, str]] | None = None,
    ) -> None:
        self.ttl_s = max(60, int(ttl_s))
        self.timeout_s = max(1.0, min(float(timeout_s), 20.0))
        self.fetcher = fetcher or self._http_fetch
        self._cache: dict[str, _CacheEntry] = {}

    def _http_fetch(self, url: str) -> tuple[str, str]:
        if not _is_allowed_url(url):
            raise ValueError("official source URL is not allowlisted")
        headers = {
            "User-Agent": "BLACK-CROWN-OPS/3.0 live-knowledge",
            "Accept": "text/html,application/xhtml+xml",
        }
        with httpx.Client(timeout=self.timeout_s, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            final_url = str(response.url)
            if not _is_allowed_url(final_url):
                raise ValueError("official source redirected outside allowlist")
            return final_url, response.text[:2_000_000]

    def _index_url(self, game: str) -> str:
        return _BF6_INDEX if game == "bf6" else _COD_INDEX

    def _discover_article(self, game: str) -> tuple[str, str]:
        index_url = self._index_url(game)
        final_index, html = self.fetcher(index_url)
        if not _is_allowed_url(final_index):
            raise ValueError("index redirect outside allowlist")
        parser = _AnchorParser()
        parser.feed(html)
        parser.close()
        seen: set[str] = set()
        for href, text in parser.links:
            if not _candidate_matches(game, href, text):
                continue
            absolute = urljoin(final_index, href)
            if absolute in seen or not _is_allowed_url(absolute):
                continue
            seen.add(absolute)
            return absolute, text
        raise LookupError(f"no official {game} patch article found")

    def _load_document(self, game: str) -> OfficialDocument:
        now = time.monotonic()
        cached = self._cache.get(game)
        if cached and cached.expires_at > now:
            return cached.document

        article_url, anchor_text = self._discover_article(game)
        final_url, raw_html = self.fetcher(article_url)
        if not _is_allowed_url(final_url):
            raise ValueError("article redirect outside allowlist")

        parser = _VisibleTextParser()
        parser.feed(raw_html)
        parser.close()
        blocks = [" ".join(x.split()) for x in parser.blocks if x.strip()]
        published = _published_date(blocks, raw_html)
        fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        document = OfficialDocument(
            game=game,
            title=_document_title(game, blocks, anchor_text),
            url=final_url,
            published=published,
            blocks=tuple(blocks[:1200]),
            fetched_at=fetched_at,
        )
        self._cache[game] = _CacheEntry(document=document, expires_at=now + self.ttl_s)
        return document

    def query(self, request: KnowledgeRequest) -> KnowledgeContext:
        if request.intent.intent not in {Intent.META_CURRENT, Intent.PATCH_CURRENT}:
            return KnowledgeContext.unknown()
        game = _game_key(request)
        if game is None:
            return KnowledgeContext.unknown()
        try:
            document = self._load_document(game)
            blocks = _select_blocks(document, request)
            facts = [
                KnowledgeFact(
                    text=f"Official document: {document.title}",
                    source=document.url,
                    last_updated=document.published,
                    confidence=KnowledgeConfidence.VERIFIED_CURRENT,
                )
            ]
            facts.extend(
                KnowledgeFact(
                    text=block,
                    source=document.url,
                    last_updated=document.published,
                    confidence=KnowledgeConfidence.VERIFIED_CURRENT,
                )
                for block in blocks
            )
            return KnowledgeContext(
                facts=facts[:18],
                source=document.url,
                last_updated=document.published,
                freshness=f"live_official; fetched_at={document.fetched_at}",
                confidence=KnowledgeConfidence.VERIFIED_CURRENT,
            )
        except Exception as exc:
            log.warning("official knowledge unavailable game=%s error=%s", game, type(exc).__name__)
            return KnowledgeContext.unknown()
