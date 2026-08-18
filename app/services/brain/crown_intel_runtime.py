# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("bco.crown_intel")

_GAMES = ("warzone", "bo7", "bf6")


@dataclass
class CrownIntelRuntime:
    """Zero-extra-cost autonomous refresher for official game intelligence.

    It reuses the exact OfficialPatchKnowledgeProvider already used by the
    Intelligence Core. No paid search/meta API is involved. When the process is
    asleep there is nothing to bill; on restart the cache is warmed again.
    """

    provider: Any
    interval_s: int = 6 * 60 * 60
    initial_delay_s: float = 2.0
    _task: asyncio.Task | None = field(default=None, init=False, repr=False)
    last_refresh_at: str = ""
    last_success_count: int = 0
    last_error_count: int = 0

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(), name="bco-crown-intel-refresh")

    async def close(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def refresh_now(self) -> dict[str, Any]:
        refresh = getattr(self.provider, "refresh", None)
        if not callable(refresh):
            return {"ok": False, "reason": "provider_refresh_unavailable"}

        success = 0
        errors = 0
        details: dict[str, str] = {}
        for game in _GAMES:
            try:
                document = await asyncio.to_thread(refresh, game)
                success += 1
                details[game] = str(getattr(document, "published", "") or "ok")
            except Exception as exc:
                errors += 1
                details[game] = type(exc).__name__
                log.warning("CROWN INTEL refresh failed game=%s error=%s", game, type(exc).__name__)

        self.last_refresh_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self.last_success_count = success
        self.last_error_count = errors
        log.info("CROWN INTEL refresh complete success=%d errors=%d", success, errors)
        return {
            "ok": success > 0,
            "refreshed_at": self.last_refresh_at,
            "success": success,
            "errors": errors,
            "games": details,
        }

    async def _loop(self) -> None:
        if self.initial_delay_s > 0:
            await asyncio.sleep(self.initial_delay_s)
        while True:
            try:
                await self.refresh_now()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("CROWN INTEL loop survived error=%s", type(exc).__name__)
            await asyncio.sleep(max(900, int(self.interval_s)))
