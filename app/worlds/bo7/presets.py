# app/worlds/bo7/presets.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Any


def _p(prof: Dict[str, Any], key: str, default: str) -> str:
    v = (prof or {}).get(key)
    return str(v).strip() if v else default


def bo7_role_text(profile: Dict[str, Any]) -> str:
    role = _p(profile, "role", "Flex")
    platform = _p(profile, "platform", "PC")
    input_ = _p(profile, "input", "Controller")
    diff = _p(profile, "difficulty", "Normal")
    return (
        "🎭 BO7 Role Setup\n\n"
        f"Роль: {role}\n"
        f"🖥 {platform} | 🎮 {input_} | 😈 {diff}\n\n"
        "BO7 — темповая игра.\n"
        "• Entry: забираешь инфу/первый контакт\n"
        "• Slayer: закрываешь трейды\n"
        "• IGL: темп, ротации, дисциплина\n"
        "• Support: утилити и выживаемость\n"
        "• Flex: где нужно — там и ты\n"
    )


def bo7_aim_sens_text(profile: Dict[str, Any]) -> str:
    input_ = _p(profile, "input", "Controller")
    diff = _p(profile, "difficulty", "Normal")
    if input_ == "KBM":
        return (
            "🎯 BO7 Aim/Sens (KBM)\n\n"
            "• DPI 800/1600\n"
            "• сенса под стабильный трек\n"
            "• ADS без постоянных изменений\n\n"
            f"Режим: {diff}\n"
            "• Normal: чистота\n"
            "• Pro: скорость\n"
            "• Demon: пик/своп/агрессия\n"
        )
    return (
        "🎯 BO7 Aim/Sens (Controller)\n\n"
        "• deadzone минимальная\n"
        "• curve одна на неделю\n"
        "• sens: быстро, но без дрожи\n\n"
        f"Режим: {diff}\n"
        "• Normal: контроль\n"
        "• Pro: быстрее вход\n"
        "• Demon: агрессия + контроль отдачи\n"
    )


def bo7_controller_tuning_text(profile: Dict[str, Any]) -> str:
    return (
        "🎮 BO7 Controller Tuning\n\n"
        "• Deadzone минимальная без дрифта\n"
        "• Curve: если трясёт — плавнее\n"
        "• ADS: держи стабильным\n"
    )


def bo7_kbm_tuning_text(profile: Dict[str, Any]) -> str:
    return (
        "⌨️ BO7 KBM Tuning\n\n"
        "• одна сенса на неделю\n"
        "• ADS multiplier стабильно\n"
        "• пик: инфа → килл → смена угла\n"
    )


def bo7_movement_positioning_text(profile: Dict[str, Any]) -> str:
    return (
        "🧠 BO7 Movement/Positioning\n\n"
        "СЕЙЧАС:\n"
        "• углы по таймингу, не по привычке\n"
        "• после 1 килла — смещение\n"
        "• держи линию огня, но не стой на месте\n\n"
        "ДАЛЬШЕ:\n"
        "• 15 минут: пик-контроль + отмена пика\n"
        "• 10 минут: трекинг по страйфу\n"
    )


def bo7_audio_visual_text(profile: Dict[str, Any]) -> str:
    return (
        "🎧 BO7 Audio/Visual\n\n"
        "• приоритет шагам/перезарядке\n"
        "• стабильный FPS важнее графики\n"
        "• убери лишние эффекты, если теряешь цель\n"
    )
