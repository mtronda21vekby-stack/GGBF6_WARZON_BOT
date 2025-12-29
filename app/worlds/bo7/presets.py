# app/worlds/bo7/presets.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Any, List, Tuple


def _p(prof: Dict[str, Any], key: str, default: str) -> str:
    v = (prof or {}).get(key)
    return str(v).strip() if v else default


def _is_kbm(profile: Dict[str, Any]) -> bool:
    return _p(profile, "input", "Controller").upper() == "KBM"


def _diff(profile: Dict[str, Any]) -> str:
    d = _p(profile, "difficulty", "Normal").lower()
    if "demon" in d:
        return "Demon"
    if "pro" in d:
        return "Pro"
    return "Normal"


def _fmt(title: str, items: List[Tuple[str, str]], footer: str = "") -> str:
    out = [title.strip(), ""]
    for i, (k, v) in enumerate(items, 1):
        out.append(f"{i}) {k}: {v}")
    if footer:
        out.append("")
        out.append(footer.strip())
    return "\n".join(out).strip()


# =========================
# BO7 — ROLE (RU)
# =========================
def bo7_role_setup_text(profile: Dict[str, Any]) -> str:
    role = _p(profile, "role", "Flex")
    diff = _diff(profile)

    return (
        "🎭 BO7 — Роль\n\n"
        f"Роль: {role} | Режим: {diff}\n\n"
        "Правило BO7 (чтобы жить дольше 8 секунд):\n"
        "• 1 контакт → 1 килл/урон → СМЕНА позиции.\n\n"
        "Юмор: если ты стоишь на месте после килла — поздравляю, ты “стационарный таргет” 😄"
    )


# =========================
# BO7 — AIM/SENS (RU) — С ЦИФРАМИ
# =========================
def bo7_aim_sens_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    role = _p(profile, "role", "Flex")

    if _is_kbm(profile):
        return _fmt(
            f"🎯 BO7 — Aim/Sens (KBM)\nРежим: {diff} | Роль: {role}\nБаза цифр:",
            [
                ("DPI", "800 (альтернатива: 1600)"),
                ("Polling Rate", "1000 Hz"),
                ("Windows Acceleration", "OFF"),
                ("In-game Sens старт", "4.5–6.5 (начни с 5.5)"),
                ("ADS Multiplier старт", "1.00"),
                ("FOV", "110–120"),
            ],
            footer=(
                "Тест 30 сек:\n"
                "• перелетаешь — -0.2 к сенсе\n"
                "• не доводишь — +0.2\n"
                "Секрет: стабильность важнее “вчера я нашёл идеал” 😄"
            ),
        )

    # Controller — “цифры на экране”
    low_ads = "0.85"
    mid_ads = "0.85"
    high_ads = "0.90"
    sens = "6/6"
    if diff == "Pro":
        sens = "7/7"
        low_ads = "0.87"
        mid_ads = "0.87"
        high_ads = "0.92"
    if diff == "Demon":
        sens = "8/8"
        low_ads = "0.90"
        mid_ads = "0.90"
        high_ads = "1.00"

    return _fmt(
        f"🎯 BO7 — Aim/Sens (Controller)\nРежим: {diff} | Роль: {role}\nЦифры (стартовая база):",
        [
            ("Sensitivity (Horiz/Vert)", sens),
            ("Aim Response Curve", "Dynamic"),
            ("ADS Multiplier (Low Zoom)", low_ads),
            ("ADS Multiplier (2x–3x)", mid_ads),
            ("ADS Multiplier (8x–9x)", high_ads),
            ("Deadzone (оба стика)", "0.00 → подними до исчезновения дрифта/дрожи"),
            ("FOV", "110"),
            ("Vibration", "OFF"),
        ],
        footer=(
            "Подгонка:\n"
            "• перелетаешь — ADS вниз на 0.02\n"
            "• не доводишь — ADS вверх на 0.02\n"
            "И пожалуйста: не меняй это каждый вечер как обои 😄"
        ),
    )


# =========================
# BO7 — CONTROLLER TUNING (RU) — С ЦИФРАМИ
# =========================
def bo7_controller_tuning_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    slope = "0.80"
    if diff == "Pro":
        slope = "0.83"
    if diff == "Demon":
        slope = "0.86"

    return _fmt(
        f"🎮 BO7 — Controller Tuning\nРежим: {diff}\nЦифры (старт):",
        [
            ("Deadzone L Min", "0.00–0.05"),
            ("Deadzone R Min", "0.00–0.06"),
            ("Trigger Deadzone", "0.00"),
            ("Response Curve Slope", slope),
            ("Vibration", "OFF"),
            ("Auto Sprint", "ON (если контроль не страдает)"),
        ],
        footer=(
            "Тест 60 сек:\n"
            "• прицел “плывёт” = +0.01 к R Min\n"
            "• микротрекинг “ватный” = slope чуть выше\n"
            "• дергаешься = slope ниже\n"
        ),
    )


# =========================
# BO7 — KBM TUNING (RU) — С ЦИФРАМИ
# =========================
def bo7_kbm_tuning_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    return _fmt(
        f"⌨️ BO7 — KBM Tuning\nРежим: {diff}\nЦифры (база):",
        [
            ("DPI", "800"),
            ("Polling Rate", "1000 Hz"),
            ("Mouse Accel", "OFF"),
            ("In-game Sens старт", "5.0"),
            ("ADS Multiplier старт", "1.00"),
        ],
        footer="Правило: одна база на неделю. Иначе ты тренируешь “сюрприз” вместо аима 😄",
    )


# =========================
# BO7 — MOVEMENT/POSITIONING (RU)
# =========================
def bo7_movement_positioning_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    role = _p(profile, "role", "Flex")

    return (
        "🧠 BO7 — Мувмент/Позиционка\n\n"
        f"Режим: {diff} | Роль: {role}\n\n"
        "1) Диагноз:\n"
        "• Если тебя “предугадывают” — ты повторяешься.\n\n"
        "2) СЕЙЧАС:\n"
        "• Килл → смещение.\n"
        "• Урон → смещение.\n"
        "• Не стой на месте: BO7 любит наказывать “статую”.\n\n"
        "3) ДАЛЬШЕ:\n"
        "• После каждого файта: «где я буду через 3 секунды?»\n"
    )


# =========================
# BO7 — AUDIO/VISUAL (RU)
# =========================
def bo7_audio_visual_text(profile: Dict[str, Any]) -> str:
    return (
        "🎧 BO7 — Аудио/Видео\n\n"
        "Аудио:\n"
        "• Сделай шаги читаемыми.\n"
        "• Меньше шума = быстрее реакция.\n\n"
        "Видео:\n"
        "• Читаемость врага > красота.\n"
    )
