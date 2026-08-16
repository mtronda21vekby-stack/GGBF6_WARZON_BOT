# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class Intent(str, Enum):
    CASUAL = "CASUAL"
    GAME_TACTICS = "GAME_TACTICS"
    DEATH_ANALYSIS = "DEATH_ANALYSIS"
    POSITIONING = "POSITIONING"
    AIM = "AIM"
    MOVEMENT = "MOVEMENT"
    LOADOUT = "LOADOUT"
    META_CURRENT = "META_CURRENT"
    GAME_SETTINGS = "GAME_SETTINGS"
    TRAINING = "TRAINING"
    ZOMBIES = "ZOMBIES"
    VOD_TEXT_ANALYSIS = "VOD_TEXT_ANALYSIS"
    PROFILE = "PROFILE"
    PLAYER_PROGRESS = "PLAYER_PROGRESS"
    PATCH_CURRENT = "PATCH_CURRENT"
    SYSTEM_HELP = "SYSTEM_HELP"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class IntentResult:
    intent: Intent
    confidence: float
    needs_current_data: bool = False
    needs_player_memory: bool = False
    preferred_depth: str = "medium"
    reason: str = ""


def _norm(text: str) -> str:
    return " ".join((text or "").lower().replace("ё", "е").split())


def _has(text: str, *phrases: str) -> bool:
    return any(p in text for p in phrases)


def classify_intent(text: str, profile: Mapping[str, Any] | None = None) -> IntentResult:
    t = _norm(text)
    profile = profile or {}
    if not t:
        return IntentResult(Intent.UNKNOWN, 1.0, reason="empty")
    if t in {"привет", "привет!", "здарова", "здравствуйте", "hello", "hi", "йо", "ку"}:
        return IntentResult(Intent.CASUAL, 0.99, preferred_depth="short", reason="greeting")
    if _has(t, "помощь", "что ты умеешь", "как пользоваться", "команды", "help"):
        return IntentResult(Intent.SYSTEM_HELP, 0.95, preferred_depth="short", reason="help keywords")
    if _has(t, "последний патч", "после патча", "патчноут", "patch note", "что изменили сегодня", "что поменяли сегодня", "обновлени"):
        return IntentResult(Intent.PATCH_CURRENT, 0.98, needs_current_data=True, preferred_depth="medium", reason="current patch request")
    if _has(t, "сейчас мета", "текущая мета", "мета сейчас", "что в мете", "лучшая пушка сейчас", "лучшее оружие сейчас", "какая пушка сейчас", "current meta"):
        return IntentResult(Intent.META_CURRENT, 0.98, needs_current_data=True, needs_player_memory=True, preferred_depth="medium", reason="current meta request")

    zombies_active = str(profile.get("zombies_active", "0")) == "1"
    if zombies_active or _has(t, "зомби", "zombies", "ashes", "astra", "pack-a-punch", "пасхал", "перки"):
        return IntentResult(Intent.ZOMBIES, 0.95, needs_player_memory=True, preferred_depth="medium", reason="zombies world")
    if _has(t, "vod", "таймкод", "тайм-код", "разбери клип", "разбор клипа", "разбери запись"):
        return IntentResult(Intent.VOD_TEXT_ANALYSIS, 0.94, needs_player_memory=True, preferred_depth="deep", reason="vod/timestamp request")
    if _has(t, "трениров", "дрилл", "разминк", "план на 20", "план трен", "как тренировать"):
        return IntentResult(Intent.TRAINING, 0.95, needs_player_memory=True, preferred_depth="deep", reason="training request")
    if _has(t, "сенс", "sensitivity", "deadzone", "мертвая зона", "fov", "aim assist", "настрой контрол", "настрой мыш", "настройки игры"):
        return IntentResult(Intent.GAME_SETTINGS, 0.95, needs_player_memory=True, preferred_depth="medium", reason="settings request")
    if _has(t, "сборк", "loadout", "лоадаут", "обвес", "аттач", "attachment", "какую пушку", "какое оружие", "что поставить на", "билд оруж"):
        return IntentResult(Intent.LOADOUT, 0.93, needs_player_memory=True, preferred_depth="medium", reason="loadout request")
    if _has(t, "умер", "умираю", "убили", "сдох", "проиграл файт", "проигрываю файт", "почему меня", "разбери смерть"):
        return IntentResult(Intent.DEATH_ANALYSIS, 0.96, needs_player_memory=True, preferred_depth="deep", reason="death/fight loss")
    if _has(t, "ротац", "позицион", "позици", "хайграунд", "high ground", "угол", "зона", "спавн"):
        return IntentResult(Intent.POSITIONING, 0.91, needs_player_memory=True, preferred_depth="medium", reason="positioning keywords")
    if _has(t, "аим", "aim", "отдач", "трек", "флик", "меткост", "прицел"):
        return IntentResult(Intent.AIM, 0.91, needs_player_memory=True, preferred_depth="medium", reason="aim keywords")
    if _has(t, "мувмент", "movement", "слайд", "стрейф", "прыж", "бхоп", "движен", "двигат"):
        return IntentResult(Intent.MOVEMENT, 0.91, needs_player_memory=True, preferred_depth="medium", reason="movement keywords")
    if _has(t, "мой профиль", "профиль игрока", "мой ранг", "мой kd", "мой кд"):
        return IntentResult(Intent.PROFILE, 0.94, needs_player_memory=True, preferred_depth="short")
    if _has(t, "мой прогресс", "прогресс", "стал лучше", "стал хуже", "за неделю", "за месяц"):
        return IntentResult(Intent.PLAYER_PROGRESS, 0.92, needs_player_memory=True, preferred_depth="deep", reason="progress request")
    if _has(t, "тильт", "сгорел", "слил пять", "слил 5", "лузстрик", "loss streak", "пуш", "файт", "как играть", "тактик", "что делать", "как выиграть", "как заходить"):
        return IntentResult(Intent.GAME_TACTICS, 0.82, needs_player_memory=True, preferred_depth="medium", reason="general tactical/emotional gameplay request")
    return IntentResult(Intent.UNKNOWN, 0.45, needs_player_memory=True, preferred_depth="medium", reason="no deterministic match")
