# -*- coding: utf-8 -*-

# ====== Warzone ======

WZ_PAD = (
    "🎮 Warzone — Controller (PS5/Xbox)\n\n"
    "✅ Base (универсально, топ-уровень)\n"
    "• Sens: 6–8 (начни с 7)\n"
    "• ADS Multiplier: 0.85–0.95 (начни с 0.90)\n"
    "• Aim Response Curve: Dynamic (если не заходит → Standard)\n"
    "• Deadzone MIN: 0.03–0.06 (если дрифт → 0.07–0.10)\n"
    "• FOV: 105–110 | ADS FOV: Affected | Weapon FOV: Wide\n"
    "• Auto Sprint: ON | Slide Behavior: Tap | Dive/Slide: Hybrid (по вкусу)\n"
    "• Camera Movement: Least (или 50%)\n\n"
    "🎯 Быстрый тест:\n"
    "1) 10 мин: трекинг + микро-фиксы\n"
    "2) Если перелетаешь — Sens -1 или ADS -0.05\n"
)

WZ_MNK = (
    "🖱 Warzone — Mouse & Keyboard (PC)\n\n"
    "✅ Base\n"
    "• DPI: 800 (или 1600, но тогда ниже sens)\n"
    "• In-game sens: 4–7 (подбирай, чтобы 180° = комфорт)\n"
    "• ADS sens multiplier: 0.80–1.00\n"
    "• FOV: 105–110 | ADS FOV: Affected | Weapon FOV: Wide\n"
    "• Mouse filtering / smoothing: OFF\n"
    "• Raw input: ON (если есть)\n\n"
    "🎯 Тест:\n"
    "• 5 мин: трекинг (не рви мышь)\n"
    "• 5 мин: флик 1 выстрел → контроль отдачи\n"
)

# ====== BO7 ======

BO7_PAD = (
    "🎮 BO7 — Controller (PS5/Xbox)\n\n"
    "✅ Base\n"
    "• Sens: 6–8\n"
    "• ADS: 0.80–0.95\n"
    "• Deadzone MIN: 0.03–0.07\n"
    "• Aim curve: Dynamic/Standard (что стабильнее)\n"
    "• FOV: 100–115\n\n"
    "🎯 Подсказка:\n"
    "Если много мажешь в ближке — ADS -0.05. Если не доворачиваешь — Sens +1.\n"
)

BO7_MNK = (
    "🖱 BO7 — Mouse & Keyboard (PC)\n\n"
    "✅ Base\n"
    "• DPI 800 | sens 4–7\n"
    "• ADS 0.8–1.0\n"
    "• smoothing OFF\n"
    "• FOV 100–115\n"
)

# ====== BF6 (EN per your request) ======

BF6_PAD_EN = (
    "🎮 BF6 — Controller (EN)\n\n"
    "Core:\n"
    "• Stick Deadzone: as low as possible without drift\n"
    "• Response Curve: Linear / Default (pick what feels consistent)\n"
    "• Sensitivity: medium, ADS slightly lower\n"
    "• Aim Assist: ON (default)\n"
    "• FOV: 90–105 (console comfort) or higher if you track well\n"
    "• Motion Blur: OFF\n\n"
    "Rule:\n"
    "• After first contact: reposition (don’t re-peek the same angle)\n"
)

BF6_MNK_EN = (
    "🖱 BF6 — Mouse & Keyboard (PC) (EN)\n\n"
    "Core:\n"
    "• DPI: 800 or 1600\n"
    "• In-game sens: keep eDPI reasonable (start ~2400–4800)\n"
    "• ADS multiplier: 0.85–1.00\n"
    "• FOV: 100–110 (start)\n"
    "• Raw input: ON (if available)\n"
    "• Mouse accel: OFF\n"
    "• Motion Blur: OFF\n"
)

def get_text(key: str) -> str:
    key = (key or "").strip()
    mapping = {
        "wz:pad": WZ_PAD,
        "wz:mnk": WZ_MNK,
        "bo7:pad": BO7_PAD,
        "bo7:mnk": BO7_MNK,
        "bf6:pad": BF6_PAD_EN,
        "bf6:mnk": BF6_MNK_EN,
    }
    return mapping.get(key, "—")
