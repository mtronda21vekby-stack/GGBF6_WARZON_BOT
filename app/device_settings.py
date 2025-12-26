# -*- coding: utf-8 -*-
from typing import Dict

# Платформы
PLAT_XBOX = "xbox"
PLAT_PS5 = "ps5"
PLAT_PC = "pc"

# Подразделы
SEC_FULL = "full"
SEC_AIM = "aim"
SEC_MOVE = "move"
SEC_VIDEO = "video"
SEC_AUDIO = "audio"

PLAT_NAME = {
    PLAT_XBOX: "Xbox",
    PLAT_PS5: "PS5",
    PLAT_PC: "PC",
}

SEC_NAME = {
    SEC_FULL: "📦 Полный сетап",
    SEC_AIM: "🎯 Aim",
    SEC_MOVE: "🕹 Movement",
    SEC_VIDEO: "🎛 Видео/графика",
    SEC_AUDIO: "🔊 Звук",
}

def _title(game: str, plat: str, section: str) -> str:
    g = (game or "warzone").upper()
    return f"⚙️ Настройки • {g} • {PLAT_NAME.get(plat, plat)} • {SEC_NAME.get(section, section)}"

def get_text(game: str, platform: str, section: str) -> str:
    """
    Вернёт текст настроек под:
    game: warzone|bo7|bf6
    platform: xbox|ps5|pc
    section: full|aim|move|video|audio
    """
    game = (game or "warzone").lower()
    platform = (platform or PLAT_PC).lower()
    section = (section or SEC_FULL).lower()

    # ---- WARZONE ----
    if game == "warzone":
        if platform in (PLAT_XBOX, PLAT_PS5):
            if section == SEC_FULL:
                return (
                    f"{_title(game, platform, section)}\n\n"
                    "🎮 Controller (PS5/Xbox) — база под Competitive:\n"
                    "• Sens: 6–8 (старт 7/7)\n"
                    "• ADS Mult: 0.85–0.95 (старт 0.90/0.85)\n"
                    "• Response Curve: Dynamic (если дергает → Standard)\n"
                    "• Aim Assist: Default\n"
                    "• Deadzone (min): 0.03–0.06 (если дрифт → 0.07–0.10)\n"
                    "• FOV: 105–110 | ADS FOV: Affected | Weapon FOV: Wide\n"
                    "• Sprint/Tac Sprint behavior: Auto Tac Sprint (если теряешь контроль → Auto Sprint)\n\n"
                    "🧠 Мышление на контроллере:\n"
                    "1) Центрирование (прицел там, где будет враг)\n"
                    "2) Стрейф в момент стрельбы (включает AA лучше)\n"
                    "3) Не репикай один угол 2 раза подряд\n"
                )
            if section == SEC_AIM:
                return (
                    f"{_title(game, platform, section)}\n\n"
                    "🎯 Aim под контроллер:\n"
                    "• Двигайся (левый стик) во время стрельбы — AA работает сильнее\n"
                    "• Микро-подводка правым стиком — минимальная\n"
                    "• Дистанция 15–30м: короткие очереди 6–10 пуль\n\n"
                    "🧪 Дрилл (7 минут):\n"
                    "• 2м — трекинг со стрейфом\n"
                    "• 3м — флик 2 цели + контроль\n"
                    "• 2м — first shot дисциплина\n"
                )
            if section == SEC_MOVE:
                return (
                    f"{_title(game, platform, section)}\n\n"
                    "🕹 Movement под контроллер:\n"
                    "• После первого хита — смена угла (не стой на линии прострела)\n"
                    "• Слайд/джамп-пик только под инфо, не наугад\n"
                    "• Если 1v2 — ресет: плейты/перезар, потом пик\n"
                )
            if section == SEC_VIDEO:
                return (
                    f"{_title(game, platform, section)}\n\n"
                    "🎛 Видео (консоль):\n"
                    "• FOV 105–110\n"
                    "• Motion Blur: Off (если есть)\n"
                    "• Film Grain: 0\n"
                    "• World/Weapon Motion Blur: Off\n"
                    "• Цвет/яркость: чтобы тени читались (не ‘кислота’)\n"
                )
            if section == SEC_AUDIO:
                return (
                    f"{_title(game, platform, section)}\n\n"
                    "🔊 Звук (консоль):\n"
                    "• Headphones preset (если есть)\n"
                    "• Music: 0–10\n"
                    "• Dialogue: ниже, чтобы шаги не терялись\n"
                    "• Важнее всего: тишина в комнате + норм уши\n"
                )

        # PC (мышка/клава)
        if platform == PLAT_PC:
            if section == SEC_FULL:
                return (
                    f"{_title(game, platform, section)}\n\n"
                    "🖱️ Keyboard & Mouse — база:\n"
                    "• DPI: 800 (или 1600) + низкая sens\n"
                    "• In-game sens: 3–7 (под DPI) — цель: eDPI ~ 2400–5600\n"
                    "• ADS sens multiplier: 0.80–1.00\n"
                    "• Raw Input: ON\n"
                    "• Mouse accel: OFF (в Windows)\n"
                    "• Polling rate: 1000 Hz (если стабильно)\n"
                    "• FOV: 105–120 (под комфорт)\n\n"
                    "🧠 Мышление на мышке:\n"
                    "1) Кроссхейр-плейсмент важнее фликов\n"
                    "2) Держи дистанцию под твой сенс\n"
                    "3) Первые 5 пуль — контроль, потом добив\n"
                )
            if section == SEC_AIM:
                return (
                    f"{_title(game, platform, section)}\n\n"
                    "🎯 Aim под мышку:\n"
                    "• Трекинг > флики (в WZ чаще)\n"
                    "• Не перетягивай мышь — микрокоррекция кистью\n"
                    "• Отдача: короткие очереди, especially 20–40м\n\n"
                    "🧪 Дрилл (7 минут):\n"
                    "• 3м — трекинг (средняя дистанция)\n"
                    "• 2м — микро-флики по 2 мишеням\n"
                    "• 2м — контроль отдачи (стоп-стрельба)\n"
                )
            if section == SEC_MOVE:
                return (
                    f"{_title(game, platform, section)}\n\n"
                    "🕹 Movement под мышку:\n"
                    "• Пики: коротко ‘инфо → урон → откат’\n"
                    "• Не стой в проходе: угол + cover + план отхода\n"
                    "• В ближке: прыгать меньше, стрейфить больше\n"
                )
            if section == SEC_VIDEO:
                return (
                    f"{_title(game, platform, section)}\n\n"
                    "🎛 Видео (PC):\n"
                    "• Цель: стабильные FPS и читаемость\n"
                    "• Upscaling: DLSS/FSR Balanced/Performance (если надо)\n"
                    "• Motion blur / film grain: OFF\n"
                    "• Низкие тени/эффекты, выше текстуры (если VRAM позволяет)\n"
                )
            if section == SEC_AUDIO:
                return (
                    f"{_title(game, platform, section)}\n\n"
                    "🔊 Звук (PC):\n"
                    "• Loudness equalization — аккуратно (если используешь)\n"
                    "• Музыка 0\n"
                    "• Важнее: баланс ‘шаги vs выстрелы’\n"
                )

    # ---- BO7 (общие, можно расширять) ----
    if game == "bo7":
        return (
            f"{_title(game, platform, section)}\n\n"
            "BO7: базовые принципы те же.\n"
            "• Controller: 6–8 sens, Dynamic, deadzone 0.03–0.07\n"
            "• PC: низкий сенс, raw input, accel off\n\n"
            "Если хочешь — сделаю BO7 отдельными точными пресетами под твой стиль (агро/позиционка)."
        )

    # ---- BF6 (EN желательно) ----
    if game == "bf6":
        return (
            f"{_title(game, platform, section)}\n\n"
            "BF6 (EN quick setup):\n"
            "• Controller: Medium sens, lower ADS, minimal deadzone without drift\n"
            "• PC: 800 DPI + low sens, Raw Input ON, mouse accel OFF\n"
            "• Playstyle: shoot → reposition, avoid re-peeking same angle\n\n"
            "Tell me your platform + role (AR/SMG/DMR) and I’ll tailor it."
        )

    return (
        f"{_title(game, platform, section)}\n\n"
        "Пока нет профиля под эту игру. Скажи игру: warzone / bo7 / bf6."
    )
