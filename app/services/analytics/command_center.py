# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


_PROFILE_FIELDS = (
    "game", "mode", "platform", "input", "role", "bf6_class", "rank", "kd",
    "playstyle", "preferred_weapons", "favorite_modes", "current_goal",
    "aim_score", "movement_score", "positioning_score", "decision_score", "comms_score",
    "strengths", "weaknesses", "training_focus", "weekly_focus",
    "last_session_summary", "preferred_response_depth", "voice", "difficulty", "tts_mode",
)
_SCORE_FIELDS = (
    ("aim", "aim_score"),
    ("movement", "movement_score"),
    ("positioning", "positioning_score"),
    ("decision", "decision_score"),
    ("comms", "comms_score"),
)
_METRICS = ("kills", "placement", "accuracy_pct", "score", "wave")


def _safe_num(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return int(number) if number.is_integer() else round(number, 3)


def _time_of(item: Mapping[str, Any]) -> str:
    return str(item.get("at") or item.get("created_at") or "")[:64]


def _metric(item: Mapping[str, Any], key: str):
    if key in item:
        return _safe_num(item.get(key))
    metrics = item.get("metrics")
    if isinstance(metrics, Mapping) and key in metrics:
        return _safe_num(metrics.get(key))
    payload = item.get("payload")
    if isinstance(payload, Mapping):
        if key in payload:
            return _safe_num(payload.get(key))
        nested = payload.get("metrics")
        if isinstance(nested, Mapping) and key in nested:
            return _safe_num(nested.get(key))
    return None


def _clean_str_list(value: Any, limit: int = 8) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text[:160])
        if len(out) >= limit:
            break
    return out


@dataclass
class CommandCenterService:
    store: Any
    profiles: Any

    def _call(self, name: str, *args, default=None):
        target = getattr(self.store, name, None)
        if not callable(target):
            return default
        try:
            return target(*args)
        except Exception:
            return default

    def _profile(self, chat_id: int) -> dict[str, Any]:
        try:
            raw = dict(self.profiles.get(chat_id) or {})
        except Exception:
            raw = {}
        return {
            key: raw.get(key)
            for key in _PROFILE_FIELDS
            if raw.get(key) not in (None, "", [], {})
        }

    def _scores(self, profile: Mapping[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for label, field in _SCORE_FIELDS:
            value = _safe_num(profile.get(field))
            if value is None:
                out[label] = None
                continue
            out[label] = max(0, min(100, value))
        return out

    def _mistakes(self, chat_id: int) -> list[dict[str, Any]]:
        rows = list(self._call("list_mistake_stats", chat_id, default=[]) or [])[:8]
        out: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            label = str(row.get("label") or "").strip()
            if not label:
                continue
            out.append({
                "label": label[:180],
                "count": max(0, int(row.get("count") or 0)),
                "last_seen": str(row.get("last_seen") or "")[:64],
            })
        return out

    def _training(self, chat_id: int) -> list[dict[str, Any]]:
        rows = list(self._call("list_training_sessions", chat_id, default=[]) or [])[:8]
        out: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            out.append({
                "focus": str(row.get("focus") or "hybrid")[:80],
                "game": str(row.get("game") or "")[:40],
                "source": str(row.get("source") or "")[:60],
                "at": _time_of(row),
            })
        return out

    def _progression(self, chat_id: int) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        rows = list(self._call("list_progression_events", chat_id, default=[]) or [])[:24]
        recent: list[dict[str, Any]] = []
        series: dict[str, list[dict[str, Any]]] = {key: [] for key in _METRICS}
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            metrics = {key: _metric(row, key) for key in _METRICS}
            metrics = {k: v for k, v in metrics.items() if v is not None}
            recent.append({
                "type": str(row.get("type") or row.get("event") or "event")[:80],
                "game": str(row.get("game") or "")[:40],
                "source": str(row.get("source") or "")[:60],
                "at": _time_of(row),
                "metrics": metrics,
            })
            for key, value in metrics.items():
                series[key].append({"at": _time_of(row), "value": value})

        # Store APIs return newest first. Charts should read oldest -> newest.
        for key in list(series):
            series[key] = list(reversed(series[key][:12]))
        return recent[:12], series

    def _vod(self, chat_id: int) -> list[dict[str, Any]]:
        rows = list(self._call("list_episodes", chat_id, 30, default=[]) or [])
        out: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, Mapping) or row.get("kind") != "vod_sampled_frames":
                continue
            analysis = row.get("analysis") if isinstance(row.get("analysis"), Mapping) else {}
            out.append({
                "game": str(row.get("game") or "")[:40],
                "at": _time_of(row),
                "summary": str(analysis.get("summary") or "")[:500],
                "confirmed_mistakes": _clean_str_list(row.get("confirmed_mistakes"), 6),
                "sampled_timestamps": list(analysis.get("sampled_timestamps") or [])[:10],
            })
            if len(out) >= 5:
                break
        return out

    def snapshot(self, chat_id: int) -> dict[str, Any]:
        cid = int(chat_id)
        profile = self._profile(cid)
        summary = str(self._call("get_summary", cid, default="") or "")[:1400]
        derived = self._call("get_derived_intelligence", cid, default={}) or {}
        if not isinstance(derived, Mapping):
            derived = {}
        mistakes = self._mistakes(cid)
        training = self._training(cid)
        progression, series = self._progression(cid)
        vod = self._vod(cid)
        stats = self._call("stats", cid, default={}) or {}
        if not isinstance(stats, Mapping):
            stats = {}

        scores = self._scores(profile)
        known_scores = sum(1 for value in scores.values() if value is not None)
        known_profile = sum(
            1 for key in ("rank", "kd", "playstyle", "current_goal")
            if profile.get(key) not in (None, "", [], {})
        )
        coverage_points = known_scores + known_profile + min(4, len(mistakes)) + min(2, len(progression))
        coverage = min(100, int(round((coverage_points / 15) * 100)))

        trends = derived.get("trends") if isinstance(derived.get("trends"), Mapping) else {}
        safe_trends: dict[str, Any] = {}
        for key, value in trends.items():
            if key not in _METRICS or not isinstance(value, Mapping):
                continue
            safe_trends[key] = {
                "previous_avg": _safe_num(value.get("previous_avg")),
                "recent_avg": _safe_num(value.get("recent_avg")),
                "delta": _safe_num(value.get("delta")),
            }

        return {
            "profile": profile,
            "summary": summary,
            "scores": scores,
            "coverage": coverage,
            "top_mistakes": mistakes,
            "training": training,
            "progression": progression,
            "metric_series": series,
            "vod_reviews": vod,
            "trends": safe_trends,
            "activity": {
                "training_sessions": int(stats.get("training_sessions") or len(training)),
                "progression_events": int(stats.get("progression_events") or len(progression)),
                "episodes": int(stats.get("episodes") or 0),
                "recurring_mistakes": int(stats.get("recurring_mistakes") or len(mistakes)),
                "backend": str(stats.get("backend") or "unknown")[:40],
            },
        }
