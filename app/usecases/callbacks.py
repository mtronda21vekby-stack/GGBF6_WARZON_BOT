from __future__ import annotations

from app.core.outgoing import Outgoing
from app.ui.keyboards import KB


async def handle_callback(brain, profiles, user_id: int, data: str) -> Outgoing:
    p = profiles.get(user_id)
    data = (data or "").strip()

    # MAIN
    if data in ("back:main", "menu:main"):
        return Outgoing(
            text="Готов. Пиши ситуацию/смерть — разберём.",
            inline_keyboard=KB.main_inline(),
            ensure_quickbar=True,
        )

    # SETTINGS
    if data == "settings:menu":
        return Outgoing(
            text="⚙️ Warzone — выбери устройство:",
            inline_keyboard=KB.settings_device_wz(),
            ensure_quickbar=True,
        )

    if data.startswith("wz_device:"):
        dev = data.split(":", 1)[1]
        return Outgoing(
            text=f"✅ Устройство для Warzone: {dev}\nДальше добавим тумблеры (KBM/PS/Xbox + normal/pro/demon) как ты требуешь.",
            inline_keyboard=KB.main_inline(),
            ensure_quickbar=True,
        )

    # ZOMBIES
    if data == "zombies:menu":
        return Outgoing("🧟 Zombies меню:", KB.zombies_menu(), ensure_quickbar=True)

    if data == "zombies:bo7":
        return Outgoing(
            "🧟 BO7 Zombies включен.\nНапиши: карта/волна/оружие/умер где — и я дам план.",
            KB.main_inline(),
            ensure_quickbar=True,
        )

    if data == "zombies:expanded":
        return Outgoing(
            "🧟‍♂️ Zombie (расширенный) включен.\nСейчас добавим: билды / задачи / приоритеты / ошибки по волнам.",
            KB.main_inline(),
            ensure_quickbar=True,
        )

    # MORE
    if data == "more:menu":
        return Outgoing("📦 Ещё:", KB.more_menu(), ensure_quickbar=True)

    if data == "daily:task":
        return Outgoing(
            "🎯 Задание дня:\n1) 10 мин tracking\n2) 10 мин recoil control\n3) 1 матч: играть от укрытий\n\n(Дальше сделаем авто под игру/стиль/уровень)",
            KB.main_inline(),
            ensure_quickbar=True,
        )

    if data == "vod:menu":
        return Outgoing(
            "🎬 VOD: пришли ссылку/описание момента (или таймкод) — сделаю разбор по ошибкам/решениям.",
            KB.main_inline(),
            ensure_quickbar=True,
        )

    # TOGGLES
    if data == "ai:toggle":
        p.ai_enabled = not p.ai_enabled
        return Outgoing(f"🤖 ИИ: {'ON' if p.ai_enabled else 'OFF'}", KB.main_inline(), ensure_quickbar=True)

    if data == "mem:toggle":
        p.mem_enabled = not p.mem_enabled
        # если у тебя в brain есть память — можно ещё brain.enable/disable
        return Outgoing(f"🧠 Память: {'✅' if p.mem_enabled else '❌'}", KB.main_inline(), ensure_quickbar=True)

    # “статусы” (заглушки пока, но без «скоро подключим мозг»)
    if data.startswith("game:"):
        p.game = data.split(":", 1)[1]
        return Outgoing(f"🎮 Игра: {p.game}", KB.main_inline(), ensure_quickbar=True)

    if data.startswith("style:"):
        p.style = data.split(":", 1)[1]
        return Outgoing(f"🎭 Стиль: {p.style}", KB.main_inline(), ensure_quickbar=True)

    if data.startswith("answer:"):
        p.answer = data.split(":", 1)[1]
        return Outgoing(f"💬 Ответ: {p.answer}", KB.main_inline(), ensure_quickbar=True)

    if data.startswith("mode:"):
        p.mode = data.split(":", 1)[1]
        return Outgoing(f"🔁 Режим: {p.mode}", KB.main_inline(), ensure_quickbar=True)

    # default
    return Outgoing(f"⚙️ {data}", KB.main_inline(), ensure_quickbar=True)
