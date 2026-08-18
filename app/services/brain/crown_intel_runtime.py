# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

from app.services.brain.live_official import OfficialPatchKnowledgeProvider

log = logging.getLogger("bco.crown_intel")
_GAMES = ("warzone", "bo7", "bf6")
_SINGLETON: "FreeCrownIntelRuntime | None" = None
_SINGLETON_LOCK = threading.Lock()


def _env_on(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().casefold() not in {"0", "false", "off", "no", ""}


def _interval_s() -> int:
    try:
        raw = int(os.getenv("CROWN_INTEL_REFRESH_INTERVAL_S", str(6 * 60 * 60)))
    except ValueError:
        raw = 6 * 60 * 60
    return max(900, min(raw, 24 * 60 * 60))


@dataclass
class FreeCrownIntelRuntime:
    provider: OfficialPatchKnowledgeProvider
    interval_s: int = 6 * 60 * 60
    enabled: bool = True
    ledger: Any = None

    def __post_init__(self) -> None:
        self.interval_s = max(900, min(int(self.interval_s), 24 * 60 * 60))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False
        self.last_refresh_epoch = 0.0
        self.last_success_count = 0
        self.last_error_count = 0
        self.last_change_count = 0

    def bind_ledger(self, ledger: Any) -> None:
        if ledger is not None:
            self.ledger = ledger

    def start(self) -> None:
        if not self.enabled or self._started:
            return
        self._started = True
        self._thread = threading.Thread(target=self._loop, name="bco-crown-intel-refresh", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def refresh_once(self) -> dict[str, Any]:
        success = 0
        errors = 0
        changed = 0
        games: dict[str, str] = {}
        loader = getattr(self.provider, "_load_document", None)
        if not callable(loader):
            return {"ok": False, "reason": "provider_loader_unavailable"}

        for game in _GAMES:
            try:
                document = loader(game)
                if self.ledger is not None:
                    try:
                        result = self.ledger.record_document(document)
                        changed += 1 if result.get("changed") else 0
                    except Exception as exc:
                        log.warning("CROWN INTEL ledger write failed game=%s error=%s", game, type(exc).__name__)
                success += 1
                games[game] = str(getattr(document, "published", "") or "verified")
            except Exception as exc:
                errors += 1
                games[game] = type(exc).__name__
                log.warning("CROWN INTEL refresh failed game=%s error=%s", game, type(exc).__name__)

        self.last_refresh_epoch = time.time()
        self.last_success_count = success
        self.last_error_count = errors
        self.last_change_count = changed
        log.info("CROWN INTEL refresh complete success=%d errors=%d changed=%d", success, errors, changed)
        return {"ok": success > 0, "success": success, "errors": errors, "changed": changed, "games": games}

    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "zero_extra_paid_api": True,
            "ledger_enabled": self.ledger is not None,
            "sources": ["callofduty.com", "ea.com"],
            "games": list(_GAMES),
            "refresh_interval_s": self.interval_s,
            "last_refresh_epoch": self.last_refresh_epoch,
            "last_success_count": self.last_success_count,
            "last_error_count": self.last_error_count,
            "last_change_count": self.last_change_count,
        }

    def _loop(self) -> None:
        if self._stop.wait(2.0):
            return
        while not self._stop.is_set():
            try:
                self.refresh_once()
            except Exception as exc:
                log.warning("CROWN INTEL loop survived error=%s", type(exc).__name__)
            if self._stop.wait(self.interval_s):
                break


def get_free_official_provider(*, ttl_s: int = 900, timeout_s: float = 6.0, ledger: Any = None) -> OfficialPatchKnowledgeProvider:
    global _SINGLETON
    with _SINGLETON_LOCK:
        if _SINGLETON is None:
            provider = OfficialPatchKnowledgeProvider(ttl_s=ttl_s, timeout_s=timeout_s)
            _SINGLETON = FreeCrownIntelRuntime(
                provider=provider,
                interval_s=_interval_s(),
                enabled=_env_on("CROWN_INTEL_AUTONOMOUS_ENABLED", "1"),
                ledger=ledger,
            )
            _SINGLETON.start()
        elif ledger is not None:
            _SINGLETON.bind_ledger(ledger)
        return _SINGLETON.provider


def get_crown_intel_runtime() -> FreeCrownIntelRuntime | None:
    return _SINGLETON


def crown_intel_runtime_snapshot() -> dict[str, Any]:
    runtime = _SINGLETON
    if runtime is None:
        return {
            "enabled": _env_on("CROWN_INTEL_AUTONOMOUS_ENABLED", "1"),
            "zero_extra_paid_api": True,
            "status": "not_initialized",
        }
    return runtime.snapshot()
