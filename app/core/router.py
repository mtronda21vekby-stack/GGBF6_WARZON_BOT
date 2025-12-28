from __future__ import annotations

from app.ui.quickbar import kb_main, kb_settings


def _safe_get(obj, path: str, default=None):
    cur = obj
    for part in path.split("."):
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur if cur is not None else default


class Router:
    def __init__(self, tg, brain, settings, profiles=None):
        self.tg = tg
        self.brain = brain
        self.settings = settings
        self.profiles = profiles

    async def _send(self, chat_id: int, text: str, reply_kb: dict | None = None):
        await self.tg.send_message(chat_id=chat_id, text=text, reply_markup=reply_kb or kb_main())

    def _p(self, user_id: int):
        return self.profiles.get(user_id) if self.profiles else None

    async def handle_update(self, upd):
        text = _safe_get(upd, "message.text", "") or ""
        text = text.strip()
        if not text:
            return

        chat_id = _safe_get(upd, "message.chat.id")
        user_id = _safe_get(upd, "message.from_user.id") or _safe_get(upd, "message.from.id")
        if chat_id is None or user_id is None:
            return

        p = self._p(int(user_id))

        # START
        if text == "/start":
            await self._send(
                int(chat_id),
                "✅ Бот жив.\nЖми кнопки снизу ⬇️\n\n⚙️ Настройки → выбери игру / input / сложность.",
                kb_main(),
            )
            return

        # NAV
        if text in ("⬅️ Назад", "📋 Меню"):
            await self._send(int(chat_id), "📋 Меню.", kb_main())
            return

        if text == "⚙️ Настройки":
            await self._send(int(chat_id), "⚙️ Настройки (1.2):", kb_settings())
            return

        # ===== 1) GAME =====
        if p and text.startswith("🎮 Игра:"):
            g = text.split(":", 1)[1].strip().lower()
            if "warzone" in g:
                p.game = "warzone"
            elif "bf6" in g:
                p.game = "bf6"
            elif "bo7" in g:
                p.game = "bo7"
            await self._send(int(chat_id), f"🎮 Игра установлена: {p.game.upper()} ✅", kb_settings())
            return

        # ===== 1) DEVICE =====
        if p and text.startswith("🖥 Input:"):
            p.device = "kbm"
            await self._send(int(chat_id), "🖥 Input: KBM ✅", kb_settings())
            return

        if p and text.startswith("🎮 Input:"):
            p.device = "pad"
            await self._send(int(chat_id), "🎮 Input: Controller ✅", kb_settings())
            return

        # ===== 2) DIFFICULTY =====
        if p and "Сложность:" in text:
            if "Normal" in text:
                p.difficulty = "normal"
            elif "Pro" in text:
                p.difficulty = "pro"
            elif "Demon" in text:
                p.difficulty = "demon"
            await self._send(int(chat_id), f"😈 Сложность: {p.difficulty.upper()} ✅", kb_settings())
            return

        # STATUS / PROFILE
        if text in ("📡 Статус", "📌 Профиль"):
            game = (p.game if p else "warzone").upper()
            device = (p.device if p else None)
            device_txt = "KBM" if device == "kbm" else "CONTROLLER" if device == "pad" else "AUTO"
            diff = (p.difficulty if p else "normal").upper()
            await self._send(
                int(chat_id),
                f"📌 Профиль:\n🎮 {game}\n🕹 {device_txt}\n😈 {diff}",
                kb_main(),
            )
            return

        # FALLBACK TEXT (пока)
        game = (p.game if p else "warzone")
        device = (p.device if p else None) or "auto"
        diff = (p.difficulty if p else "normal")
        prompt = f"[game={game} input={device} diff={diff}] {text}"

        try:
            reply = await self.brain.handle_text(int(user_id), prompt)
            out_text = getattr(reply, "text", None) or str(reply)
        except Exception:
            out_text = (
                "Ок. Напиши 3 пункта:\n"
                "1) Где умер?\n2) Чем убили?\n3) Что делал за 3 секунды до смерти?\n\n"
                "Я дам: ошибка → правило → план."
            )

        await self._send(int(chat_id), out_text, kb_main())
