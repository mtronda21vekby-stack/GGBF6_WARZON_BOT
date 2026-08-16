# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any


@dataclass
class PlayerAnalytics:
    store: Any

    @staticmethod
    def _metric_from_event(event: dict, key: str):
        if key in event:
            return event.get(key)
        metrics = event.get("metrics")
        if isinstance(metrics, dict) and key in metrics:
            return metrics.get(key)
        payload = event.get("payload")
        if isinstance(payload, dict):
            if key in payload:
                return payload.get(key)
            nested = payload.get("metrics")
            if isinstance(nested, dict) and key in nested:
                return nested.get(key)
        return None

    @classmethod
    def _numeric(cls, events: list[dict], key: str) -> list[float]:
        values: list[float] = []
        for event in events:
            try:
                value = cls._metric_from_event(event, key)
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
        try:
            mistakes = list(self.store.list_mistake_stats(chat_id) or [])[:5]
        except Exception:
            mistakes = []
        try:
            progression = list(self.store.list_progression_events(chat_id) or [])[:20]
        except Exception:
            progression = []
        try:
            training = list(self.store.list_training_sessions(chat_id) or [])[:10]
        except Exception:
            training = []
        try:
            episodes = list(self.store.list_episodes(chat_id, 20) or [])
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
