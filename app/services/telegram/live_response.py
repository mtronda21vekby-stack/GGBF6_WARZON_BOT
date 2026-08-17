# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from app.ui.presentation import tactical_card


_PHASE_LABELS = {
    "thinking": "SYNCHRONIZING CONTEXT",
    "generating": "LIVE ANALYSIS",
    "candidate": "TACTICAL SYNTHESIS",
    "reframing": "QUALITY CONTROL",
    "retry": "RECOVERY CHANNEL",
    "final": "FINALIZING",
}


def _phase_label(meta: dict[str, Any] | None) -> str:
    phase = str((meta or {}).get("phase") or "thinking").strip().lower()
    return _PHASE_LABELS.get(phase, "LIVE INTELLIGENCE")


def _status_body(text: str, meta: dict[str, Any] | None) -> str:
    clean = str(text or "").strip()
    phase = str((meta or {}).get("phase") or "thinking").strip().lower()
    attempt = max(1, int((meta or {}).get("attempt") or 1))
    if clean:
        return clean[:12_000]

    if phase == "retry":
        return (
            f"Primary generation channel recovered on attempt {attempt}.\n\n"
            "Rebuilding the answer without losing player context…"
        )
    return (
        "Player profile locked.\n"
        "Intent classified.\n"
        "Trusted knowledge selected.\n\n"
        "Generating tactical response…"
    )


@dataclass
class TelegramLiveResponse:
    """Thread-safe bridge from synchronous model streaming to Telegram drafts.

    Bot API drafts are ephemeral. The persistent final answer is still sent by
    the existing TelegramClient.send_message path, so a draft failure never
    removes or delays the real response.
    """

    tg: Any
    chat_id: int
    min_interval_s: float = 0.38
    draft_id: int = field(default_factory=lambda: secrets.randbelow(2_000_000_000) + 1)

    def __post_init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[tuple[str, dict[str, Any]]] | None = None
        self._task: asyncio.Task | None = None
        self._closed = False
        self._supported = True
        self._last_sent_at = 0.0
        self._last_text = ""
        self._last_meta: dict[str, Any] = {}

    async def start(self) -> None:
        if self._closed or not callable(getattr(self.tg, "send_live_draft", None)):
            self._supported = False
            return
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue(maxsize=1)
        self._task = asyncio.create_task(self._pump(), name=f"bco-draft-{self.draft_id}")
        self._enqueue("", {"phase": "thinking", "attempt": 1})

    def publish_from_thread(self, text: str, meta: dict[str, Any] | None = None) -> None:
        """Safe callback for AIHook running in asyncio.to_thread()."""
        if self._closed or not self._supported or self._loop is None:
            return
        payload = (str(text or ""), dict(meta or {}))
        try:
            self._loop.call_soon_threadsafe(self._enqueue, *payload)
        except RuntimeError:
            pass

    def _enqueue(self, text: str, meta: dict[str, Any]) -> None:
        if self._closed or not self._supported or self._queue is None:
            return
        # Latest-state queue: partial drafts supersede older partial drafts.
        try:
            while True:
                self._queue.get_nowait()
                self._queue.task_done()
        except asyncio.QueueEmpty:
            pass
        try:
            self._queue.put_nowait((str(text or ""), dict(meta or {})))
        except asyncio.QueueFull:
            pass

    async def _send(self, text: str, meta: dict[str, Any]) -> None:
        if not self._supported or self._closed:
            return
        label = _phase_label(meta)
        body = _status_body(text, meta)
        card = tactical_card(body, channel="LIVE INTELLIGENCE", state=label)
        try:
            mode = await self.tg.send_live_draft(self.chat_id, self.draft_id, card)
            if mode == "unsupported":
                self._supported = False
            else:
                self._last_sent_at = time.monotonic()
                self._last_text = str(text or "")
                self._last_meta = dict(meta or {})
        except Exception:
            # Draft UX is optional and must not affect the final answer.
            self._supported = False

    async def _pump(self) -> None:
        assert self._queue is not None
        while not self._closed:
            try:
                text, meta = await self._queue.get()
            except asyncio.CancelledError:
                return
            try:
                elapsed = time.monotonic() - self._last_sent_at
                if self._last_sent_at and elapsed < self.min_interval_s:
                    await asyncio.sleep(self.min_interval_s - elapsed)
                await self._send(text, meta)
            finally:
                self._queue.task_done()

    async def finish(self, final_text: str = "") -> None:
        if self._closed:
            return
        # Give Telegram one last high-quality preview before the persistent
        # Rich Message arrives through the normal send_message path.
        if self._supported and final_text:
            await self._send(
                str(final_text),
                {"phase": "final", "attempt": self._last_meta.get("attempt", 1)},
            )
        self._closed = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
