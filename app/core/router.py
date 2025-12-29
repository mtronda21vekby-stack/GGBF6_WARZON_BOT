# app/core/router.py
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.ui.quickbar import (
    kb_main,
    kb_settings,
    kb_games,
    kb_platform,
    kb_input,
    kb_difficulty,
    kb_voice,
    kb_roles,
    kb_bf6_classes,
    kb_game_settings_menu,
    kb_premium,
)

from app.worlds.bf6.presets import (
    bf6_class_text,
    bf6_aim_sens_text,
    bf6_controller_tuning_text,
    bf6_kbm_tuning_text,
)


def _safe_get(d: dict, path: list, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _game_norm(game: str) -> str:
    g = (game or "Warzone").strip()
    gl = g.lower()
    if gl in ("bf6", "battlefield", "battlefield 6", "battlefield6"):
        return "BF6"
    if gl in ("bo7", "black ops 7", "blackops7"):
        return "BO7"
    return "Warzone"


@dataclass
class Router:
    tg: Any
    brain: Any = None
    profiles: Any = None
    store: Any = None
    settings: Any = None

    async def handle_update(self, update: Dict[str, Any]) -> None:
        msg = update.get("message") or update.get("edited_message") or {}
        if not msg:
            return

        chat_id = _safe_get(msg, ["chat", "id"])
        text = (msg.get("text") or "").strip()
        if not chat_id:
            return

        # ---------- commands ----------
        if text in ("/start", "/menu", "Меню", "📋 Меню"):
            await self._send_main(
                chat_id,
                "🧠 FPS Coach Bot | Warzone / BO7 / BF6\n"
                "Нижний Premium UI закреплён. Жми кнопки снизу 👇\n\n"
                "Напиши ситуацию/смерть одной строкой — я отвечу как тиммейт или коуч (зависит от Голоса).",
            )
            return

        if text in ("/status",):
            await self._on_status(chat_id)
            return

        # ---------- MAIN quickbar ----------
        if text == "🎮 Игра":
            await self._on_game(chat_id)
            return

        if text == "⚙️ Настройки":
            await self._send(chat_id, "⚙️ Настройки:", kb_settings())
            return

        if text in ("🎭 Роль/Класс", "🎭 Роль", "🪖 Класс", "Класс", "Роль"):
            await self._on_role_or_class(chat_id)
            return

        if text in ("🧠 ИИ", "ИИ"):
            # Важно: не подменяем текст, чтобы не было "цикла"
            await self._send_main(
                chat_id,
                "🧠 ИИ включён.\n"
                "Пиши как в чат: что случилось / где умираешь / что хочешь улучшить.\n"
                "Я отвечу в выбранном Голосе (🤝 Тиммейт или 📚 Коуч) и в стиле Normal/Pro/Demon.",
            )
            return

        if text == "🎯 Тренировка":
            await self._send_main(
                chat_id,
                "🎯 Тренировка:\n"
                "Напиши: игра | платформа | input | что болит (аим/мувмент/позиционка)\n"
                "Пример: Warzone | PS | Controller | срываю трекинг на 20–40м",
            )
            return

        if text == "🎬 VOD":
            await self._send_main(
                chat_id,
                "🎬 VOD:\n"
                "Скинь 3 таймкода и что хочешь улучшить.\n"
                "Пример: 00:12 / 01:40 / 03:05 — «умираю на репике, не успеваю уйти».",
            )
            return

        if text == "🧟 Zombies":
            await self._send_main(
                chat_id,
                "🧟 Zombies:\n"
                "Пока не трогаем карты (как ты сказал).\n"
                "Если нужен совет — пиши: карта | раунд | от чего умираешь | что открыл.",
            )
            return

        if text == "📌 Профиль":
            await self._on_profile(chat_id)
            return

        if text == "📊 Статус":
            await self._on_status(chat_id)
            return

        if text == "💎 Premium":
            await self._send(chat_id, "💎 Premium центр:", kb_premium())
            return

        if text in ("🧹 Очистить память", "🧹 Очистить"):
            await self._on_clear_memory(chat_id)
            return

        if text in ("🧨 Сброс", "🧨 Reset"):
            await self._on_reset(chat_id)
            return

        if text in ("⬅️ Назад", "Назад"):
            await self._send_main(chat_id, "↩️ Ок. Меню снизу 👇")
            return

        # ---------- PREMIUM buttons ----------
        if text in ("🎙 Голос: Тиммейт/Коуч",):
            await self._send(chat_id, "🎙 Выбери голос общения:", kb_voice())
            return

        if text in ("🎙 Голос",):
            await self._send(chat_id, "🎙 Выбери голос общения:", kb_voice())
            return

        if text in ("🤝 Тиммейт",):
            self._set_profile_field(chat_id, "voice", "TEAMMATE")
            await self._send(chat_id, "✅ Голос = 🤝 Тиммейт (разговорно)", kb_settings())
            return

        if text in ("📚 Коуч",):
            self._set_profile_field(chat_id, "voice", "COACH")
            await self._send(chat_id, "✅ Голос = 📚 Коуч (по пунктам)", kb_settings())
            return

        if text in ("🧠 Память: Статус",):
            await self._on_status(chat_id)
            return

        if text in ("🎬 VOD: Разбор",):
            await self._send_main(chat_id, "🎬 Ок. Пришли 3 таймкода + цель разбора — разложу как тиммейт/коуч.")
            return

        if text in ("🎯 Тренировка: План",):
            await self._send_main(chat_id, "🎯 Ок. Напиши: игра | платформа | input | слабое место — дам план на 20 минут.")
            return

        # ---------- SETTINGS FLOW ----------
        if text == "🎮 Выбрать игру":
            await self._send(chat_id, "🎮 Выбери игру:", kb_games())
            return

        if text in ("🔥 Warzone", "💣 BO7", "🪖 BF6"):
            game = "Warzone" if "Warzone" in text else ("BO7" if "BO7" in text else "BF6")
            self._set_profile_field(chat_id, "game", game)
            await self._send(chat_id, f"✅ Игра = {game}", kb_settings())
            return

        if text == "🖥 Платформа":
            await self._send(chat_id, "🖥 Выбери платформу:", kb_platform())
            return

        if text in ("🖥 PC", "🎮 PlayStation", "🎮 Xbox"):
            platform = "PC" if "PC" in text else ("PlayStation" if "PlayStation" in text else "Xbox")
            self._set_profile_field(chat_id, "platform", platform)
            await self._send(chat_id, f"✅ Платформа = {platform}", kb_settings())
            return

        if text == "⌨️ Input":
            await self._send(chat_id, "⌨️ Выбери управление:", kb_input())
            return

        if text in ("⌨️ KBM", "🎮 Controller"):
            inp = "KBM" if "KBM" in text else "Controller"
            self._set_profile_field(chat_id, "input", inp)
            await self._send(chat_id, f"✅ Управление = {inp}", kb_settings())
            return

        if text == "😈 Режим мышления":
            await self._send(chat_id, "😈 Выбери режим:", kb_difficulty())
            return

        if text in ("🧠 Normal", "🔥 Pro", "😈 Demon"):
            diff = "Normal" if "Normal" in text else ("Pro" if "Pro" in text else "Demon")
            self._set_profile_field(chat_id, "difficulty", diff)
            await self._send(chat_id, f"✅ Режим = {diff}", kb_settings())
            return

        # voice inside settings
        if text == "🎙 Голос":
            await self._send(chat_id, "🎙 Выбери голос общения:", kb_voice())
            return

        # ---------- GAME SETTINGS PER WORLD ----------
        if text == "🧩 Настройки игры":
            prof = self._get_profile(chat_id)
            game = _game_norm(prof.get("game") or "Warzone")
            await self._send(chat_id, f"🧩 Настройки {game}:", kb_game_settings_menu(game))
            return

        # ---------- BF6 world settings ----------
        if text in ("🪖 BF6: Class Settings", "🪖 BF6 Class Settings"):
            await self._send(chat_id, "🪖 Pick BF6 class:", kb_bf6_classes())
            return

        if text in ("🟥 Assault", "🟦 Recon", "🟨 Engineer", "🟩 Medic"):
            cls = text.split(" ", 1)[-1].strip()
            self._set_profile_field(chat_id, "bf6_class", cls)
            await self._send_main(chat_id, bf6_class_text(self._get_profile(chat_id)))
            return

        if text in ("🎯 BF6: Aim/Sens", "🎯 BF6 Aim/Sens"):
            await self._send_main(chat_id, bf6_aim_sens_text(self._get_profile(chat_id)))
            return

        if text in ("🎮 BF6: Controller Tuning", "🎮 BF6 Controller Tuning"):
            await self._send_main(chat_id, bf6_controller_tuning_text(self._get_profile(chat_id)))
            return

        if text in ("⌨️ BF6: KBM Tuning", "⌨️ BF6 KBM Tuning"):
            await self._send_main(chat_id, bf6_kbm_tuning_text(self._get_profile(chat_id)))
            return

        # ---------- Warzone/BO7 role menu ----------
        if text in ("🎭 Warzone: Роль", "🎭 BO7: Роль"):
            await self._send(chat_id, "🎭 Выбери роль:", kb_roles())
            return

        if text in ("⚔️ Слэйер", "🚪 Энтри", "🧠 IGL", "🛡 Саппорт", "🌀 Флекс"):
            role_map = {
                "⚔️ Слэйер": "Slayer",
                "🚪 Энтри": "Entry",
                "🧠 IGL": "IGL",
                "🛡 Саппорт": "Support",
                "🌀 Флекс": "Flex",
            }
            self._set_profile_field(chat_id, "role", role_map.get(text, "Flex"))
            await self._send_main(chat_id, f"✅ Роль сохранена: {role_map.get(text, 'Flex')}")
            return

        # ---------- default -> AI chat ----------
        await self._chat_to_brain(chat_id, text)

    # ---------------- messaging helpers ----------------
    async def _send(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
        if reply_markup is None:
            reply_markup = kb_main()
        await self.tg.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def _send_main(self, chat_id: int, text: str) -> None:
        await self._send(chat_id, text, kb_main())

    # ---------------- profile ----------------
    def _get_profile(self, chat_id: int) -> dict:
        if self.profiles:
            for name in ("get", "get_profile", "read"):
                if hasattr(self.profiles, name):
                    try:
                        prof = getattr(self.profiles, name)(chat_id)
                        if isinstance(prof, dict):
                            return prof
                    except Exception:
                        pass
        return {
            "game": "Warzone",
            "platform": "PC",
            "input": "Controller",
            "difficulty": "Normal",
            "bf6_class": "Assault",
            "role": "Flex",
            "voice": "TEAMMATE",
        }

    def _set_profile_field(self, chat_id: int, key: str, val: str) -> None:
        # НИЧЕГО НЕ РЕЖЕМ: поддержка разных профайл-сервисов
        if self.profiles:
            for name in ("set", "set_field", "set_value", "update", "update_profile"):
                if hasattr(self.profiles, name):
                    try:
                        fn = getattr(self.profiles, name)
                        try:
                            fn(chat_id, key, val)
                        except TypeError:
                            fn(chat_id, {key: val})
                        return
                    except Exception:
                        pass

        # fallback если profiles не умеет — пишем в store (если есть)
        if self.store and hasattr(self.store, "set_profile"):
            try:
                self.store.set_profile(chat_id, {key: val})
            except Exception:
                pass

    # ---------------- UI handlers ----------------
    async def _on_game(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        game = _game_norm(prof.get("game") or "Warzone")

        extra = ""
        if game == "BF6":
            extra = f"\n🪖 BF6 Класс: {prof.get('bf6_class')}"
        else:
            extra = f"\n🎭 Роль: {prof.get('role')}"

        await self._send_main(
            chat_id,
            f"🎮 Игра: {game}\n"
            f"🖥 Платформа: {prof.get('platform')}\n"
            f"⌨️ Input: {prof.get('input')}\n"
            f"😈 Режим: {prof.get('difficulty')}\n"
            f"🎙 Голос: {prof.get('voice', 'TEAMMATE')}\n"
            f"{extra}\n",
        )

    async def _on_role_or_class(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        game = _game_norm(prof.get("game") or "Warzone")

        if game == "BF6":
            await self._send(chat_id, "🪖 Выбери BF6 класс:", kb_bf6_classes())
            return

        await self._send(chat_id, "🎭 Выбери роль (Warzone/BO7):", kb_roles())

    async def _on_profile(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        # удобное отображение
        game = _game_norm(prof.get("game") or "Warzone")
        lines = [
            f"• Игра: {game}",
            f"• Платформа: {prof.get('platform')}",
            f"• Input: {prof.get('input')}",
            f"• Режим: {prof.get('difficulty')}",
            f"• Голос: {prof.get('voice', 'TEAMMATE')}",
        ]
        if game == "BF6":
            lines.append(f"• BF6 класс: {prof.get('bf6_class')}")
        else:
            lines.append(f"• Роль: {prof.get('role', 'Flex')}")
        await self._send_main(chat_id, "📌 Профиль:\n" + "\n".join(lines))

    async def _on_status(self, chat_id: int) -> None:
        mem = {}
        if self.store and hasattr(self.store, "stats"):
            try:
                mem = self.store.stats(chat_id)
            except Exception:
                mem = {}

        ai_key = (getattr(self.settings, "openai_api_key", "") or "").strip() if self.settings else ""
        ai_enabled = bool(getattr(self.settings, "ai_enabled", True)) if self.settings else False
        model = getattr(self.settings, "openai_model", "gpt-4.1-mini") if self.settings else "?"

        ai_state = "ON" if (ai_enabled and ai_key) else "OFF"
        why = "OK" if ai_state == "ON" else ("OPENAI_API_KEY missing" if not ai_key else "AI_ENABLED=0")

        await self._send_main(
            chat_id,
            f"📊 Статус: OK\n"
            f"🧠 Memory: {mem or 'on'}\n"
            f"🤖 AI: {ai_state} | model={model} | reason={why}\n",
        )

    async def _on_clear_memory(self, chat_id: int) -> None:
        if self.store and hasattr(self.store, "clear"):
            try:
                self.store.clear(chat_id)
            except Exception:
                pass
        await self._send_main(chat_id, "🧹 Память очищена ✅")

    async def _on_reset(self, chat_id: int) -> None:
        if self.store and hasattr(self.store, "clear"):
            try:
                self.store.clear(chat_id)
            except Exception:
                pass
        if self.profiles and hasattr(self.profiles, "reset"):
            try:
                self.profiles.reset(chat_id)
            except Exception:
                pass
        await self._send_main(chat_id, "🧨 Сброс выполнен ✅")

    # ---------------- AI chat ----------------
    async def _chat_to_brain(self, chat_id: int, text: str) -> None:
        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "user", text)
            except Exception:
                pass

        prof = self._get_profile(chat_id)

        history = []
        if self.store and hasattr(self.store, "get"):
            try:
                history = self.store.get(chat_id)
            except Exception:
                history = []

        reply = None
        if self.brain and hasattr(self.brain, "reply"):
            try:
                fn = self.brain.reply
                # поддержка sync/async
                if inspect.iscoroutinefunction(fn):
                    reply = await fn(text=text, profile=prof, history=history)
                else:
                    out = fn(text=text, profile=prof, history=history)
                    if inspect.isawaitable(out):
                        reply = await out
                    else:
                        reply = out
            except Exception:
                reply = None

        if not reply:
            reply = (
                "🧠 AI fallback.\n"
                "📊 Статус покажет причину (OPENAI_API_KEY / AI_ENABLED).\n"
                "Напиши: игра | платформа | input | что болит — дам план."
            )

        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "assistant", str(reply))
            except Exception:
                pass

        await self._send_main(chat_id, str(reply))
