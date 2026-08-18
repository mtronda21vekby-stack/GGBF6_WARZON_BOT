# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CrownAlertDecision:
    deliver: bool
    alert_key: str
    priority: str
    reason: str


def alert_key(change: Mapping[str, Any]) -> str:
    stable = "|".join((
        str(change.get("game") or ""),
        str(change.get("from_hash") or ""),
        str(change.get("to_hash") or ""),
    ))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]


def decide_delivery(change: Mapping[str, Any], impact: Any, *, already_seen: bool = False) -> CrownAlertDecision:
    """High-threshold, duplicate-safe alert policy.

    A change existing in the ledger is not enough. It must be personally relevant,
    must not be the initial baseline, and must not already have been delivered.
    """
    key = alert_key(change)
    if not str(change.get("from_hash") or "").strip():
        return CrownAlertDecision(False, key, "NONE", "baseline_not_alert")
    if already_seen:
        return CrownAlertDecision(False, key, "NONE", "duplicate_suppressed")
    if not bool(getattr(impact, "relevant", False)):
        return CrownAlertDecision(False, key, "NONE", "below_relevance_threshold")
    score = int(getattr(impact, "score", 0) or 0)
    if score >= 6:
        return CrownAlertDecision(True, key, "HIGH", "strong_personal_relevance")
    if score >= 3:
        return CrownAlertDecision(True, key, "STANDARD", "personal_relevance")
    return CrownAlertDecision(False, key, "NONE", "below_relevance_threshold")
