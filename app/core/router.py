from __future__ import annotations

from app.ui.quickbar import kb_main, kb_settings, kb_ai, kb_train, kb_more


class Router:
    def __init__(self, tg, brain, settings, profiles=None):
        self.tg = tg
        self.brain = brain
        self.settings = settings
        self.profiles = profiles  # может быть None в старых версиях

    # -------- helpers --------
    async def _send(self, chat_id: int, text: str, reply_kb: dict | None = None):
        await self.tg.send_message(chat_id=chat_id, text=text, reply_markup=reply_kb or kb_main())

    def _get_profile(self, user_id: int):
        if self.profiles:
            return self.profiles.get(user_id)
        return None

    # -------- routing --------
    async def handle_update(self, upd):
        if not upd.message or not upd.message.text:
            return

        chat_id = upd.message.chat.id
        user_id = upd.message.from_user.id
        text = (upd.message.text or "").strip()

        p = self._get_profile(user_id)

        # /start
        if text == "/start":
            await self._send(
                chat_id,
                "✅ Бот жив.\n\nНапиши ситуацию/смерть — я разберу и дам план.\nИли жми кнопки снизу ⬇️",
                kb_main(),
            )
            return

        # ===== NAV PAGES (нижняя панель) =====
        if text in ("⬅️ Назад", "📋 Меню"):
            await self._send(chat_id, "📋 Меню.", kb_main())
            return

        if text == "⚙️ Настройки":
            await self._send(chat_id, "⚙️ Настройки профиля:", kb_settings())
            return

        if text == "🧠 ИИ":
            await self._send(chat_id, "🧠 ИИ-панель:", kb_ai())
            return

        if text == "🎯 Тренировка":
            await self._send(chat_id, "🎯 Тренировки:", kb_train())
            return

        if text in ("🎬 VOD", "📦 Ещё"):
            await self._send(chat_id, "🎬 VOD / Дополнительно:", kb_more())
            return

        if text == "🆘 Помощь":
            await self._send(
                chat_id,
                "🆘 Как пользоваться:\n"
                "1) Нажми ⚙️ Настройки и выбери игру / input / сложность\n"
                "2) Напиши ситуацию: где умер, чем убили, что сделал\n"
                "3) Я дам: ошибки → правило → план тренировки\n",
                kb_main(),
            )
            return

        # ===== SETTINGS actions =====
        if p and text.startswith("🎮 Игра:"):
            game = text.split(":", 1)[1].strip().lower()
            p.game = {"warzone": "warzone", "bf6": "bf6", "bo7": "bo7"}.get(game, "warzone")
            await self._send(chat_id, f"🎮 Игра установлена: {p.game.upper()}", kb_settings())
            return

        if p and text.startswith("🖥 Input:"):
            p.device = "kbm"
            await self._send(chat_id, "🖥 Input: KBM (мышь+клава) ✅", kb_settings())
            return

        if p and text.startswith("🎮 Input:"):
            p.device = "pad"
            await self._send(chat_id, "🎮 Input: Controller ✅", kb_settings())
            return

        if p and "Сложность:" in text:
            if "Normal" in text:
                p.difficulty = "normal"
            elif "Pro" in text:
                p.difficulty = "pro"
            elif "Demon" in text:
                p.difficulty = "demon"
            await self._send(chat_id, f"😈 Сложность: {p.difficulty.upper()} ✅", kb_settings())
            return

        if p and text == "🧠 Память: ON":
            p.memory_enabled = True
            await self._send(chat_id, "🧠 Память включена ✅", kb_settings())
            return

        if p and text == "🧠 Память: OFF":
            p.memory_enabled = False
            await self._send(chat_id, "🧠 Память выключена ✅", kb_settings())
            return

        # ===== AI panel actions =====
        if p and text == "🧠 ИИ: ON":
            p.ai_enabled = True
            await self._send(chat_id, "🧠 ИИ включён ✅", kb_ai())
            return

        if p and text == "🧠 ИИ: OFF":
            p.ai_enabled = False
            await self._send(chat_id, "🧠 ИИ выключен. Буду отвечать по шаблону ✅", kb_ai())
            return

        if text in ("🧾 Мой статус", "📡 Статус"):
            game = getattr(p, "game", "warzone") if p else "warzone"
            device = getattr(p, "device", None) if p else None
            diff = getattr(p, "difficulty", "normal") if p else "normal"
            ai = getattr(p, "ai_enabled", True) if p else True
            mem = getattr(p, "memory_enabled", True) if p else True
            await self._send(
                chat_id,
                "📡 Статус:\n"
                f"🎮 Игра: {str(game).upper()}\n"
                f"🕹 Input: {('KBM' if device=='kbm' else 'CONTROLLER' if device=='pad' else 'AUTO')}\n"
                f"😈 Сложность: {str(diff).upper()}\n"
                f"🧠 ИИ: {'ON' if ai else 'OFF'}\n"
                f"🧠 Память: {'ON' if mem else 'OFF'}",
                kb_main(),
            )
            return

        if text == "📌 Профиль":
            game = getattr(p, "game", "warzone") if p else "warzone"
            device = getattr(p, "device", None) if p else None
            diff = getattr(p, "difficulty", "normal") if p else "normal"
            await self._send(
                chat_id,
                "📌 Профиль:\n"
                f"🎮 {str(game).upper()}\n"
                f"🕹 {('KBM' if device=='kbm' else 'CONTROLLER' if device=='pad' else 'AUTO')}\n"
                f"😈 {str(diff).upper()}",
                kb_main(),
            )
            return

        if text == "🧹 Очистить память":
            if self.profiles:
                self.profiles.clear(user_id)
            await self._send(chat_id, "🧹 Очищено ✅", kb_main())
            return

        if text == "🧨 Сброс":
            if self.profiles:
                self.profiles.clear(user_id)
            await self._send(chat_id, "🧨 Сброс выполнен ✅", kb_main())
            return

        # ===== TRAIN actions (пока базово, расширим позже) =====
        if text in ("🎯 Aim", "🏃 Movement", "🧠 Positioning", "📌 План на сегодня"):
            await self._send(
                chat_id,
                "🎯 Ок. Напиши 1 строкой:\n"
                "— что именно не получается (пример)\n"
                "— и сколько времени есть (15/30/60)\n"
                "Я соберу план под твою игру и input.",
                kb_train(),
            )
            return

        # ===== SMART TEXT (главное: перестаём быть тупыми) =====
        # Здесь подключается твой brain. Если он пока простой — всё равно будет лучше, чем шаблон.
        # Мы даём ему контекст из профиля, чтобы ответы стали “живыми”.
        game = getattr(p, "game", "warzone") if p else "warzone"
        device = getattr(p, "device", None) if p else None
        diff = getattr(p, "difficulty", "normal") if p else "normal"
        ai = getattr(p, "ai_enabled", True) if p else True

        context = f"[game={game} input={device or 'auto'} diff={diff} ai={'on' if ai else 'off'}] "

        try:
            # если brain умеет принимать user_id + text
            reply = await self.brain.handle_text(user_id, context + text)
            out_text = getattr(reply, "text", None) or str(reply)
        except Exception:
            # если мозг пока не готов — делаем умный шаблон
            out_text = (
                "Понял.\n\n"
                "Ответь коротко 3 пунктами:\n"
                "1) Где умер? (крыша/лестница/открытое поле/внутри здания)\n"
                "2) Чем убили? (снайп/штурм/смг/дробовик)\n"
                "3) Что ты сделал за 3 секунды до смерти?\n\n"
                "Я дам: ошибка → правило → план на 15 минут."
            )

        await self._send(chat_id, out_text, kb_main())
