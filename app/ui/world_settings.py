# -*- coding: utf-8 -*-
from __future__ import annotations


def kb_world_settings(game: str, platform: str | None = None, input_: str | None = None, role: str | None = None) -> dict:
    """
    game: warzone/bo7 -> RU
    game: bf6 -> EN (labels)
    platform: pc/playstation/xbox
    input_: kbm/controller
    role: entry/anchor/sniper/assault/...
    """
    g = (game or "warzone").lower()
    plat = (platform or "").lower()
    inp = (input_ or "").lower()
    r = (role or "").lower()

    ru = g in ("warzone", "bo7")

    # Заголовок-подсказка (на самой клавиатуре не показывается, но логика ниже использует)
    # Секции: пресет -> сенса -> fov -> aim -> audio/graphics/gameplay -> show

    # Warzone/BO7 RU
    if ru:
        # динамические подсказки кнопок по input/role (не урезаем, улучшаем UX)
        aim_label = "🎮 Аим/Стик" if inp == "controller" else "🎮 Аим/Стик"
        sens_label = "🎯 Чувствительность" if inp == "controller" else "🎯 Сенса (KBM)"
        fov_label = "🖼 FOV"
        role_hint = "🎭 Роль: " + (r.upper() if r else "—")
        plat_hint = "🖥 Платформа: " + (plat.upper() if plat else "—")
        inp_hint = "⌨️ Input: " + (inp.upper() if inp else "—")

        return {
            "keyboard": [
                [{"text": "⚡ Пресет: PC"}, {"text": "⚡ Пресет: PS"}, {"text": "⚡ Пресет: Xbox"}],
                [{"text": sens_label}, {"text": fov_label}, {"text": aim_label}],
                [{"text": "🔊 Аудио"}, {"text": "🎥 Графика"}, {"text": "🧠 Геймплей"}],
                [{"text": "📄 Показать мои настройки"}],
                [{"text": f"ℹ️ {plat_hint}"}, {"text": f"ℹ️ {inp_hint}"}],
                [{"text": f"ℹ️ {role_hint}"}],
                [{"text": "⬅️ Назад"}],
            ],
            "resize_keyboard": True,
            "is_persistent": True,
        }

    # BF6 EN labels
    aim_label = "🎮 Aim/Stick" if inp == "controller" else "🎮 Aim/Stick"
    sens_label = "🎯 Sensitivity" if inp == "controller" else "🎯 Sens (KBM)"
    fov_label = "🖼 FOV"
    role_hint = "🎭 Role: " + (r.upper() if r else "—")
    plat_hint = "🖥 Platform: " + (plat.upper() if plat else "—")
    inp_hint = "⌨️ Input: " + (inp.upper() if inp else "—")

    return {
        "keyboard": [
            [{"text": "⚡ Preset: PC"}, {"text": "⚡ Preset: PS"}, {"text": "⚡ Preset: Xbox"}],
            [{"text": sens_label}, {"text": fov_label}, {"text": aim_label}],
            [{"text": "🔊 Audio"}, {"text": "🎥 Graphics"}, {"text": "🧠 Gameplay"}],
            [{"text": "📄 Show my settings"}],
            [{"text": f"ℹ️ {plat_hint}"}, {"text": f"ℹ️ {inp_hint}"}],
            [{"text": f"ℹ️ {role_hint}"}],
            [{"text": "⬅️ Back"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_sens(game: str, input_: str | None = None) -> dict:
    g = (game or "warzone").lower()
    ru = g in ("warzone", "bo7")
    inp = (input_ or "").lower()

    # под разные input
    if inp == "kbm":
        rows = [
            [{"text": "SENS: Low"}, {"text": "SENS: Mid"}, {"text": "SENS: High"}],
            [{"text": "DPI: 400"}, {"text": "DPI: 800"}, {"text": "DPI: 1600"}],
        ]
    else:
        rows = [
            [{"text": "SENS: Low"}, {"text": "SENS: Mid"}, {"text": "SENS: High"}],
            [{"text": "ADS: Low"}, {"text": "ADS: Mid"}, {"text": "ADS: High"}],
        ]

    rows.append([{"text": "⬅️ Назад" if ru else "⬅️ Back"}])

    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


def kb_fov(game: str, platform: str | None = None) -> dict:
    g = (game or "warzone").lower()
    ru = g in ("warzone", "bo7")
    plat = (platform or "").lower()

    # Консоли обычно комфортнее 100-110, PC 110-120
    if plat == "pc":
        rows = [[{"text": "FOV: 110"}, {"text": "FOV: 115"}, {"text": "FOV: 120"}]]
    else:
        rows = [[{"text": "FOV: 95"}, {"text": "FOV: 100"}, {"text": "FOV: 105"}, {"text": "FOV: 110"}]]

    rows.append([{"text": "⬅️ Назад" if ru else "⬅️ Back"}])

    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


def kb_aim(game: str, input_: str | None = None) -> dict:
    g = (game or "warzone").lower()
    ru = g in ("warzone", "bo7")
    inp = (input_ or "").lower()

    if inp == "kbm":
        rows = [
            [{"text": "AIM: Tracking"}, {"text": "AIM: Flick"}, {"text": "AIM: Hybrid"}],
        ]
    else:
        rows = [
            [{"text": "AIM: Default"}, {"text": "AIM: Strong"}, {"text": "AIM: Demon"}],
            [{"text": "Response: Standard"}, {"text": "Response: Dynamic"}],
        ]

    rows.append([{"text": "⬅️ Назад" if ru else "⬅️ Back"}])

    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


def presets(game: str, platform: str | None = None, input_: str | None = None, role: str | None = None) -> dict:
    """
    Пресеты учитывают:
    - platform
    - input
    - role
    Это стартовые “умные” значения. Дальше ты расширишь под патчи/мету.
    """
    g = (game or "warzone").lower()
    plat = (platform or "").lower()
    inp = (input_ or "").lower()
    r = (role or "").lower()

    # базовый
    base = {
        "platform": plat or "pc",
        "input_hint": inp or ("controller" if plat in ("playstation", "xbox") else "kbm"),
        "fov": 110 if plat in ("playstation", "xbox") else 120,
        "sens": "mid",
        "ads": "mid",
        "dpi": 800,
        "aim": "strong" if inp == "controller" else "hybrid",
        "audio": "high",
        "graphics": "competitive",
        "gameplay": "stable",
    }

    # роль влияет на стиль
    if g == "warzone":
        if r == "entry":
            base.update({"gameplay": "fast", "sens": "high"})
        elif r == "anchor":
            base.update({"gameplay": "stable", "sens": "mid"})
        elif r == "sniper":
            base.update({"gameplay": "slow", "sens": "low", "aim": "flick" if inp == "kbm" else "default"})

    if g == "bo7":
        if r == "slayer":
            base.update({"gameplay": "fast", "sens": "high"})
        elif r == "anchor":
            base.update({"gameplay": "stable"})
        elif r == "objective":
            base.update({"gameplay": "stable", "sens": "mid"})

    if g == "bf6":
        # BF6 labels EN, but logic same
        if r in ("assault", "engineer"):
            base.update({"gameplay": "fast"})
        elif r in ("support", "recon"):
            base.update({"gameplay": "stable"})

    return base


def render_settings(game: str, s: dict) -> str:
    g = (game or "warzone").lower()
    ru = g in ("warzone", "bo7")

    if not ru:
        return (
            "📄 BF6 SETTINGS\n\n"
            f"Platform: {s.get('platform','—')}\n"
            f"Input hint: {s.get('input_hint','—')}\n"
            f"FOV: {s.get('fov','—')}\n"
            f"Sensitivity: {s.get('sens','—')}\n"
            f"ADS: {s.get('ads','—')}\n"
            f"DPI: {s.get('dpi','—')}\n"
            f"Aim/Stick: {s.get('aim','—')}\n"
            f"Audio: {s.get('audio','—')}\n"
            f"Graphics: {s.get('graphics','—')}\n"
            f"Gameplay: {s.get('gameplay','—')}\n"
        )

    return (
        "📄 НАСТРОЙКИ ИГРЫ\n\n"
        f"Платформа: {s.get('platform','—')}\n"
        f"Input подсказка: {s.get('input_hint','—')}\n"
        f"FOV: {s.get('fov','—')}\n"
        f"Чувствительность: {s.get('sens','—')}\n"
        f"ADS: {s.get('ads','—')}\n"
        f"DPI: {s.get('dpi','—')}\n"
        f"Аим/Стик: {s.get('aim','—')}\n"
        f"Аудио: {s.get('audio','—')}\n"
        f"Графика: {s.get('graphics','—')}\n"
        f"Геймплей: {s.get('gameplay','—')}\n"
    )
