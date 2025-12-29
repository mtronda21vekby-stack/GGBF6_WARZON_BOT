# app/worlds/warzone/presets.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Any


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


def _fmt(title: str, items: list[tuple[str, str]]) -> str:
    # красивый список “цифры на экране”
    out = [title, ""]
    for i, (k, v) in enumerate(items, 1):
        out.append(f"{i}) {k}: {v}")
    return "\n".join(out).strip()


# =========================
# WARZONE — ROLES (RU)
# =========================
def wz_role_setup_text(profile: Dict[str, Any]) -> str:
    role = _p(profile, "role", "Flex")
    diff = _diff(profile)
    plat = _plat(profile)
    inp = _p(profile, "input", "Controller")

    return (
        "🎭 Warzone — Роль (RU)\n\n"
        f"Роль: {role} | Режим: {diff}\n"
        f"Платформа: {plat} | Input: {inp}\n\n"
        "Быстро и по делу:\n"
        "• Slayer — первые 2 килла и темп.\n"
        "• Entry — открываешь файт, но не умираешь бесплатно.\n"
        "• IGL — ротации/темп/решения.\n"
        "• Support — делаешь команде комфорт и выживание.\n"
        "• Flex — закрываешь дыры.\n\n"
        "Юмор, но правда: если ты “Flex” и всё равно умираешь первым — ты не Flex, ты “флексовый труп” 😄"
    )


# =========================
# WARZONE — AIM/SENS (RU) — С ЦИФРАМИ
# =========================
def wz_aim_sens_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    plat = _plat(profile)

    if _is_kbm(profile):
        # KBM — цифры зависят от мыши, но дадим “рабочую базу”
        return _fmt(
            "🎯 Warzone — Aim/Sens (KBM) (RU)\nКопируй базу и НЕ меняй каждый день:",
            [
                ("DPI", "800 (альтернатива: 1600)"),
                ("In-game Sens", "под контроль трекинга (старт: 4.0–7.0)"),
                ("ADS Multiplier", "1.00 (старт), потом тонкая правка ±0.05"),
                ("Mouse Acceleration", "OFF"),
                ("FOV", "110–120 (чем ближе файты — тем выше)"),
                ("Режим", diff),
            ],
        ) + (
            "\n\nТест 30 сек:\n"
            "• если перелетаешь цель — -0.3 к сенсе\n"
            "• если не доводишь — +0.3\n"
        )

    # Controller — тут важны точные цифры (deadzone/ADS)
    # Deadzone rule: lowest possible without stick drift (common guidance)  [oai_citation:3‡Dexerto](https://www.dexerto.com/call-of-duty/best-warzone-controller-settings-aim-assist-sensitivity-response-curve-more-1542787/?utm_source=chatgpt.com)
    # ADS multipliers example ranges from controller guides  [oai_citation:4‡CORSAIR](https://www.scufgaming.com/us/en/gaming/games/warzone/best-controller-settings-for-season-3/?srsltid=AfmBOoppiHEnR4IIMdRe3EGsTFchAAV3ltbsyBDV_e1HuLAj6mR3saoL&utm_source=chatgpt.com)
    base_low_ads = "0.80"
    base_mid_ads = "0.85"
    if diff == "Demon":
        base_low_ads = "0.85"
        base_mid_ads = "0.90"

    return _fmt(
        f"🎯 Warzone — Aim/Sens (Controller) (RU)\nПлатформа: {plat}\nЦифры (стартовая база):",
        [
            ("FOV", "110 (если close-range ад — 115–120)"),
            ("Sensitivity (Horiz/Vert)", "6/6 (Normal) | 7/7 (Pro) | 8/8 (Demon)"),
            ("Aim Response Curve", "Dynamic (старт)"),
            ("ADS Multiplier (Low Zoom)", base_low_ads),
            ("ADS Multiplier (2x–3x)", base_mid_ads),
            ("Deadzone Left Stick Min", "0.00 → подними до исчезновения дрифта"),
            ("Deadzone Right Stick Min", "0.00 → подними до исчезновения дрожи"),
            ("Left Stick Max", "0.85 (пример базового потолка)"),
            ("Right Stick Max", "0.99 (пример базового потолка)"),
        ],
    ) + (
        "\n\nПравило (важно): deadzone ставь настолько низко, насколько можно БЕЗ дрифта. "
        "Начни с 0 и поднимай по чуть-чуть.  [oai_citation:5‡Dexerto](https://www.dexerto.com/call-of-duty/best-warzone-controller-settings-aim-assist-sensitivity-response-curve-more-1542787/?utm_source=chatgpt.com)"
        "\nADS-мульты — рабочая база из популярных гайд-сборок; дальше подгоняем под руку.  [oai_citation:6‡CORSAIR](https://www.scufgaming.com/us/en/gaming/games/warzone/best-controller-settings-for-season-3/?srsltid=AfmBOoppiHEnR4IIMdRe3EGsTFchAAV3ltbsyBDV_e1HuLAj6mR3saoL&utm_source=chatgpt.com)"
    )


# =========================
# WARZONE — CONTROLLER TUNING (RU) — С ЦИФРАМИ
# =========================
def wz_controller_tuning_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    plat = _plat(profile)

    return _fmt(
        f"🎮 Warzone — Controller Tuning (RU)\nПлатформа: {plat}\nРежим: {diff}\nСтартовые цифры:",
        [
            ("Deadzone L Min", "0.00–0.05 (до исчезновения дрифта)"),
            ("Deadzone R Min", "0.00–0.06 (до исчезновения дрожи)"),
            ("Trigger Deadzone", "0.00 (быстрее регистрирует нажатие)"),
            ("Response Curve Slope", "0.80 (если “дергаешь” — 0.70)"),
            ("Vibration", "OFF (да, так лучше)"),
        ],
    ) + (
        "\n\nТест 1 минуту:\n"
        "• стоишь на месте → смотришь прицел: если плывёт — +0.01 к R Min\n"
        "• делаешь микро-трекинг: если “тормозит” — slope ближе к 0.85\n"
    )


# =========================
# WARZONE — KBM TUNING (RU) — С ЦИФРАМИ
# =========================
def wz_kbm_tuning_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)

    return _fmt(
        f"⌨️ Warzone — KBM Tuning (RU)\nРежим: {diff}\nЦифры (база):",
        [
            ("DPI", "800"),
            ("Polling Rate", "1000 Hz (если стабильный USB)"),
            ("Windows Enhance Pointer Precision", "OFF"),
            ("In-game Sens старт", "5.0"),
            ("ADS Multiplier старт", "1.00"),
        ],
    ) + (
        "\n\nВажно: меняешь только ОДНУ вещь за раз.\n"
        "Если меняешь всё сразу — ты не настраиваешь, ты гадаешь 😄"
    )


# =========================
# WARZONE — MOVEMENT/POSITIONING (RU)
# =========================
def wz_movement_positioning_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    return (
        "🧠 Warzone — Мувмент/Позиционка (RU)\n\n"
        f"Режим: {diff}\n\n"
        "СЕЙЧАС (в бою):\n"
        "• 2–3 сек в простреле = ты просишь пулю\n"
        "• Урон дал → сместись. Килл сделал → сместись.\n"
        "• Репик одного угла = платная подписка на смерть.\n\n"
        "ДАЛЬШЕ (привычка):\n"
        "• Каждые 15 сек: «Где мой выход?»\n"
        "• Если выхода нет — ты уже труп, просто пока живёшь.\n"
    )


# =========================
# WARZONE — AUDIO/VISUAL (RU)
# =========================
def wz_audio_visual_text(profile: Dict[str, Any]) -> str:
    return (
        "🎧 Warzone — Аудио/Видео (RU)\n\n"
        "Аудио:\n"
        "• Делай шаги читаемыми, но не убивай весь микс.\n"
        "• Не меняй пресеты каждый день.\n\n"
        "Видео:\n"
        "• Приоритет — читаемость врага, а не “кино”.\n"
        "• Меньше визуального мусора = больше киллов.\n"
    )
