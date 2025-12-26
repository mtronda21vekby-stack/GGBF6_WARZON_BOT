# -*- coding: utf-8 -*-
"""
Premium settings library.

✅ Совместимость:
- get_text("wz:pad") / get_text("bo7:mnk") / get_text("bf6:pad")  (старый стиль)
✅ Новый слой (для модулей):
- get_tier_text(game="warzone|bo7|bf6", device="pad|mnk", tier="normal|demon|pro")

Ничего не урезаем — только добавляем.
"""

from typing import Dict


# ============================================================
# BASE (твой исходник — оставляем как есть)
# ============================================================

WZ_PAD_BASE = (
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

WZ_MNK_BASE = (
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

BO7_PAD_BASE = (
    "🎮 BO7 — Controller (PS5/Xbox)\n\n"
    "• Sens: 6–8\n"
    "• ADS: 0.80–0.95\n"
    "• Deadzone MIN: 0.03–0.07\n"
    "• Aim curve: Dynamic/Standard (что стабильнее)\n"
    "• FOV: 100–115\n"
)

BO7_MNK_BASE = (
    "🖱 BO7 — Mouse & Keyboard\n\n"
    "• DPI 800 | sens 4–7\n"
    "• ADS 0.8–1.0\n"
    "• smoothing OFF\n"
    "• FOV 100–115\n"
)

BF6_PAD_BASE_EN = (
    "🎮 BF6 — Controller (EN)\n\n"
    "• Sensitivity: Medium (start ~ 35–55)\n"
    "• ADS Sensitivity: Lower than Hipfire\n"
    "• Deadzone: As low as possible without drift\n"
    "• FOV: High but comfortable\n"
    "• After first contact: reposition (don’t re-peek same angle)\n"
)

BF6_MNK_BASE_EN = (
    "🖱 BF6 — Mouse & Keyboard (EN)\n\n"
    "• DPI: 800\n"
    "• In-game sens: medium (adjust for consistent tracking)\n"
    "• ADS multiplier: 0.8–1.0\n"
    "• Raw input: ON (if available)\n"
    "• Mouse accel: OFF\n"
)


# ============================================================
# DEMON / PRO (расширение, ничего не ломаем)
# ============================================================

WZ_PAD_DEMON = (
    "🎮 Warzone — Controller (PS5/Xbox)\n\n"
    "😈 Demon preset (агро / быстрые дуэли)\n"
    "• Sens: 7–9 (старт 8)\n"
    "• ADS Multiplier: 0.85–0.95 (старт 0.90)\n"
    "• Aim Response Curve: Dynamic\n"
    "• Deadzone MIN: 0.03–0.05 (если дрифт → 0.06–0.10)\n"
    "• FOV: 110–120 | ADS FOV: Affected | Weapon FOV: Wide\n"
    "• Sprint/Tac Sprint Assist: ON (если есть)\n"
    "• Slide: Tap | Dive/Slide: Hybrid\n"
    "• Camera Movement: Least\n\n"
    "🎯 Правило демона:\n"
    "• 1 контакт → 1 репозиция (не стой)\n"
    "• 1 файт → 1 ресет (плейты/перезар)\n"
)

WZ_MNK_DEMON = (
    "🖱 Warzone — Mouse & Keyboard (PC)\n\n"
    "😈 Demon preset (резкий трекинг + флики)\n"
    "• DPI: 800 (или 1600)\n"
    "• Sens: под 180° комфорт (обычно ниже, чем ты хочешь)\n"
    "• ADS multiplier: 0.80–0.95\n"
    "• FOV: 110–120 | ADS: Affected | Weapon: Wide\n"
    "• Raw input ON | smoothing OFF\n\n"
    "🎯 Тест:\n"
    "• 5 мин трекинг (без дерготни)\n"
    "• 5 мин 1-clip контроль отдачи\n"
)

WZ_PAD_PRO = (
    "🎮 Warzone — Controller (PS5/Xbox)\n\n"
    "🎯 Pro preset (стабильность / турниры)\n"
    "• Sens: 6–8 (старт 7)\n"
    "• ADS Multiplier: 0.85–0.92 (старт 0.90)\n"
    "• Aim Response: Dynamic (если нестабильно → Standard)\n"
    "• Deadzone: минимально без дрифта (обычно 0.03–0.06)\n"
    "• FOV: 105–115 (старт 110)\n"
    "• Camera Movement: Least\n\n"
    "🎯 Pro-правило:\n"
    "• Не принимаешь 50/50. Угол/инфо/тиммейт → потом пик.\n"
)

WZ_MNK_PRO = (
    "🖱 Warzone — Mouse & Keyboard (PC)\n\n"
    "🎯 Pro preset (консистентность)\n"
    "• DPI: 800 (или 1600) + sens ниже\n"
    "• ADS multiplier: 0.85–1.00\n"
    "• FOV: 105–115 (старт 110)\n"
    "• Raw input ON | accel OFF | smoothing OFF\n\n"
    "🎯 Pro-правило:\n"
    "• Одинаковая сенса во всех играх → мышечная память = аим.\n"
)

BO7_PAD_DEMON = (
    "🎮 BO7 — Controller (PS5/Xbox)\n\n"
    "😈 Demon preset (агро)\n"
    "• Sens: 7–9\n"
    "• ADS: 0.80–0.92\n"
    "• Deadzone MIN: 0.03–0.06\n"
    "• Aim curve: Dynamic/Standard (что быстрее, но стабильно)\n"
    "• FOV: 105–120\n"
)

BO7_MNK_DEMON = (
    "🖱 BO7 — Mouse & Keyboard\n\n"
    "😈 Demon preset\n"
    "• DPI: 800\n"
    "• Sens: ниже среднего, чтобы не срывать трекинг\n"
    "• ADS: 0.80–0.95\n"
    "• smoothing OFF\n"
    "• FOV: 105–120\n"
)

BO7_PAD_PRO = (
    "🎮 BO7 — Controller (PS5/Xbox)\n\n"
    "🎯 Pro preset (стабильность)\n"
    "• Sens: 6–8\n"
    "• ADS: 0.85–0.95\n"
    "• Deadzone MIN: 0.03–0.07\n"
    "• Aim curve: то, что дает меньше ошибок\n"
    "• FOV: 100–115\n"
)

BO7_MNK_PRO = (
    "🖱 BO7 — Mouse & Keyboard\n\n"
    "🎯 Pro preset\n"
    "• DPI: 800\n"
    "• Sens: стабильная (без дёрганий)\n"
    "• ADS: 0.85–1.00\n"
    "• smoothing OFF\n"
    "• FOV: 100–115\n"
)

BF6_PAD_DEMON_EN = (
    "🎮 BF6 — Controller (EN)\n\n"
    "😈 Demon preset (aggressive)\n"
    "• Deadzone: as low as possible without drift\n"
    "• Sensitivity: medium-high (track first, speed second)\n"
    "• ADS Sens: slightly lower than hipfire\n"
    "• FOV: 95–110\n"
    "• Motion Blur: OFF\n\n"
    "Rule:\n"
    "• Win the angle first, then fight.\n"
)

BF6_MNK_DEMON_EN = (
    "🖱 BF6 — Mouse & Keyboard (EN)\n\n"
    "😈 Demon preset\n"
    "• DPI: 800\n"
    "• Sens: tuned for fast tracking, not flick spam\n"
    "• ADS: 0.80–0.95\n"
    "• Raw input: ON | accel: OFF\n"
    "• FOV: 100–110\n"
)

BF6_PAD_PRO_EN = (
    "🎮 BF6 — Controller (EN)\n\n"
    "🎯 Pro preset (consistent)\n"
    "• Deadzone: minimal without drift\n"
    "• Sensitivity: medium (clean micro-corrections)\n"
    "• ADS: slightly lower than hipfire\n"
    "• FOV: 90–105\n"
    "• Motion Blur: OFF\n\n"
    "Rule:\n"
    "• 1 contact → 1 reposition.\n"
)

BF6_MNK_PRO_EN = (
    "🖱 BF6 — Mouse & Keyboard (EN)\n\n"
    "🎯 Pro preset\n"
    "• DPI: 800 (or 1600)\n"
    "• Sens: consistent tracking baseline\n"
    "• ADS: 0.85–1.00\n"
    "• Raw input: ON | accel: OFF | smoothing: OFF\n"
    "• FOV: 100–110\n"
)


# ============================================================
# INTERNAL MAPPINGS
# ============================================================

# Старый mapping: ключи вида wz:pad / bo7:mnk / bf6:pad
_OLD_MAP: Dict[str, str] = {
    "wz:pad": WZ_PAD_BASE,
    "wz:mnk": WZ_MNK_BASE,
    "bo7:pad": BO7_PAD_BASE,
    "bo7:mnk": BO7_MNK_BASE,
    "bf6:pad": BF6_PAD_BASE_EN,
    "bf6:mnk": BF6_MNK_BASE_EN,
}

# Новый mapping: game -> device -> tier
_TIER_MAP: Dict[str, Dict[str, Dict[str, str]]] = {
    "warzone": {
        "pad": {
            "normal": WZ_PAD_BASE,
            "demon": WZ_PAD_DEMON,
            "pro": WZ_PAD_PRO,
        },
        "mnk": {
            "normal": WZ_MNK_BASE,
            "demon": WZ_MNK_DEMON,
            "pro": WZ_MNK_PRO,
        }
    },
    "bo7": {
        "pad": {
            "normal": BO7_PAD_BASE,
            "demon": BO7_PAD_DEMON,
            "pro": BO7_PAD_PRO,
        },
        "mnk": {
            "normal": BO7_MNK_BASE,
            "demon": BO7_MNK_DEMON,
            "pro": BO7_MNK_PRO,
        }
    },
    "bf6": {
        "pad": {
            "normal": BF6_PAD_BASE_EN,
            "demon": BF6_PAD_DEMON_EN,
            "pro": BF6_PAD_PRO_EN,
        },
        "mnk": {
            "normal": BF6_MNK_BASE_EN,
            "demon": BF6_MNK_DEMON_EN,
            "pro": BF6_MNK_PRO_EN,
        }
    }
}


# ============================================================
# PUBLIC API
# ============================================================

def get_text(key: str) -> str:
    """
    Старый API (оставляем): key = "wz:pad" | "wz:mnk" | "bo7:pad" ...
    """
    key = (key or "").strip().lower()
    return _OLD_MAP.get(key, "—")


def get_tier_text(game: str, device: str, tier: str) -> str:
    """
    Новый API (для модулей):
    game: warzone | bo7 | bf6
    device: pad | mnk
    tier: normal | demon | pro
    """
    g = (game or "").strip().lower()
    d = (device or "").strip().lower()
    t = (tier or "").strip().lower()

    if g == "wz":
        g = "warzone"
    if g not in _TIER_MAP:
        return "—"

    dev_map = _TIER_MAP[g]
    if d not in dev_map:
        d = "pad"
    tier_map = dev_map[d]
    if t not in tier_map:
        t = "normal"
    return tier_map[t]
