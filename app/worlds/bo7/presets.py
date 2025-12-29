# app/worlds/bo7/presets.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Any


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


def _fmt(title: str, items: list[tuple[str, str]]) -> str:
    out = [title, ""]
    for i, (k, v) in enumerate(items, 1):
        out.append(f"{i}) {k}: {v}")
    return "\n".join(out).strip()


def bo7_role_setup_text(profile: Dict[str, Any]) -> str:
    role = _p(profile, "role", "Flex")
    diff = _diff(profile)
    return (
        "🎭 BO7 — Роль (RU)\n\n"
        f"Роль: {role} | Режим: {diff}\n\n"
        "Правило BO7 (чтобы жить дольше 8 секунд):\n"
        "• 1 контакт → 1 килл/урон → СМЕНА позиции.\n\n"
        "Юмор: если ты стоишь на месте после килла — поздравляю, ты “стационарный таргет” 😄"
    )


def bo7_aim_sens_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)

    if _is_kbm(profile):
        return _fmt(
            "🎯 BO7 — Aim/Sens (KBM) (RU)\nБаза цифр:",
            [
                ("DPI", "800"),
                ("In-game Sens старт", "4.5–6.5"),
                ("ADS Multiplier старт", "1.00"),
                ("FOV", "110–120"),
                ("Режим", diff),
            ],
        )

    # Controller — конкретные ADS мульты часто дают 0.85 как базу  [oai_citation:8‡skycoach.gg](https://skycoach.gg/blog/call-of-duty/articles/best-black-ops-7-controller-settings?utm_source=chatgpt.com)
    low_ads = "0.85"
    mid_ads = "0.85"
    high_ads = "0.90"
    if diff == "Demon":
        low_ads = "0.90"
        mid_ads = "0.90"
        high_ads = "1.00"

    return _fmt(
        "🎯 BO7 — Aim/Sens (Controller) (RU)\nЦифры (стартовая база):",
        [
            ("Sensitivity (Horiz/Vert)", "6/6 (Normal) | 7/7 (Pro) | 8/8 (Demon)"),
            ("Aim Response Curve", "Dynamic"),
            ("ADS Multiplier (Low Zoom)", low_ads),
            ("ADS Multiplier (2x–3x)", mid_ads),
            ("ADS Multiplier (8x–9x)", high_ads),
            ("Deadzone (оба стика)", "0.00 → подними до исчезновения дрифта/дрожи"),
            ("FOV", "110"),
        ],
    ) + (
        "\n\nADS-мультипликаторы взяты из публичного BO7 гайда как “рабочая база”.  [oai_citation:9‡skycoach.gg](https://skycoach.gg/blog/call-of-duty/articles/best-black-ops-7-controller-settings?utm_source=chatgpt.com)"
        "\nДальше подгоняем: если перелетаешь — ADS чуть ниже; если не доводишь — чуть выше."
    )


def bo7_controller_tuning_text(profile: Dict[str, Any]) -> str:
    return _fmt(
        "🎮 BO7 — Controller Tuning (RU)\nЦифры (старт):",
        [
            ("Deadzone L Min", "0.00–0.05"),
            ("Deadzone R Min", "0.00–0.06"),
            ("Response Curve Slope", "0.80"),
            ("Vibration", "OFF"),
        ],
    )


def bo7_kbm_tuning_text(profile: Dict[str, Any]) -> str:
    return _fmt(
        "⌨️ BO7 — KBM Tuning (RU)\nЦифры (база):",
        [
            ("DPI", "800"),
            ("Polling Rate", "1000 Hz"),
            ("Mouse Accel", "OFF"),
            ("In-game Sens старт", "5.0"),
            ("ADS Multiplier старт", "1.00"),
        ],
    )


def bo7_movement_positioning_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    return (
        "🧠 BO7 — Мувмент/Позиционка (RU)\n\n"
        f"Режим: {diff}\n\n"
        "СЕЙЧАС:\n"
        "• Килл → смещение. Урон → смещение.\n"
        "• Если тебя “предугадывают”, значит ты повторяешься.\n\n"
        "ДАЛЬШЕ:\n"
        "• После каждого файта: «где я буду через 3 секунды?»\n"
    )


def bo7_audio_visual_text(profile: Dict[str, Any]) -> str:
    return (
        "🎧 BO7 — Аудио/Видео (RU)\n\n"
        "Аудио:\n"
        "• Сделай шаги читаемыми\n"
        "• Меньше шума = быстрее реакция\n\n"
        "Видео:\n"
        "• Читаемость врага > красота\n"
    )
