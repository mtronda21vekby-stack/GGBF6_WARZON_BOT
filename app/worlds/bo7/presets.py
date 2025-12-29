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


def _role(profile: Dict[str, Any]) -> str:
    r = _p(profile, "role", "Flex").lower()
    if "slay" in r:
        return "Slayer"
    if "entry" in r or "энтри" in r:
        return "Entry"
    if "igl" in r:
        return "IGL"
    if "support" in r or "саппорт" in r:
        return "Support"
    return "Flex"


def _fmt(title: str, items: list[tuple[str, str]]) -> str:
    out = [title, ""]
    for i, (k, v) in enumerate(items, 1):
        out.append(f"{i}) {k}: {v}")
    return "\n".join(out).strip()


def _micro_test_block(diff: str) -> str:
    if diff == "Demon":
        tip = "быстро, нагло, но контролируемо"
    elif diff == "Pro":
        tip = "быстро и чисто"
    else:
        tip = "стабильно и без истерики"

    return (
        "\n\n🧪 ТЕСТ 60 СЕК (быстрый тюнинг):\n"
        "1) 20 сек трекинг → 20 сек флики → 20 сек контроль отдачи.\n"
        "2) Перелёт = -0.05 ADS / -0.3 sens.\n"
        "3) Не дотягиваешь = +0.05 ADS / +0.3 sens.\n"
        "4) Меняй одну штуку за раз.\n"
        f"Темп режима: {tip} 😈\n"
    )


def _checklist_block() -> str:
    return (
        "\n\n✅ ЧЕК-ЛИСТ (чтобы не сломать себе руку и мозг):\n"
        "• 2 дня НЕ меняй цифры после установки.\n"
        "• Если дрожь — сначала deadzone/ADS, потом всё остальное.\n"
        "• Если “не летит” один матч — это не повод переписывать вселенную.\n"
        "• Стабильность = скилл, не скука 😄\n"
    )


# =========================
# BO7 — ROLE (RU)
# =========================
def bo7_role_setup_text(profile: Dict[str, Any]) -> str:
    role = _role(profile)
    diff = _diff(profile)

    role_rule = {
        "Slayer": "• Два килла → смещение. Урон дал → смещение. (Да, снова смещение.)",
        "Entry": "• Входишь первым, но с инфой: плечо-чек/префаер/граната.",
        "IGL": "• Контроль темпа: ты решаешь где жить, а не где умереть.",
        "Support": "• Делаешь комфорт: прикрытие, размены, сейв тиммейта.",
        "Flex": "• Закрываешь дыры: сегодня ты entry, завтра support — выживание важнее эго.",
    }.get(role, "• Flex = адаптация. Не адаптируешься — тебя адаптируют в килл-кам.")

    return (
        "🎭 BO7 — Роль (RU)\n\n"
        f"Роль: {role} | Режим: {diff}\n\n"
        "Правило BO7 (чтобы жить дольше 8 секунд):\n"
        "• 1 контакт → 1 килл/урон → СМЕНА позиции.\n"
        f"{role_rule}\n\n"
        "😄 Юмор: если ты стоишь на месте после килла — поздравляю, ты “стационарный таргет”."
    )


# =========================
# BO7 — AIM/SENS (RU) — цифры + тест + чеклист
# =========================
def bo7_aim_sens_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    role = _role(profile)

    if _is_kbm(profile):
        base_sens = "5.2"
        if diff == "Pro":
            base_sens = "5.9"
        if diff == "Demon":
            base_sens = "6.4"

        return (
            _fmt(
                "🎯 BO7 — Aim/Sens (KBM) (RU)\n"
                f"Роль: {role} | Режим: {diff}\n"
                "База цифр (рабочий старт):",
                [
                    ("DPI", "800 (альтернатива: 1600)"),
                    ("Polling Rate", "1000 Hz"),
                    ("Mouse Accel", "OFF"),
                    ("In-game Sens (старт)", base_sens),
                    ("ADS Multiplier", "1.00 (потом ±0.05)"),
                    ("FOV", "110–120"),
                    ("Motion Blur", "OFF"),
                ],
            )
            + _micro_test_block(diff)
            + _checklist_block()
        )

    # Controller
    if diff == "Normal":
        sens = "6/6"
        low_ads = "0.85"
        mid_ads = "0.85"
        high_ads = "0.90"
        rmin = "0.03–0.06"
    elif diff == "Pro":
        sens = "7/7"
        low_ads = "0.90"
        mid_ads = "0.90"
        high_ads = "0.95"
        rmin = "0.03–0.06"
    else:
        sens = "8/8"
        low_ads = "0.95"
        mid_ads = "0.95"
        high_ads = "1.00"
        rmin = "0.04–0.07"

    return (
        _fmt(
            "🎯 BO7 — Aim/Sens (Controller) (RU)\n"
            f"Роль: {role} | Режим: {diff}\n"
            "Цифры (стартовая база):",
            [
                ("Sensitivity (Horiz/Vert)", sens),
                ("Aim Response Curve", "Dynamic"),
                ("ADS Multiplier (Low Zoom)", low_ads),
                ("ADS Multiplier (2x–3x)", mid_ads),
                ("ADS Multiplier (8x–9x)", high_ads),
                ("Deadzone Left Stick Min", "0.00 → до исчезновения дрифта"),
                ("Deadzone Right Stick Min", rmin),
                ("FOV", "110"),
                ("Vibration", "OFF"),
            ],
        )
        + _micro_test_block(diff)
        + _checklist_block()
        + "\n\n🔥 Подсказка:\n"
          "• трясёт = R Min +0.01 или ADS -0.05\n"
          "• не доводишь = ADS +0.05 или sens +1\n"
    )


# =========================
# BO7 — CONTROLLER TUNING (RU)
# =========================
def bo7_controller_tuning_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    role = _role(profile)

    if diff == "Normal":
        slope = "0.75"
        rmin = "0.03–0.06"
    elif diff == "Pro":
        slope = "0.80"
        rmin = "0.03–0.06"
    else:
        slope = "0.85"
        rmin = "0.04–0.07"

    return (
        _fmt(
            "🎮 BO7 — Controller Tuning (RU)\n"
            f"Роль: {role} | Режим: {diff}\n"
            "Цифры (старт):",
            [
                ("Deadzone L Min", "0.00–0.05"),
                ("Deadzone R Min", rmin),
                ("Response Curve Slope", slope),
                ("Vibration", "OFF"),
                ("Trigger Deadzone", "0.00"),
            ],
        )
        + _micro_test_block(diff)
        + _checklist_block()
    )


# =========================
# BO7 — KBM TUNING (RU)
# =========================
def bo7_kbm_tuning_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    role = _role(profile)

    return (
        _fmt(
            "⌨️ BO7 — KBM Tuning (RU)\n"
            f"Роль: {role} | Режим: {diff}\n"
            "Цифры (база):",
            [
                ("DPI", "800"),
                ("Polling Rate", "1000 Hz"),
                ("Mouse Accel", "OFF"),
                ("In-game Sens старт", "5.2"),
                ("ADS Multiplier старт", "1.00"),
                ("FOV", "110–120"),
            ],
        )
        + _micro_test_block(diff)
        + _checklist_block()
        + "\n\n😄 Юмор: если хочешь “идеальную сенсу” за 2 минуты — это не настройки, это вера."
    )


# =========================
# BO7 — MOVEMENT/POSITIONING (RU)
# =========================
def bo7_movement_positioning_text(profile: Dict[str, Any]) -> str:
    diff = _diff(profile)
    role = _role(profile)

    now = [
        "• Килл → смещение. Урон → смещение.",
        "• Если тебя предугадывают — значит ты повторяешься.",
        "• Не стой на трупе: труп — магнит для гранат.",
    ]
    if diff == "Demon":
        now += [
            "• Плечо-чек → пик на килл → смена позиции. Быстро. Чисто.",
            "• Никаких “ещё разок выгляну” — это подписка на киллкам.",
        ]

    later = [
        "• После каждого файта: «где я буду через 3 секунды?»",
        "• Привычка: всегда держи 2 выхода из зоны.",
        "• Если нет выхода — ты уже проиграл позиционку.",
    ]

    return (
        "🧠 BO7 — Мувмент/Позиционка (RU)\n\n"
        f"Роль: {role} | Режим: {diff}\n\n"
        "СЕЙЧАС:\n" + "\n".join(now) + "\n\n"
        "ДАЛЬШЕ:\n" + "\n".join(later) + "\n\n"
        "😄 Юмор: если ты играешь “в стойку” — ты не герой, ты статуя."
    )


# =========================
# BO7 — AUDIO/VISUAL (RU)
# =========================
def bo7_audio_visual_text(profile: Dict[str, Any]) -> str:
    return (
        "🎧 BO7 — Аудио/Видео (RU)\n\n"
        "Аудио:\n"
        "1) Сделай шаги читаемыми (и свои тоже — чтобы не шёл как слон).\n"
        "2) Не меняй пресет каждый день.\n"
        "3) Если слышишь всё подряд — ты слышишь шум, а не инфу.\n\n"
        "Видео:\n"
        "1) Читаемость врага > кино.\n"
        "2) Меньше эффектов = быстрее реакция.\n\n"
        "😄 Юмор: если у тебя “идеальная картинка”, но ты слепой в файте — это не графика, это привычки."
    )
