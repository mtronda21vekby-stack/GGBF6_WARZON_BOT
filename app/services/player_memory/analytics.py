# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any


@dataclass
class PlayerAnalytics:
    store: Any

    @staticmethod
    def _numeric(events: list[dict], key: str) -> list[float]:
        values: list[float] = []
        for event in events:
            value = event.get(key)
            if value is None and isinstance(event.get("metrics"), dict):
                value = event["metrics"].get(key)
            try:
                if value is not None:
                    values.append(float(value))
            except Exception:
                continue
        return values

    @staticmethod
    def _trend(values: list[float]) -> dict[str, float] | None:
        if len(values) < 4:
            return None
        ordered = list(reversed(values[:10]))  # stores return newest first
        mid = max(2, len(ordered) // 2)
        first = ordered[:mid]
        second = ordered[mid:]
        if not second:
            return None
        a = mean(first)
        b = mean(second)
        return {"previous_avg": round(a, 3), "recent_avg": round(b, 3), "delta": round(b - a, 3)}

    def snapshot(self, chat_id: int) -> dict[str, Any]:
        mistakes = []
        fn = getattr(self.store, "list_mistake_stats", None)
        if callable(fn):
            try:
                mistakes = list(fn(chat_id) or [])[:5]
            except Exception:
                mistakes = []

        progression = []
        fn = getattr(self.store, "list_progression_events", None)
        if callable(fn):
            try:
                progression = list(fn(chat_id) or [])[:20]
            except Exception:
                progression = []

        training = []
        fn = getattr(self.store, "list_training_sessions", None)
        if callable(fn):
            try:
                training = list(fn(chat_id) or [])[:10]
            except Exception:
                training = []

        episodes = []
        fn = getattr(self.store, "list_episodes", None)
        if callable(fn):
            try:
                episodes = list(fn(chat_id, 20) or [])
            except Exception:
                episodes = []

        trends: dict[str, Any] = {}
        for key in ("kills", "placement", "accuracy_pct"):
            trend = self._trend(self._numeric(progression, key))
            if trend:
                trends[key] = trend

        return {
            "top_mistakes": [
                {"label": str(x.get("label") or ""), "count": int(x.get("count") or 0)}
                for x in mistakes if x.get("label")
            ],
            "training_sessions": len(training),
            "progression_events": len(progression),
            "recent_episodes": len(episodes),
            "trends": trends,
        }
