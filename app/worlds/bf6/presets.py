# app/worlds/bf6/presets.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Any


def _p(profile: Dict[str, Any], key: str, default: str) -> str:
    v = (profile or {}).get(key)
    return str(v).strip() if v else default


# =========================================================
# BF6 КЛАССЫ — НА РУССКОМ (это не настройки, а геймплей)
# =========================================================
def bf6_class_text(profile: Dict[str, Any]) -> str:
    cls = _p(profile, "bf6_class", "Assault")
    inp = _p(profile, "input", "Controller")
    plat = _p(profile, "platform", "PC")
    diff = _p(profile, "difficulty", "Normal")

    base = (
        f"🪖 BF6 — Класс: {cls}\n"
        f"🖥 Платформа: {plat}\n"
        f"🎮 Управление: {inp}\n"
        f"😈 Режим: {diff}\n\n"
        "Роль и приоритеты:\n"
    )

    if cls == "Assault":
        return base + (
            "🟥 Assault — вход, размен, первый контакт.\n"
            "• Заходи по таймингу, не по эго.\n"
            "• 1–2 фрага → сразу смена позиции.\n"
            "• Не репикай один и тот же угол.\n"
        )

    if cls == "Recon":
        return base + (
            "🟦 Recon — информация и контроль дистанции.\n"
            "• Держи мид/даль и давай коллы.\n"
            "• Не умирай первым — ты ценность.\n"
            "• После 1–2 пиков меняй линию.\n"
        )

    if cls == "Engineer":
        return base + (
            "🟨 Engineer — техника, фланги, анти-гаджеты.\n"
            "• Ломай сетапы и технику.\n"
            "• Играй от маршрутов, не от центра.\n"
            "• Всегда держи путь отхода.\n"
        )

    if cls == "Medic":
        return base + (
            "🟩 Medic — темп и ресы.\n"
            "• Ресай только с дымом/контролем.\n"
            "• Рес → сразу смена позиции.\n"
            "• Не стой на трупе.\n"
        )

    return base + "Класс не распознан. Открой 🪖 Класс и выбери заново."


# =========================================================
# BF6 AIM / SENS — НА АНГЛИЙСКОМ (НАСТРОЙКИ УСТРОЙСТВ)
# =========================================================
def bf6_aim_sens_text(profile: Dict[str, Any]) -> str:
    inp = _p(profile, "input", "Controller")
    diff = _p(profile, "difficulty", "Normal")

    if inp == "KBM":
        return (
            "🎯 BF6 Aim / Sens (KBM)\n\n"
            "Base settings:\n"
            "• DPI: 800 (or 1600)\n"
            "• In-game sensitivity: controlled tracking\n"
            "• ADS multiplier: keep consistent\n\n"
            f"Mode: {diff}\n"
            "• Normal: consistency > speed\n"
            "• Pro: faster micro-adjustments\n"
            "• Demon: snap shots + aggressive peeks\n"
        )

    return (
        "🎯 BF6 Aim / Sens (Controller)\n\n"
        "Base settings:\n"
        "• Sensitivity: medium-high, no jitter\n"
        "• Deadzone: minimal without drift\n"
        "• Aim response curve: choose one and stick to it\n\n"
        f"Mode: {diff}\n"
        "• Normal: smooth control\n"
        "• Pro: faster target acquisition\n"
        "• Demon: aggression with recoil control\n"
    )


# =========================================================
# BF6 CONTROLLER TUNING — EN (Xbox / PlayStation)
# =========================================================
def bf6_controller_tuning_text(profile: Dict[str, Any]) -> str:
    cls = _p(profile, "bf6_class", "Assault")
    return (
        "🎮 BF6 Controller Tuning\n\n"
        f"Class: {cls}\n\n"
        "1) Deadzones:\n"
        "• Left stick: minimal without drift\n"
        "• Right stick: minimal without shake\n\n"
        "2) Response curve:\n"
        "• Too shaky → smoother curve\n"
        "• Too slow → closer to linear\n\n"
        "3) FOV / ADS:\n"
        "• Do not change daily — adaptation matters\n"
    )


# =========================================================
# BF6 KBM TUNING — EN (PC)
# =========================================================
def bf6_kbm_tuning_text(profile: Dict[str, Any]) -> str:
    cls = _p(profile, "bf6_class", "Assault")
    return (
        "⌨️ BF6 KBM Tuning\n\n"
        f"Class: {cls}\n\n"
        "1) Sensitivity:\n"
        "• One base sensitivity for the whole week\n"
        "• Predictable ADS behavior\n\n"
        "2) Movement:\n"
        "• Strafe control while tracking\n"
        "• Peek rule: info → kill → reposition\n"
    )
