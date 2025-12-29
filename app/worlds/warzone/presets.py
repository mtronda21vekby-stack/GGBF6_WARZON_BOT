# app/worlds/warzone/presets.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Any, List, Tuple


def _p(prof: Dict[str, Any], key: str, default: str) -> str:
    v = (prof or {}).get(key)
    return str(v).strip() if v else default


def _is_kbm(profile: Dict[str, Any]) -> bool:
    return _p(profile, "input", "Controller").upper() == "KBM"


def _diff(profile: Dict[str, Any]) -> str:
    d = _p(profile, "difficulty", "Normal")
    d_low = d.lower()
    if "demon" in d_low:
        return "Demon"
    if "pro" in d_low:
        return "Pro"
    return "Normal"


def _plat(profile: Dict[str, Any]) -> str:
    p = _p(profile, "platform", "PC")
    if "play" in p.lower():
        return "PlayStation"
    if "xbox" in p.lower():
        return "Xbox"
    return "PC"


def _fmt(title: str, items: List[Tuple[str, str]], footer: str = "") -> str:
    # красивый список “цифры на экране”
    out = [title.strip(), ""]
    for i, (k, v) in enumerate(items, 1):
        out.append(f"{i}) {k}: {v}")
    if footer:
        out.append("")
        out.append(footer.strip())
    return "\n".join(out).strip()


# =========================
# WARZONE — ROLES (RU)
# =========================
def wz_role_setup_text(profile: Dict[str, Any]) -> str:
    role = _p(profile, "role", "Flex")
    diff = _diff(profile)
    plat = _plat(profile)
    inp = _p(profile, "input", "Controller")

    role_notes = {
        "Slayer": "⚔️ Slayer — первые 2 килла, темп, “я вошёл — выдохнули”.",
        "Entry": "🚪 Entry — открываешь файт, но НЕ по подписке “умираю первым”.",
        "IGL": "🧠 IGL — ротации/темп/решения. Ты мозг, а не украшение.",
        "Support": "🛡 Support — сейвы, ресы, инфа, комфорт. Ты причина побед.",
        "Flex": "🌀 Flex — закрываешь дыры. Если дыр слишком много — меняй тиммейтов 😄",
    }
    rr = role_notes.get(role, role_notes["Flex"])

    return (
        "🎭 Warzone — Роль\n\n"
        f"Роль: {role} | Режим: {diff}\n"
        f"Платформа: {plat} | Input: {inp}\n\n"
        "Коротко и по делу:\n"
        f"• {rr}\n\n"
        "Юмор, но правда: если ты “Flex” и всё равно умираешь первым — ты не Flex, ты “флексовый труп” 😄"
    )


# =========================
# WARZONE — AIM/SENS (RU) — С ЦИФРАМИ
# =========================
def wz_aim_sens_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    plat = _plat(profile)
    role = _p(profile, "role", "Flex")

    if _is_kbm(profile):
        # KBM — цифры зависят от мыши/ковра, но даём “рабочую базу”
        return _fmt(
            "🎯 Warzone — Aim/Sens (KBM)\nКопируй базу и НЕ меняй каждый день:",
            [
                ("DPI", "800 (альтернатива: 1600)"),
                ("Polling Rate", "1000 Hz (если USB стабилен)"),
                ("Windows Acceleration", "OFF"),
                ("In-game Sens (старт)", "4.0–7.0 (начни с 5.0)"),
                ("ADS Multiplier (старт)", "1.00 (правка потом ±0.05)"),
                ("FOV", "110–120 (ближе файты → выше)"),
                ("Режим", diff),
                ("Роль", role),
            ],
            footer=(
                "Тест 30 сек:\n"
                "• перелетаешь цель — -0.3 к сенсе\n"
                "• не доводишь — +0.3\n"
                "Правило: меняешь только ОДНУ штуку за раз, иначе это гадание на коврике 😄"
            ),
        )

    # Controller — тут нужны “цифры на экране”
    # ADS и deadzone подгоняются под руку/стики, но стартовая база нужна.
    base_low_ads = "0.80"
    base_mid_ads = "0.85"
    if diff == "Pro":
        base_low_ads = "0.82"
        base_mid_ads = "0.87"
    if diff == "Demon":
        base_low_ads = "0.85"
        base_mid_ads = "0.90"

    sens = "6/6"
    if diff == "Pro":
        sens = "7/7"
    if diff == "Demon":
        sens = "8/8"

    return _fmt(
        f"🎯 Warzone — Aim/Sens (Controller)\nПлатформа: {plat}\nЦифры (стартовая база):",
        [
            ("FOV", "110 (если close-range ад → 115–120)"),
            ("Sensitivity (Horiz/Vert)", f"{sens}"),
            ("Aim Response Curve", "Dynamic (старт)"),
            ("ADS Multiplier (Low Zoom)", base_low_ads),
            ("ADS Multiplier (2x–3x)", base_mid_ads),
            ("Deadzone Left Stick Min", "0.00 → подними до исчезновения дрифта"),
            ("Deadzone Right Stick Min", "0.00 → подними до исчезновения дрожи"),
            ("Left Stick Max", "0.85 (старт)"),
            ("Right Stick Max", "0.99 (старт)"),
            ("Vibration", "OFF (да, так лучше)"),
            ("Режим/Роль", f"{diff} / {role}"),
        ],
        footer=(
            "Правило №1: Deadzone ставь настолько низко, насколько можно БЕЗ дрифта.\n"
            "Правило №2: Если “перелетаешь” — снижай ADS на 0.02. Если “не доводишь” — поднимай ADS на 0.02.\n"
            "И да: если ты меняешь сенсу каждый день — ты тренируешь хаос, а не аим 😄"
        ),
    )


# =========================
# WARZONE — CONTROLLER TUNING (RU) — С ЦИФРАМИ
# =========================
def wz_controller_tuning_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    plat = _plat(profile)
    role = _p(profile, "role", "Flex")

    slope = "0.80"
    if diff == "Pro":
        slope = "0.83"
    if diff == "Demon":
        slope = "0.86"

    return _fmt(
        f"🎮 Warzone — Controller Tuning\nПлатформа: {plat} | Режим: {diff} | Роль: {role}\nСтартовые цифры:",
        [
            ("Deadzone L Min", "0.00–0.05 (до исчезновения дрифта)"),
            ("Deadzone R Min", "0.00–0.06 (до исчезновения дрожи)"),
            ("Trigger Deadzone", "0.00 (быстрее регистрирует нажатие)"),
            ("Response Curve Slope", slope),
            ("Vibration", "OFF"),
            ("Auto Sprint", "ON (если не ломает контроль)"),
            ("Aim Assist", "ON (очевидно 😄)"),
        ],
        footer=(
            "Тест 60 сек:\n"
            "• стоишь → прицел плывёт = +0.01 к R Min\n"
            "• микротрекинг “тормозит” = slope чуть выше\n"
            "• если дергаешься = slope ниже\n"
        ),
    )


# =========================
# WARZONE — KBM TUNING (RU) — С ЦИФРАМИ
# =========================
def wz_kbm_tuning_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    role = _p(profile, "role", "Flex")

    return _fmt(
        f"⌨️ Warzone — KBM Tuning\nРежим: {diff} | Роль: {role}\nЦифры (база):",
        [
            ("DPI", "800"),
            ("Polling Rate", "1000 Hz"),
            ("Windows Enhance Pointer Precision", "OFF"),
            ("In-game Sens старт", "5.0"),
            ("ADS Multiplier старт", "1.00"),
            ("FOV", "110–120"),
        ],
        footer=(
            "Важно: меняешь только ОДНУ вещь за раз.\n"
            "Если меняешь всё сразу — ты не настраиваешь, ты гадаешь 😄"
        ),
    )


# =========================
# WARZONE — MOVEMENT/POSITIONING (RU)
# =========================
def wz_movement_positioning_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    role = _p(profile, "role", "Flex")

    return (
        "🧠 Warzone — Мувмент/Позиционка\n\n"
        f"Режим: {diff} | Роль: {role}\n\n"
        "1) Диагноз:\n"
        "• 2–3 сек в простреле = ты просишь пулю.\n"
        "• Репик одного угла = платная подписка на смерть.\n\n"
        "2) СЕЙЧАС (в бою):\n"
        "• Урон дал → сместись.\n"
        "• Килл сделал → сместись.\n"
        "• Если тебя “предугадывают” — ты повторяешься.\n\n"
        "3) ДАЛЬШЕ (привычка):\n"
        "• Каждые 15 сек: «Где мой выход?»\n"
        "• Выхода нет — значит ты уже труп, просто пока живёшь 😄\n"
    )


# =========================
# WARZONE — AUDIO/VISUAL (RU)
# =========================
def wz_audio_visual_text(profile: Dict[str, Any]) -> str:
    return (
        "🎧 Warzone — Аудио/Видео\n\n"
        "Аудио:\n"
        "• Сделай шаги читаемыми, но не убивай весь микс.\n"
        "• Один пресет на неделю — иначе мозг не адаптируется.\n\n"
        "Видео:\n"
        "• Приоритет: читаемость врага, а не “кино”.\n"
        "• Меньше визуального мусора = больше киллов.\n"
    )
