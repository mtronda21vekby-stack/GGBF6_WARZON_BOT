def kb_main() -> dict:
    return {
        "keyboard": [
            [{"text": "🎮 Игра"}, {"text": "⚙️ Настройки"}, {"text": "📌 Профиль"}],
            [{"text": "🎯 Тренировка"}, {"text": "🧠 ИИ"}, {"text": "🧟 Zombies"}],
            [{"text": "🎬 VOD"}, {"text": "📡 Статус"}],
            [{"text": "🧹 Очистить память"}, {"text": "🧨 Сброс"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def kb_games() -> dict:
    return {
        "keyboard": [
            [{"text": "🔥 Warzone"}, {"text": "🪖 BF6"}, {"text": "💣 BO7"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
    }


def kb_roles(game: str) -> dict:
    if game == "warzone":
        rows = [
            [{"text": "🎯 AR"}, {"text": "💥 SMG"}],
            [{"text": "🔭 Sniper"}, {"text": "🛡 Support"}],
        ]
    elif game == "bf6":
        rows = [
            [{"text": "ASSAULT"}, {"text": "ENGINEER"}],
            [{"text": "SUPPORT"}, {"text": "RECON"}],
        ]
    else:  # bo7
        rows = [
            [{"text": "⚔️ Slayer"}, {"text": "🧠 Tactical"}],
            [{"text": "🛡 Anchor"}, {"text": "💣 Objective"}],
        ]

    rows.append([{"text": "⬅️ Назад"}])

    return {
        "keyboard": rows,
        "resize_keyboard": True,
    }
