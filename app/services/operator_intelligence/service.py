# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean, pstdev
from typing import Any, Mapping

from app.services.player_memory.service import PlayerMemoryService

MISSION_EVENT_TYPE = "operator_mission"
MISSION_SOURCE = "operator_twin_v25"

DOMAINS = (
    "aim", "movement", "positioning", "rotations", "decision", "aggression",
    "survivability", "comms", "discipline", "consistency", "tilt_susceptibility",
)

_PROFILE_SCORE_FIELDS = {
    "aim": "aim_score",
    "movement": "movement_score",
    "positioning": "positioning_score",
    "decision": "decision_score",
    "comms": "comms_score",
}

_KEYWORDS = {
    "aim": ("aim", "аим", "accuracy", "точност", "прицел", "tracking", "трекинг", "flick", "флик", "recoil", "отдач", "crosshair", "кроссхейр"),
    "movement": ("movement", "мув", "slide", "слайд", "strafe", "стрейф", "jump", "прыж", "mobility", "мобильност", "манс", "exit vector"),
    "positioning": ("position", "пози", "cover", "укрыт", "angle", "угол", "peek", "пик", "height", "высот", "headglitch", "геометр"),
    "rotations": ("rotation", "ротац", "zone", "зон", "gas", "газ", "circle", "круг", "late rotate", "ранняя рота", "тайминг зоны", "спина"),
    "decision": ("decision", "решен", "timing", "тайминг", "trade", "engage", "disengage", "reset", "ресет", "overextend", "переоцен", "контакт", "пуш"),
    "aggression": ("aggression", "агресс", "greed", "жад", "chase", "догон", "kill hungry", "overpush", "перепуш", "слишком пассив", "passive"),
    "survivability": ("surviv", "выжива", "death", "смерт", "downed", "нок", "gas death", "third party", "третья сторона", "без укрытия", "open field"),
    "comms": ("comms", "communication", "коммуникац", "callout", "колл", "инфо", "information", "тиммейт", "отряд", "связь"),
    "discipline": ("discipline", "дисцип", "repeat peek", "повторный пик", "panic", "паник", "reload", "перезар", "habit", "привыч", "rule break", "наруш"),
    "consistency": ("consistency", "стабиль", "нестабиль", "swing", "качел", "variance", "разброс", "то хорошо то плохо"),
    "tilt_susceptibility": ("tilt", "тильт", "rage", "злост", "эмоц", "нерв", "frustr", "горю", "после смерти", "после проигрыша"),
}

_MISSIONS: dict[str, dict[str, Any]] = {
    "aim": {"title": "FIRST CONTACT CONTROL", "objective": "Стабилизировать первый захват цели и не продолжать стрельбу после потери визуального контроля.", "metrics": ["first_contact_quality", "accuracy_pct", "panic_corrections"], "success": "Минимум 3 чистых первых контакта за сессию и не более 1 панической коррекции подряд."},
    "movement": {"title": "EXIT VECTOR", "objective": "После первого обмена уроном менять линию контакта вместо повторения того же движения.", "metrics": ["position_resets", "repeat_peek_deaths", "clean_executions"], "success": "Минимум 4 осознанных exit-vector ресета и не более 1 смерти на повторной линии."},
    "positioning": {"title": "POSITION RETENTION", "objective": "Не отдавать сильную геометрию ради низкоценного контакта без явного преимущества.", "metrics": ["position_retention", "first_damage_advantage", "death_cause"], "success": "2 из 3 ключевых файтов начаты из сильной позиции без добровольной потери укрытия."},
    "rotations": {"title": "LATE ROTATION DISCIPLINE", "objective": "Завершить 3 эндгейма без отказа от сильной позиции ради низкоценного килла и начинать ротацию до принуждения зоной.", "metrics": ["position_retention", "rotation_timing_ms", "death_cause", "clean_executions"], "success": "2 из 3 чистых исполнений: ранняя ротация, сохранённая позиция, смерть не из-за собственной задержки."},
    "decision": {"title": "CONTACT DISCIPLINE", "objective": "Перед продолжением файта отделять выгодный контакт от эмоционального продолжения боя.", "metrics": ["decision_resets", "resource_disadvantage_deaths", "clean_executions"], "success": "Минимум 5 явных engage/reset решений и 0 продолжений файта после потери позиции и ресурса одновременно."},
    "aggression": {"title": "VALUE-BASED PRESSURE", "objective": "Пушить только когда преимущество подтверждено уроном, числом, ресурсом или позицией.", "metrics": ["advantage_pushes", "low_value_chases", "clean_executions"], "success": "Не менее 4 пушей с подтверждённым преимуществом и не более 1 low-value chase."},
    "survivability": {"title": "SURVIVAL WINDOW", "objective": "Сократить смерти, где выход был доступен до критической потери ресурса.", "metrics": ["avoidable_deaths", "successful_disengages", "death_cause"], "success": "Минимум 3 успешных disengage и не более 1 явно предотвратимой смерти за целевую сессию."},
    "comms": {"title": "INFORMATION COMPRESSION", "objective": "Каждый колл сводить к позиции, состоянию и требуемому действию.", "metrics": ["actionable_comms", "duplicate_calls", "team_reactions"], "success": "10 actionable-коллов, максимум 2 дублирования и минимум 3 подтверждённые командные реакции."},
    "discipline": {"title": "RULE INTEGRITY", "objective": "Не нарушать заранее выбранное правило после первого эмоционального или механического сбоя.", "metrics": ["rule_breaks", "repeat_peek_deaths", "clean_executions"], "success": "Не более 1 нарушения целевого правила на 3 контрольных матча."},
    "consistency": {"title": "CONSISTENCY WINDOW", "objective": "Снизить разброс исполнения между матчами, сохраняя один и тот же контрольный протокол.", "metrics": ["clean_executions", "mission_score", "variance_signal"], "success": "3 последовательных матча без провала контрольного протокола более чем на один уровень результата."},
    "tilt_susceptibility": {"title": "TILT BREAKER", "objective": "После плохой смерти не переносить эмоциональный импульс в следующий контакт.", "metrics": ["tilt_events", "post_death_rule_breaks", "clean_executions"], "success": "После каждой отмеченной плохой смерти выполнить reset-протокол; 0 немедленных revenge-push смертей."},
}

_CALIBRATION = {
    "title": "OPERATOR BASELINE CAPTURE",
    "objective": "Собрать достаточное количество фактов до того, как BLACK CROWN начнёт утверждать устойчивую слабость.",
    "metrics": ["matches", "death_cause", "first_damage_advantage", "position_retention", "clean_executions"],
    "success": "Передать минимум 3 коротких post-match отчёта с причиной смерти, первым уроном и качеством позиции.",
}

_ALLOWED_METRICS = {
    "matches": (0.0, 100.0), "clean_executions": (0.0, 100.0), "position_retention": (0.0, 100.0),
    "first_damage_advantage": (0.0, 100.0), "rotation_timing_ms": (-600_000.0, 600_000.0),
    "deaths": (0.0, 1000.0), "accuracy_pct": (0.0, 100.0), "panic_corrections": (0.0, 1000.0),
    "position_resets": (0.0, 1000.0), "repeat_peek_deaths": (0.0, 1000.0), "decision_resets": (0.0, 1000.0),
    "resource_disadvantage_deaths": (0.0, 1000.0), "advantage_pushes": (0.0, 1000.0), "low_value_chases": (0.0, 1000.0),
    "avoidable_deaths": (0.0, 1000.0), "successful_disengages": (0.0, 1000.0), "actionable_comms": (0.0, 10_000.0),
    "duplicate_calls": (0.0, 10_000.0), "team_reactions": (0.0, 10_000.0), "rule_breaks": (0.0, 10_000.0),
    "tilt_events": (0.0, 10_000.0), "post_death_rule_breaks": (0.0, 10_000.0), "mission_score": (0.0, 100.0),
    "variance_signal": (0.0, 100.0),
}

_OUTCOMES = {
    "clean": "clean", "success": "clean", "win": "clean", "чисто": "clean", "успех": "clean",
    "mixed": "mixed", "partial": "mixed", "частично": "mixed",
    "failed": "failed", "fail": "failed", "loss": "failed", "провал": "failed", "reported": "reported",
}


class MissionConflict(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _safe_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def _time_of(item: Mapping[str, Any]) -> str:
    return str(item.get("at") or item.get("created_at") or item.get("last_seen") or "")[:64]


def _age_days(value: Any) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0, int((_now() - when.astimezone(timezone.utc)).total_seconds() // 86400))
    except Exception:
        return None


def _classify(text: Any) -> list[str]:
    low = " ".join(str(text or "").casefold().split())
    if not low:
        return []
    scored = []
    for domain, words in _KEYWORDS.items():
        score = sum(1 for word in words if word in low)
        if score:
            scored.append((score, domain))
    scored.sort(reverse=True)
    return [domain for _, domain in scored[:2]]


def _metric(item: Mapping[str, Any], key: str) -> float | None:
    if key in item:
        return _safe_number(item.get(key))
    metrics = item.get("metrics")
    if isinstance(metrics, Mapping) and key in metrics:
        return _safe_number(metrics.get(key))
    payload = item.get("payload")
    if isinstance(payload, Mapping):
        if key in payload:
            return _safe_number(payload.get(key))
        nested = payload.get("metrics")
        if isinstance(nested, Mapping) and key in nested:
            return _safe_number(nested.get(key))
    return None


@dataclass
class OperatorIntelligenceService:
    store: Any
    profiles: Any
    operator_enabled: bool = True
    missions_enabled: bool = True

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

    def _rows(self, name: str, chat_id: int, limit: int, *, takes_limit: bool = False) -> list[dict[str, Any]]:
        raw = self._call(name, int(chat_id), limit, default=[]) if takes_limit else self._call(name, int(chat_id), default=[])
        return [dict(row) for row in list(raw or [])[:limit] if isinstance(row, Mapping)]

    @staticmethod
    def _evidence_item(*, domain: str, source: str, label: str, direction: str, weight: float, at: str = "", fact_class: str = "observed_signal", value: Any = None) -> dict[str, Any]:
        return {
            "domain": domain, "source": source[:48], "label": str(label or "")[:180], "direction": direction,
            "weight": round(max(0.05, min(8.0, float(weight))), 2), "at": str(at or "")[:64],
            "fact_class": fact_class, "value": value,
        }

    def _collect_evidence(self, profile: Mapping[str, Any], mistakes: list[dict[str, Any]], progression: list[dict[str, Any]], episodes: list[dict[str, Any]], derived: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
        evidence = {domain: [] for domain in DOMAINS}
        for row in mistakes:
            label = str(row.get("label") or "").strip()
            domains = _classify(label)
            if not domains:
                continue
            count = max(1, min(20, int(row.get("count") or 1)))
            at = str(row.get("last_seen") or "")[:64]
            weight = 0.9 + min(3.6, count * 0.45)
            for domain in domains:
                evidence[domain].append(self._evidence_item(
                    domain=domain, source="recurring_mistake", label=label, direction="risk", weight=weight, at=at,
                    fact_class="high_confidence_pattern" if count >= 3 else "weak_pattern", value={"count": count},
                ))
        for domain, field in _PROFILE_SCORE_FIELDS.items():
            value = _safe_number(profile.get(field))
            if value is None:
                continue
            value = max(0.0, min(100.0, value))
            direction = "risk" if value < 55 else ("strength" if value >= 75 else "neutral")
            evidence[domain].append(self._evidence_item(
                domain=domain, source="reported_profile", label=f"{field}={value:g}", direction=direction,
                weight=1.0, fact_class="verified_fact", value=value,
            ))
        for row in progression:
            event_type = str(row.get("type") or row.get("event") or "")
            at = _time_of(row)
            if event_type == MISSION_EVENT_TYPE and str(row.get("status") or "").casefold() == "completed":
                domain = str(row.get("focus") or "").casefold()
                if domain in evidence:
                    outcome = str(row.get("outcome") or "reported").casefold()
                    direction = "strength" if outcome == "clean" else ("risk" if outcome == "failed" else "neutral")
                    evidence[domain].append(self._evidence_item(
                        domain=domain, source="mission_result", label=f"mission outcome={outcome}", direction=direction,
                        weight=1.4, at=at, fact_class="verified_fact", value=outcome,
                    ))
            accuracy = _metric(row, "accuracy_pct")
            if accuracy is not None:
                accuracy = max(0.0, min(100.0, accuracy))
                direction = "risk" if accuracy < 45 else ("strength" if accuracy >= 62 else "neutral")
                evidence["aim"].append(self._evidence_item(
                    domain="aim", source="explicit_match_report", label=f"accuracy_pct={accuracy:g}", direction=direction,
                    weight=0.8, at=at, fact_class="verified_fact", value=accuracy,
                ))
        for row in episodes:
            if str(row.get("kind") or "") != "vod_sampled_frames":
                continue
            at = _time_of(row)
            for label in list(row.get("confirmed_mistakes") or [])[:8]:
                for domain in _classify(label):
                    evidence[domain].append(self._evidence_item(
                        domain=domain, source="vod_sampled_frames", label=str(label), direction="risk", weight=2.1,
                        at=at, fact_class="high_confidence_pattern",
                    ))
        trends = derived.get("trends") if isinstance(derived.get("trends"), Mapping) else {}
        accuracy_trend = trends.get("accuracy_pct") if isinstance(trends, Mapping) else None
        if isinstance(accuracy_trend, Mapping):
            delta = _safe_number(accuracy_trend.get("delta"))
            if delta is not None and abs(delta) >= 0.5:
                evidence["aim"].append(self._evidence_item(
                    domain="aim", source="derived_trend", label=f"accuracy trend Δ{delta:+g}",
                    direction="strength" if delta > 0 else "risk", weight=min(1.8, 0.5 + abs(delta) / 8.0),
                    fact_class="weak_pattern", value=delta,
                ))
        series = [value for row in progression[:20] if (value := _metric(row, "accuracy_pct")) is not None]
        if len(series) >= 5:
            avg = mean(series)
            cv = (pstdev(series) / max(1.0, abs(avg))) * 100.0
            evidence["consistency"].append(self._evidence_item(
                domain="consistency", source="repeated_match_reports",
                label=f"accuracy relative spread={cv:.1f}% across {len(series)} reports",
                direction="risk" if cv >= 22 else ("strength" if cv <= 10 else "neutral"),
                weight=1.5, fact_class="weak_pattern", value=round(cv, 2),
            ))
        return evidence

    @staticmethod
    def _trend_for(items: list[dict[str, Any]]) -> str:
        mission = [x for x in items if x.get("source") == "mission_result"][:4]
        if len(mission) >= 2:
            score = {"strength": 1, "neutral": 0, "risk": -1}
            ordered = list(reversed(mission))
            split = max(1, len(ordered) // 2)
            first = mean(score.get(str(x.get("direction")), 0) for x in ordered[:split])
            second = mean(score.get(str(x.get("direction")), 0) for x in ordered[split:])
            if second - first >= 0.5:
                return "improving"
            if second - first <= -0.5:
                return "declining"
            return "stable"
        trend = next((x for x in items if x.get("source") == "derived_trend"), None)
        if trend:
            return "improving" if trend.get("direction") == "strength" else "declining"
        return "unknown"

    def _dimension(self, domain: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        items = sorted(items, key=lambda x: float(x.get("weight") or 0.0), reverse=True)[:12]
        if not items:
            return {
                "domain": domain, "assessment": "unknown", "claim_class": "unknown", "confidence": "unknown",
                "evidence_count": 0, "source_count": 0, "recency_days": None, "trend": "unknown",
                "uncertainty": "Недостаточно доказательств. BLACK CROWN не присваивает скрытый score.", "evidence": [],
            }
        risk = sum(float(x.get("weight") or 0) for x in items if x.get("direction") == "risk")
        strength = sum(float(x.get("weight") or 0) for x in items if x.get("direction") == "strength")
        neutral = sum(float(x.get("weight") or 0) for x in items if x.get("direction") == "neutral")
        sources = {str(x.get("source") or "") for x in items if x.get("source")}
        ages = [age for age in (_age_days(x.get("at")) for x in items) if age is not None]
        recency = min(ages) if ages else None
        if risk >= strength + 1.25:
            assessment, priority = "limiting_signal", risk - strength
        elif strength >= risk + 1.25:
            assessment, priority = "strength_signal", 0.0
        elif risk or strength:
            assessment, priority = "mixed_signal", max(0.0, risk - strength)
        else:
            assessment, priority = "neutral_observation", 0.0
        count, diversity = len(items), len(sources)
        if count >= 4 and diversity >= 2 and (recency is None or recency <= 45):
            claim_class, confidence = "high_confidence_player_pattern", "high"
        elif count >= 2 and (diversity >= 2 or count >= 3):
            claim_class, confidence = "weak_pattern", "medium"
        else:
            claim_class, confidence = "hypothesis", "low"
        if diversity < 2:
            uncertainty = "Сигнал опирается на один тип источника; нужна независимая проверка."
        elif recency is not None and recency > 45:
            uncertainty = "Сигнал устарел; требуется свежая сессия или VOD."
        elif neutral > risk + strength:
            uncertainty = "Наблюдения неоднозначны; направленный вывод пока слабый."
        else:
            uncertainty = "Вывод ограничен доступной выборкой и не является скрытой рейтинговой оценкой."
        return {
            "domain": domain, "assessment": assessment, "claim_class": claim_class, "confidence": confidence,
            "evidence_count": count, "source_count": diversity, "recency_days": recency, "trend": self._trend_for(items),
            "uncertainty": uncertainty, "evidence": items[:6], "_priority": round(priority, 2),
        }

    @staticmethod
    def _truth_model(dimensions: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
        result = {"verified_facts": 0, "high_confidence_patterns": 0, "weak_patterns": 0, "hypotheses": 0, "unknown_dimensions": 0}
        for dim in dimensions.values():
            result["verified_facts"] += sum(1 for item in dim.get("evidence", []) if item.get("fact_class") == "verified_fact")
            cls = dim.get("claim_class")
            if cls == "high_confidence_player_pattern": result["high_confidence_patterns"] += 1
            elif cls == "weak_pattern": result["weak_patterns"] += 1
            elif cls == "hypothesis": result["hypotheses"] += 1
            elif cls == "unknown": result["unknown_dimensions"] += 1
        return result

    @staticmethod
    def _operator_state(dimensions: Mapping[str, Mapping[str, Any]], truth: Mapping[str, int]) -> dict[str, Any]:
        actionable = [d for d in dimensions.values() if d.get("assessment") == "limiting_signal" and d.get("claim_class") in {"weak_pattern", "high_confidence_player_pattern"}]
        high = sum(1 for d in dimensions.values() if d.get("claim_class") == "high_confidence_player_pattern")
        known = len(DOMAINS) - int(truth.get("unknown_dimensions") or 0)
        if known < 3:
            readiness, risk, confidence = "INSUFFICIENT_DATA", "UNKNOWN", "LOW"
        else:
            risk_strength = sum(float(d.get("_priority") or 0) for d in actionable)
            risk = "HIGH" if risk_strength >= 9 else ("MODERATE" if risk_strength >= 4 else "LOW")
            readiness = "AT_RISK" if risk == "HIGH" else ("STABLE" if risk == "MODERATE" else "READY")
            confidence = "HIGH" if high >= 2 else ("MEDIUM" if known >= 5 else "LOW")
        trends = [d.get("trend") for d in dimensions.values() if d.get("trend") != "unknown"]
        if not trends: momentum = "UNKNOWN"
        elif trends.count("declining") > trends.count("improving"): momentum = "DECLINING"
        elif trends.count("improving") > trends.count("declining"): momentum = "IMPROVING"
        else: momentum = "STABLE"
        return {"readiness": readiness, "risk": risk, "confidence": confidence, "session_momentum": momentum}

    def _mission_history(self, progression: list[dict[str, Any]]) -> dict[str, Any]:
        events = [row for row in progression if str(row.get("type") or "") == MISSION_EVENT_TYPE]
        completed_ids: set[str] = set()
        active = None
        last_review = None
        completions = {domain: 0 for domain in DOMAINS}
        for row in events:
            mission_id = str(row.get("mission_id") or "").strip()
            status = str(row.get("status") or "").casefold()
            domain = str(row.get("focus") or "").casefold()
            if status == "completed":
                completed_ids.add(mission_id)
                if domain in completions: completions[domain] += 1
                if last_review is None:
                    last_review = {"mission_id": mission_id, "focus": domain, "outcome": str(row.get("outcome") or "reported"), "metrics": dict(row.get("metrics") or {}) if isinstance(row.get("metrics"), Mapping) else {}, "at": _time_of(row)}
            elif status == "accepted" and active is None and mission_id and mission_id not in completed_ids:
                active = row
        return {"active": active, "last_review": last_review, "completions": completions}

    @staticmethod
    def _mission_id(chat_id: int, focus: str, cycle: int, evidence: list[dict[str, Any]]) -> str:
        fingerprint = {"chat_id": int(chat_id), "focus": focus, "cycle": int(cycle), "evidence": [(x.get("source"), x.get("label"), x.get("direction"), x.get("value")) for x in evidence[:5]]}
        raw = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
        return "m25-" + hashlib.sha256(raw).hexdigest()[:16]

    def _candidate(self, chat_id: int, dimensions: Mapping[str, Mapping[str, Any]], history: Mapping[str, Any]) -> dict[str, Any]:
        candidates = [dict(dim) for dim in dimensions.values() if dim.get("assessment") == "limiting_signal" and dim.get("claim_class") in {"weak_pattern", "high_confidence_player_pattern"}]
        candidates.sort(key=lambda d: (float(d.get("_priority") or 0), int(d.get("evidence_count") or 0)), reverse=True)
        calibration = not candidates
        if calibration:
            focus, template, evidence, confidence = "calibration", _CALIBRATION, [], "unknown"
            basis = "Недостаточно независимых доказательств для персональной слабости. Миссия собирает baseline без выдуманного score."
            cycle = sum(int(v or 0) for v in (history.get("completions") or {}).values())
        else:
            chosen = candidates[0]
            focus, template = str(chosen.get("domain")), _MISSIONS[str(chosen.get("domain"))]
            evidence = list(chosen.get("evidence") or [])[:5]
            confidence = str(chosen.get("confidence") or "low")
            basis = f"{chosen.get('claim_class')}: {chosen.get('evidence_count')} signals / {chosen.get('source_count')} source types. {chosen.get('uncertainty')}"
            cycle = int((history.get("completions") or {}).get(focus, 0))
        return {
            "id": self._mission_id(chat_id, focus, cycle, evidence), "status": "candidate", "focus": focus,
            "title": template["title"], "objective": template["objective"], "metrics": list(template["metrics"]),
            "success_condition": template["success"],
            "next_adaptation": "Следующая миссия выбирается только после explicit post-session result и обновления Operator Twin.",
            "confidence": confidence, "calibration": calibration, "basis": basis[:700], "evidence": evidence, "generated_at": _now_iso(),
        }

    @staticmethod
    def _active_mission(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(row, Mapping) or not isinstance(row.get("mission"), Mapping):
            return None
        mission = dict(row["mission"])
        mission["status"] = "active"
        mission["accepted_at"] = _time_of(row)
        return mission

    def snapshot(self, chat_id: int) -> dict[str, Any]:
        cid = int(chat_id)
        profile = self._profile(cid)
        mistakes = self._rows("list_mistake_stats", cid, 20)
        progression = self._rows("list_progression_events", cid, 60)
        episodes = self._rows("list_episodes", cid, 40, takes_limit=True)
        derived = self._call("get_derived_intelligence", cid, default={}) or {}
        if not isinstance(derived, Mapping): derived = {}
        evidence = self._collect_evidence(profile, mistakes, progression, episodes, derived)
        dimensions = {domain: self._dimension(domain, evidence[domain]) for domain in DOMAINS}
        truth = self._truth_model(dimensions)
        state = self._operator_state(dimensions, truth)
        history = self._mission_history(progression)
        active = self._active_mission(history.get("active"))
        mission = active or self._candidate(cid, dimensions, history)
        public_dimensions = {}
        for domain, dim in dimensions.items():
            clean = dict(dim); clean.pop("_priority", None); public_dimensions[domain] = clean
        weaknesses = [{"domain": domain, "claim_class": dim.get("claim_class"), "confidence": dim.get("confidence"), "evidence_count": dim.get("evidence_count"), "trend": dim.get("trend")} for domain, dim in dimensions.items() if dim.get("assessment") == "limiting_signal" and dim.get("claim_class") != "hypothesis"][:5]
        strengths = [{"domain": domain, "claim_class": dim.get("claim_class"), "confidence": dim.get("confidence"), "evidence_count": dim.get("evidence_count"), "trend": dim.get("trend")} for domain, dim in dimensions.items() if dim.get("assessment") == "strength_signal" and dim.get("claim_class") != "hypothesis"][:5]
        return {
            "enabled": bool(self.operator_enabled), "mission_control_enabled": bool(self.missions_enabled),
            "operator": {**state, "dimensions": public_dimensions, "weakness_signals": weaknesses, "strength_signals": strengths, "truth_model": truth, "unknown_remains_unknown": True},
            "mission": mission,
            "session": {"phase": "LIVE_OBJECTIVE" if active else "PRE_SESSION", "current_objective": mission.get("objective") if active else None, "last_review": history.get("last_review")},
        }

    def accept(self, chat_id: int, mission_id: str) -> dict[str, Any]:
        if not self.operator_enabled or not self.missions_enabled: raise MissionConflict("mission_control_disabled")
        cid = int(chat_id); requested = str(mission_id or "").strip(); current = self.snapshot(cid); mission = dict(current.get("mission") or {}); current_id = str(mission.get("id") or "")
        if mission.get("status") == "active":
            if requested and requested != current_id: raise MissionConflict("stale_mission")
            return current
        if not requested or requested != current_id: raise MissionConflict("stale_mission")
        now = _now_iso()
        self._call("add_progression_event", cid, {"type": MISSION_EVENT_TYPE, "status": "accepted", "mission_id": current_id, "focus": mission.get("focus"), "mission": mission, "source": MISSION_SOURCE, "at": now})
        self._call("add_training_session", cid, {"focus": mission.get("focus"), "kind": MISSION_EVENT_TYPE, "status": "accepted", "mission_id": current_id, "source": MISSION_SOURCE, "at": now})
        self._call("add_episode", cid, {"kind": "operator_mission_accepted", "mission_id": current_id, "focus": mission.get("focus"), "mission": mission, "source": MISSION_SOURCE, "at": now})
        try: self.profiles.patch(cid, {"training_focus": mission.get("focus"), "weekly_focus": str(mission.get("title") or "")[:160], "last_session_summary": f"LIVE OBJECTIVE: {mission.get('title')} — {mission.get('success_condition')}"[:700]})
        except Exception: pass
        return self.snapshot(cid)

    @staticmethod
    def _sanitize_metrics(metrics: Mapping[str, Any] | None, outcome: str) -> dict[str, Any]:
        source = metrics if isinstance(metrics, Mapping) else {}; out = {}
        for key, (low, high) in _ALLOWED_METRICS.items():
            if key not in source: continue
            value = _safe_number(source.get(key))
            if value is None: continue
            value = max(low, min(high, value)); out[key] = int(value) if value.is_integer() else round(value, 3)
        death_cause = str(source.get("death_cause") or "").strip()
        if death_cause: out["death_cause"] = death_cause[:240]
        if "mission_score" not in out: out["mission_score"] = {"clean": 100, "mixed": 60, "failed": 20, "reported": 50}[outcome]
        return out

    def complete(self, chat_id: int, mission_id: str, *, outcome: str = "reported", metrics: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not self.operator_enabled or not self.missions_enabled: raise MissionConflict("mission_control_disabled")
        cid = int(chat_id); current = self.snapshot(cid); mission = dict(current.get("mission") or {}); requested = str(mission_id or "").strip(); current_id = str(mission.get("id") or "")
        if mission.get("status") != "active" or not requested or requested != current_id: raise MissionConflict("active_mission_required")
        normalized = _OUTCOMES.get(" ".join(str(outcome or "").casefold().split()), "reported"); clean_metrics = self._sanitize_metrics(metrics, normalized); now = _now_iso()
        self._call("add_progression_event", cid, {"type": MISSION_EVENT_TYPE, "status": "completed", "mission_id": current_id, "focus": mission.get("focus"), "outcome": normalized, "metrics": clean_metrics, "source": "explicit_operator_report", "at": now})
        self._call("add_episode", cid, {"kind": "operator_mission_completed", "mission_id": current_id, "focus": mission.get("focus"), "outcome": normalized, "metrics": clean_metrics, "success_condition": mission.get("success_condition"), "source": "explicit_operator_report", "at": now})
        try: self.profiles.patch(cid, {"training_focus": mission.get("focus"), "last_session_summary": f"POST-SESSION REVIEW: {mission.get('title')} — {normalized}; metrics={clean_metrics}"[:700]})
        except Exception: pass
        try: PlayerMemoryService(store=self.store, profiles=self.profiles)._refresh_derived(cid, self._profile(cid))
        except Exception: pass
        next_snapshot = self.snapshot(cid); next_snapshot["session"] = {"phase": "POST_SESSION_REVIEW", "current_objective": None, "last_review": {"mission_id": current_id, "focus": mission.get("focus"), "title": mission.get("title"), "outcome": normalized, "metrics": clean_metrics, "at": now}, "memory_update": "complete"}; next_snapshot["completed_mission"] = mission; next_snapshot["next_mission"] = dict(next_snapshot.get("mission") or {})
        return next_snapshot
