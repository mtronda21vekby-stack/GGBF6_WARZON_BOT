# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Mapping

from app.services.player_memory.service import PlayerMemoryService


MISSION_EVENT_TYPE = "adaptive_mission"
MISSION_SOURCE = "adaptive_mission_control_v19"

_FOCUS_SCORE_FIELDS = {
    "aim": "aim_score",
    "movement": "movement_score",
    "positioning": "positioning_score",
    "decision": "decision_score",
    "comms": "comms_score",
}

_FOCUS_ALIASES = {
    "position": "positioning",
    "rotation": "positioning",
    "позиция": "positioning",
    "позиционка": "positioning",
    "ротация": "positioning",
    "communication": "comms",
    "коммуникация": "comms",
}

_FOCUS_KEYWORDS = {
    "aim": (
        "aim", "аим", "accuracy", "точност", "прицел", "кроссхейр", "tracking",
        "трекинг", "flick", "флик", "recoil", "отдач", "first shot", "первый выстрел",
    ),
    "movement": (
        "movement", "мув", "slide", "слайд", "strafe", "стрейф", "jump",
        "прыж", "mobility", "мобильност", "ресет движения", "exit vector",
    ),
    "positioning": (
        "position", "пози", "rotation", "ротац", "zone", "зон", "gas", "газ",
        "cover", "укрыт", "angle", "угол", "peek", "пик", "height", "высот",
        "спина", "third party", "тайминг зоны",
    ),
    "decision": (
        "decision", "решен", "timing", "тайминг", "greed", "жад", "trade",
        "пуш", "push", "engage", "disengage", "паник", "overextend", "переоцен",
        "контакт", "повторный пик",
    ),
    "comms": (
        "comms", "communication", "коммуникац", "callout", "колл", "инфо",
        "information", "тиммейт", "отряд", "связь",
    ),
}

_TEMPLATES: dict[str, dict[str, Any]] = {
    "aim": {
        "title": "FIRST-SHOT LOCK",
        "objective": "Стабилизировать первый захват цели и удержать трекинг после начала контакта.",
        "match_rule": "Не начинай очередь до микро-стопа прицела. После потери цели — отпусти огонь, верни центр, продолжай.",
        "metric": "3 последовательных контакта без панической коррекции и минимум 55% подтверждённой точности.",
        "phases": (
            ("CALIBRATE", "Медленный трекинг по верхней части корпуса; скорость не увеличивать до чистой линии."),
            ("ISOLATE", "Короткие переносы: перенос → микро-стоп → выстрел. Ошибочный выстрел обнуляет повтор."),
            ("TRANSFER", "Один реальный матч: оценивать не киллы, а чистоту первого захвата и возврата на цель."),
        ),
    },
    "movement": {
        "title": "EXIT VECTOR",
        "objective": "Убрать повторяемые линии движения и превратить каждый контакт в контролируемый выход.",
        "match_rule": "После нанесённого урона не повторяй ту же линию. Меняй угол, высоту или дистанцию до следующего пика.",
        "metric": "Минимум 4 осознанных ресета позиции и не более одной смерти на повторном пике.",
        "phases": (
            ("CALIBRATE", "Связки вход → выстрел → выход без стрельбы на первом проходе."),
            ("ISOLATE", "Ресет после контакта: смена линии за одно движение без лишнего прыжка или разворота."),
            ("TRANSFER", "Один матч с обязательным exit vector после каждого первого обмена уроном."),
        ),
    },
    "positioning": {
        "title": "ROTATION EDGE",
        "objective": "Сместить ротации раньше угрозы и входить в следующий контакт с геометрическим преимуществом.",
        "match_rule": "Ротация начинается до необходимости. После одного контакта с линии — меняй сектор, а не повторяй пик.",
        "metric": "2 ранние ротации, 0 смертей в газе/спину по собственной задержке и минимум 3 контакта из укрытия.",
        "phases": (
            ("CALIBRATE", "Перед движением назвать безопасный сектор, угрозу и следующую точку укрытия."),
            ("ISOLATE", "На каждой смене зоны уходить на 10–15 секунд раньше привычного тайминга."),
            ("TRANSFER", "Один матч: приоритет сильной геометрии над жадностью по киллам."),
        ),
    },
    "decision": {
        "title": "CONTACT DISCIPLINE",
        "objective": "Снизить хаос в решениях и отделить выгодные контакты от эмоциональных пушей.",
        "match_rule": "Перед продолжением файта ответь: преимущество, выход, ресурс. Нет двух из трёх — ресет.",
        "metric": "Не менее 5 осознанных решений engage/reset и 0 смертей после очевидного проигрыша ресурса.",
        "phases": (
            ("CALIBRATE", "Разобрать три последних смерти по схеме: преимущество → ресурс → выход."),
            ("ISOLATE", "В тренировочном матче проговаривать только одно решение: engage, hold или reset."),
            ("TRANSFER", "Один матч без автоматического продолжения контакта после потери брони/позиции."),
        ),
    },
    "comms": {
        "title": "INFORMATION COMPRESSION",
        "objective": "Сделать коммуникацию короткой, приоритетной и пригодной для немедленного действия.",
        "match_rule": "Каждый колл содержит максимум три элемента: кто/где → состояние → действие.",
        "metric": "10 коротких actionable-коллов без дублирования и минимум 3 подтверждённых командных реакции.",
        "phases": (
            ("CALIBRATE", "Перевести пять длинных описаний в формат позиция → состояние → действие."),
            ("ISOLATE", "Во время матча исключить объяснения прошлого; передавать только текущую угрозу и решение."),
            ("TRANSFER", "Один командный матч с лимитом одного дыхания на каждый колл."),
        ),
    },
}

_OUTCOME_ALIASES = {
    "clean": "clean",
    "win": "clean",
    "success": "clean",
    "успех": "clean",
    "чисто": "clean",
    "mixed": "mixed",
    "partial": "mixed",
    "частично": "mixed",
    "смешанно": "mixed",
    "failed": "failed",
    "fail": "failed",
    "loss": "failed",
    "провал": "failed",
    "не получилось": "failed",
    "reported": "reported",
}

_ALLOWED_METRICS = {
    "kills": (-1_000.0, 1_000.0),
    "deaths": (0.0, 1_000.0),
    "placement": (0.0, 10_000.0),
    "accuracy_pct": (0.0, 100.0),
    "score": (-10_000_000.0, 10_000_000.0),
    "wave": (0.0, 100_000.0),
    "damage": (0.0, 100_000_000.0),
    "mission_score": (0.0, 100.0),
}


class MissionConflict(ValueError):
    """Raised when a client acts on a stale or foreign mission identifier."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if not math.isfinite(number):
        return None
    return number


def _normalize_focus(value: Any) -> str:
    text = " ".join(str(value or "").lower().split())
    if text in _FOCUS_SCORE_FIELDS:
        return text
    if text in _FOCUS_ALIASES:
        return _FOCUS_ALIASES[text]
    for alias, focus in _FOCUS_ALIASES.items():
        if alias and alias in text:
            return focus
    for focus, words in _FOCUS_KEYWORDS.items():
        if any(word in text for word in words):
            return focus
    return "positioning"


def _classify_focus(value: Any) -> str | None:
    text = " ".join(str(value or "").lower().split())
    if not text:
        return None
    scores = {
        focus: sum(1 for word in words if word in text)
        for focus, words in _FOCUS_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def _time_of(row: Mapping[str, Any]) -> str:
    return str(row.get("at") or row.get("created_at") or "")[:64]


def _age_bonus(value: Any) -> float:
    raw = str(value or "").strip()
    if not raw:
        return 0.0
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        days = max(0.0, (datetime.now(timezone.utc) - when.astimezone(timezone.utc)).total_seconds() / 86400)
    except Exception:
        return 0.0
    if days <= 7:
        return 4.0
    if days <= 30:
        return 2.0
    return 0.0


@dataclass
class AdaptiveMissionService:
    store: Any
    profiles: Any
    enabled: bool = True

    def _call(self, name: str, *args, default=None):
        fn = getattr(self.store, name, None)
        if not callable(fn):
            return default
        try:
            return fn(*args)
        except Exception:
            return default

    def _profile(self, chat_id: int) -> dict[str, Any]:
        try:
            return dict(self.profiles.get(int(chat_id)) or {})
        except Exception:
            return {}

    def _rows(self, name: str, chat_id: int, limit: int) -> list[dict[str, Any]]:
        raw = self._call(name, int(chat_id), default=[]) or []
        out: list[dict[str, Any]] = []
        for item in list(raw)[:limit]:
            if isinstance(item, Mapping):
                out.append(dict(item))
        return out

    def _history_state(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        completed_ids: set[str] = set()
        accepted_ids: set[str] = set()
        active: dict[str, Any] | None = None
        last_outcome = ""
        completion_by_focus: dict[str, int] = {focus: 0 for focus in _FOCUS_SCORE_FIELDS}

        for row in events:
            mission_id = str(row.get("mission_id") or "").strip()
            status = str(row.get("status") or "").strip().lower()
            focus = _normalize_focus(row.get("focus"))
            if status == "completed":
                completed_ids.add(mission_id)
                completion_by_focus[focus] = completion_by_focus.get(focus, 0) + 1
                if not last_outcome:
                    last_outcome = str(row.get("outcome") or "")
            elif status == "accepted":
                accepted_ids.add(mission_id)
                if active is None and mission_id not in completed_ids:
                    active = row

        return {
            "active": active,
            "accepted": len(accepted_ids),
            "completed": len(completed_ids),
            "last_outcome": last_outcome,
            "completion_by_focus": completion_by_focus,
        }

    def _focus_model(
        self,
        profile: Mapping[str, Any],
        mistakes: list[dict[str, Any]],
        derived: Mapping[str, Any],
    ) -> tuple[str, dict[str, float], list[dict[str, Any]]]:
        scores = {focus: 0.0 for focus in _FOCUS_SCORE_FIELDS}
        evidence: list[dict[str, Any]] = []

        for row in mistakes:
            label = str(row.get("label") or "").strip()
            focus = _classify_focus(label)
            if not focus:
                continue
            count = max(1, int(row.get("count") or 1))
            weight = min(8, count) * 4.0 + _age_bonus(row.get("last_seen"))
            scores[focus] += weight
            evidence.append({
                "type": "recurring_mistake",
                "focus": focus,
                "label": label[:180],
                "weight": round(weight, 1),
                "count": count,
            })

        for label in list(profile.get("weaknesses") or [])[:8]:
            focus = _classify_focus(label)
            if focus:
                scores[focus] += 7.0
                evidence.append({
                    "type": "profile_weakness",
                    "focus": focus,
                    "label": str(label)[:180],
                    "weight": 7.0,
                })

        known_scores: list[tuple[str, float]] = []
        for focus, field in _FOCUS_SCORE_FIELDS.items():
            value = _safe_number(profile.get(field))
            if value is None:
                continue
            value = _clamp(value, 0.0, 100.0)
            known_scores.append((focus, value))
            deficiency = max(0.0, 72.0 - value) * 0.28
            scores[focus] += deficiency
            if deficiency >= 3.0:
                evidence.append({
                    "type": "skill_score",
                    "focus": focus,
                    "label": f"{field}={round(value, 1)}",
                    "weight": round(deficiency, 1),
                })

        preferred = _normalize_focus(profile.get("training_focus") or profile.get("weekly_focus"))
        scores[preferred] += 5.0

        trends = derived.get("trends") if isinstance(derived.get("trends"), Mapping) else {}
        if isinstance(trends, Mapping):
            accuracy_row = trends.get("accuracy_pct") if isinstance(trends.get("accuracy_pct"), Mapping) else {}
            kills_row = trends.get("kills") if isinstance(trends.get("kills"), Mapping) else {}
            placement_row = trends.get("placement") if isinstance(trends.get("placement"), Mapping) else {}
            score_row = trends.get("score") if isinstance(trends.get("score"), Mapping) else {}
            accuracy_delta = _safe_number(accuracy_row.get("delta"))
            kills_delta = _safe_number(kills_row.get("delta"))
            placement_delta = _safe_number(placement_row.get("delta"))
            score_delta = _safe_number(score_row.get("delta"))

            if accuracy_delta is not None and accuracy_delta < 0:
                weight = min(12.0, abs(accuracy_delta) * 1.5)
                scores["aim"] += weight
                evidence.append({"type": "negative_trend", "focus": "aim", "label": f"accuracy Δ{accuracy_delta:+g}", "weight": round(weight, 1)})
            if kills_delta is not None and kills_delta < 0:
                weight = min(8.0, abs(kills_delta) * 2.0)
                scores["decision"] += weight
                scores["aim"] += weight * 0.4
                evidence.append({"type": "negative_trend", "focus": "decision", "label": f"kills Δ{kills_delta:+g}", "weight": round(weight, 1)})
            if placement_delta is not None and placement_delta > 0:
                weight = min(12.0, placement_delta * 1.2)
                scores["positioning"] += weight
                evidence.append({"type": "negative_trend", "focus": "positioning", "label": f"placement Δ{placement_delta:+g}", "weight": round(weight, 1)})
            if score_delta is not None and score_delta < 0:
                weight = min(7.0, abs(score_delta) / 150.0)
                scores["decision"] += weight
                evidence.append({"type": "negative_trend", "focus": "decision", "label": f"score Δ{score_delta:+g}", "weight": round(weight, 1)})

        if max(scores.values()) <= 5.0 and known_scores:
            lowest_focus, lowest_value = min(known_scores, key=lambda item: item[1])
            scores[lowest_focus] += 8.0
            evidence.append({
                "type": "lowest_known_score",
                "focus": lowest_focus,
                "label": f"{_FOCUS_SCORE_FIELDS[lowest_focus]}={round(lowest_value, 1)}",
                "weight": 8.0,
            })

        order = ("positioning", "decision", "aim", "movement", "comms")
        focus = max(order, key=lambda name: (scores[name], -order.index(name)))
        evidence.sort(key=lambda item: float(item.get("weight") or 0), reverse=True)
        return focus, {key: round(value, 1) for key, value in scores.items()}, evidence[:8]

    def _coverage(
        self,
        profile: Mapping[str, Any],
        mistakes: list[dict[str, Any]],
        progression: list[dict[str, Any]],
        training: list[dict[str, Any]],
    ) -> int:
        value = 0.0
        if profile.get("game"):
            value += 5
        if profile.get("input"):
            value += 5
        if profile.get("current_goal"):
            value += 7
        value += sum(8 for field in _FOCUS_SCORE_FIELDS.values() if _safe_number(profile.get(field)) is not None)
        value += min(25, sum(min(5, max(0, int(row.get("count") or 0))) for row in mistakes) * 2)
        value += min(12, len(progression) * 2)
        value += min(6, len(training))
        return int(round(_clamp(value, 0.0, 100.0)))

    def _momentum(self, derived: Mapping[str, Any], events: list[dict[str, Any]]) -> int:
        signals: list[float] = []
        trends = derived.get("trends") if isinstance(derived.get("trends"), Mapping) else {}
        if isinstance(trends, Mapping):
            scales = {
                "accuracy_pct": (10.0, 1.0),
                "kills": (3.0, 1.0),
                "placement": (5.0, -1.0),
                "score": (500.0, 1.0),
                "wave": (3.0, 1.0),
            }
            for key, (scale, direction) in scales.items():
                row = trends.get(key)
                if not isinstance(row, Mapping):
                    continue
                delta = _safe_number(row.get("delta"))
                if delta is not None:
                    signals.append(_clamp((delta / scale) * direction, -1.0, 1.0))

        outcome_signal = {"clean": 1.0, "mixed": 0.15, "failed": -1.0, "reported": 0.0}
        for row in events:
            if str(row.get("status") or "").lower() != "completed":
                continue
            signals.append(outcome_signal.get(str(row.get("outcome") or "").lower(), 0.0))
            if len(signals) >= 8:
                break

        if not signals:
            return 50
        return int(round(_clamp(50.0 + mean(signals) * 36.0, 0.0, 100.0)))

    def _risk(
        self,
        mistakes: list[dict[str, Any]],
        training: list[dict[str, Any]],
        momentum: int,
        focus_scores: Mapping[str, float],
    ) -> int:
        repeated = sum(min(6, max(0, int(row.get("count") or 0))) for row in mistakes[:5])
        concentration = max(focus_scores.values() or [0.0])
        value = 16.0 + min(38.0, repeated * 2.6) + min(18.0, concentration * 0.22)
        value += max(0.0, 50.0 - momentum) * 0.55
        value -= min(12.0, len(training) * 1.5)
        return int(round(_clamp(value, 0.0, 100.0)))

    @staticmethod
    def _risk_level(risk: int) -> str:
        if risk >= 75:
            return "CRITICAL"
        if risk >= 55:
            return "HIGH"
        if risk >= 35:
            return "MODERATE"
        return "LOW"

    @staticmethod
    def _mode(coverage: int, momentum: int, risk: int, confidence: int) -> str:
        if coverage < 28:
            return "CALIBRATE"
        if risk >= 70 or momentum < 35:
            return "STABILIZE"
        if momentum >= 62 and confidence >= 65:
            return "ATTACK"
        return "CONSOLIDATE"

    @staticmethod
    def _duration(profile: Mapping[str, Any]) -> int:
        difficulty = str(profile.get("difficulty") or profile.get("brain_mode") or "Normal").lower()
        if "demon" in difficulty or "демон" in difficulty:
            return 24
        if "pro" in difficulty or "проф" in difficulty:
            return 20
        return 16

    def _mission_id(
        self,
        chat_id: int,
        profile: Mapping[str, Any],
        focus: str,
        evidence: list[dict[str, Any]],
        cycle: int,
    ) -> str:
        fingerprint = {
            "chat_id": int(chat_id),
            "game": str(profile.get("game") or "Warzone"),
            "input": str(profile.get("input") or "Controller"),
            "difficulty": str(profile.get("difficulty") or "Normal"),
            "focus": focus,
            "cycle": int(cycle),
            "evidence": [
                {
                    "type": item.get("type"),
                    "label": item.get("label"),
                    "count": item.get("count"),
                    "weight": item.get("weight"),
                }
                for item in evidence[:6]
            ],
        }
        raw = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "m19-" + hashlib.sha256(raw).hexdigest()[:14]

    def _build_candidate(
        self,
        chat_id: int,
        profile: Mapping[str, Any],
        focus: str,
        evidence: list[dict[str, Any]],
        cycle: int,
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        template = _TEMPLATES[focus]
        duration = self._duration(profile)
        phase_minutes = [max(3, round(duration * 0.25)), max(5, round(duration * 0.45))]
        phase_minutes.append(max(4, duration - sum(phase_minutes)))
        protocol = [
            {"phase": phase, "minutes": phase_minutes[index], "action": action}
            for index, (phase, action) in enumerate(template["phases"])
        ]
        top = evidence[0] if evidence else None
        if top:
            reason = (
                f"Главный сигнал: {top.get('label')}. Вес доказательства {top.get('weight')}. "
                "Mission Control изолирует один ограничитель, чтобы результат можно было измерить."
            )
        else:
            reason = (
                "Доказательств пока мало. Это калибровочная миссия: она создаст первый "
                "надёжный сигнал для следующего протокола."
            )

        game = str(profile.get("game") or "Warzone")[:40]
        input_name = str(profile.get("input") or "Controller")[:40]
        difficulty = str(profile.get("difficulty") or "Normal")[:40]
        mission_id = self._mission_id(chat_id, profile, focus, evidence, cycle)
        return {
            "id": mission_id,
            "status": "candidate",
            "focus": focus,
            "title": str(template["title"]),
            "objective": str(template["objective"]),
            "why": reason[:700],
            "protocol": protocol,
            "match_rule": str(template["match_rule"]),
            "success_metric": str(template["metric"]),
            "duration_min": duration,
            "game": game,
            "input": input_name,
            "difficulty": difficulty,
            "mode": str(state.get("mode") or "CALIBRATE"),
            "evidence": evidence[:6],
            "generated_at": _now_iso(),
        }

    @staticmethod
    def _active_mission(row: Mapping[str, Any]) -> dict[str, Any] | None:
        raw = row.get("mission")
        if not isinstance(raw, Mapping):
            return None
        mission = dict(raw)
        mission["status"] = "active"
        mission["accepted_at"] = _time_of(row)
        return mission

    def snapshot(self, chat_id: int) -> dict[str, Any]:
        cid = int(chat_id)
        profile = self._profile(cid)
        mistakes = self._rows("list_mistake_stats", cid, 12)
        progression = self._rows("list_progression_events", cid, 40)
        training = self._rows("list_training_sessions", cid, 20)
        derived = self._call("get_derived_intelligence", cid, default={}) or {}
        if not isinstance(derived, Mapping):
            derived = {}

        events = [
            row for row in progression
            if str(row.get("type") or "") == MISSION_EVENT_TYPE
            and str(row.get("mission_id") or "").strip()
        ]
        history = self._history_state(events)
        focus, focus_scores, evidence = self._focus_model(profile, mistakes, derived)
        coverage = self._coverage(profile, mistakes, progression, training)
        momentum = self._momentum(derived, events)
        risk = self._risk(mistakes, training, momentum, focus_scores)
        gap = sorted(focus_scores.values(), reverse=True)
        separation = (gap[0] - gap[1]) if len(gap) > 1 else gap[0]
        confidence = int(round(_clamp(24.0 + coverage * 0.62 + min(12.0, separation * 0.55), 20.0, 96.0)))
        readiness = int(round(_clamp(confidence * 0.45 + momentum * 0.35 + (100 - risk) * 0.20, 0.0, 100.0)))
        mode = self._mode(coverage, momentum, risk, confidence)
        state = {
            "mode": mode,
            "readiness": readiness,
            "momentum": momentum,
            "risk": risk,
            "risk_level": self._risk_level(risk),
            "confidence": round(confidence / 100.0, 2),
            "confidence_pct": confidence,
            "coverage": coverage,
            "evidence_level": "HIGH" if confidence >= 72 else ("MEDIUM" if confidence >= 48 else "LOW"),
            "focus_scores": focus_scores,
            "dominant_focus": focus,
        }

        active = self._active_mission(history.get("active") or {})
        if active is None:
            cycle = int((history.get("completion_by_focus") or {}).get(focus, 0))
            mission = self._build_candidate(cid, profile, focus, evidence, cycle, state)
        else:
            mission = active

        return {
            "enabled": bool(self.enabled),
            "state": state,
            "mission": mission,
            "history": {
                "accepted": int(history.get("accepted") or 0),
                "completed": int(history.get("completed") or 0),
                "last_outcome": str(history.get("last_outcome") or ""),
            },
        }

    def accept(self, chat_id: int, mission_id: str) -> dict[str, Any]:
        if not self.enabled:
            raise MissionConflict("adaptive_mission_control_disabled")
        cid = int(chat_id)
        requested = str(mission_id or "").strip()
        current = self.snapshot(cid)
        mission = dict(current.get("mission") or {})
        current_id = str(mission.get("id") or "")
        if mission.get("status") == "active":
            if requested and requested != current_id:
                raise MissionConflict("stale_mission")
            return current
        if not requested or requested != current_id:
            raise MissionConflict("stale_mission")

        now = _now_iso()
        event = {
            "type": MISSION_EVENT_TYPE,
            "status": "accepted",
            "mission_id": current_id,
            "focus": mission.get("focus"),
            "mission": mission,
            "source": MISSION_SOURCE,
            "at": now,
        }
        self._call("add_progression_event", cid, event)
        self._call("add_training_session", cid, {
            "kind": MISSION_EVENT_TYPE,
            "status": "accepted",
            "mission_id": current_id,
            "focus": mission.get("focus"),
            "game": mission.get("game"),
            "source": MISSION_SOURCE,
            "at": now,
        })
        self._call("add_episode", cid, {
            "kind": "adaptive_mission_accepted",
            "mission_id": current_id,
            "focus": mission.get("focus"),
            "mission": mission,
            "source": MISSION_SOURCE,
            "at": now,
        })
        try:
            self.profiles.patch(cid, {
                "training_focus": mission.get("focus"),
                "weekly_focus": str(mission.get("title") or "")[:160],
                "last_session_summary": f"Активная миссия: {mission.get('title')} — {mission.get('success_metric')}"[:700],
            })
        except Exception:
            pass
        return self.snapshot(cid)

    @staticmethod
    def _sanitize_metrics(metrics: Mapping[str, Any] | None, outcome: str) -> dict[str, float | int]:
        source = metrics if isinstance(metrics, Mapping) else {}
        out: dict[str, float | int] = {}
        for key, (low, high) in _ALLOWED_METRICS.items():
            if key not in source:
                continue
            value = _safe_number(source.get(key))
            if value is None:
                continue
            value = _clamp(value, low, high)
            out[key] = int(value) if value.is_integer() else round(value, 3)
        if "mission_score" not in out:
            out["mission_score"] = {"clean": 100, "mixed": 60, "failed": 20, "reported": 50}[outcome]
        return out

    def complete(
        self,
        chat_id: int,
        mission_id: str,
        *,
        outcome: str = "reported",
        metrics: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise MissionConflict("adaptive_mission_control_disabled")
        cid = int(chat_id)
        current = self.snapshot(cid)
        mission = dict(current.get("mission") or {})
        requested = str(mission_id or "").strip()
        current_id = str(mission.get("id") or "")
        if mission.get("status") != "active" or not requested or requested != current_id:
            raise MissionConflict("active_mission_required")

        normalized_outcome = _OUTCOME_ALIASES.get(" ".join(str(outcome or "").lower().split()), "reported")
        clean_metrics = self._sanitize_metrics(metrics, normalized_outcome)
        now = _now_iso()
        event = {
            "type": MISSION_EVENT_TYPE,
            "status": "completed",
            "mission_id": current_id,
            "focus": mission.get("focus"),
            "outcome": normalized_outcome,
            "metrics": clean_metrics,
            "source": "explicit_operator_report",
            "at": now,
        }
        self._call("add_progression_event", cid, event)
        self._call("add_episode", cid, {
            "kind": "adaptive_mission_completed",
            "mission_id": current_id,
            "focus": mission.get("focus"),
            "outcome": normalized_outcome,
            "metrics": clean_metrics,
            "success_metric": mission.get("success_metric"),
            "source": "explicit_operator_report",
            "at": now,
        })
        try:
            self.profiles.patch(cid, {
                "training_focus": mission.get("focus"),
                "last_session_summary": (
                    f"Миссия {mission.get('title')} завершена: {normalized_outcome}; "
                    f"метрики {clean_metrics}"
                )[:700],
            })
        except Exception:
            pass

        try:
            PlayerMemoryService(store=self.store, profiles=self.profiles).refresh(cid)
        except Exception:
            pass
        return self.snapshot(cid)
