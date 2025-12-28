from app.ui.quickbar import (
    kb_main, kb_games, kb_platform, kb_input,
    kb_difficulty, kb_settings
)
from app.ui.world_settings import (
    kb_world_settings, kb_sens, kb_fov, kb_aim,
    presets, render_settings
)
from app.ui import texts


def _get_world_settings(profile) -> dict:
    s = getattr(profile, "world_settings", None)
    if not isinstance(s, dict):
        s = {}
        setattr(profile, "world_settings", s)
    return s


def _set_world_setting(profile, key: str, value):
    s = _get_world_settings(profile)
    s[key] = value


class Router:
    def __init__(self, tg, brain, profiles, settings):
        self.tg = tg
        self.brain = brain
        self.profiles = profiles
        self.settings = settings

    async def handle_update(self, upd):
        if not upd.message or not upd.message.text:
            return

        chat_id = upd.message.chat.id
        user_id = upd.message.from_user.id
        text = upd.message.text.strip()

        profile = self.profiles.get(user_id)

        # -------- START --------
        if text in ("/start", "Меню"):
            await self.tg.send_message(chat_id, texts.WELCOME, reply_markup=kb_main())
            return

        # -------- SETTINGS ROOT --------
        if text == "⚙️ Настройки":
            await self.tg.send_message(
                chat_id,
                "⚙️ Настройки профиля\n\nИди сверху вниз — так логичнее.",
                reply_markup=kb_settings(),
            )
            return

        # -------- GAME SELECT --------
        if text == "🎮 Выбрать игру":
            await self.tg.send_message(chat_id, "🎮 Выбери игру:", reply_markup=kb_games())
            return

        if text == "🔥 Warzone":
            profile.game = "warzone"
            await self.tg.send_message(chat_id, "✅ Игра: WARZONE", reply_markup=kb_settings())
            return

        if text == "💣 BO7":
            profile.game = "bo7"
            await self.tg.send_message(chat_id, "✅ Игра: BO7", reply_markup=kb_settings())
            return

        if text == "🪖 BF6":
            profile.game = "bf6"
            await self.tg.send_message(chat_id, "✅ Game: BF6", reply_markup=kb_settings())
            return

        # -------- PLATFORM --------
        if text == "🖥 Платформа":
            await self.tg.send_message(chat_id, "🖥 Выбери платформу:", reply_markup=kb_platform())
            return

        if text in ("🖥 PC", "🎮 PlayStation", "🎮 Xbox"):
            profile.platform = text.replace("🖥 ", "").replace("🎮 ", "").lower()
            await self.tg.send_message(chat_id, f"✅ Платформа: {profile.platform.upper()}", reply_markup=kb_settings())
            return

        # -------- INPUT --------
        if text == "⌨️ Input":
            await self.tg.send_message(chat_id, "⌨️ Выбери input:", reply_markup=kb_input())
            return

        if text in ("⌨️ KBM", "🎮 Controller"):
            profile.input = "kbm" if "KBM" in text else "controller"
            await self.tg.send_message(chat_id, f"✅ Input: {profile.input.upper()}", reply_markup=kb_settings())
            return

        # -------- DIFFICULTY --------
        if text == "😈 Режим мышления":
            await self.tg.send_message(chat_id, "😈 Выбери режим:", reply_markup=kb_difficulty())
            return

        if text in ("🧠 Normal", "🔥 Pro", "😈 Demon"):
            profile.mode = text.split()[-1].lower()
            await self.tg.send_message(chat_id, f"✅ Режим: {profile.mode.upper()}", reply_markup=kb_settings())
            return

        # ======================================================================
        # ✅ ШАГ 2: НАСТРОЙКИ ВНУТРИ МИРА (Warzone/BO7 RU, BF6 EN)
        # ======================================================================

        if text == "🧩 Настройки игры":
            g = (getattr(profile, "game", None) or "warzone").lower()
            await self.tg.send_message(
                chat_id,
                "🧩 Настройки выбранной игры:",
                reply_markup=kb_world_settings(g),
            )
            return

        g = (getattr(profile, "game", None) or "warzone").lower()
        s = _get_world_settings(profile)

        # --- Presets ---
        if text in ("⚡ Пресет: PC", "⚡ Пресет: PS", "⚡ Пресет: Xbox", "⚡ Preset: PC", "⚡ Preset: PS", "⚡ Preset: Xbox"):
            if "PC" in text:
                p = presets(g)["pc"]
            elif "PS" in text:
                p = presets(g)["ps"]
            else:
                p = presets(g)["xbox"]

            for k, v in p.items():
                s[k] = v

            # аккуратно подхватываем в профиль (не ломая остальное)
            profile.platform = s.get("platform", getattr(profile, "platform", None))
            if getattr(profile, "input", None) is None:
                profile.input = s.get("input_hint", None)

            msg = "✅ Preset applied." if g == "bf6" else "✅ Пресет применён."
            await self.tg.send_message(chat_id, msg, reply_markup=kb_world_settings(g))
            return

        # --- Submenus ---
        if text in ("🎯 Чувствительность", "🎯 Sensitivity"):
            await self.tg.send_message(chat_id, "Выбери вариант:" if g != "bf6" else "Choose:", reply_markup=kb_sens(g))
            return

        if text == "🖼 FOV":
            await self.tg.send_message(chat_id, "Выбери FOV:" if g != "bf6" else "Choose FOV:", reply_markup=kb_fov(g))
            return

        if text in ("🎮 Аим/Стик", "🎮 Aim/Stick"):
            await self.tg.send_message(chat_id, "Выбери вариант:" if g != "bf6" else "Choose:", reply_markup=kb_aim(g))
            return

        # --- Sens pick ---
        if text in ("SENS: Low", "SENS: Mid", "SENS: High"):
            _set_world_setting(profile, "sens", text.split(":")[1].strip().lower())
            await self.tg.send_message(chat_id, "✅ Готово." if g != "bf6" else "✅ Done.", reply_markup=kb_world_settings(g))
            return

        # --- FOV pick ---
        if text.startswith("FOV: "):
            try:
                _set_world_setting(profile, "fov", int(text.split(":")[1].strip()))
            except Exception:
                _set_world_setting(profile, "fov", text.split(":")[1].strip())
            await self.tg.send_message(chat_id, "✅ Готово." if g != "bf6" else "✅ Done.", reply_markup=kb_world_settings(g))
            return

        # --- Aim pick ---
        if text in ("AIM: Default", "AIM: Strong", "AIM: Demon"):
            _set_world_setting(profile, "aim", text.split(":")[1].strip().lower())
            await self.tg.send_message(chat_id, "✅ Готово." if g != "bf6" else "✅ Done.", reply_markup=kb_world_settings(g))
            return

        # --- Placeholder sections (we keep, not cut) ---
        if text in ("🔊 Аудио", "🔊 Audio"):
            _set_world_setting(profile, "audio", "high")
            await self.tg.send_message(chat_id, "✅ Аудио: high" if g != "bf6" else "✅ Audio: high", reply_markup=kb_world_settings(g))
            return

        if text in ("🎥 Графика", "🎥 Graphics"):
            _set_world_setting(profile, "graphics", "competitive")
            await self.tg.send_message(chat_id, "✅ Графика: competitive" if g != "bf6" else "✅ Graphics: competitive", reply_markup=kb_world_settings(g))
            return

        if text in ("🧠 Геймплей", "🧠 Gameplay"):
            _set_world_setting(profile, "gameplay", "stable")
            await self.tg.send_message(chat_id, "✅ Геймплей: stable" if g != "bf6" else "✅ Gameplay: stable", reply_markup=kb_world_settings(g))
            return

        # --- Show settings ---
        if text in ("📄 Показать мои настройки", "📄 Show my settings"):
            await self.tg.send_message(chat_id, render_settings(g, s), reply_markup=kb_world_settings(g))
            return

        # -------- BACK --------
        if text in ("⬅️ Назад", "⬅️ Back"):
            await self.tg.send_message(chat_id, "Главное меню", reply_markup=kb_main())
            return

        # -------- DEFAULT --------
        reply = await self.brain.handle_text(user_id, text)
        await self.tg.send_message(chat_id, reply.text, reply_markup=kb_main())
